#!/usr/bin/env python3
"""
QuickBooks Online Invoice Updater
----------------------------------
Reads invoice numbers from a .txt file (one per line), prompts for an ETA date,
then for each invoice:
  1. Fetches the invoice by DocNumber
  2. Sparse-updates the "ETA" custom Date field
  3. Sends the invoice email with the configured subject line

Usage:
    python update_invoices.py invoice_numbers.txt
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Credentials (loaded from .env) ─────────────────────────────────────────────
CLIENT_ID     = os.environ["QB_CLIENT_ID"]
CLIENT_SECRET = os.environ["QB_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["QB_REFRESH_TOKEN"]
REALM_ID      = os.environ["QB_REALM_ID"]

# ── Script-level constants ─────────────────────────────────────────────────────
CUSTOM_FIELD_NAME = "ETA"
EMAIL_SUBJECT     = "Your Invoice Is Ready"   # ← change subject line here

SANDBOX  = os.getenv("QB_SANDBOX", "false").lower() == "true"
BASE_URL = (
    "https://sandbox-quickbooks.api.intuit.com"
    if SANDBOX else
    "https://quickbooks.api.intuit.com"
)
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
MINOR_VER = 73


# ── Authentication ─────────────────────────────────────────────────────────────
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
    new_rt = data.get("refresh_token")
    if new_rt and new_rt != REFRESH_TOKEN:
        print(
            "[warning] Refresh token was rotated. "
            "Update QB_REFRESH_TOKEN in your .env before the next run."
        )
    return data["access_token"]


# ── API helpers ────────────────────────────────────────────────────────────────
def _json_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }


def get_invoice_by_number(token: str, doc_number: str) -> dict | None:
    """Return the first Invoice entity matching doc_number, or None."""
    query = f"SELECT * FROM Invoice WHERE DocNumber = '{doc_number}'"
    resp = requests.get(
        f"{BASE_URL}/v3/company/{REALM_ID}/query",
        params={"query": query, "minorversion": MINOR_VER},
        headers=_json_headers(token),
        timeout=15,
    )
    resp.raise_for_status()
    invoices = resp.json().get("QueryResponse", {}).get("Invoice", [])
    return invoices[0] if invoices else None


def get_custom_field_definition_id(token: str, field_name: str) -> str:
    """
    Fetch the DefinitionId for a named custom field from company Preferences.

    QBO omits custom fields from invoice responses when they have no value,
    so we cannot rely on reading the DefinitionId from the invoice itself.
    The Preferences endpoint always lists every defined custom field.

    QBO uses two naming levels per entry:
      - Top-level Name: internal key, e.g. "sales1" or "udcf_4"
      - Inner CustomField array: contains {"Name": "Name", "StringValue": "<display title>"}
    We match against the display title so callers use the label seen in the UI.
    """
    resp = requests.get(
        f"{BASE_URL}/v3/company/{REALM_ID}/preferences",
        params={"minorversion": MINOR_VER},
        headers=_json_headers(token),
        timeout=15,
    )
    resp.raise_for_status()
    prefs = resp.json().get("Preferences", {})

    sales_prefs = prefs.get("SalesFormsPrefs", {})
    for cf in sales_prefs.get("CustomField", []):
        # 1. Flat match — some QBO versions put the display name at the top level
        if cf.get("Name") == field_name:
            return str(cf["DefinitionId"])

        # 2. Nested match — display name is inside the inner CustomField list
        #    e.g. {"Name": "Name", "StringValue": "ETA", "Type": "StringType"}
        for inner in cf.get("CustomField", []):
            if inner.get("Name") == "Name" and inner.get("StringValue") == field_name:
                return str(cf["DefinitionId"])

    # Neither strategy matched — print the raw structure to help diagnose
    import json
    print("[debug] SalesFormsPrefs.CustomField raw content:")
    print(json.dumps(sales_prefs.get("CustomField", []), indent=2))
    raise ValueError(
        f"Custom field '{field_name}' not found in company Preferences. "
        "Check the debug output above for the actual field names / structure."
    )


def update_invoice_eta(token: str, invoice: dict, date_val: str, definition_id: str) -> dict:
    """
    Sparse-update only the ETA custom field on the invoice.
    Returns the updated invoice entity from QBO.
    """
    payload = {
        "Id":        invoice["Id"],
        "SyncToken": invoice["SyncToken"],
        "sparse":    True,
        "CustomField": [
            {
                "DefinitionId": definition_id,
                "Name":         CUSTOM_FIELD_NAME,
                "Type":         "DateType",
                "DateVal":      date_val,
            }
        ],
    }
    resp = requests.post(
        f"{BASE_URL}/v3/company/{REALM_ID}/invoice",
        params={"minorversion": MINOR_VER},
        json=payload,
        headers=_json_headers(token),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["Invoice"]


def send_invoice(token: str, invoice_id: str, send_to: str) -> None:
    """
    Send the invoice via QBO's send endpoint.
    The EMAIL_SUBJECT constant is passed as the email subject.
    QBO may honour it directly or fall back to the company's default template,
    depending on your QBO plan and minor API version.
    """
    resp = requests.post(
        f"{BASE_URL}/v3/company/{REALM_ID}/invoice/{invoice_id}/send",
        params={"sendTo": send_to, "minorversion": MINOR_VER},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/octet-stream",
            "Accept":        "application/json",
        },
        data=EMAIL_SUBJECT.encode(),
        timeout=15,
    )
    resp.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python update_invoices.py <invoice_numbers.txt>")

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
        sys.exit("Invoice list is empty – nothing to do.")

    # Prompt for ETA date (runtime input)
    while True:
        raw = input("Enter ETA date (YYYY-MM-DD): ").strip()
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            eta_date = raw
            break
        except ValueError:
            print("  Invalid format – please use YYYY-MM-DD.")

    token = get_access_token()

    # Resolve the ETA DefinitionId once — QBO omits blank custom fields from
    # invoice responses, so we can't rely on reading it per-invoice.
    eta_definition_id = get_custom_field_definition_id(token, CUSTOM_FIELD_NAME)
    print(f"\nResolved '{CUSTOM_FIELD_NAME}' → DefinitionId={eta_definition_id}")
    print(f"Processing {len(invoice_numbers)} invoice(s) with ETA={eta_date}…\n")

    ok = failed = 0
    for num in invoice_numbers:
        try:
            invoice = get_invoice_by_number(token, num)
            if invoice is None:
                print(f"  [SKIP]  #{num} – not found in QuickBooks")
                failed += 1
                continue

            send_to = invoice.get("BillEmail", {}).get("Address")
            if not send_to:
                print(f"  [SKIP]  #{num} – no billing email address on invoice")
                failed += 1
                continue

            updated = update_invoice_eta(token, invoice, eta_date, eta_definition_id)
            send_invoice(token, updated["Id"], send_to)
            print(f"  [OK]    #{num} → ETA set to {eta_date}, sent to {send_to}")
            ok += 1

        except requests.HTTPError as exc:
            body = exc.response.text[:300]
            print(f"  [ERROR] #{num} – HTTP {exc.response.status_code}: {body}")
            failed += 1
        except ValueError as exc:
            print(f"  [ERROR] #{num} – {exc}")
            failed += 1

    print(f"\nDone: {ok} succeeded, {failed} failed/skipped.")


if __name__ == "__main__":
    main()
