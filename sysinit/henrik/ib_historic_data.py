from ib_insync import *
# util.startLoop()  # uncomment this line when in a notebook

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)

contract = Future(symbol='HSI202506', includeExpired=True, exchange="HKFE")

# contractDetailList = ib.reqContractDetails(contract)
# print(len(contractDetailList))


bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='1 Y',
    barSizeSetting='1 day', whatToShow='MIDPOINT', useRTH=True)

# convert to pandas dataframe (pandas needs to be installed):
df = util.df(bars)
print(df)

