import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from MSC.signInMSC import sync_sign_in_MSC_complete
from QBTings.apiREST import get_access_token, get_invoice_by_number
from QBTings.playWrightQB import _wait_for_qbo_app
from QBTings.invoiceProcessing import process_future_invoice, process_invoice
from VShip.booking_changes import VSHIP_PW_LOGIN_URL, make_vship_booking_changes
from VShip.customerLookUp import lookup_customer_notif
from VShip.syncSignInVShipCRM import sign_in_vshipcrm
from VShip.writeNotif import note_writing as write_notif_in_VShip
from carrierTing.carriers import carrierIDthenETAcheck
from tinkyWinky import get_user_inputs, get_user_inputs_authed as get_authed_inputs

load_dotenv(override=True)

QBO_WEB     = "https://qbo.intuit.com"
HEADLESS  = os.getenv("QB_HEADLESS", "false").lower() == "true"
SESSION_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "QB-APITesting" / "qbo_browser_session"
USERNAME = os.getenv('VSHIP_USER_NAME') if os.getenv('VSHIP_USER_NAME')!=None else ""
PASSWORD = os.getenv('VSHIP_PASSWORD') if os.getenv('VSHIP_PASSWORD')!=None else ""
MSC_USERNAME = os.getenv('MSC_USER_NAME') if os.getenv('MSC_USER_NAME')!=None else ""
MSC_PASSWORD = os.getenv('MSC_PASSWORD') if os.getenv('MSC_PASSWORD')!=None else ""
QB = os.getenv('QB') if os.getenv('QB')!=None else ""
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
    VSHIP_token_age = (datetime.now() - datetime.fromtimestamp(Path('auth_for_VshipCRM.txt').stat().st_mtime)) if Path('auth_for_VshipCRM.txt').exists() else None
    MSC_token_age = (datetime.now() - datetime.fromtimestamp(Path('MSCauthToken.json').stat().st_mtime)) if Path('MSCauthToken.json').exists() else None
    if ((VSHIP_token_age is not None) and (VSHIP_token_age < timedelta(hours=1))) and ((MSC_token_age is not None) and (MSC_token_age < timedelta(minutes=30))):
        print("Using cached auth tokens for VShip and MSC.")
        inputs =get_authed_inputs()
        print("Fetching QuickBooks access token...")
        token = get_access_token()
    else:
        # ###Get File and User Creds from User.
        # inputs = get_user_inputs()
        inputs =get_authed_inputs()
        print("Fetching QuickBooks access token...")
        token = get_access_token()
        print("QuickBooks token obtained.")
        print("Signing in to MSC...")
        sync_sign_in_MSC_complete(MSC_USERNAME, MSC_PASSWORD)
        print("MSC sign-in complete.")
        print("Signing in to VShip CRM...")
        sign_in_vshipcrm(USERNAME, PASSWORD)
        print("VShip CRM sign-in complete.")
    # Extracting invoice numbers from file
    try:
        print("Extracting data from file...")
        invoice_numbers = get_data(inputs.filename) 
    except Exception as e:
        print(f"Failed to extract data from file: {e}")
        pause_before_exit()
        sys.exit(1)
    if not invoice_numbers:
        sys.exit("Invoice list is empty - nothing to do.")
    print(f"Loaded {len(invoice_numbers)} booking(s) from file.")
    ok = failed = 0
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    is_first_run = not any(SESSION_DIR.iterdir())
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=HEADLESS and not is_first_run,
            slow_mo=200,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        vship_page = context.new_page()
        vship_page.goto(VSHIP_PW_LOGIN_URL)
        vship_page.fill('input[name="emailId"]', USERNAME)
        vship_page.fill('input[name="password"]', PASSWORD)
        vship_page.click("button[type='submit']")
        vship_page.wait_for_load_state("networkidle")
        vship_page.context.set_default_timeout(10000)
        print("Signed into VShipCRM")
        page.goto(QBO_WEB, wait_until="load")
        try:
            page.locator("button[data-testid='AccountChoiceButton_0']").click()
            page.fill('input[name="Password"]', QB)
        except Exception as e:
            print(f"Error clicking AccountChoiceButton: {e}")
        _wait_for_qbo_app(page)
        print(f"\nStarting browser processing of {len(invoice_numbers)} booking(s)...\n")
        for bookingNum in invoice_numbers:
            print(f"{'─'*50}")
            print(f"Processing: {bookingNum}")
            if bookingNum[-1].lower() in ["0","1","2","3","4","5","6","7","8","9"]:
                try:
                    inWindow, eta = carrierIDthenETAcheck(bookingNum,pw)
                except RuntimeError as e:
                    write2FileFail(f"[ERROR] #{bookingNum} - Carrier Lookup Failed.\n{e}\n")
                    failed += 1
                    continue
                except ValueError as e:
                    write2FileFail(f"[ERROR] #{bookingNum} -  Can't determine ETA.\n{e}\n")
                    failed += 1
                    continue
                except Exception as e:
                    write2FileFail(f"[ERROR] #{bookingNum} - Unexpected error during carrier lookup.\n{e}\n")
                    failed += 1
                    continue
                print(f"  ETA: {eta.date() if eta is not None else 'N/A'} | In 6-day window: {inWindow}")
                if inWindow and (eta is not None):
                    print(f"  Looking up VShip notifications for {bookingNum}...")
                    try:
                        notif_num = lookup_customer_notif(bookingNum)
                    except Exception as e:
                        print(f"  [WARN] Notif lookup failed: {e} — defaulting to False")
                        notif_num = False
                    print(f"  Notif status: {notif_num}")
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
                                    vship_booking_id = write_notif_in_VShip(eta,1 if notif_num else 0, bookingNum)
                                    make_vship_booking_changes(vship_page, vship_booking_id, eta, bookingNum)
                                    print(f"  [OK]    #{bookingNum}\n")
                                    ok += 1                                    
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} - Note Write Error, Email Still Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            except Exception as exc:
                                write2FileFail(f"[ERROR] #{bookingNum} - QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                failed += 1
                                continue
                        else:
                            write2FileFail(f"[SKIP] #{bookingNum} - not found in QuickBooks")
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
                                    vship_booking_id = write_notif_in_VShip(eta, 0, bookingNum)
                                    make_vship_booking_changes(vship_page, vship_booking_id, eta, bookingNum)
                                    print(f"  [OK]    #{bookingNum}\n")
                                    ok += 1                                    
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} - Note Write Error, Email Still Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            except Exception as exc:
                                write2FileFail(f"[ERROR] #{bookingNum} - QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                failed += 1     
                                continue                   
                    else:
                        write2FileFail(f"[ERROR] #{bookingNum} - ETA not found")
                        failed += 1
                        continue
            elif (bookingNum[-1].lower() == "a"):
                if bookingNum[-2:].lower() == "aa":
                    print(f"Booking {bookingNum} has both Notif #1 and Notif #2. Skipping invoice update and sending to Ben.")
                    write2BFile(bookingNum)
                    continue
                elif re.search(r"(?i)[^a]a$", bookingNum):
                    inWindow, eta = carrierIDthenETAcheck(bookingNum[:-1].strip(), pw)
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
                                        vship_booking_id = write_notif_in_VShip(eta, 1 if notif_num else 0, bookingNum[:-1])
                                        make_vship_booking_changes(vship_page, vship_booking_id, eta,bookingNum)
                                        print(f"  [OK]    #{bookingNum}\n")
                                        ok += 1                                    
                                    except Exception as exc:
                                        write2FileFail(f"[ERROR] #{bookingNum} - Note Write Error, Email Still Sent\n{exc}\n")
                                        failed += 1
                                        continue
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} - QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                    failed += 1
                                    continue
                            else:
                                write2FileFail(f"[SKIP] #{bookingNum} - not found in QuickBooks")
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
                                        vship_booking_id = write_notif_in_VShip(eta, 0, bookingNum)
                                        make_vship_booking_changes(vship_page, vship_booking_id, eta, bookingNum)
                                        print(f"  [OK]    #{bookingNum}\n")
                                        ok += 1                                    
                                    except Exception as exc:
                                        write2FileFail(f"[ERROR] #{bookingNum} - Note Write Error, Email Still Sent\n{exc}\n")
                                        failed += 1
                                        continue
                                except Exception as exc:
                                    write2FileFail(f"[ERROR] #{bookingNum} - QB Invoice Processing Error, No Email Sent\n{exc}\n")
                                    failed += 1      
                                    continue                  
                        else:
                            write2FileFail(f"[ERROR] #{bookingNum} - ETA not found")
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