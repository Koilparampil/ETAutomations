from datetime import datetime, timedelta
import os
from pathlib import Path

from playwright.sync_api import Playwright, sync_playwright
import pandas as pd
from pandas import Timestamp
import traceback
import sys

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)

# Public tracking page — loading this runs Akamai's sensor script so the
# subsequent API call carries valid akamai-bm-telemetry / _abck cookies.
TRACKING_PAGE = "https://www.maersk.com/tracking/"
# Track & Trace API the site calls under the hood. Confirm via DevTools.
API_URL = "https://api.maersk.com/synergy/tracking"
CLIENT_ID = os.getenv('MAERSK_CLIENT_ID') if not os.getenv('MAERSK_CLIENT_ID')==None else ""

def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass


def checkingMaersk(booking_num: str, pw: Playwright) -> Timestamp | None:
    print(f"  [Maersk] Looking up ETA for booking {booking_num}...")
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(user_agent=USER_AGENT)
    page = context.new_page()

    page.goto(f"{TRACKING_PAGE}{booking_num}", wait_until="domcontentloaded")
    page.wait_for_timeout(300)

    print(f"  [Maersk] responded OK — parsing for ETA...")
    try:
        event_date = page.locator('[data-test="container-eta"]').locator("slot.sublabel[name='sublabel']").text_content()
    except TimeoutError as e:
        raise RuntimeError(f"Failed to get Maersk tracking info: {e}")
    try:
        real_date = pd.Timestamp(datetime.strptime(event_date, "%d %b %Y  %H:%M")) if event_date is not None else None
    except ValueError as e:
        raise ValueError(f"No ETA event found for booking {booking_num}. Can't determine ETA.\n {e}")
    browser.close()
    print(
        f"  [Maersk] Browser closed. Returning ETA: "
        f"{real_date.strftime("%m/%d/%Y") if real_date is not None else 'None'}"
    )
    return real_date


if __name__ == "__main__":
    try:
        with sync_playwright() as p:
            # Replace with a real Maersk booking number (pattern: 2 + 8 digits)
            checkingMaersk("267546627", p)
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)
