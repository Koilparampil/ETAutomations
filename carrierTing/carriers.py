"""Carrier pattern definitions and booking-number → carrier lookup."""

import asyncio
import re
import pandas as pd
from pandas import Timestamp
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from MSC.checkETA import checkingMSC

CARRIER_PATTERNS = [
    (r"EBKG\d{8}",        "MSC"),
    (r"2\d{8}",         "Maersk"),
    (r"NAM\d{7}",         "CMA"),
    (r"S3\d{8}",          "Grimaldi"),
]

custBDay = CustomBusinessDay(calendar=USFederalHolidayCalendar())
def add_business_days(date, business_days) ->Timestamp:
    return (date + (business_days * custBDay))

def carrierIDthenETAcheck(booking_num):
    match booking_num:
        case b if re.search(r"EBKG\d{8}", b):
            eta_look_up = asyncio.run(checkingMSC(booking_num))
            if eta_look_up is not None:
                if eta_look_up <= add_business_days(pd.Timestamp.now(),6):
                    return(True,eta_look_up)
                else:
                    return(False,eta_look_up)
            else:
                return(False,None)
        case b if re.fullmatch(r"2\d{8}", b):
            return(False,pd.to_datetime(2))
        case b if re.search(r"NAM\d{7}", b):
            return(False,pd.to_datetime(3))
        case b if re.search(r"S3\d{8}", b):
            return(False,pd.to_datetime(4))
        case _:
            return(False,pd.to_datetime(5))


if __name__ == "__main__":
    test_bookings = ["EBKG17208602", "EBKG11248028"]
    for booking in test_bookings:
        is_msc, eta = carrierIDthenETAcheck(booking)
        print(f"Booking: {booking} | Is MSC? {is_msc} | ETA: {eta}")