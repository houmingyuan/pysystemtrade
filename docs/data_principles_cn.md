# 期货数据原则

适用范围：`data/futures/` 下的历史期货数据链路（合约价格 → multiple prices → adjusted prices）
及配套的品种配置。接入新数据源、新增品种、修数据前，先对照本文。

最后更新：2026-09-24

## 1. 来源：一个品种只能有一个价格来源

同一品种的合约价格不能同时来自两个源。`docs/data.md:181` 的原话：

> Don't get data from both Barchart and IB. If you get the IB data first, the Barchart code
> will overwrite it. If you get the Barchart data first, the IB data won't be written.

写入路径相同、语义是按「合约 + 频率」覆盖，所以谁后跑谁赢，或者干脆拒写。切换来源时先决定
旧数据是保留、换算还是清掉，不要让两个口径在库里共存。

当前分工：深历史由 Norgate 一次性回填，日常增量走 IB（`sysproduction/update_historical_prices.py`）。

## 2. 来源：roll calendar 必须与价格同源

用 A 源的价格配 B 源的日历，换月日与合约边界会对不上。

- 换月日的硬约束：当天必须同时有 current 与 next 两个合约的价格（`docs/data.md:243`）。
  这是最容易踩的一条，HEATOIL 与 NIKKEI-SGX_mini 的问题都源于此。
- 日历在 `data/futures/roll_calendars_csv/`，纳入 git。生成后要确认单调、且对齐真实价格
  （`docs/data.md:369`）。

## 3. 单位：口径以实时增量源为准

历史可以任意换算，增量源改不了。判断口径时看实时源实际返回什么，而不是看第二手文档。

- 本仓库的价格路径是原样入库：`ib.reqHistoricalData` 拿到的 bars 不经过任何缩放
  （`sysbrokers/IB/client/ib_price_client.py:279`）。
- 配置里的 `priceMagnifier` 不参与价格换算，只用于 `effective_multiplier =
  ibMultiplier / priceMagnifier` 这一项校验（`sysbrokers/IB/ib_instruments.py:26`、
  `sysproduction/interactive_controls.py:977`）。所以「数据保留美分口径 + priceMagnifier=100」
  在本地不成立。
- 实测：IB 对 SILVER（SILZ6）返回 64.965、COPPER（HGZ6）返回 6.7535，均为美元口径。

## 4. 单位：一个口径贯穿六层

| 层 | 位置 |
| --- | --- |
| 合约价格 | parquet `futures_contract_prices` |
| multiple prices | parquet `futures_multiple_prices` |
| adjusted prices | parquet `futures_adjusted_prices` |
| Pointsize | `data/futures/csvconfig/instrumentconfig.csv` |
| ibMultiplier / priceMagnifier | `sysbrokers/IB/config/ib_config_futures.csv` |
| spreadcost | `data/futures/csvconfig/spreadcosts.csv` |

任一层单独差一个尺度都是静默错误：仓位价值 `block_value = price × pointsize × 0.01`
（`systems/positionsizing.py:323`），价格或 Pointsize 差 100 倍，仓位就错 100 倍，回测不会报错。

案例：SILVER / COPPER 曾存 Norgate 的美分口径，而其余五层都是美元口径（FIR-123）。

## 5. 元数据：必须与真实标的一致

品种代码只是标签，**乘数才决定 IB 解析到哪个合约**：PST 会把 `ibMultiplier` 塞进合约请求
（`sysbrokers/IB/ib_instruments.py:92`），填 1 解析到 FDXS（微 DAX），填 1000 解析到 SILZ6
（微银）。描述与乘数要与实际标的相符。

案例：`SGX` 名字指向新加坡，标的实为 MSCI Singapore Free（SIMSCI），描述与 Pointsize 曾沿用
STI（FIR-122）。

## 6. 可重建性：原始必备份，派生可重建

- 原始、不可再生：Norgate 导出、IB 增量，以及入库后的 `futures_contract_prices`。
- 派生、可重建：roll calendar、multiple prices、adjusted prices。

所以动数据前先备份合约价格，备份放 `/Volumes/data/systrade/backup/`（例：
`futures_contract_prices_before_norgate_20260921`、
`futures_contract_prices_silver_copper_before_unit_fix_20260924`）。

## 7. 变更：可复现、可回滚

- 修数据用仓库里的脚本，不要在终端里跑一次性命令。例：
  `sysinit/futures/rebuild_roll_calendar_from_prices.py`。
- 配置与 roll calendar 进 git，改动可 diff、可回滚。

## 8. 验收：异常显式暴露

- 验收用 `sysinit/futures/verify_data_coverage.py`，输出当门禁。
- 已知例外保留在输出里并写明原因，不加白名单静默豁免。当前唯一例外：EUA 的 3.9 年起始差，
  原因是 Norgate 没有早于 20081200 的合约（`sysinit/futures/verify_data_coverage.py:37`）。

## 9. 文档与实测冲突时以实测为准

外部工具的文档可能与本地代码版本不一致（例：norgate-pst-utils README 关于 `priceMagnifier`
缩放价格的说法）。遇到冲突以代码实际行为加实测结果为准，并把这个差异记录下来。

## 10. 已知例外（2026-09-27 复核）

以下异常已实测确认，属「已知并可接受」或「暂时无解」，不要在验收里当成新问题反复排查：

| 品种 | 现象 | 结论与处理 |
| -- | -- | -- |
| BARLEY、GICS、NIKKEI-JPY | 前端合约近 45 天成交量全为 0，价格恒定（BARLEY 315.0） | Norgate/IB 数据本身无成交；这类品种放到策略池里信号无意义，建议剔除或单独标注 |
| TSX、WHEAT-ASX | 合约价格止于 2026-09-18（Norgate 末日），IB 报 No security definition | 已用 `TSX:CDE/TSE`、`SXF:MX/MATS/TSE`、`WH/AWM/WHT:SNFE/ASX` 等候选逐一探测均无定义 → 本账户 IB 不提供；如需推进只能换数据源或找 IB 确认权限 |
| KOSPI | multiple prices 末端 2026-09-23 | 不是缺口：IB 的 K200 日线到 2026-09-23 为止，09-24/25 为韩国秋夕（추석）假期 |
| GAS_UK、SUGAR11、SUGAR_WHITE | roll calendar 前端月份不在 IB 当前可交易月份里（例：SUGAR11 前端 202703，IB 为 202702/202704） | 换月月份集合与真实挂牌不一致，属 `rollconfig` 口径问题；当前数据是最新的，暂不影响，待定口径后修 |
| AUS10、AUS_BILL90 | `instrumentconfig.csv` Pointsize 与 IB 实测乘数不一致（1000 / 2466 vs 10000） | 影响仓位规模与回测，待确认后修正（见 FIR-153） |

其中 AUS10 与 NIKKEI-SGX_mini 已在 2026-09-27 修正（Pointsize 1000→10000、100→10，与
`IBMultiplier / priceMagnifier` 对齐）；**AUS_BILL90 保留 Pointsize=2466**，理由如下，
属于「配置层有意偏离」的例外：

* PST 的规则是 `Pointsize == IBMultiplier / priceMagnifier`，AUS_BILL90 的 IB 乘数是 10000
  （IB 按「面值 1,000,000 / 100」口径给出），按此规则 Pointsize 应为 10000；
* 但 ASX 90 天银行票据的经济口径是 `1,000,000 × 90/365 × 1% ≈ 2,466`，即价格每变动 1.00
  （100−yield）对应 A$2,466 —— 这才是仓位规模应当使用的值，所以 Pointsize 保留 2466；
* `IBMultiplier=10000` 必须保留：PST 解析 IB 合约时会把这个乘数发给 IB，改成 2466 会导致
  IB 报 No security definition（实测取数依赖它）。
* 复核脚本：`sysinit/henrik/audit_pointsize_vs_ib_multiplier.py`（只读），它会把
  AUS_BILL90 报为不一致——这是预期结果，不要再改。

复核工具：

* `sysinit/henrik/audit_ib_contract_mappings.py`：全库检查「IB 能否解析该品种 + 日历前端月份是否仍在 IB 挂牌」
* `sysinit/henrik/audit_ib_price_spikes.py`：把每日更新里被尖峰检查拒绝的合约逐条归因
* `sysinit/henrik/restore_norgate_history_into_merged.py`：把 Norgate 历史并回被 IB 增量覆盖掉的合并文件

## 11. 2026-09 数据修复沉淀（构建期对齐 / 末端截断 / 合并文件保护）

为修「Norgate 历史 + IB 增量」混合口径带来的问题（FIR-127/131/137/149/150），改了以下
**上游文件**，后续 merge upstream 时需要留意冲突：

| 文件 | 改动 | 为什么 |
| -- | -- | -- |
| `sysinit/futures/build_roll_calendars.py` | 新增 `align_prices_by_date()` | 价格库同时有 Norgate 的 00:00 与 IB 的 23:00，换月对齐要求同一时间戳；按日期对齐即可落位，**不需要改原始价格数据** |
| `sysinit/futures/build_multiple_prices.py`、`sysinit/futures/multipleprices_from_db_prices_and_csv_calendars_to_db.py` | 构建 multiple prices 前先按日期对齐 | 三腿（PRICE/FORWARD/CARRY）日期不齐会让末端出现 PRICE 为空 |
| `sysinit/futures/build_multiple_prices_from_raw_data.py` | 新增 `_trim_trailing_rows_without_price()` | 各腿最后一个有价日可能不同；multiple prices 应止于「当前持有合约的最后一个有价日」 |
| `sysproduction/update_historical_prices.py` | 新增 `_keep_history_only_in_merged_file()`：重建合并文件前先与库内已有合并数据取并集（同日以新数据为准） | 分频文件只覆盖最近一段时，直接覆盖会静默丢历史（FIR-137：VIX/20260900 曾 184 行 → 2 行） |
| `sysproduction/update_sampled_contracts.py` | `has_contract_expired()` 同时捕获 `missingContract` / `ContractNotFound` | 采样表里残留合约库已删除的合约时整步采样会崩（2026-09-27 08:00 日更即因此失败） |

一次性数据修复：`sysinit/henrik/restore_norgate_history_into_merged.py`（218 个合约、恢复
131,525 行）、`sysinit/henrik/extend_roll_calendar_to_front.py`（按 §6 追加换月行，
`--use-ib-availability` 用于前端已下市的品种）。

回归测试：`tests/test_data_repair_guards.py`（末端截断 + 合并文件历史保护），
`python -m pytest tests/test_data_repair_guards.py -q` 通过。

## 附：新增品种检查清单

- [ ] 合约价格来源唯一，且与 roll calendar 同源
- [ ] `instrumentconfig.csv`：描述与真实标的一致，Pointsize 与乘数同口径
- [ ] `rollconfig.csv`：滚动周期与合约月份分布一致，RollOffsetDays / ExpiryOffset 经数据验证
- [ ] `spreadcosts.csv`：与价格同口径
- [ ] `ib_config_futures.csv`：symbol / exchange / ibMultiplier 能解析到目标合约，用
      `interactive_controls.check_price_multipliers_consistent_for_instrument` 复核
- [ ] roll calendar 覆盖合约数据范围，单调、对齐真实价格
- [ ] 重建 multiple prices 与 adjusted prices
- [ ] `verify_data_coverage.py --instrument <CODE>` 为 OK，或例外已记录
