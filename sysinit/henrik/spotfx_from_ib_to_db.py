"""
从 IB 抓取 spot FX 行情并写入生产存储（Parquet）。

与上游 sysinit/futures/spotfx_from_ib_to_db.py 的差别只有一个：
连接参数从 private_config.yaml 的 config.fx_data 读取，缺失时回退到 config.broker。

这样交易路径继续使用纸面账户（broker.account / broker.port），
而 FX 行情可以走实盘账户（行情订阅与额度挂在实盘账户上）。

用法：
    python sysinit/henrik/spotfx_from_ib_to_db.py
"""

from sysdata.config.private_config import get_private_config_as_dict
from sysdata.data_blob import dataBlob
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysbrokers.IB.ib_Fx_prices_data import ibFxPricesData
from sysbrokers.IB.ib_connection import connectionIB

FX_DATA_CLIENT_ID = 688


def fx_connection_settings() -> dict:
    """
    FX 取数用的连接参数：优先 config.fx_data，回退 config.broker
    """
    config = get_private_config_as_dict()["config"]
    broker = config.get("broker", {})
    fx_data = config.get("fx_data", {})

    return dict(
        account=fx_data.get("account", broker.get("account")),
        host=fx_data.get("host", broker.get("host")),
        port=fx_data.get("port", broker.get("port")),
    )


def update_spot_fx_from_ib():
    settings = fx_connection_settings()
    print(
        "FX 取数连接: host=%s port=%s account=%s"
        % (settings["host"], settings["port"], settings["account"])
    )

    data = dbFuturesSimData()
    db_fx_prices_data = data.db_fx_prices_data

    conn = connectionIB(
        FX_DATA_CLIENT_ID,
        ib_ipaddress=settings["host"],
        ib_port=settings["port"],
        account=settings["account"],
        log_name="update_spot_fx",
    )
    try:
        ib_fx_prices_data = ibFxPricesData(conn, dataBlob(log_name="update_spot_fx"))
        list_of_fx_codes = ib_fx_prices_data.get_list_of_fxcodes()
        print("待更新货币对: %d 个" % len(list_of_fx_codes))

        for fx_code in list_of_fx_codes:
            fx_prices = ib_fx_prices_data.get_fx_prices(fx_code)
            db_fx_prices_data.update_fx_prices(
                code=fx_code, new_fx_prices=fx_prices
            )
            print("已更新 %s，共 %d 行" % (fx_code, len(fx_prices)))
    finally:
        conn.close_connection()


if __name__ == "__main__":
    update_spot_fx_from_ib()
