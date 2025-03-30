import shutil
import os
import pandas as pd
from sysdata.config.control_config import get_control_config
from sysinit.futures.rollcalendars_from_db_prices_to_csv import build_and_write_roll_calendar

roll_calendars_path = "/Users/henrik/dev/pysystemtrade/data/futures/roll_calendars_csv/new"
dst_roll_calendars_path = "/Users/henrik/dev/pysystemtrade/data/futures/roll_calendars_csv"
def merge_roll_calendars(instrument_code, from_dir, dst_dir):
    from_path = os.path.join(from_dir, instrument_code + ".csv")
    dst_path = os.path.join(dst_dir, instrument_code + ".csv")
    
    if not os.path.exists(dst_path):
        # copy file
        shutil.copy(from_path, dst_path)
    else:   
        # read csv from from_path
        new_df = pd.read_csv(from_path)       
        dst_df = pd.read_csv(dst_path)
        
        # if datetime in new_df is missing HH:MM:SS, add it
        new_df['DATE_TIME'] = new_df['DATE_TIME'].apply(lambda x: x + ' 00:00:00' if len(x) == 10 else x)        
        
        # update record in dst_df with new_df
        dst_df = pd.concat([dst_df, new_df], ignore_index=True)
        dst_df = dst_df.drop_duplicates(subset=['current_contract'], keep='first')
        dst_df = dst_df.sort_values(by=['DATE_TIME'], ascending=True)
        
        
        
        # write to dst_path
        dst_df.to_csv(dst_path, index=False)    

def main():
    control_config = get_control_config()
    barchart_config = control_config.get_element_or_default("barchart", [])

    instrument_list = barchart_config["download_list"]

    for instrument_code in instrument_list:
        build_and_write_roll_calendar(instrument_code, 
                                    output_datapath=roll_calendars_path, 
                                    check_before_writing=False)
        
    for instrument_code in instrument_list:
        print("merge calendars for %s" % instrument_code)
        merge_roll_calendars(instrument_code, 
                             roll_calendars_path, 
                             dst_roll_calendars_path)

if __name__ == "__main__":
    main()

