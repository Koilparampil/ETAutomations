import json

from playwright.async_api import async_playwright
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, TimeoutError as timeException
import requests
from VShip.syncSignInVShipCRM import sign_in_vshipcrm
from tinkyWinky_log_only import UserInputs, get_user_inputs

class NoteError(Exception):
    pass

def normalize(s) -> str:
    return (
        s.split(",")[0]
        .split("_")[0]
        .split(" ")[0]
        .strip()
    )

def note_writing_pt2(eta: pd.Timestamp, notifNum: int, booking_id: str, token: str, comment: str):
    try:
        resp_note = requests.post(
        f"https://vship2000-prod-api.azurewebsites.net/api/Bookings/{booking_id}/comments", 
        json={
            "comment": comment,
            "commentType": 1,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            'sec-ch-ua': '"Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Referer": "https://vshipcrm.com/"},
        )
        if resp_note.status_code != 201 and resp_note.status_code not in [400,401,403]:
            raise ValueError(f"Note creation failed with status code: {resp_note.status_code}\n{resp_note.text}")
        elif resp_note.status_code in [400,401,403]:
            raise ValueError(f"Note creation failed with status code: {resp_note.status_code}\n{resp_note.text}")
    except Exception as e:
        raise NoteError(f"Error creating note: {e}")
    
    
def note_writing(eta: pd.Timestamp, notifNum: int, booking_no: str):
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
    comment = ""
    if eta <= pd.Timestamp.now():
                comment= f"ARRIVED ON {eta.strftime('%m/%d')}. NOTIF #{notifNum}"
    else:
                comment= f"ARRIVING ON {eta.strftime('%m/%d')}. NOTIF #{notifNum}"
                
    try:
        resp_note = requests.post(
        f"https://vship2000-prod-api.azurewebsites.net/api/Bookings/{booking_id}/comments", 
        json={
            "comment": comment,
            "commentType": 1,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            'sec-ch-ua': '"Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Referer": "https://vshipcrm.com/"},
        )
        if resp_note.status_code != 201 and resp_note.status_code not in [400,401,403]:
            raise ValueError(f"Note creation failed with status code: {resp_note.status_code}\n{resp_note.text}")
        elif resp_note.status_code in [400,401,403] and (datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime) > timedelta(minutes = 3)):
            print(f"Note creation failed with status code: {resp_note.status_code}. ReSigning In")
            inputs: UserInputs = get_user_inputs()
            sign_in_vshipcrm(inputs.username, inputs.password)
            note_writing_pt2(eta, notifNum, booking_id, token, comment)
        elif resp_note.status_code in [400,401,403] and (datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime) <= timedelta(minutes = 3)):
            raise ValueError(f"Note creation failed with status code: {resp_note.status_code}\n{resp_note.text}")
    except Exception as e:
        raise NoteError(f"Error creating note: {e}")    
    

def old_write_notif_in_VShip(eta: pd.Timestamp, notifNum: int, booking_no: str):
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