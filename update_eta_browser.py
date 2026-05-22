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
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

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
QBO_WEB     = "https://app.qbo.intuit.com"
SESSION_DIR = Path(".qbo_browser_session")


# ── REST API — invoice lookup only ─────────────────────────────────────────────
def get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if (new_rt := data.get("refresh_token")) and new_rt != REFRESH_TOKEN:
        print("[warning] Refresh token rotated — update QB_REFRESH_TOKEN in .env")
    return data["access_token"]


def get_invoice_by_number(token: str, doc_number: str) -> dict | None:
    query = f"SELECT * FROM Invoice WHERE DocNumber = '{doc_number}'"
    resp = requests.get(
        f"{BASE_URL}/v3/company/{REALM_ID}/query",
        params={"query": query, "minorversion": MINOR_VER},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])
    return invoices[0] if invoices else None


# ── Browser helpers ────────────────────────────────────────────────────────────
def _wait_for_qbo_app(page, timeout: int = 180_000):
    """Block until QBO app shell loads (not login/auth pages)."""
    if "accounts.intuit.com" in page.url or "/login" in page.url:
        print("\n[browser] Please log in to QuickBooks in the browser window.")
        print("[browser] Waiting up to 3 minutes…")
        page.wait_for_url(f"{QBO_WEB}/**", timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=30_000)
        print("[browser] Logged in — continuing.\n")


def _find_input_by_label(page, label: str, timeout: int = 8_000):
    """
    Locate an input associated with a visible label text.
    Tries aria get_by_label first, then proximity-based locators.
    """
    for locator in [
        page.get_by_label(label, exact=True),
        page.locator(f"input[aria-label='{label}']"),
        page.locator(f"label:has-text('{label}') + div input"),
        page.locator(f"label:has-text('{label}') + input"),
        page.locator(f"[data-automation*='{label.lower()}'] input"),
    ]:
        try:
            locator.first.wait_for(state="visible", timeout=timeout // len([1]))
            return locator.first
        except PWTimeout:
            continue
    raise RuntimeError(
        f"Could not locate '{label}' input on the page. "
        "QBO may have changed its UI — inspect the field in Chrome DevTools "
        "and update the locator in _find_input_by_label()."
    )


def _click_button(page, *names: str, timeout: int = 8_000):
    """Try button names in order, click the first one found."""
    for name in names:
        try:
            btn = page.get_by_role("button", name=name, exact=True)
            btn.wait_for(state="visible", timeout=timeout // len(names))
            btn.click()
            return name
        except PWTimeout:
            continue
    raise RuntimeError(
        f"None of these buttons were found: {names}. "
        "QBO UI may have changed — check the button text in the browser."
    )


# ── Core logic ─────────────────────────────────────────────────────────────────
def process_invoice(page, invoice_id: str, doc_number: str, eta_date: str):
    """Update ETA and send one invoice via the QBO web UI."""
    # QBO displays dates as M/D/YYYY in the US locale
    dt = datetime.strptime(eta_date, "%Y-%m-%d")
    qbo_date = f"{dt.month}/{dt.day}/{dt.year}"

    # ── 1. Open the invoice edit page ─────────────────────────────────────────
    page.goto(f"{QBO_WEB}/app/invoice?txnId={invoice_id}", wait_until="domcontentloaded")
    _wait_for_qbo_app(page)
    page.wait_for_load_state("networkidle", timeout=30_000)

    if "accounts.intuit.com" in page.url:
        raise RuntimeError(
            "Session expired. Delete .qbo_browser_session/ and re-run to log in again."
        )

    # ── 2. Update ETA field ───────────────────────────────────────────────────
    eta_input = _find_input_by_label(page, "ETA")
    eta_input.triple_click()           # select existing value
    eta_input.fill(qbo_date)
    eta_input.press("Tab")             # dismiss any date-picker popup
    page.wait_for_timeout(400)

    # ── 3. Save the invoice ───────────────────────────────────────────────────
    _click_button(page, "Save", "Save and close")
    page.wait_for_load_state("networkidle", timeout=30_000)
    print(f"    Saved  — ETA={eta_date}")

    # ── 4. Open send dialog ───────────────────────────────────────────────────
    _click_button(page, "Review and send", "Send")
    page.wait_for_load_state("networkidle", timeout=20_000)

    # ── 5. Update email subject ───────────────────────────────────────────────
    try:
        subj = page.get_by_label("Subject", exact=True)
        subj.wait_for(state="visible", timeout=5_000)
        subj.triple_click()
        subj.fill(EMAIL_SUBJECT)
        print(f"    Subject set to: {EMAIL_SUBJECT!r}")
    except PWTimeout:
        print("    [note] Subject field not found — QBO default subject will be used.")

    # ── 6. Confirm send ───────────────────────────────────────────────────────
    _click_button(page, "Send email", "Send")
    page.wait_for_load_state("networkidle", timeout=20_000)
    print(f"    Email sent.")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python update_eta_browser.py <invoice_numbers.txt>")

    txt_path = sys.argv[1]
    try:
        with open(txt_path) as fh:
            invoice_numbers = [
                ln.strip() for ln in fh
                if ln.strip() and not ln.strip().startswith("#")
            ]
    except FileNotFoundError:
        sys.exit(f"File not found: {txt_path}")

    if not invoice_numbers:
        sys.exit("Invoice list is empty — nothing to do.")

    while True:
        raw = input("Enter ETA date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            eta_date = raw
            break
        except ValueError:
            print("  Invalid format — please use YYYY-MM-DD.")

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
        page.goto(QBO_WEB, wait_until="domcontentloaded")
        _wait_for_qbo_app(page)

        ok = failed = 0
        print(f"\nProcessing {len(invoices)} invoice(s) with ETA={eta_date}…\n")

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
