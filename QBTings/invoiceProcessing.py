import asyncio
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv
from pandas import Timestamp
from playwright.sync_api import Page, sync_playwright, TimeoutError as PWTimeout

from QBTings.playWrightQB import _click_button, _find_input_by_label, _is_on_auth_page, _wait_for_qbo_app
import MSC.checkETA as checkMSC
from stringTing.subjectEdit import subjectDecision
load_dotenv()

# ── Credentials ────────────────────────────────────────────────────────────────
CLIENT_ID     = os.environ["QB_CLIENT_ID"]
CLIENT_SECRET = os.environ["QB_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["QB_REFRESH_TOKEN"]
REALM_ID      = os.environ["QB_REALM_ID"]

# ── Constants ──────────────────────────────────────────────────────────────────
EMAIL_SUBJECT = "Your Invoice Is Ready"  # ← change subject line here

SANDBOX   = os.getenv("QB_SANDBOX", "false").lower() == "true"
HEADLESS  = os.getenv("QB_HEADLESS", "false").lower() == "true"
BASE_URL  = (
    "https://sandbox-quickbooks.api.intuit.com"
    if SANDBOX else
    "https://quickbooks.api.intuit.com"
)
TOKEN_URL   = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
MINOR_VER   = 73
QBO_WEB     = "https://qbo.intuit.com"
SESSION_DIR = Path(".qbo_browser_session")
# ── Core Processes ─────────────────────────────────────────────────────────────────
def process_invoice(page: Page, eta_date: Timestamp, invoice_id: str, notif_num: bool):
    """Update ETA and send one invoice via the QBO web UI."""
    # QBO displays dates as M/D/YYYY in the US locale
    qbo_date = eta_date.date().strftime("%m/%d/%Y")
        
    # ── 1. Open the invoice edit page ─────────────────────────────────────────
    page.goto(f"{QBO_WEB}/app/invoice?txnId={invoice_id}", wait_until="load")

    if _is_on_auth_page(page):
        raise RuntimeError(
            "Session expired. Delete .qbo_browser_session/ and re-run to log in again."
        )
    didPay = page.locator("#balanceAmount").inner_text().strip() == "$0.00"
    invNum = page.locator("#sales-forms-ui/reference_number").input_value().strip()
    subject = subjectDecision(invNum,eta_date,notif_num,didPay)
        
    # ── 2. Wait for invoice form then update ETA ──────────────────────────────
    # Use element visibility as the "page ready" signal — QBO's SPA never
    # reaches networkidle because it continuously makes background requests.
    eta_input = _find_input_by_label(page, "Date Field")
    eta_input.dblclick()           # select existing value
    eta_input.fill(qbo_date)
    eta_input.press("Tab")             # dismiss any date-picker popup
    page.wait_for_timeout(400)

    # # ── 3. Save the invoice ───────────────────────────────────────────────────
    # _click_button(page, "Save", "Save and close")
    # page.wait_for_load_state("load", timeout=15_000)
    # page.wait_for_timeout(1_500)   # let QBO finish its post-save XHRs
    # print(f"    Saved  — ETA={eta_date}")

    # ── 4. Open send dialog ───────────────────────────────────────────────────
    _click_button(page, "Review and send")
    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(800)

    # ── 5. Update email subject ───────────────────────────────────────────────
    try:
        subj = page.get_by_label("Subject", exact=True)
        subj.wait_for(state="visible", timeout=5_000)
        subj.dblclick()
        subj.fill(subject)
        print(f"Subject set to: {subject}")
    except PWTimeout:
        print("[note] Subject field not found — QBO default subject will be used.")

    # ── 6. Confirm send ───────────────────────────────────────────────────────
    _click_button(page, "Send invoice")
    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(800)
    print(f"    Email sent.")

def process_future_invoice(page, eta_date: Timestamp, invoice_id: str, bookNum:str):
    """Update ETA and send one invoice via the QBO web UI."""
    # QBO displays dates as M/D/YYYY in the US locale
    qbo_date = eta_date.date().strftime("%m/%d/%Y")
        
    # ── 1. Open the invoice edit page ─────────────────────────────────────────
    page.goto(f"{QBO_WEB}/app/invoice?txnId={invoice_id}", wait_until="load")

    if _is_on_auth_page(page):
        raise RuntimeError(
            "Session expired. Delete .qbo_browser_session/ and re-run to log in again."
        )

    # ── 2. Wait for invoice form then update ETA ──────────────────────────────
    # Use element visibility as the "page ready" signal — QBO's SPA never
    # reaches networkidle because it continuously makes background requests.
    eta_input = _find_input_by_label(page, "Date Field")
    eta_input.dblclick()           # select existing value
    eta_input.fill(qbo_date)
    eta_input.press("Tab")             # dismiss any date-picker popup
    page.wait_for_timeout(400)

    # # ── 3. Save the invoice ───────────────────────────────────────────────────
    _click_button(page, "Save", "Save and close")
    page.wait_for_load_state("load", timeout=15_000)
    page.wait_for_timeout(1_500)   # let QBO finish its post-save XHRs
    print(f"    Saved  — ETA={eta_date}")


# ── Manual test harness ─────────────────────────────────────────────────────────
def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass


if __name__ == "__main__":
    from QBTings.apiREST import get_access_token, get_invoice_by_number

    try:
        doc_number = input("Invoice DocNumber to test: ").strip()

        while True:
            raw = input("ETA date (YYYY-MM-DD): ").strip()
            try:
                eta_date = Timestamp(datetime.strptime(raw, "%Y-%m-%d"))
                break
            except ValueError:
                print("  Invalid format — please use YYYY-MM-DD.")

        future = input("Test process_future_invoice instead of process_invoice? (y/N): ").strip().lower() == "y"
        notif_num = False
        if not future:
            notif_raw = input("notif_num (True/False/2) [default False]: ").strip().lower()
            notif_num = {"true": True, "false": False, "2": 2}.get(notif_raw, False)

        token = get_access_token()
        invoice = get_invoice_by_number(token, doc_number)
        if invoice is None:
            sys.exit(f"Invoice #{doc_number} not found in QuickBooks.")

        SESSION_DIR.mkdir(exist_ok=True)
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                str(SESSION_DIR),
                headless=False,
                slow_mo=200,
                viewport={"width": 1440, "height": 900},
            )
            page = context.new_page()
            page.goto(QBO_WEB, wait_until="load")
            _wait_for_qbo_app(page)

            if future:
                process_future_invoice(page, eta_date, invoice["Id"], doc_number)
            else:
                process_invoice(page, eta_date, invoice["Id"], notif_num)

            context.close()
        print("Done.")
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)