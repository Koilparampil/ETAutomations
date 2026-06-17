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
    except requests.RequestException as e:
        print(f"HTTP request failed: {e}")
        raise
    
    
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
            if any("notif #2" in comment.get("comment", "").lower() for comment in comments_all):
                return 2
            else:
                return True
        else:
            return False
    except (KeyError, IndexError,AttributeError) as e:
        print(f"Error parsing response JSON while finding notifs: {e}")
        raise json.JSONDecodeError(f"Unexpected JSON structure for comments: {resp.text}", resp.text, 0)
    
    

if __name__ == "__main__":
    booking_no = "EBKG17422302"
    try:
        result = lookup_customer_notif(booking_no)
        if result is True:
            print(f"Booking {booking_no} has a notif #1 but no notif #2.")
        elif result == 2:
            print(f"Booking {booking_no} has both notif #1 and notif #2.")
        else:
            print(f"Booking {booking_no} has no notif #1.")
    except Exception as e:
        print(f"An error occurred: {e}")