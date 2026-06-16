#!/usr/bin/env python3
"""
QBO Invoice ETA Updater — Browser Automation
---------------------------------------------
The ETA field is a User Defined Custom Field (UDCF) that QBO's REST API v3
cannot write to. This script drives the QBO web interface with Playwright
to update ETA and send each invoice — exactly as a user would in a browser.

Setup (one-time):
    pip install playwright && playwright install chromium
    pip install -r requirements.txt

First run: opens a visible browser — log in to QBO manually once.
           The session is saved to .qbo_browser_session/ for future runs.
Subsequent runs: reuses the saved session (headed by default; set
                 QB_HEADLESS=true in .env for silent/headless mode).

Usage:
    python update_eta_browser.py invoice_numbers.txt
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from QBTings.apiREST import get_access_token, get_invoice_by_number
from QBTings.playWrightQB import _wait_for_qbo_app
from QBTings.invoiceProcessing import process_future_invoice, process_invoice
from VShip.customerLookUp import lookup_customer_notif
from VShip.writeNotif import note_writing as write_notif_in_VShip
from carrierTing.carriers import carrierIDthenETAcheck
from tinkyWinky import get_user_inputs

load_dotenv()

QBO_WEB     = "https://qbo.intuit.com"
HEADLESS  = os.getenv("QB_HEADLESS", "false").lower() == "true"
SESSION_DIR = Path(".qbo_browser_session")

# ── Helper Functions ─────────────────────────────────────────────────────────────────
def write2BFile(booking):
    with open("Send2Ben.txt", "a") as f:
        f.write(f"{booking}\n")
        f.close()
def write2FileFail(booking):
    with open("Failed_To_Process.txt", "a") as f:
        f.write(f"{booking}\n")
        f.close()
def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass
    
def get_data(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    return [line.strip() for line in lines if line.strip()]

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    ###Get File and User Creds from User.
    inputs = get_user_inputs()
    # Extracting invoice numbers from file
    try:
        print("Extracting data from file...")
        invoice_numbers = get_data(inputs.filename) 
    except Exception as e:
        print(f"Failed to extract data from file: {e}")
        pause_before_exit()
        sys.exit(1)
    if not invoice_numbers:
        sys.exit("Invoice list is empty — nothing to do.")
    token = get_access_token()
    ok = failed = 0
    SESSION_DIR.mkdir(exist_ok=True)
    is_first_run = not any(SESSION_DIR.iterdir())
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=HEADLESS and not is_first_run,
            slow_mo=200,
            viewport={"width": 1440, "height": 900},
            args=["--start-maximized"],
        )
        page = context.new_page()
        # Trigger login check
        page.goto(QBO_WEB, wait_until="load")
        _wait_for_qbo_app(page)
        for bookingNum in invoice_numbers:
            print(f"Processing booking number: {bookingNum}")
            if bookingNum[-1].lower() in ["0","1","2","3","4","5","6","7","8","9"]:
                try:
                    inWindow, eta = carrierIDthenETAcheck(bookingNum)
                except RuntimeError as e:
                    write2FileFail(f"[ERROR] #{bookingNum} — Carrier Lookup Failed.\n{e}\n")
                    failed += 1
                    continue
                except ValueError as e:
                    write2FileFail(f"[ERROR] #{bookingNum} —  Can't determine ETA.\n{e}\n")
                    failed += 1
                    continue
                except Exception as e:
                    write2FileFail(f"[ERROR] #{bookingNum} — Unexpected error during carrier lookup.\n{e}\n")
                    failed += 1
                    continue
                if inWindow and (eta is not None):
                    try:
                        notif_num = lookup_customer_notif(bookingNum)
                    except Exception as e:
                        print(f"Error occurred while looking up customer notification for {bookingNum}: {e}")
                        notif_num = False
                    if notif_num == 2:
                        print(f"Booking {bookingNum} has both Notif #1 and Notif #2. Skipping invoice update and sending to Ben.")
                        write2BFile(bookingNum)
                        continue
                    else:
                        inv = get_invoice_by_number(token, bookingNum)
                        if inv is not None:
                            try:
                                process_invoice(page, eta, inv['Id'], notif_num)
                                try:
                                    write_notif_in_VShip(eta, notif_num, bookingNum)
                                    print(f"  [OK]    #{bookingNum}\n")
                                    ok += 1                                    
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} — Note Write Error, Email Still Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            except Exception as exc:
                                write2FileFail(f"[ERROR] #{bookingNum} — QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                failed += 1
                                continue
                        else:
                            write2FileFail(f"[SKIP] #{bookingNum} — not found in QuickBooks")
                            failed += 1
                            continue
                else:
                    if eta is not None:
                        print(f"ETA is outside the 6-business-day window")
                        inv = get_invoice_by_number(token, bookingNum)
                        if inv is not None:
                            try:
                                process_future_invoice(page, eta, inv['Id'], bookingNum)
                                try:
                                    write_notif_in_VShip(eta, 0, bookingNum)
                                    print(f"  [OK]    #{bookingNum}\n")
                                    ok += 1                                    
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} — Note Write Error, Email Still Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            except Exception as exc:
                                write2FileFail(f"[ERROR] #{bookingNum} — QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                failed += 1     
                                continue                   
                    else:
                        write2FileFail(f"[ERROR] #{bookingNum} — ETA not found")
                        failed += 1
                        continue
            elif (bookingNum[-1].lower() == "a"):
                if bookingNum[-2:].lower() == "aa":
                    print(f"Booking {bookingNum} has both Notif #1 and Notif #2. Skipping invoice update and sending to Ben.")
                    write2BFile(bookingNum)
                    continue
                elif re.search(r"(?i)[^a]a$", bookingNum):
                    inWindow, eta = carrierIDthenETAcheck(bookingNum[:-1].strip())
                    if inWindow and (eta is not None):
                        try:
                            notif_num = lookup_customer_notif(bookingNum[:-1])
                        except Exception as e:
                            print(f"Error occurred while looking up customer notification for {bookingNum[:-1]}: {e}")
                            notif_num = False
                        if notif_num == 2:
                            print(f"Booking {bookingNum} has both Notif #1 and Notif #2. Skipping invoice update and sending to Ben.")
                            write2BFile(bookingNum)
                            continue
                        else:
                            inv = get_invoice_by_number(token, bookingNum)
                            if inv is not None:
                                try:
                                    process_invoice(page, eta, inv['Id'], notif_num)
                                    try:
                                        write_notif_in_VShip(eta, notif_num, bookingNum[:-1])
                                        print(f"  [OK]    #{bookingNum}\n")
                                        ok += 1                                    
                                    except Exception as exc:
                                        write2FileFail(f"[ERROR] #{bookingNum} — Note Write Error, Email Still Sent\n{exc}\n")
                                        failed += 1
                                        continue
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} — QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            else:
                                write2FileFail(f"[SKIP] #{bookingNum} — not found in QuickBooks")
                                failed += 1
                                continue
                    else:
                        if eta is not None:
                            print(f"ETA is outside the 6-business-day window")
                            inv = get_invoice_by_number(token, bookingNum)
                            if inv is not None:
                                try:
                                    process_future_invoice(page, eta, inv['Id'], bookingNum)
                                    try:
                                        write_notif_in_VShip(eta, 0, bookingNum)
                                        print(f"  [OK]    #{bookingNum}\n")
                                        ok += 1                                    
                                    except Exception as exc:
                                        write2FileFail(f"[ERROR] #{bookingNum} — Note Write Error, Email Still Sent\n{exc}\n")
                                        failed += 1
                                        continue
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} — QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                    failed += 1      
                                    continue                  
                        else:
                            write2FileFail(f"[ERROR] #{bookingNum} — ETA not found")
                            failed += 1
                            continue
            elif (bookingNum[-1].lower() == "r"):
                print("Don't need to do this one, ends in R")
                continue
            else:
                print(f"Do this one manually: {bookingNum} added to failed List")
                write2FileFail(bookingNum)
                failed += 1
        context.close()
    print(f"Done: {ok} succeeded, {failed} failed/skipped.")


if __name__ == "__main__":
    main()
