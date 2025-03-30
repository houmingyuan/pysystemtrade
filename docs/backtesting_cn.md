这是使用 pysystemtrade 作为回测平台的用户指南。在阅读本文之前，您应该已经阅读过[介绍](/docs/introduction.md)。

相关文档：

- [存储期货和现货外汇数据](/docs/data.md)
- [使用 pysystemtrade 作为生产交易环境](/docs/production.md)
- [将 pysystemtrade 连接到交互式经纪商](/docs/IB.md)
- [最近的未记录更改](/docs/recent_changes.md)

本指南分为四个部分。第一部分['如何做？'](#how-do-i)解释了如何执行许多常见任务。第二部分['指南'](#guide)详细说明了代码的相关部分，并解释了如何修改或创建新部分。第三部分['流程'](#Processes)更详细地讨论了跨越代码多个部分的某些流程。最后一部分['参考'](#reference)包括方法和参数列表。

目录
=================

<!--ts-->
* [目录](#table-of-contents)
* [如何做？](#how-do-i)
   * [如何... 对单个交易规则和工具进行实验](#how-do-i-experiment-with-a-single-trading-rule-and-instrument)
   * [如何... 创建标准期货回测](#how-do-icreate-a-standard-futures-backtest)
   * [如何... 创建估计参数的期货回测](#how-do-icreate-a-futures-backtest-which-estimates-parameters)
   * [如何... 查看回测的中间结果](#how-do-isee-intermediate-results-from-a-backtest)
   * [如何... 查看回测的盈利情况](#how-do-isee-how-profitable-a-backtest-was)
   * [如何... 更改回测参数](#how-do-ichange-backtest-parameters)
      * [选项1：更改配置文件](#option-1-change-the-configuration-file)
      * [选项2：更改配置对象；创建新系统](#option-2-change-the-configuration-object-create-a-new-system)
      * [选项3：在现有系统内更改配置对象（不推荐 - 高级）](#option-3-change-the-configuration-object-within-an-existing-system-not-recommended---advanced)
      * [选项4：创建私有配置文件](#option-4-create-a-private-config-file)
      * [选项5：更改项目默认值（绝对不推荐）](#option-5-change-the-project-defaults-definitely-not-recommended)
   * [如何... 在不同工具集上运行回测](#how-do-irun-a-backtest-on-a-different-set-of-instruments)
      * [更改工具：更改配置文件](#change-instruments-change-the-configuration-file)
      * [更改工具：更改配置对象](#change-instruments-change-the-configuration-object)
   * [如何... 仅在更新的数据上运行回测](#how-do-i-run-the-backtest-only-on-more-recent-data)
   * [如何... 在所有可用工具上运行回测](#how-do-irun-a-backtest-on-all-available-instruments)
   * [如何... 从回测中排除某些工具](#how-do-i-exclude-some-instruments-from-the-backtest)
   * [如何... 排除某些工具获得正工具权重](#how-do-i-exclude-some-instruments-from-having-positive-instrument-weights)
   * [如何... 创建自己的交易规则](#how-do-icreate-my-own-trading-rule)
      * [编写函数](#writing-the-function)
      * [将交易规则添加到配置中](#adding-the-trading-rule-to-a-configuration)
   * [如何... 使用不同的数据或工具](#how-do-iuse-different-data-or-instruments)
   * [如何... 保存我的工作](#how-do-i-save-my-work)
* [指南](#guide)
   * [数据](#data)
      * [使用标准数据对象](#using-the-standard-data-objects)
         * [通用数据对象](#generic-data-objects)
         * [csvFuturesSimData 对象](#the-csvfuturessimdata-object)
         * [dbFuturesSimData 对象](#the-dbfuturessimdata-object)
            * [设置 MongoDB 和 Parquet](#setting-up-mongodb-and-parquet)
            * [使用 dbFuturesSimData](#using-dbfuturessimdata)
         * [Arctic](#arctic)
            * [使用 Arctic 而不是 Parquet 进行回测](#backtesting-with-arctic-instead-of-parquet)
      * [创建自己的数据对象](#creating-your-own-data-objects)
         * [Data() 类](#the-data-class)
   * [配置](#configuration)
      * [创建配置对象](#creating-a-configuration-object)
         * [1) 使用字典创建配置对象](#1-creating-a-configuration-object-with-a-dictionary)
         * [2) 从文件创建配置对象](#2-creating-a-configuration-object-from-a-file)
         * [3) 从预构建系统创建配置对象](#3-creating-a-configuration-object-from-a-pre-baked-system)
         * [4) 从列表创建配置对象](#4-creating-a-configuration-object-from-a-list)
         * [5) 从 .csv 文件创建配置文件](#5-creating-configuration-files-from-csv-files)
      * [项目默认值和私有配置](#project-defaults-and-private-configuration)
         * [更改某些函数时处理默认值](#handling-defaults-when-you-change-certain-functions)
         * [默认值和私有配置如何工作](#how-the-defaults-and-private-configuration-work)
      * [查看配置参数](#viewing-configuration-parameters)
      * [修改配置参数](#modifying-configuration-parameters)
      * [在系统中使用配置](#using-configuration-in-a-system)
      * [包含自己的配置选项](#including-your-own-configuration-options)
      * [保存配置](#saving-configurations)
      * [修改配置类](#modifying-the-configuration-class)
   * [系统](#system)
      * [预构建系统](#pre-baked-systems)
         * [第15章的期货系统](#futures-system-for-chapter-15)
         * [第15章的估计系统](#estimated-system-for-chapter-15)
      * [使用系统对象](#using-the-system-object)
         * [在系统内访问子阶段、数据和配置](#accessing-child-stages-data-and-config-within-a-system)
         * [系统方法](#system-methods)
      * [系统缓存和序列化](#system-caching-and-pickling)
      * [序列化和反序列化保存的缓存数据](#pickling-and-unpickling-saved-cache-data)
      * [高级缓存](#advanced-caching)
         * [回测时的高级缓存](#advanced-caching-when-backtesting)
         * [实盘交易系统的高级缓存行为](#advanced-caching-behaviour-with-a-live-trading-system)
      * [非常高级：在新代码或修改代码中的缓存](#very-advanced-caching-in-new-or-modified-code)
      * [创建新的"预构建"系统](#creating-a-new-pre-baked-system)
      * [更改或创建新的系统类](#changing-or-making-a-new-system-class)
   * [阶段](#stages)
      * [阶段"布线"](#stage-wiring)
      * [编写新阶段](#writing-new-stages)
      * [特定阶段](#specific-stages)
      * [阶段：原始数据](#stage-raw-data)
         * [使用标准 RawData 类](#using-the-standard-rawdata-class)
            * [波动率计算](#volatility-calculation)
         * [新的或修改的原始数据类](#new-or-modified-raw-data-classes)
      * [阶段：规则](#stage-rules)
         * [数据和数据参数](#data-and-data-arguments)
      * [规则类和指定交易规则列表](#the-rules-class-and-specifying-lists-of-trading-rules)
         * [从配置对象创建规则列表](#creating-lists-of-rules-from-a-configuration-object)
         * [交互式传递交易规则列表](#interactively-passing-a-list-of-trading-rules)
         * [创建单个交易规则的变体](#creating-variations-on-a-single-trading-rule)
         * [使用新创建的 Rules() 实例](#using-a-newly-created-rules-instance)
         * [将交易规则传递给预构建系统函数](#passing-trading-rules-to-a-pre-baked-system-function)
         * [动态更改系统中的交易规则（高级）](#changing-the-trading-rules-in-a-system-on-the-fly-advanced)
      * [阶段：预测缩放和上限](#stage-forecast-scale-and-cap)
         * [使用固定权重](#using-fixed-weights)
         * [动态计算估计的预测缩放](#calculating-estimated-forecasting-scaling-on-the-fly)
            * [池化预测缩放估计（默认）](#pooled-forecast-scale-estimate-default)
            * [单个工具预测缩放估计](#individual-instrument-forecast-scale-estimate)
      * [阶段：预测组合](#stage-forecast-combine)
         * [使用固定权重和乘数](#using-fixed-weights-and-multipliers)
         * [使用估计权重和多样化乘数](#using-estimated-weights-and-diversification-multiplier)
            * [估计预测权重](#estimating-the-forecast-weights)
            * [移除昂贵的交易规则](#removing-expensive-trading-rules)
            * [估计预测多样化乘数](#estimating-the-forecast-diversification-multiplier)
         * [预测映射](#forecast-mapping)
      * [阶段：头寸缩放](#stage-position-scaling)
         * [使用标准 PositionSizing 类](#using-the-standard-positionsizing-class)
      * [阶段：创建投资组合](#stage-creating-portfolios)
         * [使用固定权重和工具多样化乘数(/systems/portfolio.py)](#using-fixed-weights-and-instrument-diversification-multipliersystemsportfoliopy)
         * [使用估计权重和工具多样化乘数(/systems/portfolio.py)](#using-estimated-weights-and-instrument-diversification-multipliersystemsportfoliopy)
            * [估计工具权重](#estimating-the-instrument-weights)
            * [使用估计的预测多样化乘数](#using-an-estimated-forecast-diversification-multiplier)
         * [缓冲和头寸惯性](#buffering-and-position-inertia)
         * [资金修正](#capital-correction)
      * [阶段：会计](#stage-accounting)
         * [使用标准 Account 类](#using-the-standard-account-class)
         * [accountCurve](#accountcurve)
         * [嵌套的 accountCurveGroup](#a-nested-accountcurvegroup)
            * [加权和未加权的账户曲线组](#weighted-and-unweighted-account-curve-groups)
         * [测试账户曲线](#testing-account-curves)
         * [成本](#costs)
      * [阶段：账户](#stage-accounts)
         * [使用标准的 Account 类](#using-the-standard-account-class)
         * [pandl_for_instrument](#pandl_for_instrument)
         * [pandl_for_subsystem](#pandl_for_subsystem)
         * [pandl_across_subsystems](#pandl_across_subsystems)
         * [pandl_for_trading_rule](#pandl_for_trading_rule)
         * [pandl_for_trading_rule_weighted](#pandl_for_trading_rule_weighted)
         * [pandl_for_trading_rule_unweighted](#pandl_for_trading_rule_unweighted)
         * [pandl_for_all_trading_rules](#pandl_for_all_trading_rules)
         * [pandl_for_all_trading_rules_unweighted](#pandl_for_all_trading_rules_unweighted)
         * [pandl_for_instrument_rules](#pandl_for_instrument_rules)
         * [pandl_for_instrument_rules_unweighted](#pandl_for_instrument_rules_unweighted)
         * [pandl_for_instrument_forecast](#pandl_for_instrument_forecast)
         * [pandl_for_instrument_forecast_weighted](#pandl_for_instrument_forecast_weighted)
* [流程](#processes)
   * [文件名](#file-names)
   * [日志记录](#logging)
      * [基本日志记录](#basic-logging)
      * [高级日志记录](#advanced-logging)
   * [优化](#optimisation)
      * [优化函数和数据](#the-optimisation-function-and-data)
      * [移除昂贵资产（仅预测权重）](#removing-expensive-assets-forecast-weights-only)
      * [合并毛收益（仅预测权重）](#pooling-gross-returns-forecast-weights-only)
      * [计算净成本（工具和预测权重）](#working-out-net-costs-both-instrument-and-forecast-weights)
      * [时间段](#time-periods)
      * [矩估计](#moment-estimation)
      * [方法](#methods)
         * [等权重](#equal-weights)
         * [单期（不推荐）](#one-period-not-recommend)
         * [自举法（推荐，但较慢）](#bootstrapping-recommended-but-slow)
         * [收缩法（可以，但难以校准）](#shrinkage-okay-but-tricky-to-calibrate)
         * [手工制作（推荐）](#handcrafting-recommended)
      * [后处理](#post-processing)
   * [估计相关性和多样化乘数](#estimating-correlations-and-diversification-multipliers)
   * [资金修正 - 变动资金](#capital-correction---varying-capital)
* [参考](#reference)
   * [标准 system.data 和 system.stage 方法表](#table-of-standard-systemdata-and-systemstage-methods)
      * [列说明](#explanation-of-columns)
      * [系统对象](#system-object)
      * [数据对象](#data-object)
      * [原始数据阶段](#raw-data-stage)
      * [交易规则阶段（书籍第7章）](#trading-rules-stage-chapter-7-of-book)
      * [预测缩放和上限阶段（书籍第7章）](#forecast-scaling-and-capping-stage-chapter-7-of-book)
      * [组合预测阶段（书籍第8章）](#combine-forecasts-stage-chapter-8-of-book)
      * [头寸缩放阶段（书籍第9章和第10章）](#position-sizing-stage-chapters-9-and-10-of-book)
      * [投资组合阶段（书籍第11章）](#portfolio-stage-chapter-11-of-book)
      * [会计阶段](#accounting-stage)
   * [配置选项](#configuration-options)
      * [原始数据](#raw-data)
         * [计算波动率](#calculating-volatility)
      * [规则阶段](#rules-stage)
         * [交易规则](#trading-rules)
      * [预测缩放和上限阶段](#forecast-scaling-and-capping-stage)
         * [预测标量（固定）](#forecast-scalar-fixed)
         * [预测标量（估计）](#forecast-scalar-estimated)
         * [预测上限（固定 - 所有类）](#forecast-cap-fixed---all-classes)
      * [预测组合阶段](#forecast-combination-stage)
         * [预测权重（固定）](#forecast-weights-fixed)
         * [预测权重（估计）](#forecast-weights-estimated)
            * [获取预测的交易规则列表](#list-of-trading-rules-to-get-forecasts-for)
            * [估计预测权重的参数](#parameters-for-estimating-forecast-weights)
         * [预测多样化乘数（固定）](#forecast-diversification-multiplier-fixed)
         * [预测多样化乘数（估计）](#forecast-diversification-multiplier-estimated)
            * [预测映射配置](#forecast-mapping-config)
      * [头寸缩放阶段](#position-sizing-stage)
         * [资金缩放参数](#capital-scaling-parameters)
      * [投资组合组合阶段](#portfolio-combination-stage)
         * [工具权重（固定）](#instrument-weights-fixed)
         * [工具权重（估计）](#instrument-weights-estimated)
         * [工具多样化乘数（固定）](#instrument-diversification-multiplier-fixed)
         * [工具多样化乘数（估计）](#instrument-diversification-multiplier-estimated)
         * [缓冲](#buffering)
      * [会计阶段配置](#accounting-stage-config)
         * [缓冲配置](#buffering-config)
         * [成本配置](#costs-config)
         * [资金修正配置](#capital-correction-config)
<!--te-->

# 如何做？

   * [如何... 对单个交易规则和工具进行实验](#how-do-i-experiment-with-a-single-trading-rule-and-instrument)
   * [如何... 创建标准期货回测](#how-do-icreate-a-standard-futures-backtest)
   * [如何... 创建估计参数的期货回测](#how-do-icreate-a-futures-backtest-which-estimates-parameters)
   * [如何... 查看回测的中间结果](#how-do-isee-intermediate-results-from-a-backtest)
   * [如何... 查看回测的盈利情况](#how-do-isee-how-profitable-a-backtest-was)
   * [如何... 更改回测参数](#how-do-ichange-backtest-parameters)
   * [如何... 在不同工具集上运行回测](#how-do-irun-a-backtest-on-a-different-set-of-instruments)
   * [如何... 创建自己的交易规则](#how-do-icreate-my-own-trading-rule)
   * [如何... 使用不同的数据或工具](#how-do-iuse-different-data-or-instruments)
   * [如何... 保存我的工作](#how-do-i-save-my-work)

## 如何... 对单个交易规则和工具进行实验

虽然该项目主要用于处理交易系统，但也可以在不构建系统的情况下进行一些有限的实验。请参见[介绍](introduction.md)中的示例。

## 如何... 创建标准期货回测

这将创建我在第15章中定义的坚定系统交易者示例，使用提供的 csv 数据，并显示您在欧元市场中的头寸：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system()
system.portfolio.get_notional_position("EDOLLAR")
```
更多信息请参见[标准期货系统](#futures-system-for-chapter-15)。

## 如何... 创建估计参数的期货回测

这将创建我在第15章中定义的坚定系统交易者示例，使用提供的 csv 数据，并估计预测标量、工具和预测权重，以及工具和预测多样化乘数：

```python
from systems.provided.futures_chapter15.estimatedsystem import futures_system
system=futures_system()
system.portfolio.get_notional_position("EDOLLAR")
```

更多信息请参见[估计期货系统](#futures-system-for-chapter-15)。

## 如何... 查看回测的中间结果

这将为您显示标准期货回测中欧元期货的 EWMAC 规则之一的原始预测（在缩放和上限之前）：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system()
system.rules.get_raw_forecast("EDOLLAR", "ewmac64_256")
```

要查看所有可能的中间结果列表，使用 `print(system)` 查看每个阶段的名称，然后使用 `stage_name.methods()`。或者查看[此表](#table-of-standard-systemdata-and-systemstage-methods)并查找标记为 **D** 的诊断行。另外，您可以输入 `system` 获取阶段列表，输入 `system.stagename.methods()` 获取特定阶段的方法列表（将 stagename 替换为实际阶段名称）。

## 如何... 查看回测的盈利情况

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system()
system.accounts.portfolio().stats() ## 查看一些统计数据
system.accounts.portfolio().curve().plot() ## 绘制账户曲线
system.accounts.portfolio().percent.curve().plot() ## 以百分比形式绘制账户曲线
system.accounts.pandl_for_instrument("US10").percent.stats() ## 生成10年期债券的百分比统计数据
system.accounts.pandl_for_instrument_forecast("EDOLLAR", "carry").sharpe() ## 特定交易规则变体的夏普比率
```

有关可用统计信息的更多信息，请参见[相关指南部分](#using-the-standard-account-class)。

## 如何... 更改回测参数

回测在以下位置查找其配置信息：

1. 配置对象中的元素
2. 如果未找到，则在：如果存在，则在 `/private/private_config.yaml` 中的私有 yaml 配置
3. 如果未找到，则在：项目默认值中

配置对象可以从 [yaml](https://pyyaml.org/) 文件加载，或使用字典创建。这意味着您可以通过以下任何方式修改系统行为：

1. 更改或创建配置 yaml 文件，读取它，并创建新系统
2. 更改内存中的配置对象，并使用它创建新系统
3. 在现有系统内更改配置对象（高级）
4. 创建私有配置 yaml `/private/private_config.yaml`（如果您想进行影响所有回测的全局更改，这很有用）
5. 更改项目默认值（绝对不推荐）

有关所有可能的配置选项列表，请参见[此表](#configuration-options)。

如果您使用选项 2 或 3，您可以[将配置保存](#saving-configurations)到 yaml 文件。

### 选项1：更改配置文件

本项目中的配置存储在 [yaml](https://pyyaml.org) 文件中。如果您不熟悉 yaml 也不用担心；它只是一种用纯文本创建嵌套字典、列表和其他 Python 对象的好方法。只需注意，就像在 Python 中一样，缩进对于创建嵌套很重要。

您可以通过复制[这个](/systems/provided/futures_chapter15/futuresconfig.yaml)文件并修改它来创建新的配置文件。最佳实践是将其保存为 `pysystemtrade/private/this_system_name/config.yaml`（您需要先创建几个目录）。

然后，您应该创建一个指向新配置文件的新系统：

```python
from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

my_config=Config("private.this_system_name.config.yaml")
system=futures_system(config=my_config)
```

有关如何在 pysystemtrade 中指定文件名的信息，请参见[此处](#file-names)。

### 选项2：更改配置对象；创建新系统

我们也可以直接修改已加载系统的配置对象，然后使用它创建新系统：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system()
new_config=system.config

new_weights=dict(SP500=0.5, KR10=0.5) ## 创建新权重
new_idm=1.1 ## 新的 IDM

new_config.instrument_weights=new_weights
new_config.instrument_div_multiplier=new_idm

system=futures_system(config=new_config)
```

对于估计权重：

```python
from systems.provided.futures_chapter15.estimatedsystem import futures_system
system=futures_system()
new_config=system.config

new_config.instruments=["SP500", "KR10"]

del(new_config.rule_variations) ## 意味着所有工具将使用所有交易规则

# 如果我们想给不同工具不同的规则集，这个阶段是可选的
new_config.rule_variations=dict(SP500=['ewmac16_64','carry'], KR10=['ewmac32_128', 'ewmac64_256', 'carry'])

system=futures_system(config=new_config)
```

## 如何... 仅在更新的数据上运行回测

您需要在 .yaml 回测配置文件中设置 start_date：

```
## 注意您必须使用这种格式
start_date: '2000-01-19'
```

## 如何... 在所有可用工具上运行回测

如果配置中没有 `instrument_weights` 或 `instruments` 元素，那么回测将在数据中的所有可用工具上运行。

## 如何... 从回测中排除某些工具

请参见[工具文档](/docs/instruments.md)。

## 如何... 排除某些工具获得正工具权重

请参见[工具文档](/docs/instruments.md)。

## 如何... 创建自己的交易规则

在某个时候，您应该阅读相关指南部分['规则'](#trading-rules)，因为这个主题比我在这里简要解释的内容要多得多。

### 编写函数

交易规则由以下部分组成：

- 一个函数
- 一些数据（指定为位置参数）
- 一些可选的控制参数（指定为关键字参数）

所以函数必须是这样的：

```python
def trading_rule_function(data1):
   ## 对 data1 做一些操作

def trading_rule_function(data1, arg1=default_value):
   ## 对 data1 做一些操作
   ## 由 arg1 的值控制

def trading_rule_function(data1, data2):
   ## 对 data1 和 data2 做一些操作

def trading_rule_function(data1, data2, arg1=default_value, arg2=default_value):
   ## 对 data1 做一些操作
   ## 由 arg1 和 arg2 的值控制
```

... 以此类推。

函数必须返回一个 Tx1 的 pandas 数据框。

### 将交易规则添加到配置中

我们可以修改 YAML 文件或已经加载到内存中的配置对象。有关更多详细信息，请参见['更改回测参数'](#how-do-ichange-backtest-parameters)。如果您想使用 YAML 文件，您需要先将函数保存到 .py 模块中，这样它就可以通过字符串引用（我们也可以对内存中的配置对象使用这种方法）。

例如，像这样导入的规则：

```python
from systems.futures.rules import ewmac
```

也可以这样引用：`systems.futures.rules.ewmac`

另外请注意，规则的数据列表也将以字符串引用的形式引用系统对象中的方法。例如，要获取每日价格，我们将使用方法 `system.rawdata.daily_prices(instrument_code)`（有关系统中所有数据方法的列表，请参见[阶段方法](#table-of-standard-systemdata-and-systemstage-methods)或输入 `system.rawdata.methods()` 和 `system.rawdata.methods()`）。在交易规则规范中，这将显示为 "rawdata.daily_prices"。

如果没有包含数据，系统将默认传递单个数据项 - 工具的价格。最后，如果缺少任何或所有 `other_arg` 关键字参数，函数将使用其自己的默认值。

在这个阶段，我们还可以删除任何不想要的交易规则。我们还应该修改预测标量（参见[预测缩放估计](#calculating-estimated-forecasting-scaling-on-the-fly)）、预测权重，可能还需要修改预测多样化乘数（参见[估计预测多样化乘数](#estimating-correlations-and-diversification-multipliers)）。如果您正在估计权重和标量（即在提供的预构建估计期货系统中），这将自动完成。

*如果您使用固定值（默认值），那么如果您不为规则包含预测标量，它将使用值 1.0。如果您在配置中不包含预测权重，系统将默认使用等权重。但如果您包含预测权重，但遗漏了新规则，那么它不会被用于计算组合预测。*

这是 EWMAC 规则新变体的示例。这个规则使用两种类型的数据 - 价格（期货拼接）和预计算的波动率估计。

YAML: (示例)
```
trading_rules:
  .... 现有规则 ...
  new_rule:
     function: systems.futures.rules.ewmac
     data:
         - "rawdata.daily_prices"
         - "rawdata.daily_returns_volatility"
     other_args:
         Lfast: 10
         Lslow: 40
#
#
## 以下部分用于固定标量、权重和多样化乘数：
#
forecast_scalars:
  ..... 现有规则 ....
  new_rule=10.6
#
forecast_weights:
  .... 现有规则 ...
  new_rule=0.10
#
forecast_div_multiplier=1.5
#
#
## 或者如果您正在估计这些数量，使用此部分：
#
use_forecast_weight_estimates: True
use_forecast_scale_estimates: True
use_forecast_div_mult_estimates: True

rule_variations:
     EDOLLAR: ['ewmac16_64','ewmac32_128', 'ewmac64_256', 'new_rule']
#
# 或者如果所有工具的所有变体都相同
#
rule_variations: ['ewmac16_64','ewmac32_128', 'ewmac64_256', 'new_rule']
#
```

Python (示例 - 假设我们已经加载了要修改的配置对象)

```python

from systems.trading_rules import TradingRule

# 方法 1
new_rule = TradingRule(
   dict(function="systems.futures.rules.ewmac", data=["rawdata.daily_prices", "rawdata.daily_returns_volatility"],
        other_args=dict(Lfast=10, Lslow=40)))

# 方法 2 - 适用于动态创建的函数
from systems.futures.rules import ewmac

new_rule = TradingRule(dict(function=ewmac, data=["rawdata.daily_prices", "rawdata.daily_returns_volatility"],
                            other_args=dict(Lfast=10, Lslow=40)))

## 两种方法 - 修改配置
config.trading_rules['new_rule'] = new_rule

## 如果您使用固定权重和标量

config.forecast_scalars['new_rule'] = 7.0
config.forecast_weights = dict(...., new_rule=0.10)  ## 所有现有预测权重都需要更新
config.forecast_div_multiplier = 1.5

## 如果您使用估计值

config.use_forecast_scale_estimates = True
config.use_forecast_weight_estimates = True
use_forecast_div_mult_estimates: True

config.rule_variations = ['ewmac16_64', 'ewmac32_128', 'ewmac64_256', 'new_rule']
# 或者为不同工具指定不同的变体
config.rule_variations = dict(SP500=['ewmac16_64', 'ewmac32_128', 'ewmac64_256', 'new_rule'], US10=['new_rule', ....)
```

一旦我们通过任何方法获得新配置，我们就可以在系统中使用它，例如：

```python
## 放入新系统

from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(config=config)
```

## 如何... 使用不同的数据或工具

模拟使用的默认数据是期货拼接价格、外汇和合约相关数据的 .csv 文件。我的意图是更新这些数据，并尝试在每个版本中保持其相对最新。数据存储在 [data/futures 目录](/data/futures) 中。

如果您愿意，可以更新这些数据。请小心将其保存为正确格式的 .csv，否则 pandas 会报错。像这样检查文件格式是否正确：

```python
import pandas as pd
test=pd.read_csv("filename.csv")
test
```
您还可以为新工具添加新文件。请确保保持文件格式和标题名称一致。

您可以为 .csv 文件创建自己的目录。例如，假设您想从 `pysystemtrade/private/system_name/adjusted_price_data` 获取调整后的价格。以下是使用方法：

```python
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData
from systems.provided.futures_chapter15.basesystem import futures_system

data=csvFuturesSimData(csv_data_paths=dict(csvFuturesAdjustedPricesData = "private.system_name.adjusted_price_data"))
system=futures_system(data=data)
```
注意，我们在项目内部使用 Python 风格的 "." 引用，而不是给出实际路径名。有关如何在 pysystemtrade 中指定文件名的信息，请参见[此处](#file-names)。

您可以在 `csv_data_paths` 中使用的完整键列表是：
* `csvFuturesInstrumentData`（配置和成本）
* `csvFuturesMultiplePricesData`（当前、下一个和远期合约的价格）
* `csvFuturesAdjustedPricesData`（拼接后调整的价格）
* `csvFxPricesData`（外汇价格）
* `csvRollParametersData`（滚动配置）
  
请注意，您不能将调整后的价格和远期数据放在同一目录中，因为它们使用相同的文件格式。

有关使用 .csv 文件的更多详细信息，请参见[此处](#the-csvfuturessimdata-object)。

如果您想将数据存储在 Mongo DB 数据库中，您需要[使用不同的数据对象](#the-dbfuturessimdata-object)。

如果您想从 Quandl.com 获取数据，请参见文档[处理期货数据](/docs/data.md)

如果您想从其他地方获取数据（例如数据库、雅虎财经、经纪商、quandl...），您需要[创建自己的数据对象](#creating-your-own-data-objects)。

如果您想使用不同的数据值（例如股票市盈率、利率...），您需要[创建自己的数据对象](#creating-your-own-data-objects)。

如果您想深入了解数据存储，请参见文档[处理期货数据](/docs/data.md)

## 如何... 保存我的工作

为了保持组织性，最好将任何工作保存到类似 `pysystemtrade/private/this_system_name/` 的目录中（您需要先创建目录）。如果您计划为 github 做贡献，请注意避免将 'private' 添加到您的提交中（[您可能想阅读这个](https://24ways.org/2013/keeping-parts-of-your-codebase-private-on-github/)）。

您可以保存系统缓存的内容，以避免在再次处理系统时重新进行计算（但在重新加载它们之前，您可能想阅读[系统缓存和序列化](#system-caching-and-pickling)）。

```python
from systems.provided.futures_chapter15.basesystem import futures_system

system = futures_system()
system.accounts.portfolio().sharpe() ## 执行一系列将被保存在缓存中的计算

system.cache.pickle("private.this_system_name.system.pck") ## 使用任何您喜欢的文件扩展名

## 在新会话中
from systems.provided.futures_chapter15.basesystem import futures_system

system = futures_system()
system.cache.unpickle("private.this_system_name.system.pck")

## 这将运行得更快并重用之前的计算
# 只有复杂的会计 p&l 对象不会保存在缓存中
system.accounts.portfolio().sharpe()
```

您还可以将配置对象保存到 yaml 文件中 - 请参见[保存配置](#saving-configurations)。

# 指南

指南部分更详细地解释了系统的每个部分如何工作：

1. [数据](#data) 对象
2. [配置](#configuration) 对象和 yaml 文件
3. [系统](#system) 对象
4. 系统内的[阶段](#stages)

每个部分都分为难度逐渐增加的部分；从使用提供的标准对象到编写您自己的对象。

## 数据

数据对象用于向系统提供数据。数据对象处理特定**类型**的数据（通常是资产类别特定的，例如期货）来自特定**来源**（例如 .csv 文件、数据库等）。

### 使用标准数据对象

当前版本提供了两种特定的数据对象 - `csvFuturesSimData`（.csv 文件）和 `dbFuturesSimData`（数据库存储）

请参见[处理期货数据](/docs/data.md)

#### 通用数据对象

您可以直接导入和使用数据对象：

*这些命令适用于所有数据对象 - 使用 `csvFuturesSimData` 版本作为示例。*

```python
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

data=csvFuturesSimData()

## 获取数据
data.methods() ## 方法列表

data.get_raw_price(instrument_code)
data[instrument_code] ## 与 get_raw_price 做同样的事情

data.get_instrument_list()
data.keys() ## 也获取工具列表

data.get_value_of_block_price_move(instrument_code)
data.get_instrument_currency(instrument_code)
data.get_fx_for_instrument(instrument_code, base_currency) # 获取工具货币和基础货币之间的汇率
```

或在系统中使用：

```python
## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(data=data)

system.data.get_instrument_currency(instrument_code) # 等等
```

（注意，在交易[规则](#stage-rules)中指定数据项时，您应该省略 system，例如 `data.get_raw_price`）

如果您设置了 start_date 配置选项，则只会显示数据的子集：

```python
## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(data=data)

# 我们也可以在 .yaml 文件中这样做。注意使用的格式必须相同
system.config.start_date = '2000-01-19'

## 或作为 datetime（显然在 yaml 中不起作用）
import datetime
system.config.start_date = datetime.datetime(2000,1,19)
```

#### csvFuturesSimData 对象

`csvFuturesSimData` 对象的工作方式如下：

```python
from sysdata.sim.csv_futures_sim_data import csvFuturesSimData

## 使用默认文件夹
data=csvFuturesSimData()

## 或者使用不同的文件夹，通过提供包含要使用的文件夹的字典
data=csvFuturesSimData(csv_data_paths = dict(key_name = "pathtodata.with.dots"))

# 允许的键名是 'csvFxPricesData'（外汇价格）、'csvFuturesMultiplePricesData' 
# （用于远期和远期价格）、
# 'csvFuturesAdjustedPricesData' 和 'csvFuturesInstrumentData'（配置和成本）。
# 如果键名不存在，则使用系统默认值

# 一个覆盖存储在 /psystemtrade/private/data/fxdata/ 中的外汇数据的示例：

data=csvFuturesSimData(csv_data_paths = dict(csvFxPricesData="private.data.fxdata"))

# 警告：不要将 multiple_price_data 和 adjusted_price_data 存储在同一个目录中
#          它们使用相同的文件名！

## 获取数据
data.methods() ## 将列出任何额外的方法
data.get_instrument_raw_carry_data(instrument_code) ## 期货特定的数据

## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(data=data)
system.data.get_instrument_raw_carry_data(instrument_code)
```

每个相关路径名必须包含以下四种类型的 .csv 文件（其中 code 是 instrument_code）：

1. 静态配置和成本数据 - `instrument_config.csv` 标题：Instrument、Pointsize、AssetClass、Currency。成本的额外标题：Slippage、PerBlock、Percentage、PerTrade。有关更多详细信息，请参见['成本'](#costs)。
2. 滚动参数数据。有关更多详细信息，请参见[存储期货和现货外汇数据](/docs/data.md)。
3. 调整后的价格数据 - `code.csv`（例如 SP500.csv）标题：DATETIME、PRICE
4. 远期和远期数据 - `code.csv`（例如 AEX.csv）：标题：DATETIME、PRICE、CARRY、FORWARD、CARRY_CONTRACT PRICE_CONTRACT、FORWARD_CONTRACT
5. 货币数据 - `ccy1ccy2fx.csv`（例如 AUDUSDfx.csv）标题：DATETIME、FXRATE

DATETIME 应该是 `pandas.to_datetime` 可以解析的内容。注意，(2) 中的价格是连续拼接的价格（参见[波动率计算](#volatility-calculation)），而 (3) 中的价格列是我们当前交易的合约价格。

至少我们需要为每个工具的货币对默认货币（定义为"USD"）有一个货币文件；以及我们交易的账户货币（即对于英国投资者，您需要一个 `GBPUSDfx.csv` 文件）。如果有交叉汇率文件，将使用它们；否则将使用 USD 汇率来计算隐含交叉汇率。

请参见 [pysystemtrade/data/futures](/data/futures) 子目录中的数据，您可以修改这些文件：

- [调整后的价格](/data/futures/adjusted_prices_csv)
- [配置和成本](/data/futures/csvconfig)
- [期货特定的远期和远期价格](/data/futures/multiple_prices_csv)
- [现货外汇价格](/data/futures/fx_prices_csv)

有关更多信息，请参见[期货数据文档](/docs/data.md#csvfuturessimdata)。

#### dbFuturesSimData 对象

这是一个从 [Mongo DB](https://mongodb.com)（静态）和 [Parquet](https://parquet.apache.org/)（时间序列）获取数据的 simData 对象。它更适合实盘交易。对于生产代码和存储大量数据（例如单个期货合约），我们可能需要比 .csv 文件更强大的东西。

##### 设置 MongoDB 和 Parquet

显然，您需要确保已经有一个 Mongo DB 实例在运行。您可能会发现已经有一个在运行，在 Linux 中使用 `ps wuax | grep mongo` 然后终止相关进程。

因为 mongoDB 数据不包含在 github 仓库中，所以在使用之前，您需要将所需的数据写入 Mongo 和 Parquet。
您可以从头开始，按照['期货数据工作流程'](/docs/data.md#part-1-a-futures-data-workflow)进行。或者您可以运行以下脚本，这些脚本将从现有的 github .csv 文件复制数据：

- [调整后的价格](/sysinit/futures/repocsv_adjusted_prices.py)
- [多重价格](/sysinit/futures/repocsv_multiple_prices.py)
- [现货外汇价格](/sysinit/futures/repocsv_spotfx_prices.py)
- [价差数据](/sysinit/futures/repocsv_spread_costs.py)

当然也可以混合使用这两种方法。

##### 使用 dbFuturesSimData

一旦您有了数据，就只需要替换默认的 csv 数据对象： 

```python
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from systems.provided.futures_chapter15.basesystem import futures_system

data = dbFuturesSimData()
system = futures_system(data=data)
```

dbFuturesSimData 对象提供了与 csvFuturesSimData 相同的接口，但数据是从 MongoDB 和 Parquet 中获取的。有关更多信息，请参见[期货数据文档](/docs/data.md#dbfuturessimdata)。

### 创建您自己的数据对象

如果您想从其他地方获取数据（例如数据库、雅虎财经、经纪商、quandl...），您需要创建一个新的数据对象。您可以通过继承 `sysdata.data.Data` 类来实现这一点。

```python
from sysdata.data import Data

class MyData(Data):
    def __init__(self):
        super().__init__()
        # 在这里进行任何必要的初始化

    def get_raw_price(self, instrument_code):
        # 返回一个 pandas 时间序列，包含原始价格
        pass

    def get_instrument_list(self):
        # 返回一个工具代码列表
        pass

    def get_value_of_block_price_move(self, instrument_code):
        # 返回一个浮点数，表示一个价格块移动的价值
        pass

    def get_instrument_currency(self, instrument_code):
        # 返回一个字符串，表示工具的货币
        pass

    def get_fx_for_instrument(self, instrument_code, base_currency):
        # 返回一个 pandas 时间序列，包含工具货币和基础货币之间的汇率
        pass
```

有关更多信息，请参见[期货数据文档](/docs/data.md#creating-your-own-data-objects)。

## 配置

配置对象用于存储系统的配置信息。配置对象可以从 yaml 文件中加载，也可以直接修改。

### 使用标准配置对象

当前版本提供了两种特定的配置对象 - `sysdata.config.Config` 和 `sysdata.config.ConfigWithInheritance`。

请参见[配置文档](/docs/configuration.md)

#### 通用配置对象

您可以直接导入和使用配置对象：

*这些命令适用于所有配置对象 - 使用 `Config` 版本作为示例。*

```python
from sysdata.config import Config

config = Config()

## 获取配置
config.methods() ## 方法列表

config.get_value("key")
config["key"] ## 与 get_value 做同样的事情

config.get_value_or_default("key", default_value)
config.get_value_or_none("key")

## 设置配置
config.set_value("key", value)
config["key"] = value ## 与 set_value 做同样的事情

## 删除配置
config.delete_value("key")
del config["key"] ## 与 delete_value 做同样的事情

## 保存配置
config.save_to_yaml("private.this_system_name.config.yaml")

## 从 yaml 加载配置
config.load_from_yaml("private.this_system_name.config.yaml")
```

或在系统中使用：

```python
## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system()

system.config.get_value("key") # 等等
```

如果您设置了 start_date 配置选项，则只会显示数据的子集：

```python
## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system()

# 我们也可以在 .yaml 文件中这样做。注意使用的格式必须相同
system.config.start_date = '2000-01-19'

## 或作为 datetime（显然在 yaml 中不起作用）
import datetime
system.config.start_date = datetime.datetime(2000,1,19)
```

#### Config 对象

`Config` 对象的工作方式如下：

```python
from sysdata.config import Config

## 使用默认配置
config = Config()

## 或者使用不同的配置，通过提供包含要使用的配置的字典
config = Config(config_dict = dict(key_name = value))

# 一个覆盖存储在 /psystemtrade/private/config/myconfig.yaml 中的配置的示例：

config = Config(config_dict = dict(start_date = '2000-01-19'))

## 获取配置
config.methods() ## 将列出任何额外的方法

## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system(config=config)
system.config.get_value("key")
```

#### ConfigWithInheritance 对象

`ConfigWithInheritance` 对象的工作方式与 `Config` 对象类似，但它支持配置继承。这意味着您可以从一个基础配置继承，然后覆盖特定的值。

```python
from sysdata.config import ConfigWithInheritance

## 使用默认配置
config = ConfigWithInheritance()

## 或者使用不同的配置，通过提供包含要使用的配置的字典
config = ConfigWithInheritance(config_dict = dict(key_name = value))

# 一个覆盖存储在 /psystemtrade/private/config/myconfig.yaml 中的配置的示例：

config = ConfigWithInheritance(config_dict = dict(start_date = '2000-01-19'))

## 获取配置
config.methods() ## 将列出任何额外的方法

## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system(config=config)
system.config.get_value("key")
```

### 创建您自己的配置对象

如果您想使用不同的配置格式（例如 JSON、XML...），您需要创建一个新的配置对象。您可以通过继承 `sysdata.config.Config` 类来实现这一点。

```python
from sysdata.config import Config

class MyConfig(Config):
    def __init__(self):
        super().__init__()
        # 在这里进行任何必要的初始化

    def get_value(self, key):
        # 返回配置值
        pass

    def set_value(self, key, value):
        # 设置配置值
        pass

    def delete_value(self, key):
        # 删除配置值
        pass

    def save_to_yaml(self, filename):
        # 将配置保存到 yaml 文件
        pass

    def load_from_yaml(self, filename):
        # 从 yaml 文件加载配置
        pass
```

有关更多信息，请参见[配置文档](/docs/configuration.md#creating-your-own-config-objects)。

## 系统

系统对象是回测系统的核心。系统对象包含多个阶段，每个阶段负责系统的不同部分。

### 使用标准系统对象

当前版本提供了一个特定的系统对象 - `futures_system`。

请参见[系统文档](/docs/system.md)

#### 通用系统对象

您可以直接导入和使用系统对象：

*这些命令适用于所有系统对象 - 使用 `futures_system` 版本作为示例。*

```python
from systems.provided.futures_chapter15.basesystem import futures_system

system = futures_system()

## 获取系统数据
system.methods() ## 方法列表

system.get_raw_price(instrument_code)
system[instrument_code] ## 与 get_raw_price 做同样的事情

system.get_instrument_list()
system.keys() ## 也获取工具列表

system.get_value_of_block_price_move(instrument_code)
system.get_instrument_currency(instrument_code)
system.get_fx_for_instrument(instrument_code, base_currency) # 获取工具货币和基础货币之间的汇率

## 获取系统配置
system.config.get_value("key")
system.config["key"] ## 与 get_value 做同样的事情

## 获取系统数据
system.data.get_raw_price(instrument_code)
system.data[instrument_code] ## 与 get_raw_price 做同样的事情

system.data.get_instrument_list()
system.data.keys() ## 也获取工具列表

system.data.get_value_of_block_price_move(instrument_code)
system.data.get_instrument_currency(instrument_code)
system.data.get_fx_for_instrument(instrument_code, base_currency) # 获取工具货币和基础货币之间的汇率

## 获取系统阶段
system.rules.get_raw_forecast(instrument_code, rule_name)
system.positionSize.get_position_forecast(instrument_code)
system.portfolio.get_notional_position(instrument_code)
system.accounts.portfolio().sharpe()
```

如果您设置了 start_date 配置选项，则只会显示数据的子集：

```python
## 在系统中使用
from systems.provided.futures_chapter15.basesystem import futures_system
system = futures_system()

# 我们也可以在 .yaml 文件中这样做。注意使用的格式必须相同
system.config.start_date = '2000-01-19'

## 或作为 datetime（显然在 yaml 中不起作用）
import datetime
system.config.start_date = datetime.datetime(2000,1,19)
```

#### futures_system 对象

`futures_system` 对象的工作方式如下：

```python
from systems.provided.futures_chapter15.basesystem import futures_system

## 使用默认配置
system = futures_system()

## 或者使用不同的配置，通过提供包含要使用的配置的字典
system = futures_system(config_dict = dict(key_name = value))

# 一个覆盖存储在 /psystemtrade/private/config/myconfig.yaml 中的配置的示例：

system = futures_system(config_dict = dict(start_date = '2000-01-19'))

## 获取系统数据
system.methods() ## 将列出任何额外的方法

## 获取系统阶段
system.rules.get_raw_forecast(instrument_code, rule_name)
system.positionSize.get_position_forecast(instrument_code)
system.portfolio.get_notional_position(instrument_code)
system.accounts.portfolio().sharpe()
```

### 创建您自己的系统对象

如果您想使用不同的系统架构（例如多资产、多策略...），您需要创建一个新的系统对象。您可以通过继承 `systems.system.System` 类来实现这一点。

```python
from systems.system import System

class MySystem(System):
    def __init__(self):
        super().__init__()
        # 在这里进行任何必要的初始化

    def get_raw_price(self, instrument_code):
        # 返回一个 pandas 时间序列，包含原始价格
        pass

    def get_instrument_list(self):
        # 返回一个工具代码列表
        pass

    def get_value_of_block_price_move(self, instrument_code):
        # 返回一个浮点数，表示一个价格块移动的价值
        pass

    def get_instrument_currency(self, instrument_code):
        # 返回一个字符串，表示工具的货币
        pass

    def get_fx_for_instrument(self, instrument_code, base_currency):
        # 返回一个 pandas 时间序列，包含工具货币和基础货币之间的汇率
        pass

    def get_raw_forecast(self, instrument_code, rule_name):
        # 返回一个 pandas 时间序列，包含原始预测
        pass

    def get_position_forecast(self, instrument_code):
        # 返回一个 pandas 时间序列，包含位置预测
        pass

    def get_notional_position(self, instrument_code):
        # 返回一个 pandas 时间序列，包含名义位置
        pass

    def get_portfolio(self):
        # 返回一个 pandas 时间序列，包含投资组合
        pass
```

有关更多信息，请参见[系统文档](/docs/system.md#creating-your-own-system-objects)。

#### 5) 从 .csv 文件创建配置文件

有时从 .csv 文件指定某些参数，然后将它们推送到 .yaml 文件中会更方便。如果您想使用这种方法，可以使用以下两个函数：

```python
from sysinit.configtools.csvweights_to_yaml import instr_weights_csv_to_yaml  # 用于工具权重
from sysinit.configtools.csvweights_to_yaml import forecast_weights_by_instrument_csv_to_yaml  # 每个工具的预测权重
from sysinit.configtools.csvweights_to_yaml import forecast_mapping_csv_to_yaml # 每个工具的预测映射
```

这些函数将创建 .yaml 文件，然后可以将其粘贴到您现有的配置文件中。

### 项目默认值和私有配置

许多（但不是全部）配置参数都有默认值，如果参数不在对象中，系统会使用这些默认值。这些默认值可以在 [defaults.yaml 文件](/sysdata/config/defaults.yaml) 中找到。[配置选项](#configuration-options) 部分解释了默认值是什么，以及它们在哪里使用。

我建议您不要更改这些默认值。最好在每个系统配置文件中使用您想要的设置，或者如果这是您想要应用于所有回测的内容，则使用私有配置文件。

如果存在 `/private/private_config.yaml` 文件，它将被用作私有配置文件。

基本上，每当将配置对象添加到系统中时，如果存在私有配置文件，我们就会添加该文件中的元素。然后对于任何剩余的缺失元素，我们会从 defaults.yaml 中添加元素。

#### 当您更改某些函数时处理默认值

在某些地方，您可以更改用于执行特定计算的函数，例如波动率估计（这*不*包括交易规则 - 我们更改这些函数的方式完全不同）。如果您要使用与原始参数相同的参数，这很简单。但是，如果您更改参数，则需要更改项目默认值 .yaml 文件。我建议保留原始参数，并添加具有不同名称的新参数，以避免意外破坏系统。

#### 默认值和私有配置如何工作

当添加到系统时，配置类会填充原始配置对象中缺失但存在于 (i) 私有 .yaml 文件和 (ii) 默认 .yaml 文件中的参数。例如，如果配置中缺少 forecast_scalar，则将使用默认值 1.0。这对于顶级配置项（列表、str、int 和 float）也是类似的工作方式。

如果配置中的字典中缺少任何内容，这也会发生（例如，如果 `config.forecast_div_mult_estimate` 是一个字典，那么默认 .yaml 中存在但配置中不存在的任何键都将被添加）。最后，它也适用于嵌套字典，例如，如果 `config.instrument_weight_estimate['correlation_estimate']` 中缺少任何键，它们将从默认文件中填充。如果某个内容在配置中是字典或嵌套字典，但在默认值中不是（反之亦然），则值不会被替换，可能会发生不好的事情。最好保持配置文件和默认文件具有匹配的结构（至少对于您想要更改的项目！）。这也是添加新参数并保留原始参数的一个很好的理由。

请注意，这意味着配置在进入系统对象之前和之后可能会不同；后者将填充默认值。

```python
from sysdata.config.configdata import Config
my_config=Config()
print(my_config) ## 空配置
```

```
 Config with elements:
```

现在在系统中：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(config=my_config)

print(system.config) ## 充满默认值
print(my_config) ## 相同的对象
```

```
 Config with elements: average_absolute_forecast, base_currency, buffer_method, buffer_size, buffer_trade_to_edge, forecast_cap, forecast_correlation_estimate, forecast_div_mult_estimate, forecast_div_multiplier, forecast_scalar, forecast_scalar_estimate, forecast_weight_estimate, instrument_correlation_estimate, instrument_div_mult_estimate, instrument_div_multiplier, instrument_weight_estimate, notional_trading_capital, percentage_vol_target, use_SR_costs, use_forecast_scale_estimates, use_forecast_weight_estimates, use_instrument_weight_estimates, volatility_calculation
```

请注意，这对于工作的交易系统来说还不够，因为交易规则不是由默认值填充的：

```python
system.accounts.portfolio()
```

```
# 删除完整的错误跟踪
Exception: A system config needs to include trading_rules, unless rules are passed when object created
```

### 查看配置参数

无论我们是使用 yaml 文件还是交互式创建字典，我们最终都会得到一个字典。顶级字典中的键将成为配置的属性。然后我们可以使用字典键或列表位置来访问任何嵌套数据。例如，使用上面的简单配置：

```python
my_config.optionone
my_config.optiontwo['a']
my_config.optionthree[0]
```

### 修改配置参数

修改配置同样简单。例如，使用上面的简单配置：

```python
my_config.optionone=1.0
my_config.optiontwo['d']=5.0
my_config.optionthree.append(6.3)
```

您还可以添加新的顶级配置项：

```python
my_config.optionfour=20.0
setattr(my_config, "optionfour", 20.0) ## 如果您更喜欢这种方式
```

或删除它们：

```python
del(my_config.optionone)
```

对于真实的配置，您需要小心处理嵌套参数：

```python
config.instrument_div_multiplier=1.1 ## 不是嵌套的，没问题

## 这是一个如何更改嵌套参数的示例
## 如果元素在您的配置中尚不存在
## 如果元素确实存在，那么显然这样做会覆盖配置中的所有其他参数 - 所以不要这样做！

config.volatility_calculation=dict(days=20)

## 如果它确实存在，您可以这样做：
config.volatility_calculation['days']=20
```

如果您要更改已包含在系统中的配置，这一点尤其重要，该配置将已经包含所有默认值：

```python
system.config.instrument_div_multiplier=1.1 ## 不是嵌套的，没问题

## 如果我们更改任何嵌套的内容，我们需要只更改一个元素以避免清除默认值：
# 所以，这样做：
system.config.volatility_calculation['days']=20

# 不要这样做：
# system.config.volatility_calculation=dict(days=20)
```

### 在系统中使用配置

一旦我们对配置满意，我们就可以在系统中使用它：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system(config=my_config)
```

请注意，只有当配置包含在系统中时，才会填充私有配置和默认值。

### 包含您自己的配置选项

如果您开发自己的阶段或修改现有阶段，您可能想要包含新的配置选项。以下是您的代码应该做的：

```python
## 假设您的配置项称为 my_config_item；在相关方法中：

    parameter=system.config.my_config_item

    ## 您还可以使用嵌套的配置项，例如按 instrument_code 键控的字典（或嵌套列表）
    parameter=system.config.my_config_dict[instrument_code]

    ## 列表也可以工作。
```

有关系统及其阶段中所有方法的列表，请参见[阶段方法](#table-of-standard-systemdata-and-systemstage-methods)。或者：
```python
system ## 列出所有阶段
system.accounts.methods() ## 列出特定阶段中的所有方法
system.data.methods() ## 对数据也有效
```

我们还可以访问或更改配置对象的元素：

```python
system.config.trading_rules
system.config.instrument_div_multiplier=1.2
```

#### 系统方法

基本系统只有几个自己的公共方法（除了下面描述的用于缓存的方法之外）：

`system.get_instrument_list()` 这将获取系统中的工具列表，可以从配置对象中获取（如果它包含工具权重），也可以从数据对象中获取。

这些方法也获取工具列表，有关更多信息，请参见[工具文档](/docs/instruments.md)：
```
get_list_of_bad_markets
get_list_of_markets_not_trading_but_with_data
get_list_of_duplicate_instruments_to_remove
get_list_of_ignored_instruments_to_remove
get_list_of_instruments_to_remove
get_list_of_markets_with_trading_restrictions
```

`system.log` 提供对系统日志的访问。有关更多详细信息，请参见[日志记录](#logging)。

### 系统缓存和序列化

拉取数据和计算系统中的各个阶段可能是一个耗时的过程。所以代码支持缓存。当我们第一次通过调用阶段方法（如 `system.portfolio.get_notional_position("EDOLLAR")`）请求一些数据时，系统首先检查是否已经预先计算了这个数字。如果没有，它将从头开始计算这个数字。这反过来可能涉及计算需要的初步数字，除非它们已经被预先计算。例如，要获得组合预测，我们需要已经有特定工具的不同交易规则变体的所有单独预测。一旦我们计算了一个特定的数据点（这可能需要一些时间），它就会存储在系统对象缓存中（以及我们计算的任何中间结果）。下次我们请求它时，它将立即被提供。

大多数时候您不需要担心缓存。如果您正在测试不同的配置，或更新或更改数据，您只需要确保在每次更改后从头开始重新创建系统对象。新的系统对象将有一个空的缓存。

缓存标签

```python
from copy import copy
from systems.provided.futures_chapter15.basesystem import futures_system

system=futures_system()
system.combForecast.get_combined_forecast("EDOLLAR")

## 缓存中有什么？
system.cache.get_cache_refs_for_instrument("EDOLLAR")

   [_get_forecast_scalar_fixed in forecastScaleCap for instrument EDOLLAR [carry] , get_raw_forecast in rules for instrument EDOLLAR [ewmac32_128]  ...


## 让我们对配置进行更改：
system.config.forecast_div_multiplier=0.1

## 这将产生相同的结果，因为我们已经缓存了结果
system.combForecast.get_combined_forecast("EDOLLAR")

## 但如果我们用新配置创建一个新系统...
system=futures_system(config=system.config)

## 检查缓存是否为空：
system.cache.get_cache_refs_for_instrument("EDOLLAR")

## ... 我们得到不同的结果
system.combForecast.get_combined_forecast("EDOLLAR")

## 我们也可以关闭缓存
## 首先清除缓存
system.cache.clear()

## ... 这里应该什么都没有
system.cache.get_cache_refs_for_instrument("EDOLLAR")

## 现在关闭缓存
system.cache.set_caching_off()

## 现在获取一些数据后：
system.combForecast.get_combined_forecast("EDOLLAR")

##.... 缓存仍然是空的
system.cache.get_cache_refs_for_instrument("EDOLLAR")

## 如果我们更改配置
system.config.forecast_div_multiplier=100.0

## ... 那么结果会不同，而不需要创建新系统
system.combForecast.get_combined_forecast("EDOLLAR")
```

### 序列化和反序列化保存的缓存数据

回测一个大型系统可能需要一段时间。能够保存缓存的内容并在以后重新加载是很有用的。我使用 python 的 pickle 模块来做这个。

由于无聊的 python 相关原因，缓存中并非所有元素都会被保存。会计信息和估计权重时使用的优化函数将被排除，不会被重新加载。

```python
from systems.provided.futures_chapter15.basesystem import futures_system

system = futures_system()
system.accounts.portfolio().sharpe() ## 做了一堆将被保存在缓存中的计算。有点慢...

system.cache.get_itemnames_for_stage("accounts") # 包括 'portfolio'

# 如果我再次请求这个，它会超快
system.accounts.portfolio().sharpe()

## 保存它
system.cache.pickle("private.this_system_name.system.pck") ## 使用 'dot' 方法来标识工作区中的文件。使用任何您喜欢的文件扩展名


## 现在在新会话中
system = futures_system()
system.cache.get_items_with_data() ## 检查空缓存

system.cache.unpickle("private.this_system_name.system.pck")

system.cache.get_items_with_data() ## 缓存现在已填充。系统实例中的任何现有数据都将被删除。
system.get_itemnames_for_stage("accounts") ## 现在不包括 ('accounts', 'portfolio', 'percentageTdelayfillTroundpositionsT')

system.accounts.portfolio().sharpe() ## 不是来自缓存，但这将运行得更快并重用许多先前的计算

```

有关如何在 pysystemtrade 中指定文件名的信息，请参见[此处](#file-names)。

### 高级缓存

也可以选择性地删除某些缓存项，同时保持系统的其余部分完整。如果不了解[阶段连接](#stage-wiring)，您不应该这样做。您需要很好地了解每个阶段中的各种方法，以了解删除或保留特定数据值的下游影响。

缓存中存储的数据有四个属性：

1. 未受保护的数据，在请求时从缓存中删除
2. 受保护的数据，通常不会被删除。冗长估计的输出通常受到保护
3. 特定于特定工具的数据（可以受保护或不受保护）
4. 适用于整个系统或至少适用于多个工具的数据（可以受保护或不受保护）

受保护的项目和整个系统通用的项目通常不会被删除，因为它们通常是计算最慢的东西。

例如，这里是我们如何在获取名义位置后检查缓存（这会生成大量中间结果）。注意我们可以过滤和处理缓存键列表的方式。

```python
system.portfolio.get_notional_position("EDOLLAR")

system.cache.get_items_with_data() ## 这列出所有内容。
system.cache.get_cacherefs_for_stage("portfolio") ## 列出特定阶段中的所有内容
system.cache.get_items_with_data().filter_by_stage_name("portfolio") ## 更惯用的方式
system.cache._get_protected_items() ## 列出受保护的项目
system.cache.get_items_with_data().filter_by_instrument_code("EDOLLAR") ## 列出工具的数据项
system.cache.get_cache_refs_across_system() ## 列出跨整个系统或多个工具运行的项目

system.cache.get_items_with_data().filter_by_itemname('get_capped_forecast').unique_list_of_instrument_codes() ## 列出所有具有上限预测的工具

```

现在，如果我们想选择性地清除缓存的部分内容，我们可以执行以下操作之一：

```python
system.cache.delete_items_for_instrument(instrument_code) ## 删除与工具相关的所有内容：不受保护，或跨系统项目
```

### 阶段：规则

交易规则是完全系统化交易系统的核心。这个阶段的描述与其他阶段不同，将以创建交易规则的教程形式呈现。

基类 Rules() [在这里](/systems/forecasting.py)，通常不需要修改这个类。一个交易规则由以下部分组成：

- 一个函数
- 一些数据（作为位置参数指定）
- 一些可选的控制参数（作为关键字参数指定）

因此，函数必须类似于以下形式：

```python
def trading_rule_function(data1):
   ## 对 data1 进行处理

def trading_rule_function(data1, arg1=default_value):
   ## 对 data1 进行处理
   ## 由 arg1 的值控制

def trading_rule_function(data1, data2):
   ## 对 data1 和 data2 进行处理

def trading_rule_function(data1, data2, arg1=default_value, arg2=default_value):
   ## 对数据进行处理
   ## 由 arg1 和 arg2 的值控制
```

... 等等。

我们至少需要知道函数，因为其他参数是可选的，如果没有指定数据，则使用工具价格。只指定函数的规则是"裸"规则。它应该只接受一个数据参数（即价格），并且没有需要新参数值的其他参数。

在这个项目中有一个特定的 [TradingRule 类](/systems/forecasting.py)。一个 `TradingRule` 实例包含 3 个元素 - 一个函数、函数需要的任何数据列表，以及可以传递给函数的任何其他参数的字典。

函数可以是实际函数，也可以是对它的相对引用，例如 `systems.provided.futures_chapter15.rules.ewmac`（当从文件创建配置时这很有用）。数据必须始终以系统对象的属性和方法引用的形式出现，例如 `data.daily_prices` 或 `rawdata.get_daily_prices`。必须传递单个数据项或列表。其他参数以字典的形式出现。

我们可以通过多种不同的方式创建交易规则。我注意到不同的人发现不同的定义规则方式更自然，因此这里故意保持灵活性。

只包含函数的裸规则可以按如下方式定义：

```python
from systems.trading_rules import TradingRule

TradingRule(ewmac)  ## 使用实际函数
TradingRule("systems.provided.futures_chapter15.rules.ewmac")  ## 函数的字符串引用
```

我们还可以添加数据和其他参数。数据始终是字符串列表或单个字符串。其他参数始终是字典。

```python
TradingRule(ewmac, data='rawdata.get_daily_prices', other_args=dict(Lfast=2, Lslow=8))
```

多个数据也可以，并且可以省略数据或 other_args：

```python
TradingRule(some_rule, data=['rawdata.get_daily_prices','data.get_raw_price'])
```

有时用"整体"方式指定规则更容易。你可以使用 3 元组来做到这一点。注意这里我们用字符串指定函数，并列出多个数据项：

```python
TradingRule(("systems.provided.futures_chapter15.rules.ewmac", ['rawdata.get_daily_prices','data.get_raw_price'], dict(Lfast=3, Lslow=12)))
```

你也可以用字典指定规则。如果使用字典，关键字可以省略（但不能省略 `function`）。

```python
TradingRule(dict(function="systems.provided.futures_chapter15.rules.ewmac", data=['rawdata.get_daily_prices','data.get_raw_price']))
```

注意，如果你使用"整体"方法，并且在调用 `TradingRule` 时也包含 `data` 或 `other_args` 参数，你会收到警告。

当从 YAML 文件读取配置对象时使用字典方法；这些配置对象在嵌套字典中包含交易规则。

YAML：（示例）
```yaml
trading_rules:
  ewmac2_8:
     function: systems.futures.rules.ewmac
     data:
         - "data.daily_prices"
         - "rawdata.daily_returns_volatility"
     other_args:
         Lfast: 2
         Lslow: 8
     forecast_scalar: 10.6
```

Python（示例）
```python
config.trading_rules=dict(ewmac2_8=dict(function="systems.futures.rules.ewmac", data=["rawdata.daily_prices", "rawdata.daily_returns_volatility"], other_args=dict(Lfast=2, Lslow=8), forecast_scalar=10.6))
```

### 预测缩放和封顶阶段

预测缩放和封顶阶段负责调整和限制交易规则产生的预测值。这个阶段包括预测的缩放、上限设置和估计。

#### 固定预测缩放
你可以通过以下方式设置固定的预测缩放：

1. 在交易规则定义中设置：
```yaml
trading_rules:
  ewmac2_8:
     function: systems.futures.rules.ewmac
     forecast_scalar: 10.6
```

2. 单独设置：
```yaml
forecast_scalars:
   ewmac2_8: 10.6
   ewmac4_16: 15.0
```

#### 估计预测缩放
你可以使用系统自动估计预测缩放：

```yaml
use_forecast_scale_estimates: True
forecast_scalar_estimate:
   pool_instruments: True
   func: "sysquant.estimators.forecast_scalar.forecast_scalar"
   window: 250000
   min_periods: 500
   backfill: True
```

主要参数说明：
- pool_instruments：是否在多个工具上池化估计
- window：估计窗口大小
- min_periods：最小所需周期数
- backfill：是否回填缺失值

#### 预测上限
预测上限用于限制预测的最大绝对值：

```yaml
# 设置固定上限
forecast_cap: 20.0
```

你可以通过以下方式获取缩放和上限后的预测：

```python
# 获取缩放后的预测
scaled_forecast = system.forecastScaleCap.get_scaled_forecast("EDOLLAR", "ewmac2_8")

# 获取上限后的预测
capped_forecast = system.forecastScaleCap.get_capped_forecast("EDOLLAR", "ewmac2_8")
```

#### 预测映射
预测映射允许对预测进行非线性转换：

```yaml
forecast_mapping:
   func: "syscore.mapping.map_forecast_value"
   threshold: 20.0
   a_param: 1.0
   b_param: 0.5
   clip: True
```

主要参数说明：
- threshold：映射阈值
- a_param：映射参数 a
- b_param：映射参数 b
- clip：是否裁剪超出范围的值

#### 注意事项

1. 缩放设置：
- 选择合适的缩放因子
- 考虑不同市场的特点
- 注意缩放的稳定性

2. 上限管理：
- 设置合理的上限值
- 监控上限的影响
- 考虑市场条件变化

3. 估计过程：
- 使用足够的历史数据
- 考虑估计的稳定性
- 注意样本外表现

4. 映射配置：
- 选择适当的映射函数
- 调整映射参数
- 验证映射效果

### 阶段：头寸缩放

头寸缩放阶段负责根据波动率目标和账户规模调整交易头寸。这个阶段主要处理名义头寸，暂时不考虑损益的复利效应。

#### 波动率目标和资金配置
你可以通过以下方式设置波动率目标和资金配置：

```yaml
# 基本配置
percentage_vol_target: 20.0  # 以百分比表示的年化波动率目标
notional_trading_capital: 1000000  # 名义交易资本
base_currency: "USD"  # 基础货币

# 风险配置
risk_target: 0.2  # 目标风险水平
risk_overlay: True  # 是否启用风险叠加
```

#### 头寸计算
头寸计算涉及以下步骤：

1. 获取子系统头寸：
```python
# 获取子系统头寸
subsys_position = system.positionSize.get_subsystem_position("EDOLLAR")
```

2. 计算实际头寸：
```python
# 获取实际头寸
position = system.positionSize.get_position("EDOLLAR")
```

3. 获取头寸缩放因子：
```python
# 获取头寸缩放因子
scaling_factor = system.positionSize.get_volatility_scalar("EDOLLAR")
```

#### 头寸限制
可以通过以下方式设置头寸限制：

```yaml
# 固定头寸限制
position_limits:
   EDOLLAR: 100  # 单个工具的最大头寸
   default: 50    # 默认最大头寸

# 动态头寸限制
dynamic_position_limits:
   enabled: True
   window: 250    # 计算窗口大小
   position_ceiling: 100  # 最大允许头寸
```

#### 头寸缓冲
为了减少交易频率，可以使用头寸缓冲：

```yaml
buffer_positions:
   enabled: True
   buffer_size: 0.10  # 10% 的缓冲区
   buffer_method: "symmetric"  # 对称缓冲
```

#### 注意事项

1. 风险管理：
- 设置合适的波动率目标
- 监控总体风险敞口
- 考虑相关性影响

2. 头寸限制：
- 设置合理的头寸上限
- 考虑市场流动性
- 注意保证金要求

3. 头寸调整：
- 使用适当的缓冲机制
- 控制交易频率
- 考虑交易成本

4. 资金管理：
- 合理分配资金
- 监控资金使用
- 维护风险平衡

// ... existing code ...

### 阶段：创建投资组合

- 代码在这里：[/systems/portfolio.py](/systems/portfolio.py)

工具权重和工具多样化乘数用于将不同工具组合成最终投资组合（我的书第十一章）。

#### 使用固定权重和工具多样化乘数(/systems/portfolio.py)

默认使用固定权重和乘数。

两者都是可配置的。如果省略，将使用相等权重和 1.0 的乘数。

YAML：
```yaml
instrument_weights:
    EDOLLAR: 0.5
    US10: 0.5
instrument_div_multiplier: 1.2
```

注意，标准固定基类中的 `get_instrument_weights` 方法会在不同工具的价格历史和预测有不同开始日期时自动调整原始预测权重。它不会调整乘数。这意味着在过去乘数可能会太高。

#### 使用估计的权重和工具多样化乘数(/systems/portfolio.py)

你可以"动态"估计正确的工具多样化乘数，也可以估计工具权重。这个功能包含在预制的[估计期货系统](#futures-system-for-chapter-15)中。通过设置 `config.use_instrument_weight_estimates=True` 和/或 `config.use_instrument_div_mult_estimates=True` 来访问它。

##### 估计工具权重

参见[优化](#optimisation)获取更多信息。

##### 使用估计的预测多样化乘数

参见[估计多样化乘数](#estimating-correlations-and-diversification-multipliers)。

#### 缓冲和仓位惯性

仓位惯性，或缓冲，是一种减少交易成本的方法。其思想是，通过在当前仓位周围应用"不交易"缓冲区，如果我们的最优仓位只是略有变化，我们就避免交易。我的书第 11 章对这个主题有更多介绍。

我使用两种方法。*仓位*缓冲与我的书中使用的仓位惯性方法相同。我们将当前仓位与最优仓位进行比较。如果它不在 10%（"缓冲区"）之内，那么我们交易到最优仓位，否则我们不会费心。

这个配置将实现我的书中的仓位惯性。

YAML：
```yaml
buffer_trade_to_edge: False
buffer_method: position
buffer_size: 0.10
```

第二种方法是*预测*缓冲。在这里，我们取平均绝对仓位（我们用预测 10 得到的）的一部分，并用它来确定缓冲区宽度。这在理论上更正确；因为当我们接近零时缓冲区不会缩小。其次，如果超出缓冲区，我们交易到缓冲区的最近边缘，而不是去最优仓位。这进一步降低了交易成本。以下是我推荐的预测缓冲设置：

YAML：
```yaml
buffer_trade_to_edge: True
buffer_method: forecast
buffer_size: 0.10
```

注意，缓冲可以在舍入和未舍入的仓位上工作。对于舍入的仓位，我们舍入缓冲区的下限和上限。

这些 Python 方法允许你看到缓冲的运行情况。

```python
system.portfolio.get_notional_position("US10") ## 获取缓冲前的仓位
system.portfolio.get_buffers_for_position("US10") ## 获取缓冲区的上下边缘
system.accounts.get_buffered_position("US10", roundpositions=True) ## 获取缓冲后的仓位
```

注意，在实时交易系统中，缓冲是在系统模块的下游完成的，在一个也可以看到我们实际持有的当前仓位的过程中[策略订单生成](/docs/production.md)。

最后，如果你将 buffer_method 设置为 none，则不会有缓冲。

#### 资本修正

如果你想看到反映变化资本的仓位，那么请阅读[资本修正](#capital-correction---varying-capital)部分。

### 阶段：账户

最后一个阶段是非常重要的账户阶段，它计算损益。

#### 使用标准的 Account 类

- 代码在这里：[/systems/accounts/accounts_stage.py](/systems/accounts/accounts_stage.py)

标准账户类包括几个有用的方法：

- `portfolio`：计算整个系统的损益（返回 accountCurveGroup）
- `pandl_for_instrument`：特定工具对损益的贡献（返回 accountCurve）
- `pandl_for_subsystem`：计算单个工具的独立表现（返回 accountCurve）
- `pandl_across_subsystems`：将所有子系统的损益组合在一起（与投资组合不同！不使用工具权重）（返回 accountCurveGroup）
- `pandl_for_trading_rule`：一个交易规则在所有工具上的表现（返回 accountCurveGroup）
- `pandl_for_trading_rule_weighted`：一个交易规则在所有工具上作为总资本比例的表现（返回 accountCurveGroup）
- `pandl_for_trading_rule_unweighted`：一个交易规则在所有工具上的未加权表现（返回 accountCurveGroup）
- `pandl_for_all_trading_rules`：所有交易规则在所有工具上的表现（返回嵌套的 accountCurveGroup）
- `pandl_for_all_trading_rules_unweighted`：所有交易规则在所有工具上的未加权表现（返回嵌套的 accountCurveGroup）
- `pandl_for_instrument_rules`：所有交易规则对特定工具的表现（返回 accountCurveGroup）
- `pandl_for_instrument_rules_unweighted`：所有交易规则对一个工具的未加权表现（返回 accountCurveGroup）
- `pandl_for_instrument_forecast`：计算特定交易规则变体对特定工具的表现（返回 accountCurve）
- `pandl_for_instrument_forecast_weighted`：计算特定交易规则变体对特定工具作为总资本比例的表现（返回 accountCurve）

（注意：[缓冲](#buffering-and-position-inertia)的仓位只在最终投资组合阶段使用；预测和子系统的仓位不会被缓冲。所以它们的交易成本可能会略微高估）。

（警告：参见[加权和未加权账户曲线组](#weighted-and-unweighted-account-curve-groups)）

这些类大多共享一些有用的参数（都是布尔值）：

- `delayfill`：假设我们在下一个交易日的收盘价交易。始终默认为 True（更保守）
- `roundpositions`：将仓位舍入到最接近的工具块。对投资组合和工具默认为 True，对子系统默认为 False。在 `pandl_for_instrument_forecast` 或 `pandl_for_trading_rule` 中不使用（始终为 False）

所有损益方法都返回 `accountCurve`（对于工具、子系统和工具预测）或 `accountCurveGroup`（对于投资组合和交易规则）类型的对象，或者甚至是嵌套的 `accountCurveGroup`（`pandl_for_all_trading_rules`，`pandl_for_all_trading_rules_unweighted`）。这继承自 pandas 数据框，所以可以绘图、平均等。它还有一些特殊的方法。要查看它们是什么，使用 `stats` 方法：

```python
from systems.provided.futures_chapter15.basesystem import futures_system
system=futures_system()
system.accounts.portfolio().stats()
```

```
[[('min', '-1.997e+05'),
  ('max', '4.083e+04'),
  ('median', '-1.631'),
  ('mean', '156.9'),
  ('std', '5226'),
  ('skew', '-7.054'),
  ('ann_mean', '4.016e+04'),
  ('ann_std', '8.361e+04'),
  ('sharpe', '0.4803'),
  ('sortino', '0.5193'),
  ('avg_drawdown', '-1.017e+05'),
  ('time_in_drawdown', '0.9621'),
  ('calmar', '0.1199'),
  ('avg_return_to_drawdown', '0.395'),
  ('avg_loss', '-3016'),
  ('avg_gain', '3371'),
  ('gaintolossratio', '1.118'),
  ('profitfactor', '1.103'),
  ('hitrate', '0.4968'),
  ('t_stat', '2.852'),
  ('p_value', '0.004349')],
 ('You can also plot / print:',
  ['rolling_ann_std', 'drawdown', 'curve', 'percent'])]
```

`stats` 方法列出三种输出：

1. 也可以用自己的方法提取的统计数据，例如要提取 sortino 使用 `system.accounts.portfolio().sortino()`
2. 可以用来做有趣图表的方法，例如 `system.accounts.portfolio().drawdown()`
3. 可以用来获取不同期间回报的属性，例如 `systems.accounts.portfolio().annual`

#### `accountCurve` 详解

`accountCurve` 和组对象比表面看起来要复杂得多。

让我们从 `accountCurve` 开始，这是你从 `systems.account.pandl_for_subsystem` 等获得的输出

```python
acc_curve=system.accounts.pandl_for_subsystem("EDOLLAR")
```

这*看起来*像一个 pandas 数据框，每天是一个不同的回报。但实际上它比这更有趣。这里面实际上有三个不同的账户曲线；不含成本的*总*损益，*成本*，和包含成本的*净*损益。我们可以这样访问它们：

```python
acc_curve.gross
acc_curve.net
acc_curve.costs
acc_curve.to_ncg_frame() ## 这个方法返回一个包含所有 3 个元素作为列的数据框
```

*净*版本与 acc_curve 相同；这是故意的，以鼓励你查看净回报。每个曲线默认显示每日回报，但我们也可以访问不同的频率（每日、每周、每月、每年）：

```python
acc_curve.gross.daily ## 等同于 acc_curve.gross
acc_curve.net.daily ## 等同于 acc_curve 和 acc_curve.net
acc_curve.net.weekly ## 或者也可以用 acc_curve.weekly
acc_curve.costs.monthly
```

一旦你有了所需的频率，你就可以使用任何统计方法：

```python
acc_curve.gross.daily.stats() ## 获取方法列表。等同于 acc_curve.gross.stats()
acc_curve.annual.sharpe() ## 基于年度的夏普比率
acc_curve.gross.weekly.std() ## 每周回报的标准差
acc_curve.daily.ann_std() ## 每日（净）回报的年化标准差
acc_curve.costs.annual.median() ## 年度成本的中位数
```

... 或其他有趣的方法：

```python
import syscore.pandas.strategy_functions

acc_curve.rolling_ann_std()  ## 每日（净）回报的滚动年度标准差
acc_curve.gross.curve()  ## 累积回报 = 总每日回报的账户曲线
syscore.pandas.strategy_functions.drawdown()  ## 每月净回报的回撤
acc_curve.costs.weekly.curve()  ## 累积每周成本
```

就个人而言，我更喜欢以百分比形式查看统计数据。这很容易。只需在使用任何统计方法之前使用 .percent 属性：

```python
import syscore.pandas.strategy_functions

acc_curve.capital  ## 告诉我用于计算百分比的资本
acc_curve.percent
acc_curve.gross.daily.percent
acc_curve.net.daily.percent
acc_curve.costs.monthly.percent
acc_curve.gross.daily.percent.stats()
acc_curve.monthly.percent.sharpe()
acc_curve.gross.weekly.percent.std()
acc_curve.daily.percent.ann_std()
acc_curve.costs.annual.percent.median()
acc_curve.percent.rolling_ann_std()
acc_curve.gross.percent.curve()
syscore.pandas.strategy_functions.drawdown()
acc_curve.costs.weekly.percent.curve()
```

顺便说一下，你可以以任何顺序"链式"使用百分比、频率和总/净/成本运算符；底层对象实际上没有改变，只是改变了它的表示方式。如果你想反转百分比运算符，你可以使用 .value_terms()。

#### `accountCurveGroup` 详解

`accountCurveGroup` 是你从 `systems.account.portfolio`、`systems.account.pandl_across_subsystems`、`pandl_for_instrument_rules_unweighted`、`pandl_for_trading_rule` 和 `pandl_for_trading_rule_unweighted` 获得的输出。例如：

```python
acc_curve_group=system.accounts.portfolio()
```

同样，这*看起来*像一个 pandas 数据框，或者像一个普通的账户曲线对象。所以例如这些都可以工作：

```python
acc_curve_group.gross.daily.stats() ## 获取方法列表。等同于 acc_curve.gross.stats()
acc_curve_group.annual.sharpe() ## 基于年度的夏普比率
acc_curve_group.gross.weekly.std() ## 每周回报的标准差
acc_curve_group.daily.ann_std() ## 每日（净）回报的年化标准差
acc_curve_group.costs.annual.median() ## 年度成本的中位数
```

这些实际上都是给出整个投资组合的损益（所有资产的单个账户曲线之和）；默认给出净的、每日曲线。要找出我们使用哪些资产，使用 acc_curve_group.asset_columns；要访问特定资产，我们使用 `acc_curve_group['assetName']`。

```python
acc_curve_group.asset_columns
acc_curve_group['US10']
```

*警告：参见[加权和未加权账户曲线组](#weighted-and-unweighted-account-curve-groups)*

第二个命令返回*仅*美国 10 年期国债的账户曲线。所以我们可以做这样的事情：

```python
acc_curve_group['US10'].gross.daily.stats() ## 获取方法列表。等同于 acc_curve.gross.stats()
acc_curve_group['US10'].annual.sharpe() ## 基于年度的夏普比率
acc_curve_group['US10'].gross.weekly.std() ## 每周回报的标准差
acc_curve_group['US10'].daily.ann_std() ## 每日（净）回报的年化标准差
acc_curve_group['US10'].costs.annual.median() ## 年度成本的中位数

acc_curve_group.gross['US10'].weekly.std() ## 注意获取账户曲线的等效方式
```

有时绘制所有单个账户曲线更好，所以我们可以获取一个数据框。

```python
acc_curve_group.to_frame() ## 返回所有资产的净账户曲线的数据框
acc_curve_group.net.to_frame() ## 返回所有资产的净账户曲线的数据框
acc_curve_group.gross.to_frame() ## 返回所有资产的总账户曲线的数据框
acc_curve_group.costs.to_frame() ## 返回所有资产的成本账户曲线的数据框
```

*警告：参见[加权和未加权账户曲线组](#weighted-and-unweighted-account-curve-groups)*

你还可以获取任何统计方法的字典，在所有资产上测量：

```python
acc_curve_group.get_stats("sharpe", "net", "daily") ## 使用每日数据获取所有年化夏普比率
acc_curve_group.get_stats("sharpe", freq="daily") ## 等效
acc_curve_group.get_stats("sharpe", curve_type="net") ## 等效
acc_curve_group.net.get_stats("sharpe", freq="daily") ## 等效
acc_curve_group.net.get_stats("sharpe", percent=False) ## 默认以百分比形式给出统计数据，这会关闭它
```

*警告：参见[加权和未加权账户曲线组](#weighted-and-unweighted-account-curve-groups)*

你可以获取这些的汇总统计数据。这些可以是所有资产的简单平均值，或者按每个资产的数据量加权的时间加权平均值。

```python
acc_curve_group.get_stats("sharpe").mean() ## 获取使用每日数据的净回报年化夏普比率的简单平均值
acc_curve_group.get_stats("sharpe").std(timeweighted=True) ## 获取资产间夏普比率的时间加权标准差
acc_curve_group.get_stats("sharpe").tstat(timeweighted=False) ## 平均夏普比率的 t 统计量
acc_curve_group.get_stats("sharpe").pvalue(timeweighted=True) ## 时间加权平均夏普比率的 t 统计量的 p 值
```

#### 嵌套的 `accountCurveGroup`

嵌套的 `accountCurveGroup` 是你从 `pandl_for_all_trading_rules` 和 `pandl_for_all_trading_rules_unweighted` 获得的输出。例如：

```python
nested_acc_curve_group=system.accounts.pandl_for_all_trading_rules()
```

```

# 流程

本节详细介绍了跨越多个阶段的重要流程：日志记录、估计相关性和分散化乘数、优化和资本修正。

## 文件名

有几种不同的方式可以指定路径和文件名。首先，我们可以使用*相对*路径名。其次，我们可能想要使用*绝对*路径，这是实际的全路径名。如果我们想要访问 pysystemtrade 目录结构之外的东西，这很有用。最后我们有操作系统差异的问题；你是使用 '\\' 还是 '/' 的人？

为了方便，我写了一些函数来在这些不同格式和底层操作系统表示之间转换。

```python
from syscore.fileutils import get_resolved_pathname, resolve_path_and_filename_for_package

# 同时解析文件名和路径名。在写入例如配置文件名称时很有用
## 绝对格式
### Windows（注意在字符串中使用双反斜杠）确保包含初始反斜杠，否则将被视为相对格式
resolve_path_and_filename_for_package("\\home\\rob\\file.csv")

### Unix。确保包含初始正斜杠，
resolve_path_and_filename_for_package("/home/rob/file.csv")

## 相对格式，在已安装的 pysystemtrade 中查找文件
### 点格式。注意没有初始 '点'，我们不需要包含 'pysystemtrade'
resolve_path_and_filename_for_package("syscore.tests.pricedata.csv")

# 分别指定路径和文件名
resolve_path_and_filename_for_package("\\home\\rob", "file.csv")
resolve_path_and_filename_for_package("/home/rob", "file.csv")
resolve_path_and_filename_for_package("syscore.tests", "pricedata.csv")

# 只解析路径名
get_resolved_pathname("/home/rob")
get_resolved_pathname("\\home\\rob")
get_resolved_pathname("syscore.tests")

## 不要使用这些：-
### 可以在相对文件名中使用 Unix 或 Windows 格式，但我更喜欢不这样做，这样绝对和相对之间有更清晰的区别。
### 但这可以工作：
resolve_path_and_filename_for_package("syscore/tests/pricedata.csv")

### 同样，我更喜欢不在绝对文件名中使用点格式，但它也可以工作
resolve_path_and_filename_for_package(".home.rob.file.csv")

### 最后，你可以在单个字符串中混合使用上述格式，但这不会使代码非常易读！
resolve_path_and_filename_for_package("\\home/rob.file.csv")
```

这些函数在传入文件名时在内部使用，所以在指定例如配置文件名时，你可以自由使用这些文件格式中的任何一种。

```
### 绝对：Windows（注意在字符串中使用双反斜杠）
"\\home\\rob\\file.csv"

### 绝对：Unix。
"/home/rob/file.csv"

## 相对：点格式，在已安装的 pysystemtrade 中查找文件
"syscore.tests.pricedata.csv"
```

## 日志记录

### 基本日志记录

pysystemtrade 使用 [Python 日志模块](https://docs.python.org/3.10/library/logging.html)。系统、数据、配置和每个阶段对象都有一个 .log 属性，允许系统向用户报告；用于估计相关性和进行优化的函数也是如此。

默认情况下，日志消息将在 DEBUG 级别打印到控制台（`std.out`）。这是你在 sim 中得到的。这由 `syslogging.logger.py` 中的 `_configure_sim()` 函数配置。

如果你想更改级别或消息格式，那么创建一个指向替代 YAML 日志配置的环境变量。对于 Bash 来说是这样的：

```
PYSYS_LOGGING_CONFIG=/home/path/to/your/logging_config.yaml
```

它可以是项目内的文件，所以会接受相对点路径格式。有一个示例 YAML 文件复制了默认的 sim 配置：

```
PYSYS_LOGGING_CONFIG=syslogging.logging_sim.yaml
```

如果你在编写自己的代码，并想通知用户正在发生的事情，你应该做以下事情之一：

```python
## self 可以是系统、阶段、配置或数据对象
#
self.log.debug("这是 logging.DEBUG 级别的消息")
self.log.info("这是 logging.INFO 级别的消息")
self.log.warning("logging.WARNING 级别")
self.log.error("logging.ERROR 级别")
self.log.critical("logging.CRITICAL 级别")

# 参数化消息
log.info("你好 %s", "世界")
log.info("再见 %s %s", "残酷的", "世界")
```

我强烈鼓励使用日志记录而不是打印，因为在 '无头' 自动化交易服务器上打印将不可见。

### 高级日志记录

根据我的经验，翻阅长日志文件是一个相当耗时的过程。另一方面，使用日志记录方法来监控系统行为通常比尝试创建定量诊断更有用。为此，我是带有*属性*的日志记录的忠实粉丝。这个项目为此使用了 [logging.LoggerAdapter](https://docs.python.org/3.10/library/logging.html#loggeradapter-objects) 的自定义版本：

```python
from syslogging.logger import *

# 在日志记录器初始化时设置属性
log = get_logger("日志记录器名称", {"stage": "first"})

# 在消息创建时设置属性
log.info("日志记录器名称", instrument_code="GOLD")
```

日志记录器用名称初始化；应该是顶层调用函数的名称。生产类型包括价格收集、执行等。每次调用日志方法时，它通常知道以下一个或多个：

- stage：由 System 对象中的阶段使用，如 'rawdata'
- component：顶层函数的其他部分，有自己的日志记录器
- currency_code：货币代码（用于外汇），格式 'GBPUSD'
- instrument_code：不言而喻
- contract_date：不言而喻，格式 'yyyymm'
- broker：经纪商名称
- clientid：IB 唯一标识
- strategy_name：不言而喻
- order_id：不言而喻，用于实盘交易
- instrument_order_id：不言而喻，用于实盘交易
- contract_order_id：不言而喻，用于实盘交易
- broker_order_id：不言而喻，用于实盘交易

你确实需要跟踪你的日志记录器有什么属性。一般来说，你应该使用这种模式来写入日志项：

```python
# 这是来自 ForecastScaleCap 代码
#
# 这个日志已经有 type=base_system，和 stage=forecastScaleCap
#
self.log.debug("计算 %s %s 的缩放预测" % (instrument_code, rule_variation_name),
    instrument_code=instrument_code, rule_variation_name=rule_variation_name
)
```

这保持了原始日志属性完整的优势。如果你想做一些更复杂的事情，值得查看 [`syslogging.get_logger()`](/syslogging/logger.py) 的文档字符串，它显示了使用模式，包括如何合并属性。

## 优化

参见我关于优化的博客文章：
[无成本](https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html)
和[有成本](https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html)。

我使用优化器来计算预测和工具权重。这个过程对两者几乎相同。

### 优化函数和数据

从配置中：
```
forecast_weight_estimate: ## 也可以应用于工具权重
   func: sysquant.optimisation.generic_optimiser.genericOptimiser ## 这是唯一提供的函数
   pool_instruments: True ## 不用于工具权重
   frequency: "W" ## 其他选项：D, M, Y
```

我建议使用每周数据，因为它加快速度且不影响样本外表现。

### 移除昂贵的资产（仅用于预测权重）

再次，我建议你查看这篇[博客文章](https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html)。

```
forecast_weight_estimate:
   ceiling_cost_SR: 0.13 ## 允许资产的最大成本，年度 SR 单位。
    
```

参见 ['costs'](#costs) 了解如何在估计预测成本时配置池化。

默认情况下，这设置为 9999，这实际上意味着所有交易规则都包含在优化阶段。但是可以使用 `post_ceiling_cost_SR` 来移除太贵的规则。如果你正在池化总回报，这是推荐的。

### 池化总回报（仅用于预测权重）

跨工具的池化仅在计算预测权重时可用。再次，我建议你查看这篇[博客文章](https://qoppac.blogspot.com/2016/05/optimising-weights-with-costs.html)。只有规则通过了成本上限（`ceiling_cost_SR`）的工具才会包含在池化过程中。如果你想池化所有工具，不管成本如何，那么你应该将 `ceiling_cost_SR` 设置为某个高数字，并使用 `post_ceiling_cost_SR` 在优化完成后消除昂贵的规则（这是默认的）。

```
forecast_weight_estimate:
   pool_gross_returns: True ## 池化总回报用于估计
forecast_cost_estimate:
   use_pooled_costs: False  ### 使用具有相同交易规则集的工具间 [SR 成本 * 周转率] 的加权平均值
```

// ... existing code ...

### 预测映射阶段

预测映射是一个新功能，允许我们以非线性的方式映射预测。这对于处理预测的极端值特别有用。

#### 预测映射参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于在滚动样本外基础上估计预测映射参数的方法。任何缺失的配置元素都从项目默认值中提取。必需的参数是 pool_instruments（确定我们是否在多个工具上池化估计）和 func（用于估计的字符串函数指针）。其余参数传递给估计函数。

参见[预测映射估计](#calculating-estimated-forecast-mapping-on-the-fly)了解更多细节。

如果你考虑使用自己的函数，请参见[配置自己的函数的默认值](#handling-defaults-when-you-change-certain-functions)

YAML：
```
# 这是我们进行估计的方式。这些也是*默认值*。
use_forecast_mapping_estimates: True
forecast_mapping_estimate:
   pool_instruments: True
   func: "sysquant.estimators.forecast_mapping.forecast_mapping"
   window: 250000
   min_periods: 500
   backfill: True
   a_param: 0.5
   b_param: 0.5
   threshold: 0.5
```

Python（示例）
```python
## 池化示例
config.forecast_mapping_estimate=dict(pool_instruments=True, func="sysquant.estimators.forecast_mapping.forecast_mapping", window=250000, min_periods=500, backfill=True, a_param=0.5, b_param=0.5, threshold=0.5)
```

### 位置缩放阶段

位置缩放阶段负责根据波动率目标调整位置大小。这包括：

1. 计算每个工具的波动率
2. 根据波动率目标调整位置大小
3. 应用位置限制

#### 波动率计算参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于计算波动率的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 days（用于计算波动率的天数）和 min_periods（最小周期数）。其余参数传递给波动率计算函数。

YAML：
```
volatility_calculation:
   days: 250
   min_periods: 100
   vol_floor: 0.1
```

Python（示例）
```python
config.volatility_calculation=dict(days=250, min_periods=100, vol_floor=0.1)
```

#### 位置限制参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于限制位置大小的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 max_position（最大位置大小）和 min_position（最小位置大小）。其余参数传递给位置限制函数。

YAML：
```
position_limits:
   max_position: 1.0
   min_position: -1.0
```

Python（示例）
```python
config.position_limits=dict(max_position=1.0, min_position=-1.0)
```

// ... existing code ...

### 投资组合阶段

投资组合阶段负责创建和管理投资组合。这包括：

1. 计算每个工具的投资组合权重
2. 应用多样化乘数
3. 计算最终的投资组合位置

#### 投资组合权重参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于计算投资组合权重的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 pool_instruments（确定我们是否在多个工具上池化估计）和 func（用于估计的字符串函数指针）。其余参数传递给权重计算函数。

YAML：
```
# 这是我们进行估计的方式。这些也是*默认值*。
use_portfolio_weight_estimates: True
portfolio_weight_estimate:
   pool_instruments: True
   func: "sysquant.estimators.portfolio_weight_estimator.portfolio_weight_estimator"
   window: 250000
   min_periods: 500
   backfill: True
```

Python（示例）
```python
## 池化示例
config.portfolio_weight_estimate=dict(pool_instruments=True, func="sysquant.estimators.portfolio_weight_estimator.portfolio_weight_estimator", window=250000, min_periods=500, backfill=True)
```

#### 投资组合多样化乘数参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于计算投资组合多样化乘数的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 pool_instruments（确定我们是否在多个工具上池化估计）和 func（用于估计的字符串函数指针）。其余参数传递给乘数计算函数。

YAML：
```
# 这是我们进行估计的方式。这些也是*默认值*。
use_portfolio_div_multiplier_estimates: True
portfolio_div_multiplier_estimate:
   pool_instruments: True
   func: "sysquant.estimators.diversification_multipliers.diversification_multiplier"
   window: 250000
   min_periods: 500
   backfill: True
```

Python（示例）
```python
## 池化示例
config.portfolio_div_multiplier_estimate=dict(pool_instruments=True, func="sysquant.estimators.diversification_multipliers.diversification_multiplier", window=250000, min_periods=500, backfill=True)
```

### 会计阶段

会计阶段负责计算和跟踪交易系统的盈亏。这包括：

1. 计算每个工具的盈亏
2. 计算交易成本
3. 计算投资组合的总体盈亏

#### 交易成本参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于计算交易成本的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 cost_per_trade（每笔交易的成本）和 cost_per_contract（每份合约的成本）。其余参数传递给成本计算函数。

YAML：
```
trading_costs:
   cost_per_trade: 0.001
   cost_per_contract: 0.0001
```

Python（示例）
```python
config.trading_costs=dict(cost_per_trade=0.001, cost_per_contract=0.0001)
```

#### 会计方法参数
表示为：字符串、浮点数和整数的字典。关键词：参数名称。默认值：见下文

用于选择会计方法的参数。任何缺失的配置元素都从项目默认值中提取。必需的参数是 method（会计方法）和 delayfill（是否延迟填充）。其余参数传递给会计方法。

YAML：
```
accounting_method:
   method: "standard"
   delayfill: True
```

Python（示例）
```python
config.accounting_method=dict(method="standard", delayfill=True)
```

// ... existing code ...

### 账户曲线和账户曲线组

账户曲线和账户曲线组是用于分析交易系统性能的重要工具。它们提供了关于系统在不同时间尺度上的表现的信息。

#### 账户曲线
账户曲线是一个包含三个不同账户曲线的对象：
1. 毛利润（gross p&l）
2. 成本（costs）
3. 净利润（net p&l）

你可以通过以下方式访问这些曲线：

```python
# 获取毛利润曲线
gross_pnl = system.accounts.gross()

# 获取成本曲线
costs = system.accounts.costs()

# 获取净利润曲线
net_pnl = system.accounts.net()
```

每个曲线都包含以下频率的收益：
- 日收益（daily）
- 周收益（weekly）
- 月收益（monthly）
- 年收益（annual）

你可以使用以下方法获取这些收益：

```python
# 获取日收益
daily_returns = system.accounts.daily()

# 获取周收益
weekly_returns = system.accounts.weekly()

# 获取月收益
monthly_returns = system.accounts.monthly()

# 获取年收益
annual_returns = system.accounts.annual()
```

#### 账户曲线组
账户曲线组是一个包含多个资产账户曲线的对象。它提供了以下功能：

1. 访问单个资产的性能指标：
```python
# 获取特定资产的账户曲线
asset_curve = system.accounts.curve_for_asset("EDOLLAR")

# 获取特定资产的统计信息
asset_stats = system.accounts.stats_for_asset("EDOLLAR")
```

2. 获取所有资产的统计信息：
```python
# 获取所有资产的统计信息
all_stats = system.accounts.stats()

# 获取所有资产的简单平均值
mean_stats = system.accounts.mean()

# 获取所有资产的标准差
std_stats = system.accounts.std()

# 获取所有资产的 t 统计量
t_stats = system.accounts.t_stat()

# 获取所有资产的 p 值
p_values = system.accounts.p_value()
```

3. 获取特定交易规则的统计信息：
```python
# 获取特定交易规则的统计信息
rule_stats = system.accounts.stats_for_rule("ewmac2_8")

# 获取特定交易规则的简单平均值
rule_mean = system.accounts.mean_for_rule("ewmac2_8")

# 获取特定交易规则的标准差
rule_std = system.accounts.std_for_rule("ewmac2_8")

# 获取特定交易规则的 t 统计量
rule_t_stat = system.accounts.t_stat_for_rule("ewmac2_8")

# 获取特定交易规则的 p 值
rule_p_value = system.accounts.p_value_for_rule("ewmac2_8")
```

4. 获取特定资产的特定交易规则的统计信息：
```python
# 获取特定资产的特定交易规则的统计信息
asset_rule_stats = system.accounts.stats_for_asset_rule("EDOLLAR", "ewmac2_8")

# 获取特定资产的特定交易规则的简单平均值
asset_rule_mean = system.accounts.mean_for_asset_rule("EDOLLAR", "ewmac2_8")

# 获取特定资产的特定交易规则的标准差
asset_rule_std = system.accounts.std_for_asset_rule("EDOLLAR", "ewmac2_8")

# 获取特定资产的特定交易规则的 t 统计量
asset_rule_t_stat = system.accounts.t_stat_for_asset_rule("EDOLLAR", "ewmac2_8")

# 获取特定资产的特定交易规则的 p 值
asset_rule_p_value = system.accounts.p_value_for_asset_rule("EDOLLAR", "ewmac2_8")
```

所有方法都共享以下布尔参数：
- delayfill：是否延迟填充
- roundpositions：是否对位置进行四舍五入

// ... existing code ...

### 加权和未加权账户曲线组

在系统中，我们有两种类型的账户曲线组：加权和未加权。

#### 加权账户曲线组
加权账户曲线组考虑了每个工具或交易规则在总风险资本中的比例。这些曲线可以通过以下方法访问：

```python
# 获取投资组合级别的曲线
portfolio_curve = system.accounts.portfolio()

# 获取特定工具的曲线
instrument_curve = system.accounts.pandl_for_instrument("EDOLLAR")

# 获取特定工具的预测加权曲线
forecast_weighted_curve = system.accounts.pandl_for_instrument_forecast_weighted("EDOLLAR")

# 获取特定工具的子系统曲线
subsystem_curve = system.accounts.pandl_for_subsystem("EDOLLAR")
```

#### 未加权账户曲线组
未加权账户曲线组显示每个工具或交易规则的独立表现，不考虑其在投资组合中的权重。这些曲线可以通过以下方法访问：

```python
# 获取跨子系统的曲线
across_subsystems_curve = system.accounts.pandl_across_subsystems()

# 获取特定工具的未加权曲线
instrument_unweighted_curve = system.accounts.pandl_for_instrument_unweighted("EDOLLAR")

# 获取特定交易规则的未加权曲线
rule_unweighted_curve = system.accounts.pandl_for_trading_rule_unweighted("ewmac2_8")

# 获取所有交易规则的未加权曲线
all_rules_unweighted_curve = system.accounts.pandl_for_all_trading_rules_unweighted()
```

#### 注意事项
1. 单个加权曲线可能显示较低的收益和较高的波动性，因为它们考虑了风险贡献。
2. 未加权曲线对于评估单个工具或交易规则的表现很有用，但可能无法提供有意义的投资组合级别总结。
3. 应谨慎解释单个账户曲线，而整体投资组合曲线更可靠。
4. 建议使用 t 检验来测试账户曲线的统计显著性。

#### 成本计算
成本计算可以包括：
1. 固定拖累（constant drag）
2. 实际交易成本（actual trade costs）

你可以通过以下方式配置成本计算：

YAML：
```
use_SR_costs: True
SR_cost: 0.13
```

Python：
```python
config.use_SR_costs = True
config.SR_cost = 0.13
```

// ... existing code ...

### 日志记录和文件命名

#### 文件命名
系统支持多种指定文件路径的方式：

1. 相对路径：
```python
# 相对于工作目录
data = csvFuturesSimData("data/futures")

# 相对于项目根目录
data = csvFuturesSimData("~/pysystemtrade/data/futures")
```

2. 绝对路径：
```python
# 完整的文件系统路径
data = csvFuturesSimData("/Users/username/projects/pysystemtrade/data/futures")
```

你可以使用 `syscore.fileutils` 中的函数来解析文件名：

```python
from syscore.fileutils import resolve_path, get_filename_for_package
from syscore.fileutils import get_resolved_pathname

# 解析相对路径
resolved_path = resolve_path("data/futures")

# 获取包的文件名
package_file = get_filename_for_package("systems.provided.futures_chapter15.futuresconfig.yaml")

# 获取解析后的路径名
resolved_pathname = get_resolved_pathname("data/futures/EDOLLAR.csv")
```

#### 日志记录
系统使用 Python 的 logging 模块进行日志记录。你可以通过环境变量配置日志级别和格式：

```python
import os
import logging

# 设置日志级别
os.environ["LOG_LEVEL"] = "DEBUG"

# 设置日志格式
os.environ["LOG_FORMAT"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

日志级别包括：
- DEBUG：详细的调试信息
- INFO：一般信息
- WARNING：警告信息
- ERROR：错误信息
- CRITICAL：严重错误信息

建议使用日志而不是打印语句，因为日志提供了更好的可追踪性和可配置性。

示例：
```python
# 创建日志记录器
logger = logging.getLogger("my_system")

# 记录不同级别的消息
logger.debug("这是一条调试消息")
logger.info("这是一条信息消息")
logger.warning("logging.WARNING 级别")
logger.error("logging.ERROR 级别")
logger.critical("logging.CRITICAL 级别")

# 使用参数化消息
instrument_code = "EDOLLAR"
position = 100
logger.info("工具 %s 的位置是 %d", instrument_code, position)
```

你也可以使用带有属性的自定义日志适配器：

```python
from systems.system_logging import LoggerAdapter

# 创建带有属性的日志适配器
logger = LoggerAdapter(logging.getLogger("my_system"), {"stage": "portfolio"})

# 记录带有属性的消息
logger.info("计算投资组合权重")  # 将包含 stage="portfolio" 属性
```

// ... existing code ...

### 优化过程

优化是系统中的一个重要过程，用于计算预测权重、工具权重和多样化乘数。本节将详细介绍优化过程的各个方面。

#### 计算预测权重和工具权重

预测权重和工具权重的计算通常使用周数据进行，以提高效率。这个过程包括以下步骤：

1. 数据准备：
```yaml
# 配置使用周数据
frequency: "W"   # 可选值：D（日）、W（周）、M（月）

# 配置日期方法
date_method: "expanding"  # 可选值：expanding、in_sample、rolling
```

2. 移除昂贵的资产：
```yaml
# 配置成本上限
forecast_weight_estimate:
   ceiling_cost_SR: 0.13  # 高于此夏普比率成本的资产将被移除
```

3. 预测权重的粗收益池化：
```yaml
# 配置是否池化粗收益
forecast_weight_estimate:
   pool_gross_returns: True
```

4. 工具权重的相关性池化：
```yaml
# 配置是否池化相关性
instrument_weight_estimate:
   pool_instruments: True
```

#### 估计相关性和多样化乘数

相关性和多样化乘数的估计过程包括：

1. 配置相关性估计：
```yaml
# 使用指数移动平均估计相关性
correlation_estimate:
   func: "syscore.correlations.estimate_correlation_single_period"
   using_exponent: True
   ew_lookback: 250
   min_periods: 20
   floor_at_zero: True
```

2. 配置多样化乘数估计：
```yaml
# 预测多样化乘数估计
forecast_div_multiplier_estimate:
   func: "syscore.divmultipliers.diversification_multiplier_from_list"
   ewma_span: 125
   floor_at_zero: True
   
# 投资组合多样化乘数估计
portfolio_div_multiplier_estimate:
   func: "syscore.divmultipliers.diversification_multiplier_from_list"
   ewma_span: 125
   floor_at_zero: True
```

#### 资本修正

资本修正过程用于根据盈亏调整风险资本。有三种主要方法：

1. 固定资本：
```yaml
capital_multiplier:
   func: "syscore.capital.fixed_capital"
```

2. 完全复利：
```yaml
capital_multiplier:
   func: "syscore.capital.full_compounding"
```

3. 半复利：
```yaml
capital_multiplier:
   func: "syscore.capital.half_compounding"
```

你可以通过以下方式获取资本乘数：
```python
# 获取当前资本乘数
multiplier = system.accounts.capital_multiplier()
```

#### 优化注意事项

1. 数据清洗：
- 在优化之前确保数据已经被适当清洗
- 处理缺失值和异常值
- 考虑数据的时间范围和频率

2. 参数选择：
- 选择适当的回看期间
- 考虑最小周期数要求
- 权衡样本大小和统计显著性

3. 稳健性检查：
- 使用不同的样本期间验证结果
- 考虑参数的敏感性
- 评估结果的统计显著性

4. 实施考虑：
- 考虑交易成本的影响
- 评估流动性限制
- 考虑实际执行的可行性

// ... existing code ...
```

### 系统对象和数据对象

系统对象和数据对象是系统的核心组件，提供了访问和管理交易系统各个方面的接口。

#### 系统对象
系统对象是整个交易系统的核心，它包含了所有的交易逻辑和数据处理功能。以下是主要的系统对象方法：

##### 获取工具列表
```python
# 获取系统中的所有工具
instruments = system.get_instrument_list()

# 获取特定市场的工具
market_instruments = system.get_instrument_list_for_market("EDOLLAR")
```

##### 获取原始数据
```python
# 获取每日价格
daily_prices = system.rawdata.get_daily_prices("EDOLLAR")

# 获取每日收益
daily_returns = system.rawdata.daily_returns("EDOLLAR")

# 获取波动率
volatility = system.rawdata.daily_returns_volatility("EDOLLAR")
```

##### 获取交易规则
```python
# 获取所有交易规则
rules = system.rules.trading_rules()

# 获取特定交易规则的原始预测
raw_forecast = system.rules.get_raw_forecast("EDOLLAR", "ewmac2_8")
```

##### 获取预测
```python
# 获取缩放后的预测
scaled_forecast = system.forecastScaleCap.get_scaled_forecast("EDOLLAR", "ewmac2_8")

# 获取组合预测
combined_forecast = system.combForecast.get_combined_forecast("EDOLLAR")
```

#### 数据对象
数据对象负责管理和提供系统所需的所有数据。以下是主要的数据对象方法：

##### 获取价格数据
```python
# 获取原始价格
raw_price = data.get_raw_price("EDOLLAR")

# 获取每日价格
daily_price = data.daily_prices("EDOLLAR")

# 获取每周价格
weekly_price = data.weekly_prices("EDOLLAR")
```

##### 获取其他数据
```python
# 获取汇率
fx_rate = data.get_fx_rate("EDOLLAR")

# 获取利率
interest_rate = data.get_interest_rate("EDOLLAR")

# 获取持仓限制
position_limit = data.get_position_limit("EDOLLAR")
```

##### 获取回测数据
```python
# 获取回测开始日期
start_date = data.get_start_date()

# 获取回测结束日期
end_date = data.get_end_date()

# 获取回测日期范围
date_range = data.get_date_range()
```

#### 注意事项

1. 数据访问：
- 使用适当的缓存机制避免重复计算
- 注意数据的时间对齐
- 处理缺失数据的情况

2. 性能考虑：
- 优化数据访问模式
- 使用适当的数据结构
- 考虑内存使用

3. 数据质量：
- 验证数据的完整性
- 检查数据的一致性
- 处理异常值

4. 系统配置：
- 确保系统参数正确设置
- 验证系统组件的连接
- 监控系统性能
```

### 原始数据阶段

原始数据阶段负责处理和准备系统所需的基础数据。这个阶段包括数据的清洗、转换和初步计算。

#### 标准 RawData 类
标准的 RawData 类提供了以下主要功能：

##### 价格数据处理
```python
# 获取每日价格
daily_prices = system.rawdata.get_daily_prices("EDOLLAR")

# 获取每日收益
daily_returns = system.rawdata.daily_returns("EDOLLAR")

# 获取价格变化
price_change = system.rawdata.daily_denominator_price("EDOLLAR")
```

##### 波动率计算
波动率计算是原始数据阶段的一个重要部分。你可以通过以下方式配置波动率计算：

```yaml
volatility_calculation:
   days: 35
   min_periods: 10
   vol_floor: 0.0
```

主要参数说明：
- days：用于计算波动率的天数
- min_periods：计算所需的最小周期数
- vol_floor：波动率的最小值

你可以使用以下方法获取波动率数据：
```python
# 获取每日收益波动率
vol = system.rawdata.daily_returns_volatility("EDOLLAR")

# 获取价格波动率
price_vol = system.rawdata.get_price_volatility("EDOLLAR")
```

##### 滚动收益计算
```python
# 获取年化滚动收益
annual_roll = system.rawdata.daily_annualised_roll("EDOLLAR")

# 获取每日滚动收益
daily_roll = system.rawdata.daily_roll("EDOLLAR")
```

#### 创建新的 RawData 类
你可以通过继承标准 RawData 类来创建自己的原始数据处理类：

```python
from systems.rawdata import RawData

class MyRawData(RawData):
    def __init__(self):
        super().__init__()
        
    def my_custom_calculation(self, instrument_code):
        # 获取基础数据
        price = self.get_daily_prices(instrument_code)
        
        # 进行自定义计算
        result = self.custom_calc(price)
        
        return result
        
    def custom_calc(self, price):
        # 实现你的自定义计算逻辑
        return price.some_calculation()
```

#### 注意事项

1. 数据质量控制：
- 检查数据的完整性
- 处理缺失值
- 识别和处理异常值

2. 性能优化：
- 使用适当的缓存机制
- 优化计算密集型操作
- 考虑内存使用效率

3. 数据一致性：
- 确保时间序列对齐
- 处理不同时区的数据
- 维护数据的一致性

4. 可扩展性：
- 设计模块化的数据处理流程
- 允许灵活的数据源配置
- 支持新数据类型的添加

// ... existing code ...
```

### 交易规则阶段

交易规则阶段负责定义和管理系统中的交易规则。这个阶段包括规则的创建、配置和执行。

#### 交易规则定义
交易规则可以通过多种方式定义：

1. 使用函数：
```python
def ewmac_forecast(price, fast_span=32, slow_span=128):
    # 计算快速和慢速移动平均线
    fast_ma = price.ewm(span=fast_span).mean()
    slow_ma = price.ewm(span=slow_span).mean()
    
    # 计算差值并标准化
    forecast = (fast_ma - slow_ma) / price.std()
    
    return forecast
```

2. 使用配置：
```yaml
trading_rules:
  ewmac2_8:
     function: systems.futures.rules.ewmac
     data:
         - "rawdata.daily_prices"
         - "rawdata.daily_returns_volatility"
     other_args:
         Lfast: 2
         Lslow: 8
     forecast_scalar: 10.6
```

3. 使用 TradingRule 类：
```python
from systems.trading_rules import TradingRule

# 方法1：直接传递函数
rule1 = TradingRule(ewmac_forecast)

# 方法2：使用字典定义
rule2 = TradingRule(dict(
    function=ewmac_forecast,
    data=['rawdata.daily_prices'],
    other_args=dict(fast_span=32, slow_span=128)
))
```

#### 规则变体创建
你可以创建同一规则的多个变体：

```python
from systems.trading_rules import create_variations_oneparameter

# 创建基础规则
base_rule = TradingRule(ewmac_forecast)

# 创建不同参数的变体
variations = create_variations_oneparameter(
    base_rule,
    [4, 10, 20, 40],
    "fast_span"
)
```

#### 规则组合
你可以将多个规则组合在一起：

```python
# 创建规则字典
trading_rules = {
    'ewmac2_8': rule1,
    'ewmac4_16': rule2,
    'ewmac8_32': rule3
}

# 在系统中使用规则
from systems.forecasting import Rules

rules = Rules(trading_rules)
system = System([rules, ...], data, config)
```

#### 规则执行
规则的执行通过以下方法实现：

```python
# 获取原始预测
raw_forecast = system.rules.get_raw_forecast("EDOLLAR", "ewmac2_8")

# 获取所有规则的预测
all_forecasts = system.rules.get_all_forecasts()

# 获取规则列表
rule_list = system.rules.trading_rules()
```

#### 注意事项

1. 规则设计：
- 确保规则逻辑清晰
- 考虑规则的可扩展性
- 注意规则的计算效率

2. 参数选择：
- 选择合适的参数范围
- 考虑参数的稳定性
- 避免过度优化

3. 规则组合：
- 考虑规则间的相关性
- 平衡规则的复杂度
- 注意规则的互补性

4. 性能监控：
- 跟踪规则的表现
- 评估规则的稳定性
- 监控规则的计算成本

// ... existing code ...
```

### 创建投资组合阶段

投资组合阶段负责将各个工具的头寸组合成一个完整的投资组合。这个阶段包括权重分配、多样化乘数应用和最终头寸计算。

#### 固定权重和多样化乘数
你可以通过以下方式设置固定的投资组合权重和多样化乘数：

1. 设置工具权重：
```yaml
instrument_weights:
   EDOLLAR: 0.5
   US10: 0.5
```

2. 设置多样化乘数：
```yaml
instrument_div_multiplier: 1.5
```

#### 估计权重和多样化乘数
你也可以使用系统自动估计权重和多样化乘数：

```yaml
use_instrument_weight_estimates: True
instrument_weight_estimate:
   func: "sysquant.estimators.instrument_weight_estimator.instrument_weight_estimator"
   window: 250000
   min_periods: 500
   backfill: True
   
use_instrument_div_mult_estimates: True
instrument_div_multiplier_estimate:
   func: "sysquant.estimators.diversification_multipliers.diversification_multiplier"
   window: 250000
   min_periods: 500
   backfill: True
```

#### 投资组合构建
投资组合构建过程包括：

1. 获取子系统头寸：
```python
# 获取子系统头寸
subsys_pos = system.portfolio.get_subsystem_position("EDOLLAR")
```

2. 计算投资组合权重：
```python
# 获取工具权重
weight = system.portfolio.get_instrument_weights("EDOLLAR")

# 获取多样化乘数
div_mult = system.portfolio.get_instrument_diversification_multiplier()
```

3. 计算最终头寸：
```python
# 获取投资组合头寸
port_pos = system.portfolio.get_notional_position("EDOLLAR")
```

#### 头寸缓冲
为了减少交易成本，可以使用头寸缓冲：

```yaml
buffer_positions:
   enabled: True
   buffer_method: "position"  # 或 "forecast"
   buffer_size: 0.10
   
position_inertia:
   enabled: True
   inertia_size: 0.1
```

#### 注意事项

1. 投资组合构建：
- 考虑资产间相关性
- 平衡风险分配
- 维护多样化效果

2. 权重管理：
- 定期重新平衡
- 控制交易成本
- 考虑流动性约束

3. 风险控制：
- 监控投资组合风险
- 调整多样化乘数
- 维护风险目标

4. 执行效率：
- 优化交易执行
- 减少市场冲击
- 控制交易成本

// ... existing code ...
```

### 预测权重和多样化乘数

#### 预测权重变化
你可以通过以下方式设置预测权重的变化：

1. 所有工具使用相同的规则变化：
```yaml
rule_variations:
     - "ewmac"
     - "carry"
```

```python
config.rule_variations=["ewmac", "carry"]
```

2. 为不同工具设置不同的规则变化：
```yaml
rule_variations:
     SP500:
      - "ewmac"
      - "carry"
     US10:
      - "ewmac"
```

```python
config.forecast_weights=dict(SP500=["ewmac","carry"], US10=["ewmac"])
```

#### 预测多样化乘数（固定）
可以设置为：
(a) 所有工具使用相同的值
(b) 为每个工具设置不同的值

默认值：1.0

1. 所有工具使用相同的值：
```yaml
forecast_div_multiplier: 1.0
```

```python
config.forecast_div_multiplier=1.0
```

2. 为每个工具设置不同的值：
```yaml
forecast_div_multiplier:
     SP500: 1.4
     US10:  1.1
```

```python
config.forecast_div_multiplier=dict(SP500=1.4, US10=1.0)
```

#### 预测映射配置
通过字典形式表示，可以为每个工具设置不同的映射参数：
- a_param：默认值 1.0
- b_param：默认值 1.0
- threshold：默认值 0.0

```yaml
forecast_mapping:
  AUD:
    a_param: 1.0
    b_param: 1.0
    threshold: 0.0
```

Python示例（如何修改特定参数）：
```python
config.forecast_mapping = dict()
config.forecast_maping['AUD'] = dict(a_param=1.0, b_param=1.0, threshold = 0.0)
config.forecast_maping['AUD']['a_param'] = 1.0
```

#### 资金规模参数
以下参数用于控制资金规模：

```yaml
percentage_vol_target: 16.0        # 年化波动率目标（百分比）
notional_trading_capital: 1000000  # 名义交易资金
base_currency: "USD"               # 基础货币
```

```python
config.percentage_vol_target=16.0
config.notional_trading_capital=1000000
config.base_currency="USD"
```

#### 投资组合权重估计
可以在固定权重和估计权重之间切换：

```yaml
use_instrument_weight_estimates: True
```

```python
config.use_instrument_weight_estimates=True
```

调整权重平滑参数：
```yaml
instrument_weight_ewma_span: 125
```

// ... existing code ...
```

#### 资金管理函数
系统提供了几种不同的资金管理函数：

1. 固定资金（默认）：
```yaml
capital_multiplier:
   func: syscore.capital.fixed_capital
```

2. 其他可用的资金管理函数包括：
- `full_compounding`：完全复利
- `half_compounding`：半复利

这些函数决定了如何根据交易盈亏调整可用资金。选择合适的资金管理方法对于风险控制和收益最大化至关重要。

#### 总结

本文档详细介绍了系统的各个关键组成部分：
1. 交易规则的定义和实现
2. 预测的缩放和上限设置
3. 头寸规模的确定
4. 投资组合的构建
5. 资金管理的方法

通过合理配置这些组件，可以构建一个完整的交易系统。在实际应用中，需要根据具体情况调整各个参数，并持续监控系统表现，及时进行必要的调整。

// ... existing code ...
```

</rewritten_file>