from ib_async import *
from sysdata.config.production_config import get_production_config

# util.startLoop()  # uncomment this line when in a notebook

production_config = get_production_config()

ib = IB()
ib.connect(
    production_config.get_element("ib_ipaddress"),
    production_config.get_element("ib_port"),
    clientId=1,
)

contract = Future(symbol='HSI202506', includeExpired=True, exchange="HKFE")

# contractDetailList = ib.reqContractDetails(contract)
# print(len(contractDetailList))


bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='1 Y',
    barSizeSetting='1 day', whatToShow='MIDPOINT', useRTH=True)

# convert to pandas dataframe (pandas needs to be installed):
df = util.df(bars)
print(df)
