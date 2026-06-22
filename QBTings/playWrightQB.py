import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Browser helpers ────────────────────────────────────────────────────────────
def _is_on_auth_page(page) -> bool:
    return any(h in page.url for h in ("accounts.intuit.com", "login.intuit.com", "/login"))


def _wait_for_qbo_app(page, timeout: int = 180_000):
    """Block until QBO app shell loads (not login/auth pages)."""
    if _is_on_auth_page(page):
        print("\n[browser] Please log in to QuickBooks in the browser window.")
        print("[browser] Waiting up to 3 minutes…")
        # "**/app/**" matches any URL that has /app/ in the path,
        # e.g. https://qbo.intuit.com/app/homepage
        page.wait_for_url("**/app/homepage?**", timeout=timeout)
        page.wait_for_load_state("load", timeout=15_000)
        print("[browser] Logged in - continuing.\n")


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
        "QBO may have changed its UI - inspect the field in Chrome DevTools "
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
        "QBO UI may have changed - check the button text in the browser."
    )