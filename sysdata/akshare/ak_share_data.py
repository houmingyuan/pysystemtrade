import pandas as pd
import datetime

import akshare as ak

from syscore.exceptions import missingData
from syscore.objects import get_methods
from syscore.dateutils import ARBITRARY_START
from syscore.pandas.frequency import (
    get_intraday_pdf_at_frequency,
    resample_prices_to_business_day_index,
)
from sysdata.base_data import baseData  
from syslogging.logger import *
from sysobjects.spot_fx_prices import fxPrices
from sysobjects.instruments import instrumentCosts
from sysdata.sim.sim_data import simData

class akshareData(simData):
    """
    Core data object - Base class for akshare data
    """
    def __repr__(self):
        return "akshareData object with %d instruments" % len(self.get_instrument_list())
    
    def all_asset_classes(self) -> list:
        asset_class_data = self.get_instrument_asset_classes()
        return asset_class_data.all_asset_classes()
    
    def all_instruments_in_asset_class(self, asset_class: str) -> list:
        """
        Return all the instruments in a given asset class

        :param asset_class: str
        :return: list of instrument codes
        """
        asset_class_data = self.get_instrument_asset_classes()
        list_of_instrument_codes = self.get_instrument_list()
        asset_class_instrument_list = asset_class_data.all_instruments_in_asset_class(
            asset_class, must_be_in=list_of_instrument_codes
        )

        return asset_class_instrument_list  
    
    def asset_class_for_instrument(self, instrument_code: str) -> str:
        """
        Which asset class is some instrument in?

        :param instrument_code:
        :return: str
        """ 
        asset_class_data = self.get_instrument_asset_classes()
        asset_class = asset_class_data[instrument_code]

        return asset_class
    
    def length_of_history_in_days_for_instrument(self, instrument_code: str) -> int:
        """
        How many days of history do we have for a given instrument?

        :param instrument_code:
        :return: int
        """
        return len(self.daily_prices(instrument_code))
    
    def get_raw_price_from_start_date(self, instrument_code: str, start_date: datetime.datetime) -> pd.Series:
        """
        """
        price = self.get_backadjusted_futures_price(instrument_code)
        if len(price) == 0:
            raise Exception("Instrument code %s has no data!" % instrument_code)

        return price[start_date:]
    
    def get_instrument_raw_carry_data(self, instrument_code: str) -> pd.DataFrame:  
        """
        """
        all_price_data = self.get_multiple_prices(instrument_code)
        carry_data = all_price_data[
            [price_name, carry_name, price_contract_name, carry_contract_name]
        ]

        return carry_data
    
    def get_current_and_forward_price_data(self, instrument_code: str) -> pd.DataFrame:
        """
        """
        all_price_data = self.get_multiple_prices(instrument_code)

        return all_price_data[
            [price_name, forward_name, price_contract_name, forward_contract_name]
        ]
    
    def get_rolls_per_year(self, instrument_code: str) -> int:
        """
        """
        roll_parameters = self.get_roll_parameters(instrument_code)
        rolls_per_year = roll_parameters.rolls_per_year_in_hold_cycle()

        return rolls_per_year
    
    def get_raw_cost_data(self, instrument_code: str) -> instrumentCosts:
        return instrumentCosts()
    
    def get_value_of_block_price_move(self, instrument_code: str) -> float:
        return 0.0
    
    def get_instrument_currency(self, instrument_code: str) -> str:
        instr_object = self.get_instrument_object_with_meta_data(instrument_code)
        meta_data = instr_object.meta_data
        currency = meta_data.Currency

        return currency
    
    def get_instrument_asset_classes(self) -> assetClassesAndInstruments:
        return assetClassesAndInstruments()
    
    def get_spread_cost(self, instrument_code: str) -> float:
        raise NotImplementedError
    
    def get_backadjusted_futures_price(self, instrument_code: str) -> futuresAdjustedPrices:
        raise NotImplementedError
    
    def get_multiple_prices(self, instrument_code: str) -> futuresMultiplePrices:
        start_date = self.start_date_for_data()

        return self.get_multiple_prices_from_start_date(
            instrument_code, start_date=start_date
        )
    
    def get_multiple_prices_from_start_date(self, instrument_code: str, start_date: datetime.datetime) -> futuresMultiplePrices:
        raise NotImplementedError
    
    def get_instrument_meta_data(self, instrument_code: str) -> futuresInstrumentWithMetaData:
        raise NotImplementedError
    
    def get_roll_parameters(self, instrument_code: str) -> rollParameters:
        raise NotImplementedError
    
    def get_instrument_object_with_meta_data(self, instrument_code: str) -> futuresInstrumentWithMetaData:
        raise NotImplementedError   
    
if __name__ == "__main__":
    import doctest

    doctest.testmod()
    
    
    

 
        
        
