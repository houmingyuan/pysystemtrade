# 前端合约与换月周期遗留问题（FIR-131 拆分）

2026-09-25 修完 FIR-131 的主线（时间戳口径统一 + 按日期对齐重建 + 按成交量订正日历末端）后，
仍有四类问题需要逐品种处理。本文是清单与处理建议，对应 Linear issue「换月周期与前端合约遗留问题」。

## 现状

* 106 个品种中 105 个 multiple prices 有 PRICE（仅 MILK 没有），前端合约与成交量第一一致的从 0 个升到 74 个
* 复跑/回退工具：`sysinit/henrik/repair_front_contracts.py`（`--dry-run`、`--instruments`、
  `--recent-only`、`--allow-missing-front`、`--no-trim`）
* 备份：`/Users/henrik/data/backup/fir131_before_timestamp_fix_20260925`

## A. 前端合约与成交量第一不一致（32 个）

| 品种 | 当前前端 | 近期成交量第一 |
| --- | --- | --- |
| AUD、CAD、CHF、EUR、MXP、NZD、SPI200 | 20270300 | 20261200 |
| CAC、DAX、EUROSTX、FTSE100、FTSE250、RUSSELL_mini、SMI、SP400、TECDAX | 20260900 | 20261200 |
| GOLD、CORRA | 20261000／20261200 | 20261200／20270600 |
| CRUDE_W | 20261200 | 20261100 |
| GAS_UK | 20270300 | 20261100 |
| GAS_US | 20261000 | 20261100 |
| GICS | 20261100 | 20261000 |
| NIKKEI-SGX、NIKKEI-SGX_mini | 20261000 | 20261200 |
| PLAT | 20260700 | 20261000 |
| SILVER | 20260700 | 20261200 |
| FED | 20261000 | 20261100 |
| SOFR | 20290900 | 20261200 |
| SONIA3 | 20260900 | 20271200 |
| VIX | 20260900 | 20261000 |
| WHEAT-ASX | 20270100 | 20270900 |
| MILK | 20260800 | 20261000 |

注：GICS、TECDAX、WHEAT-ASX 等近期成交量只有几十手甚至为 0，成交量判据本身不可靠，需人工确认换月月份。
SOFR／SONIA3／FED 属于换月周期配置（`data/futures/csvconfig/rollconfig.csv` 一类）指向远期合约，
是配置问题而不是数据问题。

## B. 前端合约缺少近期日线（4 个）

| 品种 | 最后有价日 | 说明 |
| --- | --- | --- |
| MILK | 无 PRICE | 日历 2026-08-25 那行指向的合约在价格库里没有数据，重建报 “Missing contracts in middle of roll calendar” |
| PLAT | 2026-07-29 | 前端 20260700 已到期，20261000 只有 08-25 之后的数据 |
| SILVER | 2026-07-29 | 前端 20260700 已到期，20261200 只有小时线 |
| VIX | 2026-09-16 | 前端 20260900 到期，20261000 需要 09-17 之后的换月 |

## C. adjusted prices 末端仍是水平线（11 个）

BARLEY、CAC、DAX、EUROSTX、FED、FTSE100、FTSE250、PLAT、SILVER、SMI、VIX

与 A、B 两组重叠，根因是前端合约没有最新价格，补上前端后应自动恢复。

## D. 与 FIR-127 重叠：停在 2026-09-18 的 21 个品种

AUS10、AUS3、AUS_BILL90、BARLEY、CAC、CORRA、DAX、EURIBOR-ICE、EUROSTX、FTSE100、
FTSE250、GOLD、JPY、NIKKEI-SGX_mini、RUSSELL_mini、SMI、SONIA3、SP400、TECDAX、TSX、WHEAT-ASX

这批是 IB 每日更新因价格尖峰被拒（`max_price_spike` 8 倍）导致没有写入，需要按 FIR-127 的口径
重新取样或人工确认价格。

## 处理建议

1. 先做 B 组与 D 组的数据补齐（IB 采样 + 尖峰白名单），这两组补上后 C 组多半自动消失
2. A 组按品种核对换月周期配置：先看 `rollconfig` 里的合约月份集合是否与真实交易月份一致，
   改完配置后用 `sysinit/futures/rebuild_roll_calendar_from_prices.py` 重建日历，
   再用 `sysinit/henrik/repair_front_contracts.py` 复跑并验收
3. 验收标准与 FIR-131 相同：全品种 PRICE 非 NaN、adjusted 末端不再水平、trading hours 菜单无
   NO TRADING HOURS，另外增加一条「前端合约 = 近期成交量第一（成交量过小的品种人工确认）」
