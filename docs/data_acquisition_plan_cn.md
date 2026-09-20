# 历史数据获取方案（Windows 侧导出 + Mac 侧导入）

本文记录把深度历史期货数据接入 pysystemtrade 的方案。数据在 Windows 上导出，在 macOS 上导入与使用。

## 1. 背景与目标

当前的 barchart 通道有两个硬约束：每天 250 次下载配额（Premier 档），以及"已存在文件不刷新"的行为导致数据长期冻结。实测 252 个品种中有 189 个仍停在 2024-03。

目标是引入一个深度历史数据源，一次性补齐回填，日常增量更新交给 IB。

## 2. 供应商选择

| 供应商 | 价格 | 覆盖 | 历史深度 | 频率 | 现成导出工具 |
| --- | --- | --- | --- | --- | --- |
| CSI Gold 世界期货 | $200/年 | 近 1000 个期货 | 30 年 | 日线 | 无，需自写转换 |
| CSI Silver 世界期货 | $200/年 | 同上 | 10 年 | 日线 | 无 |
| Norgate Futures | $270/年（半年 $148.50） | 约 100 个市场 | 约 1980 年起 | 日线 | 有，norgate-pst-utils |
| Kibot | $139 起，分钟级另加 | 全球期货 | 1998 年起 | 日线+分钟 | 无，但 CSV/API 直接可用 |
| Barchart Premier | $239.95/年 | 同现况 | 深 | 日线+小时 | 有，bc-utils |
| IB | 已有 | — | 仅约 1 年到期合约 | 日线+小时 | 仓库原生支持 |

**推荐**：优先 CSI Gold 世界期货，单位价格的历史深度最高；若希望减少一次性工作量，选 Norgate，因为有现成导出工具可直接产出 pysystemtrade 格式。

## 3. Windows 侧准备

### 3.1 运行环境

- Apple Silicon Mac 上使用虚拟机：UTM（免费）或 Parallels Desktop；Windows 11 ARM 通过模拟可运行上述 Windows 软件
- 磁盘预留 64GB 以上
- Norgate 官方 FAQ 明确允许两个安装额度，且明确允许"从 Mac 上的 Windows 虚拟机导出数据、再在 Mac 上处理"，后者不计入安装数
- CSI 的 Unfair Advantage 同为 Windows 软件，官网不推荐在 macOS 上运行

### 3.2 路线 A：Norgate

1. 在 Windows 安装 Norgate Data Updater（NDU）与 `norgatedata` Python 包
2. 获取 [norgate-pst-utils](https://github.com/davidszp/norgate-pst-utils)，按其说明配置导出的品种清单
3. 运行 `norgate_utils/export.py`，产出 `INSTRUMENT_YYYYMM00.csv` 形式的逐合约 CSV

### 3.3 路线 B：CSI Unfair Advantage

1. 订阅 Gold 世界期货（$200/年，含 30 年历史）；也可先用 $20 试用验证流程
2. 安装 UA，建立 portfolio，加入需要导出的全部合约
3. 导出 ASCII 或 CSI 格式，逐合约一个文件
4. 由于 UA 导出格式与本仓库不一致，需要自行编写转换脚本，把列名与时间格式对齐第 4 节规范

## 4. 导出格式规范（关键，务必对齐）

导入端 `sysdata/csv/csv_futures_contract_prices.py` 对文件名与列名有硬性要求：

- **文件名**：`<Instrument>_<YYYYMM00>.csv` 表示合并频率；`Day_<Instrument>_<YYYYMM00>.csv` 与 `Hour_<Instrument>_<YYYYMM00>.csv` 分别表示日线与小时线
- **合约月份**：`YYYYMM00`，末两位固定为 `00`
- **品种代码**：大小写需与 `data/futures/csvconfig/instrumentconfig.csv` 的 `Instrument` 列完全一致
- **必需列**：`Time`、`Open`、`High`、`Low`、`Close`、`Volume`
- **时间格式**：ISO 形式，例如 `2026-09-10T00:00:00`；解析配置需与实际导出格式一致
- **每行一个时间点**，按时间升序

示例：

```
Time,Open,High,Low,Close,Volume
2026-09-08T00:00:00,477.5,479.0,475.25,476.75,152340
2026-09-09T00:00:00,476.75,481.0,476.0,480.5,187220
```

## 5. Mac 侧导入步骤

1. 把导出的 CSV 放到独立目录，例如 `/Volumes/data/systrade/histdata`，与 barchart 目录分开，避免混淆
2. 在 `sysinit/` 下新增或复用导入脚本，用 `ConfigCsvFuturesPrices` 定义本数据源的列名与时间格式
3. 调用 `init_db_with_split_freq_csv_prices_for_code`（见 `sysinit/futures/contract_prices_from_split_freq_csv_to_db.py`）把逐合约价格写入 Parquet
4. 重建 roll calendar：`python sysinit/henrik/fix_rollcalendars.py <INSTRUMENT> ...`，或全量走 `sysinit/henrik/update_rollcalendars.py`
5. 重跑 multiple prices 与 adjusted prices：`sysinit/henrik/update_multiple_prices_tolerant.py` 与 `update_adjusted_prices_tolerant.py`
6. 核验：末日期、品种数、以及抽样品种的价格量级是否与预期一致

## 6. 注意事项

- **不要混用数据源**：仓库文档明确指出 barchart 与 IB 的数据会互相覆盖，因为写入路径相同；导入新数据源前需确认写入策略（`ignore_duplication`）与覆盖顺序
- **roll calendar 必须与价格同源**：用 A 数据源的价格配 B 数据源的 roll calendar，会出现合约边界与 roll 日期不匹配
- **导入后先做对照回测**：确认价格量级、波动率与之前一致，再据此重跑历史回测
- **日常增量仍走 IB**：深度历史一次性回填后，每日增量用 `sysproduction/update_historical_prices.py`（IB 通道），避免继续消耗 barchart 配额
