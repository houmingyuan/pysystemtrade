# 时间配置与处理（本仓库）

> 2026-09-27 编写。整理的起因是排查 HANG / HANGTEC 的「交易时间」显示异常，发现
> 「行情时间戳」「交易时间窗口」「调度时间」三类时间容易互相混淆，而且配置层级、
> 时区口径、夏令时都有坑。本文把三类时间的口径、配置位置、代码位置与排查方法固定下来。

## 0. 先分清三类「时间」

| 类别 | 含义 | 配置 / 代码 | 出错时的表现 |
| --- | --- | --- | --- |
| **行情时间戳** | 每条价格记录的 index（日线是当日几点几分） | `syscore/dateutils.py` 常量；`sysdata/parquet/*`；导入脚本 | 换月日两侧合约「同日不同时间戳」→ roll calendar 静默截断、前端合约停在过期月份、PRICE 为 NaN |
| **交易时间（可交易窗口）** | 系统认为「现在能不能下单 / 离收盘还有多久」 | `GMT_offset_hours` + `ib_config_trading_hours.yaml` / `private_config_trading_hours.yaml` + IB 的合约时段 | 诊断菜单出现 `NO TRADING HOURS`、窗口与真实交易时段错位、某些品种窗口为空 |
| **调度时间** | 什么时候跑哪一段生产流程 | `syscontrol/control_config.yaml`、`run_daily_data_update` 的 launchd/cron | 数据没更新、报「无失败」但数据不动 |

**这三者互不相干**：`control_config.yaml` 里的 `23:00` 是流程调度时间，不是行情时间戳；
交易窗口改的是「能不能下单」，不改变行情数据。

## 1. 行情时间戳

### 1.1 各数据源的口径（实测）

| 来源 | 时间戳 | 说明 |
| --- | --- | --- |
| IB 日线 | **当日 23:00**（notional closing time） | `syscore/dateutils.py` 的 `NOTIONAL_CLOSING_TIME_AS_PD_OFFSET`（hours=23）+ `replace_midnight_with_notional_closing_time()`；IB 取数在 `sysbrokers/IB/client/ib_price_client.py` 的 `_ib_timestamp_to_datetime` 里统一套用 |
| IB 小时线 | 原始时间（21:30 / 01:00 / 02:00 …） | 不做任何换算 |
| Norgate / CSV 导入 | **导出原样**：只有日期 → 解析成 00:00 | `sysinit/henrik/import_norgate_csv.py`（FIR-144 之后不再把 00:00 改写成 23:00） |
| FX（spotfx） | 23:00 | 与 IB 日线口径一致 |
| multiple prices / adjusted prices | 取决于构建时的价格数据 | 现在全库按「日期」对齐（见 1.2），所以绝大多数是 **00:00** |

举例（2026-09-27 实测）：

```
CORN#20261200 合约价格末 3 行   : 01:00（小时线）
CORN multiple / adjusted 末 3 行: 00:00（按日期对齐后的日线）
AUDUSD spotfx 末 3 行           : 23:00
```

### 1.2 混合口径怎么处理（不要改原始数据）

历史来自 Norgate（00:00）、增量来自 IB（23:00），同一个品种里两种口径混用会让
`adjust_to_price_series` 找不到「同一时间戳」的换月日，从而静默截断日历（曾造成
30+ 品种前端合约过期、PRICE 为 NaN）。本仓库的处理原则是**不动原始价格数据**，
在构建期对齐：

| 位置 | 做法 |
| --- | --- |
| `sysinit/futures/build_roll_calendars.py` | `align_prices_by_date()`：把每条价格的时间戳规范到当日 00:00、同日去重，再用于换月对齐 |
| `sysinit/futures/build_multiple_prices.py`、`sysinit/futures/multipleprices_from_db_prices_and_csv_calendars_to_db.py` | 构建 multiple prices 前同样先按日期对齐（否则三腿日期不齐，末端会出现 PRICE 为空） |
| `sysinit/futures/build_multiple_prices_from_raw_data.py` | `_trim_trailing_rows_without_price()`：末端 PRICE 为空时截断到「当前持有合约的最后一个有价日」 |
| `sysproduction/update_historical_prices.py` | `_keep_history_only_in_merged_file()`：IB 增量重建合并文件前先与库内合并数据取并集，避免分频文件只覆盖最近一段时把历史丢掉 |

roll calendar 自身的日期语义（`DATE_TIME`、链式连续、不写未来行等）见
`docs/roll_calendar_rules_cn.md`；已知例外与改动清单见 `docs/data_principles_cn.md` §10/§11。

## 2. 交易时间（可交易窗口）

### 2.1 计算链路

```
IB 返回该合约的 tradingHours 字符串（交易所当地时间，形如
  "20260927:CLOSED;20260928:0915-20260928:1200;...;20260928:1700-20260929:0300"）
        │
        │ ① 时区换算：time_diff(交易所时区) + GMT_offset_hours
        ▼
解析成 (开盘, 收盘) 时段列表
        │
        │ ② 按天裁剪（见 2.3）
        ▼
        │ ③ 与保存的周窗口求交集（窗口若带 timezone，读取时已自动换算成本机时间；
        │    时区窗口可被品种条目覆盖）
        ▼
listOfTradingHours
        │
        ├─ okay_to_trade_now()          → 现在能否下单
        └─ less_than_N_hours_left(N)     → 离收盘是否不足 N 小时
```

代码位置：

| 步骤 | 文件 |
| --- | --- |
| ① 时区换算 | `sysbrokers/IB/ib_trading_hours.py`：`get_time_difference()`（固定表 + `GMT_offset_hours`） |
| ② 解析与按天裁剪 | 同上：`parse_trading_hours_string()` / `parse_trading_for_day()` |
| ③ 求交集 | `sysbrokers/IB/client/ib_contracts_client.py` 的 `_ib_get_uncached_trading_hours()` → `sysobjects/production/trading_hours/intersection_of_weekly_and_specific_trading_hours.py` |
| 结果对象 | `sysobjects/production/trading_hours/trading_hours.py`（`okay_to_trade_now` / `less_than_N_hours_left`） |
| 诊断菜单 | `sysproduction/interactive_diagnostics.py`：`get_trading_hours_for_all_instruments()`（菜单 1 → 12） |

### 2.2 时区换算：`GMT_offset_hours`

* 位置：**`private_config.yaml` 的顶层键**（不是 `config:` 下面；只有顶层会被
  `production_config` 读到，写在 `config:` 里等于没写，实际会用 `defaults.yaml` 的 0）。
* 含义：**本机时区相对 GMT 的偏移**（本机 Asia/Shanghai → 8；英国夏令时 1、冬令时 0）。
* 公式：`换算小时 = 交易所时区固定偏移（代码里的表） + GMT_offset_hours`。
  例：`Hongkong` 表的偏移是 -8，配 `GMT_offset_hours=8` → 净 0（香港时间 = 本机时间）；
  配 0 → 净 -8（把香港时间当成伦敦时间用，本机 8 小时前的时刻）。
* 校验：

```bash
python -c "from sysdata.config.production_config import get_production_config; \
print(get_production_config().GMT_offset_hours)"
python -c "from sysbrokers.IB.ib_trading_hours import get_time_difference; \
print(get_time_difference('Hongkong'), get_time_difference('US/Central'), get_time_difference('MET'))"
```

注意：**交易窗口本身不要靠 `GMT_offset_hours` 手工换算**——窗口用 §2.4 的时区写法
（`timezone` + 交易所当地时间）表达，`GMT_offset_hours` 只负责把 IB 返回的时段换算到本机时间。

### 2.3 按天裁剪（2026-09-27 起）

IB 的时段直接用来下单太激进（时区表不含 DST、开收盘流动性差），所以会做安全裁剪。
**规则是按「交易所当地交易日」分组后裁剪**，而不是逐段裁：

* 当天的**第一段**：开盘 +1 小时，收盘不变；
* 当天的**最后一段**：收盘 −1 小时，开盘不变；
* 中间段：不动；
* 一天只有一段：开盘 +1 且收盘 −1。

分组用的是 IB 条目里的交易所当地日期前缀（如 `20260928:1700-20260929:0300` 归到 `20260928`），
因为「一天分几段」是交易所定义的。

例子（香港，2026-09-28，换算到本机时间后）：

| IB 原始（HK） | 裁剪后（本机） | 说明 |
| --- | --- | --- |
| 09:15–12:00 | **10:15–12:00** | 第一段：开盘 +1 |
| 13:00–16:30 | 13:00–16:30 | 中间段：不动 |
| 17:00–次日 03:00 | 17:00–次日 02:00 | 最后一段：收盘 −1 |

（旧实现是逐段裁，会得到 10:15–11:00、14:00–15:30、18:00–02:00 —— 每段两端都被削，
短段会被削成零长度而消失。）

回归测试：`tests/test_ib_trading_hours_trimming.py`。

### 2.4 与保存窗口求交集

裁剪后的 IB 时段还要与「保存的交易窗口」求交集，两个来源：

* `private/private_config_trading_hours.yaml`（存在时优先使用）
* `sysbrokers/IB/ib_config_trading_hours.yaml`（默认值，上游文件）

文件里可以按**时区**或**品种**配置。**推荐写法：直接给「交易所时区 + 交易所当地时段」，
不要手工换算**——读取时（`sysdata/production/trading_hours.py` → `read_trading_hours()`）
由 `sysdata/production/trading_hours_timezone.py` 换算成本机时间：

```yaml
# 时区写法：hours 里是交易所当地时间（HKT），timezone 用 IANA 名称
Hongkong:
  timezone: Asia/Hong_Kong
  hours:
    - '09:00'
    - '17:00'

# 一天多段（嵌套列表）、按 weekday 分别配置都可以放在 hours 里
US/Central:
  timezone: America/Chicago
  hours:
    - - '08:30'
      - '13:20'

# 只针对某个品种（会覆盖时区窗口）
HANG:
  Monday:
    - '09:00'
    - '17:00'
  Saturday: []
```

换算规则：

* 每个 weekday 取「该 weekday 在交易所时区的下一个发生日」作为代表日期，用 `zoneinfo`
  换算到本机时区 → **交易所的夏令时会被自动处理**（同一个配置在冬/夏令时下对应不同的本机时间）；
* 换算后跨越本机午夜的时段会按本机日期自动拆段（如芝加哥 09:00–14:00 在夏令时下
  → 本机 `22:00–23:59` + `00:00–03:00`），并归到对应的**本机** weekday；
* 不带 `timezone` 的旧写法仍然兼容（视为本机时间的时段，代码不做换算）。

交集为空的时段会被丢弃（`remove_zero_length_from_opening_times()`）；如果整天都没有交集，
该品种在这一天就是「不可交易」。

### 2.5 谁在用这些窗口

* 订单生成 / 执行窗口判断：`sysbrokers/broker_futures_contract_data.py` 的
  `okay_to_trade_now()`、`less_than_N_hours_left()`（上面 `tradingHours` 对象的方法）。
* 诊断菜单 1 → 12 会把每个品种的最终窗口打印出来（`NO TRADING HOURS` 表示没有 priced 合约，
  通常是该品种还没导入数据，不是交易时间配置的问题）。

改窗口会影响**生产里的下单/执行判断**，但不改变行情数据与回测输入。

## 3. 调度时间

与交易窗口无关，单独一栏：

| 流程 | 时间 | 位置 |
| --- | --- | --- |
| 数据更新（采样 → IB 价格 → multiple/adjusted → FX） | 每日 **08:00**（launchd），脚本内最多等外置卷 30 分钟 | `sysproduction/linux/scripts/run_daily_data_update` + `~/Library/LaunchAgents/com.henrik.systrade.update.plist` |
| 生产流程窗口（默认） | 见 `syscontrol/control_config.yaml`：`run_daily_prices_updates: 20:00`、`run_daily_fx_and_contract_updates: 07:00`、`run_daily_update_multiple_adjusted_prices: 23:00`、`run_systems: 20:05` 等 | `syscontrol/control_config.yaml` |

注意：`control_config.yaml` 里的 `23:00` 是「跑流程」的时间，不是日线时间戳（日线时间戳
是 23:00 纯属另一套约定，见 1.1）。

## 4. 本机当前状态（2026-09-27）

| 项 | 值 | 位置 | 状态 |
| --- | --- | --- | --- |
| `GMT_offset_hours` | **8** | `private/private_config.yaml` 顶层 | 已修（原先写在 `config:` 下不生效，实际是 0） |
| 时区窗口写法 | **全部改为「交易所时区 + 当地时段」** | `private/private_config_trading_hours.yaml` | 已改（代码自动换算成本机时间，含交易所夏令时） |
| └ `Hongkong` / `HongKong` | `Asia/Hong_Kong` 09:00–17:00 | 同上 | 覆盖港股日盘；**夜盘暂不纳入** |
| └ `US/Central` / `US/Eastern` | `America/Chicago` 09:00–14:00 / `America/New_York` 09:00–14:00 | 同上 | 等同旧伦敦口径 15:00–20:00 / 14:00–19:00（GMT） |
| └ `MET` / `Japan` / `GB-Eire` / `Australia/NSW` | `Europe/Berlin` 09:00–16:00 / `Asia/Tokyo` 10:00–15:00 / `Europe/London` 09:00–16:00 / `Australia/Sydney` 08:00–13:00 | 同上 | 均为旧伦敦口径的等价换算 |
| 行情数据末端 | 65 个品种 2026-09-26、37 个 2026-09-25，其余为例外 | `/Volumes/data/systrade/parquet` | 见 `docs/data_principles_cn.md` §10 |

已确认的两个案例：

* **HANG / HANG_mini**（HKT 窗口 09:00–17:00）：最终窗口 = 早盘 10:15–12:00、午盘 13:00–16:30（半日市收盘 16:00 → 15:00）；夜盘被窗口排除。
* **BTP**（Berlin 09:00–16:00）：最终窗口 = 本机 **16:00–22:00**（此前窗口是旧口径时交集为空）。
* **CORN / AUD / SP500**（Chicago 09:00–14:00）：最终窗口 = 本机 **22:00–23:59 + 00:00–03:00**（夏令时口径；冬令时会自动变成 23:00–04:00）。

## 5. 操作手册

### 5.1 修改某个市场的交易窗口

1. 打开 `private/private_config_trading_hours.yaml`；
2. 找到该市场对应的**时区键**（IB 的 `timeZoneId`，如 `US/Central`、`MET`、`Japan`、
   `Hongkong`（小写 k 也要写）、`Australia/NSW`），或直接写**品种键**做单独覆盖；
3. **按交易所当地时间**写时段，并写上 IANA 时区名（`timezone: Asia/Hong_Kong`），
   不要自己换算成本机时间；多段用嵌套列表；跨午夜由代码自动拆段；
4. 需要的话可以在 `timezone` 之外直接写 weekday（`Monday: ['09:00','17:00']`）做按天配置；
   旧写法（不带 `timezone`、直接给本机时间）仍然可用，但新配置建议统一用新写法；
5. 保存后用 5.2 的命令核对；
6. 如果本机所在地区有夏令时，`GMT_offset_hours` 仍按本机当前偏移填写（用于 IB 时段换算）；
   交易所侧的夏令时由 `timezone` 自动处理，不需要手工调整窗口。

### 5.2 验证

```bash
# 1) 配置是否生效
python -c "from sysdata.config.production_config import get_production_config; print(get_production_config().GMT_offset_hours)"
python -c "from sysbrokers.IB.ib_trading_hours import get_time_difference; print(get_time_difference('Hongkong'))"

# 2) 某品种的最终交易窗口（连 IB，只读）
python - <<'PY'
from sysdata.data_blob import dataBlob
from sysproduction.data.broker import dataBroker
from sysproduction.data.contracts import dataContracts
from sysobjects.contracts import futuresContract
code = "HANG"
with dataBlob(log_name="CheckHours") as data:
    broker = dataBroker(data).broker_futures_contract_data
    cid = dataContracts(data).get_priced_contract_id(code)
    for h in broker.get_trading_hours_for_contract(futuresContract(code, cid)):
        print(h.opening_time, "→", h.closing_time)
PY

# 3) 全库巡检：菜单 1 → 12（View trading hours for all instruments）
python -c "from sysproduction.interactive_diagnostics import interactive_diagnostics as f; f()"
```

### 5.3 关键代码与常量速查

| 内容 | 位置 |
| --- | --- |
| 日线 notional closing = 23:00 | `syscore/dateutils.py`：`NOTIONAL_CLOSING_TIME_AS_PD_OFFSET`、`replace_midnight_with_notional_closing_time()` |
| IB 日线/小时线时间戳转换 | `sysbrokers/IB/client/ib_price_client.py`：`_ib_timestamp_to_datetime()` |
| 时区固定偏移表 + `GMT_offset_hours` | `sysbrokers/IB/ib_trading_hours.py`：`get_time_difference()` / `get_GMT_offset_hours()` |
| 解析 + 按天裁剪 | 同上：`parse_trading_hours_string()` / `parse_trading_for_day()` / `parse_phrase()` |
| 与保存窗口求交集 | `sysbrokers/IB/client/ib_contracts_client.py`：`_ib_get_uncached_trading_hours()` |
| 交易时间配置读取与换算 | `sysdata/production/trading_hours.py`：`read_trading_hours()`；换算实现 `sysdata/production/trading_hours_timezone.py` |
| 交易窗口对象 | `sysobjects/production/trading_hours/trading_hours.py` |
| 构建期按日期对齐 | `sysinit/futures/build_roll_calendars.py`：`align_prices_by_date()` |
| 末端 PRICE 截断 | `sysinit/futures/build_multiple_prices_from_raw_data.py`：`_trim_trailing_rows_without_price()` |
| 合并文件历史保护 | `sysproduction/update_historical_prices.py`：`_keep_history_only_in_merged_file()` |
| 流程调度时间 | `syscontrol/control_config.yaml` |

## 6. 踩过的坑（排查清单）

1. **配置层级写错**：`private_config.yaml` 里只有**顶层键**会被 `production_config` 读到。
   写进 `config:` 块里的键（`GMT_offset_hours`、`ignore_instruments`、`control`、`start_date`）
   都不生效——只有我们自己的脚本（如 `sysinit/henrik/spotfx_from_ib_to_db.py` 读 `config.fx_data`）
   会显式去读这个块。另外「忽略品种」的正确键名是 **`exclude_instrument_lists`**
   （`sysdata/config/instruments.py`），不是 `ignore_instruments`。
2. **窗口口径**：新写法是「交易所时区 + 交易所当地时间」，由代码换算（推荐）；
   旧写法直接给本机时间，不带 `timezone`。两种写法混用时容易搞混——
   本仓库已统一改成新写法。旧配置里从伦敦口径手工搬过来的值（如把 `01:00–06:00`
   改成 `09:00–14:00`）在新写法下应该还原成交易所当地时间（HKT 09:00–14:00）。
3. **逐段裁 vs 按天裁**：现在是按天裁（首段开盘 +1、末段收盘 −1）。看到某天多段之间
   「少了一小时」先确认是不是首/末段。
4. **日线 00:00 / 23:00 混用**：会让换月日两侧合约「同日不同时间戳」，导致日历被静默截断。
   处理办法是构建期按日期对齐（见 1.2），**不要**去改原始价格数据（改过也会被下一次导入/增量覆盖）。
5. **合并文件被 IB 增量覆盖**：历史只存在于合并文件时（没有 `Day@`/`Hour@`），上游重建会把历史丢掉。
   已修（`_keep_history_only_in_merged_file()`），恢复脚本 `sysinit/henrik/restore_norgate_history_into_merged.py`。
6. **调度时间 ≠ 数据时间戳**：`control_config.yaml` 的 23:00 是跑流程的时间；日线时间戳 23:00 是 IB 口径。
7. **IB 只给最近几天的 `tradingHours`**：诊断菜单里某品种只列出 2 天是正常的，不是数据缺失。
8. **`NO TRADING HOURS` 的两种原因**：① 没有 priced 合约（该品种还没导入数据，如 HANGTEC/HANGENT）；
   ② 该品种窗口与 IB 时段交集为空（配置问题）。用 5.2 的第 2 段代码可以快速区分。

## 参考

* `docs/roll_calendar_rules_cn.md`：换月日历的规则、重建与延伸
* `docs/data_principles_cn.md`：数据原则、已知例外（§10）、本轮代码改动（§11）
* `docs/production.md` 的 “Trading hours configuration”：上游对时区窗口的说明
