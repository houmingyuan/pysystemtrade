# 系统化交易框架 × 代码架构对照

本文把 Robert Carver《Systematic Trading》的模块化交易框架与本仓库（pysystemtrade）的代码结构逐层对应，回答“某个概念在哪一层、哪段代码、哪个配置项里”。

## 1. 总体架构

书中的核心命题：交易系统 = 交易规则（引擎）+ 风险与仓位管理框架（底盘），两者必须解耦——规则只依赖价格波动率，绝不看账户大小；账户大小与风险偏好只出现在波动率目标那一层。

代码中的对应关系：一个系统 = `System`（由若干 `SystemStage` 组成的树）+ `Config`（一组 YAML 参数）+ `simData`（数据对象）。每个 Stage 只负责框架中的一层，通过 `parent` 互相调用，`systems/system_cache.py` 负责惰性求值与缓存。

| 构件 | 代码位置 | 作用 |
| --- | --- | --- |
| 系统容器 | `systems/basesystem.py` (`System`) | 持有 stage 列表、data、config，负责组装与对外接口 |
| 阶段基类 | `systems/stage.py` (`SystemStage`) | 所有模块的父类，提供 `parent` 与日志 |
| 计算缓存 | `systems/system_cache.py` | `@input/@output/@diagnostic` 装饰器，避免重复计算 |
| 参数 | `sysdata/config/configdata.py`、`sysdata/config/defaults.yaml` | 全局默认值 + 每个系统自己的 YAML 覆盖 |
| 数据 | `sysdata/sim/` (`simData`) | 回测与实盘共用的数据抽象 |

## 2. 主干数据流

```
sysdata（价格 / 合约 / 成本 / 汇率）
        |
    RawData            原始价格、波动率估计
        |
    Rules              交易规则 -> 原始预测
        |
 ForecastScaleCap     预测缩放（x forecast_scalar）-> 截断 ±20
        |
 ForecastCombine      规则权重加权 -> x 预测分散化乘数 -> 组合预测
        |
 PositionSizing       现金波动率目标 / 每块价值波动 -> 波动率标量 -> 子系统仓位
        |
   Portfolios          x 工具权重 x 工具分散化乘数 -> 组合名义仓位 -> 缓冲
        |
    Account            回测盈亏
        |
   （生产）最优仓位 -> 订单 -> 执行 -> 券商
```

标准装配见 `systems/provided/basic/system.py`，书中第 15 章的例子见 `systems/provided/futures_chapter15/basesystem.py`：

```python
System([Account(), Portfolios(), PositionSizing(), RawData(),
        ForecastCombine(), ForecastScaleCap(), rules], data, config)
```

列表顺序即框架的计算顺序（自下而上解析依赖）。

## 3. 七个模块的代码对照

| 书的框架模块 | 代码模块 | 关键类 / 方法 | 配置项 |
| --- | --- | --- | --- |
| 交易标的 Instruments | `sysobjects/instruments.py`、`contracts.py`、`rolls.py`、`sysdata/futures/` | `instrumentData`、`futuresContract`、`rollCalendar` | `instruments:`、合约与展期日历 |
| 预测 Forecasts | `systems/forecasting.py` + `systems/provided/rules/*.py` | `Rules.get_raw_forecast`、`ewmac`、`carry`、`breakout`、`accel`、`rel_mom`、`mr_wings` | `trading_rules:` |
| 预测缩放与截断 | `systems/forecast_scale_cap.py` | `get_scaled_forecast`、`get_capped_forecast`、`get_forecast_scalar` | `trading_rules.<rule>.forecast_scalar`、`forecast_cap: 20.0` |
| 组合预测 | `systems/forecast_combine.py`、`sysquant/estimators/diversification_multipliers.py`、`sysquant/estimators/correlations.py` | `ForecastCombine.get_combined_forecast`、`get_forecast_weights` | `forecast_weights:`、`forecast_div_multiplier:`、`use_forecast_weight_estimates` |
| 波动率目标 + 仓位规模 | `systems/positionsizing.py` | `get_vol_target_dict`、`get_daily_cash_vol_target`、`get_average_position_at_subsystem_level`、`get_subsystem_position` | `percentage_vol_target`、`notional_trading_capital`、`base_currency` |
| 组合 Portfolios | `systems/portfolio.py`、`systems/buffering.py` | `Portfolios.get_notional_position`、`get_instrument_diversification_multiplier`、`calculate_buffers` | `instrument_weights:`、`instrument_div_multiplier:`、`buffer_method`、`buffer_size` |
| 速度与规模 Speed and Size | `systems/accounts/account_costs.py`、`sysquant/estimators/turnover.py`、`sysquant/optimisation/` | `accountCosts`、`turnoverDataForTradingRule`、优化器族 | 成本估计与权重估计配置 |

框架之外的工程化补充：

| 组件 | 代码位置 | 说明 |
| --- | --- | --- |
| 账户与回测 | `systems/accounts/` | `accounts_stage.Account`，含成本、缓冲、订单模拟 |
| 风险度量 | `systems/risk.py`、`systems/risk_overlay.py` | 组合风险与风险叠加（对应 `systems/provided/attenuate_vol`） |
| 预测映射 | `systems/forecast_mapping.py` | 小账户场景下把预测非线性映射，避免因最小手数被迫过度交易 |
| 参数估计 | `sysquant/estimators/` | 预测标量、波动率、相关性、分散化乘数、换手率的估计器 |
| 权重优化 | `sysquant/optimisation/` | 手工分层（`handcraft`）、收缩、等权、单期优化等 |

## 4. 书中关键常量与代码位置

| 书中规定 | 代码位置 |
| --- | --- |
| 预测平均绝对值 ≈ 10（一致的“接口”） | `ForecastScaleCap.target_abs_forecast`、`sysquant/estimators/forecast_scalar.py`、配置 `average_absolute_forecast` |
| 单条规则预测上限 ±20 | `ForecastScaleCap.get_forecast_cap/get_forecast_floor`、配置 `forecast_cap` |
| 组合预测同样截断到 ±20 | `systems/forecast_combine.py` 输出前的 `cap` 处理 |
| 分散化乘数 = 1/√(W·H·Wᵀ)，负相关先归零 | `sysquant/estimators/diversification_multipliers.py` |
| 波动率估计：25 日标准差或 36 日 EWMA | `RawData.daily_returns_volatility`、`get_daily_percentage_volatility` |
| 波动率标量 = 现金波动率目标 ÷ 每块账户货币波动 | `PositionSizing.get_average_position_at_subsystem_level` |
| 仓位 = 波动率标量 × 预测 ÷ 10 | `PositionSizing.get_subsystem_position`（`vol_scalar * forecast / avg_abs_forecast`） |
| 仓位惰性：偏离不足 10% 不交易 | `systems/buffering.py`，默认 `buffer_method: forecast`、`buffer_size: 0.10` |
| 年化 = 日波动 × 16 | `PositionSizing.annual_cash_vol_target` |
| 标准化成本（SR 单位/次往返） | `systems/accounts/account_costs.py` 与换手率估计器 |

## 5. 三种使用者的代码入口

| 书中角色 | 特征 | 代码入口 |
| --- | --- | --- |
| Asset allocating investor | 固定预测 + 固定权重，低频 | `systems/provided/basic` 搭配固定 `forecast_weights`/`instrument_weights`；`static_small_system_optimise` |
| Semi-automatic trader | 人工产生预测，框架负责风险 | `systems/forecast_mapping.py` + 手工权重配置 |
| Staunch systems trader | 多规则全系统化，每日运行 | `systems/provided/futures_chapter15`（EWMAC + carry，对应书中第 15 章） |

## 6. 生产运行链路

回测与实盘共用同一套 Stage，差别只在数据源与运行方式：

`sysproduction/` 数据更新（`run_daily_price_updates.py`、`run_daily_fx_and_contract_updates.py`）
→ 用真实资金跑系统得到最优仓位（`sysproduction/strategy_code/run_system_classic.py`、`update_system_backtests.py`）
→ 写入数据库（`sysobjects/production/optimal_positions.py`）
→ 生成订单（`run_strategy_order_generator.py`，`sysproduction/update_strategy_orders.py`）
→ 订单栈与撮合（`sysexecution/stack_handler/`，含展期订单、父子订单派生）
→ 执行算法（`sysexecution/algos/`）
→ 券商接口（`sysbrokers/`，如 IB）
→ 监控与报表（`dashboard/`、`sysproduction/reporting/`、`syscontrol/`）

## 7. 主要配置文件

| 文件 | 内容 |
| --- | --- |
| `sysdata/config/defaults.yaml` | 全局默认参数（含 `buffer_size`、`forecast_cap` 等） |
| `private/private_config.yaml` | 本机私有配置（数据源、券商、账号） |
| `private/private_control_config.yaml` | 进程控制配置 |
| `systems/provided/futures_chapter15/futuresconfig.yaml` | 书中第 15 章完整示例：`trading_rules`、`forecast_weights`、`forecast_div_multiplier`、`percentage_vol_target`、`instrument_weights`、`instrument_div_multiplier`、分组信息 |
| `systems/provided/futures_chapter15/futuresestimateconfig.yaml` | 把固定权重换成估计权重（`use_forecast_scale_estimates` 等开关） |

## 8. 小结

书提供的是“每层应该算什么”的规范，本仓库提供的是“每层由哪个 Stage 承担、参数放在哪里、如何缓存与复用”的工程实现。新增交易规则只需要按接口产出预测并给出 `forecast_scalar`，框架下游的缩放、组合、波动率目标、仓位与组合环节无需改动——这正是书中“模块化 + 明确定义接口”的设计意图。
