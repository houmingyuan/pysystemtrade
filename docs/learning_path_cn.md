# 使用 pysystemtrade 需要掌握的编程知识

本文按用途把需要掌握的编程知识分成三层：跑回测（必需）、维护数据、运行生产与对接券商。每层列出对应的代码位置和“学会的标志”，最后给出建议的学习顺序。书中概念与代码的对应关系见 `docs/framework_architecture.md`，这里不重复。

## 1. 技术栈一览

统计口径：仓库内已跟踪的 673 个 `.py` 文件（2026-10）。

| 技术 | 引用的文件数 | 用在哪里 | 需要掌握的程度 |
| --- | --- | --- | --- |
| Python | — | 全部代码（`invest` 环境为 3.13，项目要求 ≥ 3.10） | 熟练，重点是面向对象 |
| pandas | 222 | 价格、预测、仓位、盈亏都是 Series / DataFrame | 熟练，最重要 |
| numpy | 93 | 向量化计算、NaN 处理 | 常用操作 |
| matplotlib | 12 | 价格与净值曲线 | 会 `.plot()` 即可 |
| PyYAML | 9 | 回测与生产配置 | 看懂 YAML 语法 |
| scipy / statsmodels | 7 / 2 | 参数估计、权重优化 | 用到时再查 |
| MongoDB（pymongo） | 2 | 合约、换月状态、订单、进程控制 | 会用 `mongosh` 查询 |
| Parquet（pyarrow） | 0（经 pandas 间接调用） | 价格数据 | 会用 `pd.read_parquet` |
| ib_async / asyncio | 16 / 2 | IB 券商接口 | 理解 `async/await` 与事件循环 |
| Flask | 1 | `dashboard/` | 只在修改 dashboard 时需要 |

## 2. 第一层：跑回测、看懂结果（必需）

1. **Python 基础**：函数、模块与 import、异常处理、f-string、`pathlib`。
2. **面向对象（重点）**：仓库里有 500 多个类，继承关系很多。回测系统由 `System`（`systems/basesystem.py`）和若干 `SystemStage`（`systems/stage.py`）组成，按 `rawdata → rules → forecastScaleCap → combForecast → positionSize → portfolio → accounts` 依次计算，各层通过 `parent` 互相调用。要能读懂类、继承、方法重写、`@property`、`@classmethod`、`@dataclass`。
3. **装饰器与缓存**：`systems/system_cache.py` 里的 `@diagnostic`、`@output` 会缓存计算结果（`systems/` 下仅 `@diagnostic` 就有约 180 处），`@input`、`@dont_cache` 只是标记，不做缓存。结果算过一次就被缓存，之后修改配置不会自动重算：要新建 system，或调用 `system.cache.delete_all_items()`（见 `docs/backtesting.md`「System Caching and pickling」）。
4. **pandas（最核心，最值得花时间）**：
   - 基本对象：`Series`、`DataFrame`、`DatetimeIndex`；
   - 常用操作：`resample`、`reindex`、`ffill`、`shift`、`rolling`、`ewm`；
   - 按日期对齐、NaN 的传播、带时区与不带时区的时间戳（本仓库的时间约定见 `docs/time_configuration_cn.md`）。

   交易规则通常只有几行 pandas，例如 EWMAC 就是快、慢两条 `ewm` 均线之差除以波动率（`systems/provided/rules/ewmac.py:120`）。
5. **numpy**：向量化计算与 NaN 处理。版本差异会改变输出，例如 numpy 2 把标量打印成 `np.int64(2)`，`syscore/pandas/find_data.py` 等处的 doctest 因此失败。
6. **matplotlib**：会画价格和净值曲线即可。
7. **YAML 与 CSV 配置**：
   - 回测参数写在 YAML 里，分三层，后面的覆盖前面的：`sysdata/config/defaults.yaml` → `private/private_config.yaml` → 回测自己的 YAML（见 `docs/backtesting.md`「How the defaults and private configuration work」）；
   - 品种与换月参数在 `data/futures/csvconfig/` 的 CSV 里（`instrumentconfig.csv`、`rollconfig.csv`）；
   - `private/` 不进版本控制，本机的回测配置 `private/futures_1m_*.yaml` 也在这里。
8. **IPython / Jupyter**：逐层查看中间结果，是理解框架最快的方式（示例见下）。

下面的代码从原始预测一路查到子系统仓位：

```python
from systems.provided.futures_chapter15.basesystem import futures_system

system = futures_system()  # 读取仓库自带的 CSV 示例数据，共 6 个品种
system.rules.get_raw_forecast("SOFR", "ewmac16_64").tail()               # 原始预测
system.forecastScaleCap.get_capped_forecast("SOFR", "ewmac16_64").tail()  # 缩放并截断后的预测
system.combForecast.get_combined_forecast("SOFR").tail()                 # 组合预测
system.positionSize.get_subsystem_position("SOFR").tail()                # 子系统仓位
```

仓库自带的示例数据较旧（SOFR 止于 2024-03-28），只适合学习。用生产价格库的完整数据跑回测，入口是 `sysinit/henrik/backtest_config.py`：

```bash
python3 sysinit/henrik/backtest_config.py --config private/futures_1m_v0.yaml --system v0
```

不加 `--output` 时结果写到 `/private/tmp/backtest_config.csv`。`docs/backtest_*.csv` 是已有的回测记录，练习时不要让 `--output` 指向它们。

**学会的标志**：

- 能读懂 `examples/introduction/` 下的 `asimpletradingrule.py` 和 `simplesystem.py`（逐步讲解见 `docs/introduction.md`）；
- 能写一条自己的规则函数并加进配置（`docs/backtesting_cn.md`「如何... 创建自己的交易规则」）；
- 能在 IPython 里从原始预测一路查到子系统仓位，并解释每一步的数值为什么变化。

## 3. 第二层：维护数据

9. **数据存储**：
   - 价格（合约价格、multiple / adjusted prices、汇率）存在 Parquet 文件里，路径由 `private/private_config.yaml` 的 `parquet_store` 指定。本机是 `/Users/henrik/data/parquet`，其中 `~/data` 是指向外置卷 `/Volumes/data/systrade` 的软链接；
   - MongoDB 存合约、换月状态、订单、进程控制等（`sysdata/mongodb/`），会用 `mongosh` 或 MongoDB Compass 查询即可；
   - 数据层的入口是 `dataBlob`（`sysdata/data_blob.py`）：代码通过各类 `xxxData` 对象读写数据，同一套接口有 CSV、MongoDB、Parquet 等实现。这是读懂 `sysdata/`、`sysproduction/` 的关键；
   - 数据概念与本仓库的数据约定见 `docs/data.md`、`docs/data_principles_cn.md`、`docs/roll_calendar_rules_cn.md`。
10. **命令行与 shell 脚本**：zsh/bash 基础、环境变量、退出码、管道与重定向。日更就是一个 zsh 脚本（`sysproduction/linux/scripts/run_daily_data_update`），日志写在 `/Volumes/data/systrade/log/update_YYYYMMDD.log`。读懂这个脚本，就能排查大多数日更失败。

**学会的标志**：

- 能用两种方式读出同一份 adjusted prices，并说清它们的关系：

  ```python
  import pandas as pd
  from sysproduction.data.prices import diagPrices

  raw = pd.read_parquet("/Users/henrik/data/parquet/futures_adjusted_prices/SOFR.parquet")  # 直接读文件
  adj = diagPrices().get_adjusted_prices("SOFR")  # 经数据层读取
  ```

- 能看懂一次日更日志：失败在哪一步、原因是什么。

## 4. 第三层：运行生产与对接券商（进阶）

11. **asyncio 与 IB 接口**：`sysbrokers/IB/` 基于 ib_async，是异步接口，至少要理解事件循环与 `async/await`。还要了解 IB 自身的概念：Gateway、端口（本机实盘 4001、纸面 4002）、client id、合约定义、行情权限。见 `docs/IB.md`。
12. **定时任务与运维**：
    - launchd 或 cron：本机日更由 `~/Library/LaunchAgents/com.henrik.systrade.update.plist` 每天 08:00 触发；launchd 在机器睡眠时会等唤醒后执行，关机则直接错过；
    - 日志、进程管理、邮件告警；生产各 `run_*` 进程的作用见 `docs/production.md`；
    - 下单经过三级订单栈：品种级 → 合约级 → 券商级（`sysexecution/order_stacks/`），整条链路见 `docs/framework_architecture.md` 第 6 节。
13. **Flask（可选）**：只在修改 `dashboard/` 时需要，见 `docs/dashboard_and_monitor.md`。

**学会的标志**：

- 能说清一笔交易从最优仓位到券商订单，经过了哪些进程和订单栈；
- 能自己排查 IB 连接问题：端口未监听、client id 冲突、缺少行情权限。

## 5. 通用工具

| 工具 | 需要掌握的内容 |
| --- | --- |
| git | 分支、提交、stash、`.gitignore`；从上游 `pst-group/pysystemtrade` 同步并解决冲突（本仓库本地改动多，经常用到） |
| conda | 使用 `invest` 环境；pandas、numpy 的版本会直接影响结果 |
| pytest | 运行测试、看懂失败信息 |
| IDE 调试器 | 在 VS Code 或 PyCharm 里打断点、单步执行；读大型框架比到处加 `print` 快得多 |

环境安装见 `docs/installation.md`。

## 6. 领域知识（不是编程，但绕不开）

代码里的概念都来自 Robert Carver 的书：

- 期货换月、carry；
- multiple prices（同时记录当前、下一个和 carry 合约价格的表）与 adjusted prices（拼接后的连续价格）；
- 波动率目标、预测缩放与截断、预测组合、分散化乘数；
- 以 Sharpe 为单位衡量的交易成本。

建议先读《Systematic Trading》，再读《Advanced Futures Trading Strategies》。

## 7. 建议的学习顺序

| 阶段 | 内容 | 主要材料 | 完成标志 |
| --- | --- | --- | --- |
| 1 | Python 基础与面向对象 | 任一 Python 入门教程 | 能读懂 `systems/stage.py`、`systems/basesystem.py` |
| 2 | pandas | pandas 官方 User Guide | 能读懂 `systems/provided/rules/` 下的规则函数 |
| 3 | 跑通第一个回测 | `docs/introduction.md`、`docs/backtesting_cn.md`、`examples/introduction/` | 第 2 节的标志 |
| 4 | 数据层 | `docs/framework_architecture.md`、`docs/data.md` | 第 3 节的标志 |
| 5 | shell、MongoDB、IB | `docs/production.md`、`docs/IB.md`；维护日更时边做边学 | 第 4 节的标志 |
