from playwright.async_api import async_playwright, TimeoutError
import time
import os
from dotenv import load_dotenv
import traceback
import asyncio
import sys

TRACKING_PAGE = "https://www.mymsc.com/myMSC/tracking"

def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass
    
def on_request(req):
        print("REQ", req.method, req.url)
        print("Headers:", req.headers)
        print('\n')
        
async def on_response(resp):
    # global pdf_url
    # ct = resp.headers.get("content-type", "")
    # if "application/pdf" in ct.lower() and resp.ok:
    #     pdf_url = resp.url
    print("RESP", resp.status)
    print("Headers:", resp.headers)
    print("Data:", await resp.json())
    print('\n')
        
async def checkingMSC(booking_num):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context =  await browser.new_context(
            storage_state="auth_for_MSC.json"
        )
        page = await context.new_page()
        context.on("request", on_request)
        context.on("response", on_response)
        await page.goto(TRACKING_PAGE, wait_until="domcontentloaded")
        print("At the Tracking Page now")
        await page.locator('input[type="radio"][name="ReferenceType"][value="Booking Number"]').check()
        await page.locator('input[name="ReferenceNumber"]').fill(f"{booking_num}")
        await page.locator("button[type='submit']").nth(1).click()
        input("waiting....")
    return 0


if __name__ == "__main__":
    try:
        asyncio.run(checkingMSC("EBKG15361757"))
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)