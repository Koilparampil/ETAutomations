"""
Maersk Track & Trace ETA lookup.

Maersk's public tracking is protected by Akamai Bot Manager. The
`akamai-bm-telemetry` header and the `_abck` / `bm_sz` cookies that Akamai
requires CANNOT be hand-crafted — they are produced by a JavaScript sensor
that Akamai injects into the page and that scores real browser behaviour.
So, exactly like the MSC flow, we load the real tracking page in a Chromium
browser first (which runs that sensor automatically) and THEN fire the
tracking API call through `context.request`, which inherits the browser's
cookies and headers (including whatever Akamai populated).

⚠️  CONFIRM AGAINST DEVTOOLS:
    The API_URL endpoint and the JSON paths used in `_extract_eta` below are
    best-effort placeholders for Maersk's Track & Trace API. Capture a real
    lookup in Chrome DevTools → Network (the same way the MSC GraphQL query
    was captured) and adjust API_URL / the parsing block if they differ.
    On failure the error messages print the raw payload to help you map it.
"""
from datetime import datetime, timedelta
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


def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass


def _extract_eta(data, booking_num: str) -> Timestamp | None:
    """
    Pull the estimated arrival date out of Maersk's tracking payload.

    Maersk nests the schedule under transport legs/events and the exact key
    path can vary by response. Rather than hard-code a fragile path, we walk
    the whole payload collecting any field that looks like an arrival ETA
    (key contains 'eta', or both 'estim' and 'arriv') whose value parses as a
    date, then return the LATEST one (the final destination arrival).

    Replace this with the exact DevTools-confirmed path once known.
    """
    candidates: list[Timestamp] = []

    def _walk(node, key_hint=""):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, str(k).lower())
        elif isinstance(node, list):
            for item in node:
                _walk(item, key_hint)
        else:
            looks_like_eta = (
                "eta" in key_hint
                or ("estim" in key_hint and "arriv" in key_hint)
                or "estimatedarrival" in key_hint
            )
            if looks_like_eta and node:
                try:
                    ts = pd.to_datetime(node)
                    candidates.append(ts)
                    print(f"  [Maersk] Candidate ETA field '{key_hint}' = {node} → {ts.date()}")
                except (ValueError, TypeError):
                    pass

    _walk(data)

    if not candidates:
        top_keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
        raise ValueError(
            f"No ETA-looking field found in Maersk payload for booking {booking_num}. "
            f"Top-level keys: {top_keys}. "
            "Inspect the response in DevTools and update _extract_eta()."
        )

    final_eta = max(candidates)
    print(f"  [Maersk] Selected final ETA (latest of {len(candidates)} candidate(s)): {final_eta.date()}")
    return final_eta


def checkingMaersk(booking_num: str, pw: Playwright) -> Timestamp | None:
    print(f"  [Maersk] Looking up ETA for booking {booking_num}...")
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(user_agent=USER_AGENT)
    page = context.new_page()

    # Load the tracking page so Akamai's bot-manager sensor runs and
    # populates the akamai-bm-telemetry header + _abck / bm_sz cookies.
    print(f"  [Maersk] Loading tracking page to generate Akamai telemetry...")
    page.goto(f"{TRACKING_PAGE}{booking_num}", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)  # give the Akamai sensor time to run

    print(f"  [Maersk] Calling Track & Trace API for {booking_num}...")
    resp = context.request.get(
        f"{API_URL}/{booking_num}",
        params={"operator": "MAEU"},
        headers={
            "referer": "https://www.maersk.com/",
            "accept": "application/json",
            "sec-ch-ua": '"Chromium";v="143", "Not A(Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": USER_AGENT,
            "content-type": "application/json",
        },
    )

    if not resp.ok:
        # A 403 here almost always means Akamai blocked the request — the
        # telemetry didn't validate. Increase the wait above, or interact
        # with the page (scroll/click) before calling so more signals fire.
        browser.close()
        raise RuntimeError(
            f"Failed to get Maersk tracking info (likely Akamai block): "
            f"{resp.status} {resp.text()[:300]}"
        )

    print(f"  [Maersk] API responded OK — parsing for ETA...")
    data = resp.json()
    event_date = _extract_eta(data, booking_num)

    browser.close()
    print(
        f"  [Maersk] Browser closed. Returning ETA: "
        f"{event_date.date() if event_date is not None else 'None'}"
    )
    return event_date


if __name__ == "__main__":
    try:
        with sync_playwright() as p:
            # Replace with a real Maersk booking number (pattern: 2 + 8 digits)
            print(checkingMaersk("230000000", p))
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)
