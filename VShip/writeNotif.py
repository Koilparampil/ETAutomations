from playwright.async_api import async_playwright
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as timeException
from VShip.syncSignInVShipCRM import sign_in_vshipcrm
from tinkyWinky_log_only import UserInputs, get_user_inputs
def normalize(s) -> str:
    return (
        s.split(",")[0]
        .split("_")[0]
        .split(" ")[0]
        .strip()
    )
    
    

def write_notif_in_VShip(eta: pd.Timestamp, notifNum: int, booking_no: str):
    if Path('auth_for_VshipCRM.json').exists() and datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.json').stat().st_mtime) < timedelta(hours = 2):
        print("Using existing authentication state.")
    else:
        inputs: UserInputs = get_user_inputs()
        sign_in_vshipcrm(inputs.username, inputs.password) 
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
                storage_state="auth_for_VshipCRM.json"
            )
        context.set_default_timeout(5000)
        page = context.new_page()
        page.goto("https://vshipcrm.com/Booking/Booking")
        print("Working on booking:", booking_no)
        try:
            search = page.locator('input[type="search"]')
            search.fill(booking_no)
            processing = page.locator('#booking_processing')
            if processing.is_visible():
                processing.wait_for(state="hidden")
            row = page.locator(
                '#booking tbody#tBody tr',
                has=page.locator(f'td:nth-child(4):text-is("{booking_no}")')
                )
            row.wait_for(state="visible")                        
            locator = row.locator('a.openDialog.btn.btn-warning:has-text("Edit")')
            locator.click()
        except timeException as e:
            print(f"Something Timed out, trying again...\n{e}")
            try:
                page.goto("https://vshipcrm.com/Home/GlobalSearch")
                page.fill('input[name="Booking_No"]', booking_no)
                page.evaluate("reInitGrid()")
                page.wait_for_load_state("networkidle")
                row = page.locator(
                '#global-search-table tbody tr',
                has=page.locator(f'td:nth-child(4):text-is("{booking_no}")')
                )
                row.locator('a[title="Edit"][href^="/Booking/CreateBooking/"]').click()
            except Exception as e:
                raise ReferenceError(f"Error For {booking_no}:\nCant't Find it...\n{e}")
        page.wait_for_load_state("networkidle")
        booking_num_on_page = normalize(page.locator('input#Booking_No').get_attribute('value'))
        if booking_num_on_page.find(booking_no)!=-1:
            print(f"Filling note in Booking No: {booking_no}")
            if eta <= pd.Timestamp.now():
                page.locator('#InternalComment').fill(f"ARRIVED ON {eta.strftime('%m/%d')}. NOTIF #{notifNum}")
                page.get_by_role("button", name="Save").click()
            else:
                page.locator('#InternalComment').fill(f"ARRIVING ON {eta.strftime('%m/%d')}.")
                page.get_by_role("button", name="Save").click()  
        else:
            raise ValueError(f"Booking Num not found on page of booking info: {booking_no}")           
        browser.close()