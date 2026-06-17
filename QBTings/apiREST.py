import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

load_dotenv(override=True)
# ── Credentials ────────────────────────────────────────────────────────────────
CLIENT_ID     = os.environ["QB_CLIENT_ID"]
CLIENT_SECRET = os.environ["QB_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["QB_REFRESH_TOKEN"]
REALM_ID      = os.environ["QB_REALM_ID"]
SANDBOX   = os.getenv("QB_SANDBOX", "false").lower() == "true"
BASE_URL  = (
    "https://sandbox-quickbooks.api.intuit.com"
    if SANDBOX else
    "https://quickbooks.api.intuit.com"
)
TOKEN_URL   = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
MINOR_VER   = 73
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
