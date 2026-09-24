"""
非交互地更新全部品种的采样合约（本地新增文件，非上游内容）。

为什么需要这个入口：
    上游 sysproduction/update_sampled_contracts.py 的 __main__ 入口会调用
    get_valid_instrument_code_from_user()，是交互式提问，launchd / cron 下会挂住。
    但 sysproduction/update_historical_prices.py 依赖采样合约表：
    采样表为空时，每个品种都只报 "No contracts marked for sampling"，
    于是整轮 IB 价格更新空转、退出码却是 0。

    这里直接调用上游的非交互路径 updateSampledContracts(data).update_sampled_contracts()，
    默认 ALL_INSTRUMENTS，覆盖 multiple prices 里的全部品种。

采样合约表存在 MongoDB（sampled_contracts），记录每个品种需要向 IB 取数的合约，
并在换月时随 roll calendar 扩充。因此本步骤需要在每日价格更新之前执行。

用法：
    python -m sysproduction.run_daily_contract_sampling
"""

from sysdata.data_blob import dataBlob
from sysproduction.update_sampled_contracts import updateSampledContracts


def run_daily_contract_sampling():
    with dataBlob(log_name="Update-Sampled-Contracts") as data:
        updateSampledContracts(data).update_sampled_contracts()


if __name__ == "__main__":
    run_daily_contract_sampling()
