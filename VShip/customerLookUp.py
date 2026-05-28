from pathlib import Path
from typing import Literal
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import playwright.async_api
import os
from playwright.sync_api import sync_playwright, TimeoutError as timeException
from MSC.checkETA import on_response
from VShip.syncSignInVShipCRM import sign_in_vshipcrm
import re

VSHIP_LOGIN_URL = "https://vshipcrm.com/Home/Index"

def lookup_customer_notif(booking_no: str) -> bool | Literal[2]:
    if Path('auth_for_VshipCRM.json').exists() and datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.json').stat().st_mtime) < timedelta(hours = 2):
        print("Using existing authentication state.")
    else:
        VSHIP_username = os.getenv('USER_NAME') if not os.getenv('USER_NAME')==None else ""
        VSHIP_password = os.getenv('EMAIL_PASSWORD') if not os.getenv('EMAIL_PASSWORD')==None else ""        
        sign_in_vshipcrm(VSHIP_username, VSHIP_password)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state="auth_for_VshipCRM.json"
        )
        context.set_default_timeout(5000)
        page = context.new_page()
        page.goto("https://vshipcrm.com/Booking/Booking")
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
            print(f"Something Timed out, trying again... {e}")
            try:
                page.goto("https://vshipcrm.com/Home/GlobalSearch")
                page.fill('input[name="Booking_No"]', booking_no)
                page.evaluate("reInitGrid()")
                processing = page.locator('#booking_processing')
                if processing.is_visible():
                    processing.wait_for(state="hidden")
                row = page.locator(
                '#global-search-table tbody tr',
                has=page.locator(f'td:nth-child(4):text-is("{booking_no}")')
                )
                row.locator('a[title="Edit"][href^="/Booking/CreateBooking/"]').click()
            except Exception as e:
                print(f"Error For {booking_no}:\nSomething Timed out (again)...\n{e}")
        print("At the View Page now")
        all_comments = page.locator("article.comments").all_inner_texts()
        full_text = " ".join(all_comments).lower()
        if "notif #1" in full_text:
            if "notif #2" in full_text:
                return 2
            else:
                return True
        else:
            return False