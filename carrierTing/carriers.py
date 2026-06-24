"""Carrier pattern definitions and booking-number → carrier lookup."""

import re
import pandas as pd
from pandas import Timestamp
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay
from playwright.sync_api import Playwright, sync_playwright

from MSC.checkETA import checkingMSC
from Maersk.checkETA import checkingMaersk

CARRIER_PATTERNS = [
    (r"EBKG\d{8}",        "MSC"),
    (r"2\d{8}",         "Maersk"),
    (r"NAM\d{7}",         "CMA"),
    (r"S3\d{8}",          "Grimaldi"),
]

custBDay = CustomBusinessDay(calendar=USFederalHolidayCalendar())
def add_business_days(date, business_days) ->Timestamp:
    return (date + (business_days * custBDay))

def carrierIDthenETAcheck(booking_num:str, pw:Playwright) -> tuple[bool, pd.Timestamp | None]:
    match booking_num:
        case b if re.search(r"EBKG\d{8}", b):
            print(f"  [Carrier] Identified as MSC — querying tracking API...")
            eta_look_up = checkingMSC(booking_num, pw)
            if eta_look_up is not None:
                window_cutoff = add_business_days(pd.Timestamp.now(), 6)
                in_window = eta_look_up <= window_cutoff
                print(f"  [Carrier] ETA={eta_look_up.date()} | Window Cutoff={window_cutoff.date()} | InWindow={in_window}")
                return (in_window, eta_look_up)
            else:
                print(f"  [Carrier] MSC returned no ETA for {booking_num}")
                return (False, None)
        case b if re.fullmatch(r"2\d{8}", b):
            print(f"  [Carrier] Identified as Maersk — querying tracking API...")
            eta_look_up = checkingMaersk(booking_num, pw)
            if eta_look_up is not None:
                window_cutoff = add_business_days(pd.Timestamp.now(), 6)
                in_window = eta_look_up <= window_cutoff
                print(f"  [Carrier] ETA={eta_look_up.date()} | Window Cutoff={window_cutoff.date()} | InWindow={in_window}")
                return (in_window, eta_look_up)
            else:
                print(f"  [Carrier] Maersk returned no ETA for {booking_num}")
                return (False, None)
        case b if re.search(r"NAM\d{7}", b):
            raise RuntimeError(f"CMA ETA lookup not yet implemented for booking {booking_num}")
        case b if re.search(r"S3\d{8}", b):
            raise RuntimeError(f"Grimaldi ETA lookup not yet implemented for booking {booking_num}")
        case b if re.search(r"2026\d{6}", b):
            raise RuntimeError(f"This is a Ref Number: {booking_num}")
        case _:
            raise RuntimeError(f"No carrier pattern matched booking {booking_num} — process manually")


if __name__ == "__main__":
    test_bookings = ["EBKG17208602", "EBKG11248028"]
    for booking in test_bookings:
        with sync_playwright() as p:
            is_msc, eta = carrierIDthenETAcheck(booking, p)
            print(f"Booking: {booking} | Is MSC? {is_msc} | ETA: {eta}")