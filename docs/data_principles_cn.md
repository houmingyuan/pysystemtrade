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
