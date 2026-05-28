from playwright.async_api import async_playwright
import playwright.async_api
import os
from VShip.asyncSignInVShipCRM import async_sign_in_vshipcrm
import re

VSHIP_LOGIN_URL = "https://vshipcrm.com/Home/Index"

async def lookup_customer_info(booking_no: str|None) -> tuple[str|None, str|None, bool|int]:
    if booking_no:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                storage_state="auth_for_VshipCRM.json"
            )
            page = await context.new_page()
            
            try:
                await page.goto("https://vshipcrm.com/Home/GlobalSearch")
                print("At the Booking Page now")
                await page.fill('input[name="Booking_No"]', booking_no)
                await page.evaluate("reInitGrid()")
                await page.wait_for_load_state("networkidle")
            except playwright.async_api.TimeoutError:
                print("Sign in messed up: trying to sign in again")
                VSHIP_username = os.getenv('USER_NAME') if not os.getenv('USER_NAME')==None else ""
                VSHIP_password = os.getenv('EMAIL_PASSWORD') if not os.getenv('EMAIL_PASSWORD')==None else ""
                await async_sign_in_vshipcrm(VSHIP_username, VSHIP_password)
                
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context(
                    storage_state="auth_for_VshipCRM.json"
                )
                page = await context.new_page()                
                await page.goto("https://vshipcrm.com/Home/GlobalSearch")
                print("At the Booking Page now")
                await page.fill('input[name="Booking_No"]', booking_no)
                await page.evaluate("reInitGrid()")
                await page.wait_for_load_state("networkidle")        
            print("grid loaded now")
            row = page.locator("tr").filter(
                has=page.locator("td").filter(
                has_text=re.compile(rf"^{re.escape(booking_no)}$")
                )
            )
            await row.locator('a[title="Edit"][href^="/Booking/ViewBooking/"]').click()
            await page.wait_for_load_state("networkidle")  
            
            print("At the View Page now")
            email = await page.locator("strong:has-text('Email')").locator("xpath=../following-sibling::div//span").inner_text()
            email = email.strip() if email else None
            
            customer_name = await page.locator("strong:has-text('Customer Name')").locator("xpath=../following-sibling::div//span").inner_text()
            customer_name =customer_name.strip() if customer_name else None
            
            all_comments = await page.locator("article.comments").all_inner_texts()
            full_text = " ".join(all_comments).lower()
            if "notif #1" in full_text:
                if "notif #2" in full_text:
                    notifPresence = 2
                notifPresence =True
            else:
                notifPresence = False
    else:
        print("No booking number provided")
        return None, None, False
    return email, customer_name, notifPresence