import os
import traceback
import sys
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from playwright.sync_api import Page, Playwright, sync_playwright, TimeoutError as timeException
from tinkyWinky_log_only import UserInputs, get_user_inputs

VSHIP_PW_LOGIN_URL ="https://vshipcrm.com/auth"


def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass
    
    
    
def make_vship_booking_changes(page:Page, booking_id:str, eta: pd.Timestamp, bookingNum: str):
    print(f"  [VShip] Updating booking {booking_id} with ETA {eta.date()}...")
    page.goto(f"https://vshipcrm.com/booking/operations?edit=true&bookingId={booking_id}")
    page.wait_for_load_state("networkidle")
    page.locator("#expected_Arrival_Date").fill(eta.strftime("%Y-%m-%d"))
    page.locator("#expected_Arrival_Date").press("Tab")
    page.click("button[type='submit']")
    btn = page.locator("button[type='submit']")
    btn.wait_for(state="hidden", timeout=10000)
    page.wait_for_load_state("networkidle")
    print(f"  [VShip] VShip ETA {eta.date()} for {bookingNum} done.")
if __name__ == "__main__":
    try:
        load_dotenv(override=True)
        USERNAME = os.getenv('VSHIP_USER_NAME') if not os.getenv('VSHIP_USER_NAME')==None else ""
        user_name = USERNAME if USERNAME is not None else ""
        PASSWORD = os.getenv('VSHIP_PASSWORD') if not os.getenv('VSHIP_PASSWORD')==None else ""
        password = PASSWORD if PASSWORD is not None else ""
        print(f"[debug] USERNAME from .env: {user_name!r}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(VSHIP_PW_LOGIN_URL)
            page.fill('input[name="emailId"]', user_name)
            page.fill('input[name="password"]', password)
            page.click("button[type='submit']")
            
            page.wait_for_load_state("networkidle")
            page.context.set_default_timeout(10000)
            print("Signed into VShipCRM")
            make_vship_booking_changes(page, "72892", pd.Timestamp("2023-06-01"), "EBKG11248028")
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)