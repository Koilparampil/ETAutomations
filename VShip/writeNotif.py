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
            raise ValueError(f"Note creation failed with status code (not unauth problem): {resp_note.status_code}\n{resp_note.text}")
        elif resp_note.status_code in [400,401,403]:
            raise ValueError(f"Note creation pt 2 failed with status code unauth Problem: {resp_note.status_code}\n{resp_note.text}")
    except Exception as e:
        raise NoteError(f"Error creating note: {e}")
    
    
def note_writing(eta: pd.Timestamp, notifNum: int, booking_no: str):
    if Path('auth_for_VshipCRM.txt').exists() and datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime) < timedelta(hours = 1):
        print("Using existing authentication state.")
    else:
        inputs: UserInputs = get_user_inputs("VShip Login")
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
    except requests.RequestException as e:
        raise requests.HTTPError("auth issue maybe?", e)
    
    
    comment = ""
    if eta < pd.Timestamp.now():
                comment= f"ARRIVED ON {eta.strftime('%m/%d')}. NOTIF #{notifNum+1}"
    else:
                comment= f"ARRIVING ON {eta.strftime('%m/%d')}."
                
                
                
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
            inputs: UserInputs = get_user_inputs("VShip Login")
            sign_in_vshipcrm(inputs.username, inputs.password)
            with open('auth_for_VshipCRM.txt', 'r') as f:
                token = f.read().strip()
            note_writing_pt2(eta, notifNum, booking_id, token, comment)
        elif resp_note.status_code in [400,401,403] and (datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime) <= timedelta(minutes = 3)):
            raise ValueError(f"Note creation failed with status code, no resign in: {resp_note.status_code}\n{resp_note.text}")
    except Exception as e:
        raise NoteError(f"Error creating note: {e}")    
    

if __name__ == "__main__":
    eta = pd.Timestamp.now() + pd.Timedelta(days=2)
    notifNum = 1 if False else 0
    bk_num = "EBKG54698731_CUSTOME HOLD_MOROCCO BLAGH"
    note_writing(eta, notifNum, bk_num)