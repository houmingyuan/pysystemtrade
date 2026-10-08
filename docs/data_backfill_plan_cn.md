# 品种数据补全计划：备份导入 + Barchart/Norgate 补缺

目标：**不改动现有 106 个品种的价格数据**，先把备份里已有的品种导入，再补齐剩余缺口。

## 1. 现状盘点（2026-09-30）

| 口径 | 数量 | 位置 |
| --- | --- | --- |
| 配置层（instrumentconfig.csv） | 589 | 仓库 |
| 价格库现有数据 | 106 | /Volumes/data/systrade/parquet + mongo |
| 现有数据的来源 | 106 | data/futures/norgate_export（与价格库品种完全一致） |
| Barchart 完整备份 | 188 品种 / 8,091 个合约月文件 | /Volumes/data/systrade/backup/barchart_full_20260915.tar.gz |
| 备份 ∩ 价格库 | 83 | — |
| **备份有、价格库没有** | **105** | 全部已在 instrumentconfig，元数据齐全 |
| 备份与 Norgate 都没有 | **378** | 需新导出 |

缺失品种合计 483（589 − 106）= 105（备份可解）+ 378（需新下载）。

378 个缺口按类别：Equity 101、FX 60、Bond 56、SingleStock 54、Sector 32、Metals 23、
OilGas 15、Housing 12、Ags 9、STIR 7、Weather 4、Vol 3、CommodityIndex 1、Other 1。

其中 SingleStock 54、Sector 32、Housing 12、Weather 4、CommodityIndex 1 共 103 个
不是标准期货（个股、板块指数、房价、天气），需要先确认可得性与建模口径，
不能直接套用现有期货管线；剩余 275 个是标准期货。

## 2. 原则

1. **现有 106 个品种零改动**：新品种以新增文件/collection 追加，禁止覆盖已有品种文件。
2. **一个品种一个价格来源**（仓库既定数据原则）：Barchart 与 Norgate 不得混用于同一品种。
3. **先备份后操作**：先跑 run_backups，并把 parquet/mongo 现状另存。
4. **可回滚**：每步产生独立备份目录，沿用 backup/<fir_id>_<step>_<date> 命名。
5. **先小批量验证再放量**：每批先做 3–5 个品种的端到端验证。
6. **Norgate 已覆盖的品种不做处理**（本次口径）：Norgate 能提供数据的品种由 Norgate 负责，
   本次补全只处理「Barchart 备份有、Norgate 没有」的 105 个品种；
   Norgate 导出目前正好覆盖价格库现有的 106 个品种，两者品种清单一致。

## 3. 阶段计划

### 阶段 0：冻结与基线（0.5 天）

```bash
python3 pst_import/verify_data_coverage.py     # 记录现有 106 品种覆盖基线
python3 sysproduction/run_backups.py           # parquet + mongo 备份
```

验收：基线可复现，后续步骤可与之对比。

### 阶段 1：从 Barchart 备份导入 105 个品种（3–5 天）

1. 解包到临时目录（不直接写数据目录）：

```bash
mkdir -p /private/tmp/barchart_20260915
tar -xzf /Volumes/data/systrade/backup/barchart_full_20260915.tar.gz -C /private/tmp/barchart_20260915
```

2. 文件名规范化：Barchart 是 Day_<BCSymbol>_<YYYYMM>00.csv，PST 需要
   <INSTRUMENT>_<YYYYMM>00.csv。现有映射表
   sysinit/futures/barchart_futures_contract_prices.py:market_map 只覆盖约 30 个代码，
   188 个品种需要补一张完整对照表（Barchart symbol → PST instrument），并抽样核对。

3. 导入合约价格（逐品种，Day 优先、Hour 可选）：

```bash
# 在 private_control_config.yaml 的 barchart.download_list 放开目标品种后执行
python3 sysinit/futures/update_historical_prices.py
```

4. 补换月参数并生成 roll calendar（新品种必须做，否则无法生成连续价格）：

```bash
python3 sysinit/futures/build_roll_calendars.py
python3 sysinit/henrik/rebuild_roll_calendar_from_volume.py --instrument <CODE>
```

5. 构建 multiple / adjusted prices：

```bash
python3 sysinit/futures/update_multiple_prices.py
python3 sysinit/futures/update_adjusted_prices.py
```

6. 单品种验收：
   - pst_import/verify_instrument_dataflow.py --instrument <CODE>：合约价格 → multiple → adjusted 全链路；
   - sysinit/henrik/audit_pointsize_vs_ib_multiplier.py：Points 与 IB 乘数一致性；
   - 价格量级抽样与公开数据比对（重点核对美分/美元口径，参考 FIR-123）；
   - 沿日日更链路的 max_price_spike 检查（FIR-127）。

### 阶段 2：补齐 378 个缺口（先调研，后工程）

2a. 标准期货 275 个（Equity 101、FX 60、Bond 56、Metals 23、OilGas 15、Ags 9、STIR 7、Vol 3）

* 优先走 Norgate（覆盖约 100 个市场、历史深、自带 norgate-pst-utils 换月日历），
  按 docs/data_acquisition_plan_cn.md 的流程导入；
* Norgate 未覆盖的再用 Barchart 导出（仓库只有 CSV→DB 导入工具，下载依赖外部导出）。

2b. 非标准期货 103 个（SingleStock 54、Sector 32、Housing 12、Weather 4、CommodityIndex 1）

* 先做可得性调研：Barchart 是否提供、是否有合约规格/乘数/换月规则；
* 当前管线假设「有合约月份的期货」，这类标的需要单独设计数据模型；本阶段只登记结论。

### 阶段 3：验收与入库（1–2 天）

* 覆盖率报告：每个新品种的起始日期、合约月数、缺口比例、最后更新日期；
* 口径一致性：Pointsize / IB 乘数 / 价格单位三方一致（FIR-122、FIR-123、FIR-153 检查项）；
* 重复市场检查：与现有品种相关 > 0.98 的只保留一个（screen_trading_rules.py --universe available 的去重逻辑）；
* 只有通过验收的品种才加入回测品种池配置。

## 4. 风险与注意事项

| 风险 | 说明 | 对策 |
| --- | --- | --- |
| 同名不同源 | 同一品种既有 Barchart 又有 Norgate 数据，口径与时间戳不同 | 一品种一来源，导入前先出冲突清单 |
| 时间戳 | 历史上出现过 23:00 与 00:00 两种口径（FIR-144） | 保留源文件原始时间戳，不做批量平移 |
| 合约月份映射 | 文件名解析错会导致价格错配 | 完整 symbol 对照表 + 抽样核对 + 换月日历合理性检查 |
| 单位口径 | 美分/美元、Points 与 IB 乘数不一致（FIR-123） | 每个新品种做一次三方核对 |
| 换月日历缺失 | 新品种无 roll calendar 会卡住 multiple prices（FIR-114/118） | 导入后立即生成并验证 |
| 非期货品种 | 个股/板块/房价/天气不适用当前框架 | 先调研，不直接进工程 |
| 数据量 | 105 个品种 × 数十年合约月，mongo/parquet 明显增长 | 数据卷尚有 1.8Ti 可用，分批导入并监控 |

## 5. 需要确认的事项

1. Barchart 账号是否仍可用？导出清单是否覆盖阶段 2a 的 275 个标准期货？
2. Norgate 订阅是否包含这些市场？（现有 norgate_export 只覆盖 106 个品种，需重新导出）
3. 阶段 2b 的 103 个非期货品种是否在本期范围内？
4. 导入优先级：按资产类别（先补 Equity/Ags/Bond）还是按流动性与成本？

## 6. 工作量预估

| 阶段 | 工作量 | 依赖 |
| --- | --- | --- |
| 0 冻结与基线 | 0.5 天 | — |
| 1 备份导入 105 个品种 | 3–5 天 | symbol 对照表 |
| 2a 标准期货 275 个 | 5–10 天 | Norgate/Barchart 导出 |
| 2b 非期货 103 个 | 调研 1–2 天 | 可得性确认 |
| 3 验收与入库 | 1–2 天 | 阶段 1/2 |

## 7. 本次盘点用到的命令

## 8. 阶段 1 试点结果（FIR-212，2026-09-30）

试点品种：V2X / CHFJPY / HANGTECH（均满足「Barchart 备份有、Norgate 没有」）。

### 8.1 已跑通的链路（以 V2X 为例）

```bash
# 1. 解包（只取试点品种）
tar -xzf /Volumes/data/systrade/backup/barchart_full_20260915.tar.gz \
    --include='barchart/*V2X*' -C /private/tmp/barchart_pilot
# 2. 导入合约价格 → 166 个合约
python3 sysinit/henrik/pilot_backfill.py --instrument V2X \
    --datapath /private/tmp/barchart_pilot/barchart --steps prices
# 3. 换月日历（参数法生成后必须用成交量法重建，见 8.2）
python3 sysinit/henrik/rebuild_roll_calendar_from_volume.py --instrument V2X
# 4. multiple + adjusted prices
python3 sysinit/henrik/pilot_backfill.py --instrument V2X \
    --steps multiple adjusted --no-merge
# 5. 校验
python3 pst_import/verify_instrument_dataflow.py --instrument V2X
```

结果：V2X 合约价格 166 个、换月日历 157 行（至 2026-02-20）、
adjusted prices 2012-12-20 ~ 2026-03-13（3,352 行），校验中价格链路全部 OK。

### 8.2 试点发现的三个问题

1. **CSV 表头不统一**：8,091 个文件里有 15 个把收盘列写成 `Latest` 而不是 `Close`
   （多为最近月份的 Hour/Day 文件），直接导入会抛 `KeyError: 'Close'`。
   处理：导入前把表头规范化为 `Close`（本次在临时目录做，未改动备份）。
2. **参数法换月日历会截断**：用 `build_and_write_roll_calendar`（按 rollconfig 的
   周期与偏移推导）生成的 V2X 日历只到 2025-04-22，导致 multiple/adjusted prices
   比合约价格短 10 个月。改用**成交量法重建**（`rebuild_roll_calendar_from_volume.py`）
   后日历到 2026-02-20，与价格覆盖一致。→ 放量时必须统一用成交量法。
3. **备份里的数据是「历史」，不是「最新」**：备份文件时间为 2026-09-15，但内容截止日期
   按品种不同：V2X 2026-03-13、CHFJPY 2025-07-15、HANGTECH 2025-04-25。
   即备份只能补历史，**尾部仍需 Barchart 重新导出或 IB 补**——与本次计划的分工一致。

### 8.3 放量前需要补的两件事

1. 加一步「表头规范化」预处理（`Latest` → `Close`），并写进批量脚本；
2. 明确尾部补数来源：Barchart 新导出（覆盖 2025-04 ~ 2026-09）或 IB 增量，
   否则新品种的连续价格会停在备份截止日。

### 8.4 试点的数据现状

### 8.5 阶段 1 全部完成（2026-09-30）

105 个「Barchart 备份有、Norgate 没有」的品种**全部导入并完成链路**
（合约价格 → 换月日历 → multiple prices → adjusted prices），
`futures_adjusted_prices` 从 106 个增加到 **211 个**。

过程中修掉两个工具问题：

1. **换月日历不要做「与价格对齐」的再调整**：`process_multiple_prices_single_instrument`
   默认 `adjust_calendar_to_prices=True`，会按 rollconfig 的周期/偏移重排日历，
   对成交量法生成的日历反而引入「日历中间缺合约」「调整后日历为空」的错误。
   新品种统一用 `adjust_calendar_to_prices=False`。
2. **季度挂牌品种的 carry 合约要就近取**：COPPER-micro、NIKKEI 这类只挂 3/6/9/12 月的品种，
   按 `CarryOffset` 推出的 carry 月份（如 20240600）根本没有挂牌，
   导致 multiple prices 报「Missing contract ... in middle of roll calendar」。
   已在 `rebuild_roll_calendar_from_volume.py` 增加「carry 合约就近吸附到实际挂牌月份」的逻辑。

内容截止日：105 个品种的 adjusted prices 大多止于 2024-12 ~ 2026-03
（各品种备份内容不同），**尾部仍需 IB 或新 Barchart 导出补齐**。

V2X 已进入价格库（合约价格 / 换月日历 / multiple / adjusted），但**止于 2026-03-13**，
尚未接入任何生产或回测配置。如果不需要，可以按品种删除这三个产物回滚。

```bash
# Barchart 备份覆盖（不解包，只列文件名）
tar -tzf /Volumes/data/systrade/backup/barchart_full_20260915.tar.gz | grep -E '\.csv$' | wc -l

# 价格库品种与分类
python3 sysinit/henrik/summarise_universe.py --output docs/universe_summary.csv
```
