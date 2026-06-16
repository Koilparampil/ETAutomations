import json
from pathlib import Path
from typing import Literal
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import playwright.async_api
import os
from playwright.sync_api import sync_playwright, TimeoutError as timeException
import requests
from MSC.checkETA import on_response
from VShip.syncSignInVShipCRM import sign_in_vshipcrm
import re

from tinkyWinky_log_only import UserInputs, get_user_inputs

VSHIP_LOGIN_URL = "https://vshipcrm.com/Home/Index"

def lookup_customer_notif(booking_no: str) -> bool | Literal[2]:
    if not booking_no:
        print("No booking number provided")
        raise ValueError("No booking number provided")
    
    if Path('auth_for_VshipCRM.txt').exists() and datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime) < timedelta(hours = 1):
        print("Using existing authentication state.")
    else:
        inputs: UserInputs = get_user_inputs()
        sign_in_vshipcrm(inputs.username, inputs.password) 
    with open('auth_for_VshipCRM.txt', 'r') as f:
        token = f.read().strip()

    try:
        resp = requests.get(
            f"https://vship2000-prod-api.azurewebsites.net/api/Bookings/searchBooking?searchText={booking_no}&page=1&pageSize=50",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=10,
            )
        resp.raise_for_status()
        booking_id =resp.json().get("value").get("data")[0].get("bookingId")
    except (KeyError, IndexError,AttributeError) as e:
        print(f"Error parsing response JSON: {e}")
        raise json.JSONDecodeError(f"Unexpected JSON structure: {resp.text}", resp.text, 0)
    
    
    resp = requests.get(
    f"https://vship2000-prod-api.azurewebsites.net/api/Bookings/{booking_id}/comments",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    },
    timeout=10,
    )
    resp.raise_for_status()
    try:
        comments_all = resp.json().get("value").get("internalComments")
        matches = [comment for comment in comments_all if ("notif #1" in comment.get("comment", "").lower())]
        if matches:
            if any("notif #2" in match.get("comment", "").lower() for match in matches):
                return 2
            else:
                return True
        else:
            return False
    except (KeyError, IndexError,AttributeError) as e:
        print(f"Error parsing response JSON while finding notifs: {e}")
        raise json.JSONDecodeError(f"Unexpected JSON structure for comments: {resp.text}", resp.text, 0)
    
##################    
    
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