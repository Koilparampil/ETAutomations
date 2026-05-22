#!/usr/bin/env python3
"""
QBO Invoice ETA Updater — Browser Automation
---------------------------------------------
The ETA field is a User Defined Custom Field (UDCF) that QBO's REST API v3
cannot write to. This script drives the QBO web interface with Playwright
to update ETA and send each invoice — exactly as a user would in a browser.

Setup (one-time):
    pip install playwright && playwright install chromium

First run: opens a visible browser — log in to QBO manually once.
           The session is saved to .qbo_browser_session/ for future runs.
Subsequent runs: reuses the saved session (headed by default; set
                 QB_HEADLESS=true in .env for silent/headless mode).

Usage:
    python update_eta_browser.py invoice_numbers.txt
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from QBTings.apiREST import get_access_token, get_invoice_by_number
from QBTings.playWrightQB import _wait_for_qbo_app
from QBTings.invoiceProcessing import process_invoice
from tinkyWinky import get_user_inputs

load_dotenv()

QBO_WEB     = "https://qbo.intuit.com"
HEADLESS  = os.getenv("QB_HEADLESS", "false").lower() == "true"
SESSION_DIR = Path(".qbo_browser_session")

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
    inputs = get_user_inputs()
    try:
        print("Extracting data from file...")
        invoice_numbers = get_data(inputs.filename) 
    except Exception as e:
        print(f"Failed to extract data from file: {e}")
        pause_before_exit()
        sys.exit(1)

    if not invoice_numbers:
        sys.exit("Invoice list is empty — nothing to do.")

    # while True:
    #     raw = input("Enter ETA date (YYYY-MM-DD): ").strip()
    #     try:
    #         datetime.strptime(raw, "%Y-%m-%d")
    #         eta_date = raw
    #         break
    #     except ValueError:
    #         print("  Invalid format — please use YYYY-MM-DD.")

    # Resolve invoice IDs via REST API before opening browser
    token = get_access_token()
    print(f"\nLooking up {len(invoice_numbers)} invoice(s) via REST API…")
    invoices = {}
    for num in invoice_numbers:
        inv = get_invoice_by_number(token, num)
        if inv is None:
            print(f"  [SKIP] #{num} — not found in QuickBooks")
        else:
            invoices[num] = inv
            print(f"  [FOUND] #{num} — QBO Id={inv['Id']}")

    if not invoices:
        sys.exit("\nNo invoices found — nothing to process.")

    SESSION_DIR.mkdir(exist_ok=True)
    is_first_run = not any(SESSION_DIR.iterdir())

    print(f"\nOpening browser ({'headless' if HEADLESS and not is_first_run else 'headed'})…")
    if is_first_run:
        print("[browser] First run detected — browser will open visibly for login.")

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

        ok = failed = 0


        for num, inv in invoices.items():
            print(f"  #{num}")
            try:
                process_invoice(page, inv["Id"], num, eta_date)
                print(f"  [OK]    #{num}\n")
                ok += 1
            except Exception as exc:
                print(f"  [ERROR] #{num} — {exc}\n")
                failed += 1
                # Screenshot for debugging
                shot_path = f"error_{num}.png"
                try:
                    page.screenshot(path=shot_path)
                    print(f"           Screenshot saved to {shot_path}")
                except Exception:
                    pass

        context.close()

    print(f"Done: {ok} succeeded, {failed} failed/skipped.")


if __name__ == "__main__":
    main()
