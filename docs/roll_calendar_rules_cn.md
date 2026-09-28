# 换月日历：规则、重建与延伸方法

> 2026-09-26 编写。起因是 09-25/26 对 VIX 日历做过几次改动，其中相当一部分建立在错误的
> 理解上（把「预生成日历」当成可以直接覆盖的成品、用现成脚本盲目延伸）。本文先把规则定下来，
> 再谈怎么改。

## 1. 日历是什么、放在哪里

* 文件：`data/futures/roll_calendars_csv/<INSTRUMENT>.csv`，每个品种一张，**只有 CSV 一种存储**
  （multiple / adjusted / 合约价格都在 parquet 或 mongo，日历不在）。
* 加载器：`sysdata/csv/csv_roll_calendars.py`（目录常量 `CSV_ROLL_CALENDAR_DIRECTORY`），
  按 `{instrument_code}.csv` 取名；文件不存在直接抛 `Calendar for X not found!`，**不会自动生成**。
* 日更链路（采样合约 → IB 合约价格 → multiple prices → adjusted prices）只**读**日历；
  `adjust_to_price_series` 只在内存里平移换月日，**从不回写 CSV**。

## 2. 行的语义

四列：`DATE_TIME, current_contract, next_contract, carry_contract`。

一行 `D` 的含义是：**在 D 日，从 `current_contract` 换到 `next_contract`**。

* `current_contract`：D 日之前（从上一行换月日到 D）持有的合约 = 该段期间的 **priced** 合约
* `next_contract`：D 日之后持有的合约，同时是段内的 **forward** 合约
* `carry_contract`：carry 规则用的对照合约，由 rollconfig 的 `CarryOffset` 决定
  （`-1` = 上一个月，`+1` = 下一个月）

**因此：某一天的「前端（priced）合约」= 最后一条 `DATE_TIME ≤ 该日` 的行的 `next_contract`。**

代码依据：`sysinit/futures/build_multiple_prices_from_raw_data.py` 的
`_calc_roll_date_info` / `_calc_contract_date_info` 用「下一条换月行」的 `current_contract`
填充两个换月日之间的区间；在链式连续（见下）时等价于上式的 `next_contract`。

实证（2026-09-26，全库 106 个品种）：入库 multiple prices 的末行 `PRICE_CONTRACT`
与「最后一条已发生换月行的 `next_contract`」一致的有 **93 个**；不一致的 13 个基本是
日历刚被改过、但 multiple prices 还没重建的品种。

交易侧取合约的方式也是取 multiple prices 的**最后一行**：
`sysobjects/multiple_prices.py: current_contract_dict()` → `sysproduction/data/contracts.py:
get_priced_contract_id()`。

## 3. 三条硬性不变量（CSV 必须满足）

1. **时间戳唯一**：同一天只能有一行。若同一个时间戳有两行，
   `roll_calendar.loc[date]` 会返回 2 行 → 构建时报
   `Missing contracts in middle of roll calendar ... not in price data!`
2. **链式连续**：`row_i.next_contract == row_{i+1}.current_contract`。
   中间断一环，前端就会跳过某个合约（VIX 曾出现 `202609 → 202611`，202610 从未成为前端）。
3. **三腿在换月日附近都有价**：`adjust_to_price_series` 要求 current/next（以及 carry，
   除非它先失败再按「omit carry」重试）在**同一天**都有价格。

## 4. multiple prices 的重建规则

入口：`sysinit/futures/multipleprices_from_db_prices_and_csv_calendars_to_db.py:
process_multiple_prices_single_instrument()`，顺序是：

1. 读 CSV 日历 + 合约合并价格；
2. `add_phantom_row()`（第一次）；
3. `adjust_roll_calendar()` → `adjust_to_price_series()`：把每行换月日平移到「三腿都有价」的日子；
4. `add_phantom_row()`（第二次）；
5. `futuresMultiplePrices.create_from_raw_data()`：按换月日分段生成 `PRICE/FORWARD/CARRY` 及三个合约号；
6. 写库（parquet / mongo）。

`add_phantom_row()` 的规则（`multipleprices_from_db_prices_and_csv_calendars_to_db.py:161`）：

* 若**日历最后一行日期 > now**（日历写到了未来）→ 原样返回，不做任何事；
* 否则追加一行，日期 = `now + 5 天`，`current = 最后一行.next_contract`，
  `next = current.next_held_contract()`（按 roll 参数推算），`carry = current.carry_contract()`。

也就是说：**phantom row 只是把「当前前端」钉住，不会把前端推进到下一个合约。**
前端要前进，必须有人在 CSV 里补上「已经发生且价格已具备」的换月行。

写库是 append-only：`sysdata/parquet/parquet_multiple_prices.py:_merge_multiple_prices()`
只保留 `index > 库里最后时间戳` 的新数据。**要重建历史必须先删掉库里旧的 multiple prices。**

adjusted prices 由 multiple prices 再做 back-adjustment 生成
（`sysinit/futures/adjustedprices_from_db_multiple_to_db.py:process_adjusted_prices_single_instrument`），
所以日历/ multiple 一改，两者都要重建。

## 5. `adjust_to_price_series` 的真实行为（最容易出错之处）

* 逐行寻找「current/next(/carry) 都有价」的**离名义换月日最近**的日期，
  `_find_closest_valid_date_to_approx_roll_date()` **没有前后窗口限制**；
* 若某行找不到可用的日期，且日历里已经有数据 → 直接 `break`，**日历从该行起被截断**；
* 于是：**写在价格数据末端之后的换月行会被「挤」回数据末端**。
  实测：VIX 一行的名义换月日 2026-10-21 被改写成 2026-09-25，
  结果前端提前两个月跳到更远的合约。

结论：**CSV 里不要出现超出「该品种合约价格覆盖范围」的换月行。**

## 6. 正确的新增 / 延伸流程

1. 备份 `data/futures/roll_calendars_csv/<X>.csv`。
2. 取 `data_end = 该品种合约价格最后日期`；`held = 日历最后一行的 next_contract`。
3. 循环推算下一个名义换月日：`nominal = 该合约到期日 + RollOffsetDays`；
   * 若 `nominal > data_end` → **停止**（不要写未来行）；
   * 找 `> 上一行日期` 且 `held / next` 都有价的最近日期，作为实际换月日；
   * 追加一行 `(实际换月日, current=held, next=该周期下一个合约, carry=按 CarryOffset)`；
   * `held = next`，继续。
4. 校验（必须全过）：
   * 时间戳唯一；
   * 链式连续（`row_i.next == row_{i+1}.current`）；
   * 每行三腿都有价格；
   * 重建后：末端 `PRICE/FORWARD/CARRY` 非空、前端合约 = 近一周成交量第一。
5. 重建 multiple prices（历史重建要先删库；只补新行可以走 merge）→ 重建 adjusted prices → 复核。

**操作节奏**：因为不能预写未来行，换月日过后（且两腿有价）就尽快补那一行；
在补之前，前端会停留在旧合约（phantom row 只能钉住旧前端）。

## 7. 本次踩过的错误（负面清单）

1. **用 `extend_roll_calendars.py --extend` 延伸**：它按 roll 参数生成「到未来」的行，
   超出 data_end 的行会被挤回数据末端；而且它把新行与旧行 `concat` 后
   `[~index.duplicated(keep="first")]` 去重，**同一天的两行会被丢掉一行**——
   VIX 被丢掉的正是 `202610→202611` 那一行，链式不变量被破坏，前端跳过 202610。
2. **把 norgate 预生成日历当成可直接覆盖的成品**：那 5 张只覆盖到 2026-01-22，
   直接覆盖会让前端钉在 202605；且它们保留了「同一天两行换月」的历史写法，
   在价格补齐后会触发第 3 节的不变量 1，全量重建直接报错。
3. **`RollOffsetDays=-60` 与 VIX 真实流动性不符**：VIX 前端合约一直交易到接近到期，
   -60 天换月会让前端比成交量第一提前约 2 个月。
4. **只改换月偏移、不改 carry 偏移**：前端贴近到期后，`CarryOffset=-1`
   指向的上月合约已经到期 → `CARRY` 整列为空，carry 交易规则失效。
   （把 `CarryOffset` 改成 `+1` 才能取到活着的对照合约。）
5. **改完日历不重建 multiple/adjusted**：库里仍是旧前端，与日历不一致（VIX 至今如此）。
6. 误用「预置日历」概念：上游随仓库附带的 CSV 是**冻结快照**（VIX 上游版本停在 2022-05），
   本仓库 2026-09-24 的一次批量刷新把 107 张日历整体重写过，属于本地生成物，
   不能当作权威基准。

## 8. 脚本清单与可信度

| 脚本 | 作用 | 评价 |
| --- | --- | --- |
| `sysinit/futures/build_roll_calendars.py` | 核心：`generate_approximate_calendar` / `adjust_to_price_series` / `create_from_prices` | 规则来源，读懂再用 |
| `sysinit/futures/rollcalendars_from_db_prices_to_csv.py` | 由价格 + 参数重建整张日历 | 会重写历史，需先比对 |
| `sysinit/futures/extend_roll_calendars.py`、`pst_import/extend_roll_calendars.py` | 向前延伸 | **有越界生成 + keep=first 丢行两个缺陷，勿直接用** |
| `pst_import/fix_roll_calendars.py`、`sysinit/futures/fix_roll_calendars.py` | 全量重建 | 高风险：早期稀疏数据会被截断 |
| `sysinit/henrik/repair_front_contracts.py` | 修前端 + 重建 multiple/adjusted | 本地工具，会裁剪日历末端 |
| `sysinit/henrik/rebuild_roll_calendar_from_volume.py` | 按成交量重建单品种日历 | 换月时机更贴近流动性，但历史段也会被改写 |

## 9. 待办

* 按第 6 节的方法实现一个「只延伸到 data_end、保持链式连续」的延伸脚本（替代现有 extend 脚本）。
* 明确 VIX 的换月参数口径（`RollOffsetDays`、`CarryOffset`），再决定是否重写 VIX 历史日历；
  重写历史会改变回测结果，需要单独确认。
