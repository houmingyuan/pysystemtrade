from sysdata.data_blob import dataBlob
from sysbrokers.IB.ib_connection import connectionIB
from sysbrokers.IB.ib_Fx_prices_data import ibFxPricesData
from sysdata.sim.db_futures_sim_data import dbFuturesSimData
from sysdata.csv.csv_spot_fx import csvFxPricesData
from sysdata.config.private_config import get_private_config_as_dict

def spotfx_from_csv_to_db():
    csv_fx_prices = csvFxPricesData()
    list_of_ccy_codes = csv_fx_prices.get_list_of_fxcodes()

    db_fx_price_data = data.db_fx_prices_data

    for currency_code in list_of_ccy_codes:
        fx_prices = csv_fx_prices.get_fx_prices(currency_code)
        print(currency_code)
        db_fx_price_data.add_fx_prices(
            code=currency_code, fx_price_data=fx_prices, ignore_duplication=True
        )

if __name__ == "__main__":
    data=dbFuturesSimData()
    db_fx_prices_data = data.db_fx_prices_data
    
    account =get_private_config_as_dict()["config"]["broker"]["account"]

    conn = connectionIB(688, account=account)
    ib_fx_prices_data = ibFxPricesData(conn, dataBlob())
    
    list_of_fx_codes = ib_fx_prices_data.get_list_of_fxcodes()
    
    for fx_code in list_of_fx_codes:
        fx_prices = ib_fx_prices_data.get_fx_prices(fx_code)        
        db_fx_prices_data.update_fx_prices(
            code=fx_code, new_fx_prices=fx_prices
        )        
   
    conn.close_connection()
