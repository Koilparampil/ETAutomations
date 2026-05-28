from playwright.async_api import async_playwright, TimeoutError
import time
import os
from dotenv import load_dotenv
import traceback
import asyncio
import sys
import json

load_dotenv()
LOGIN_URL = os.getenv('LOGIN_URL') if not os.getenv('LOGIN_URL')==None else ""
login_url = LOGIN_URL if LOGIN_URL is not None else ""

HOME_PAGE = os.getenv('HOME_PAGE') if not os.getenv('HOME_PAGE')==None else ""
home_page = HOME_PAGE if HOME_PAGE is not None else ""

HOME_PAGE = os.getenv('HOME_PAGE') if not os.getenv('HOME_PAGE')==None else ""
home_page = HOME_PAGE if HOME_PAGE is not None else ""

API_TOKEN_URL = "https://www.mymsc.com/myMSC/token/getaccesstoken"



def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass


async def async_sign_in_MSC(username, password):

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(login_url)
        print(await page.title())
        try:
            await page.locator("#onetrust-accept-btn-handler").click(timeout=300)
        except:
            pass

        # Wait long enough for slow page loads before filling username
        await page.wait_for_selector("#UserName", timeout=10000)

        # Use press_sequentially instead of fill — fill() does not fire the
        # React onChange event on this site, so the framework sees the field
        # as empty even though the DOM value is set. press_sequentially
        # dispatches real keystrokes which trigger React state correctly.
        username_input = page.locator("#UserName")
        await username_input.click()
        await username_input.press_sequentially(username, delay=50)

        await page.evaluate("nextClicked()")

        # Wait for the password field to appear — correct signal that
        # nextClicked() finished its page transition.
        await page.wait_for_selector("#password", timeout=10000)
        print(await page.title())

        password_input = page.locator("#password")
        await password_input.click()
        await password_input.press_sequentially(password, delay=50)

        await page.click("button[type='submit']")
        try:
            await page.wait_for_selector(
                "button.msc-header__nav-item--last",
                timeout=10000
            )
            await page.locator("button.msc-header__nav-item--last:has(span.icon-user-black)").click()
            await page.context.storage_state(path="auth_for_MSC.json")
            print("Signed in and saved authentication state for MSC.")
        except TimeoutError:
            pass
        gettingAPIToken = await context.request.get(
            API_TOKEN_URL,
            headers = {
                "referer": "https://www.mymsc.com/myMSC/welcome",
                "mymsc-user-email": "chris@vship2000.com",
                "mymsc-user-roles": "Customer",
                'sec-ch-ua': '"Chromium";v="143", "Not A(Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                'content-type': "application/json",
            }
        )
        if gettingAPIToken.ok:
            with open("MSCauthToken.json",'w') as f:
                json.dump(await gettingAPIToken.json(), f)
        else:
            print("failed")
        await browser.close()

        
if __name__ == "__main__":
    try:
        load_dotenv()
        USERNAME = os.getenv('MSC_USER_NAME') if not os.getenv('MSC_USER_NAME')==None else ""
        user_name = USERNAME if USERNAME is not None else ""
        PASSWORD = os.getenv('MSC_PASSWORD') if not os.getenv('MSC_PASSWORD')==None else ""
        password = PASSWORD if PASSWORD is not None else ""
        print(f"[debug] USERNAME from .env: {user_name!r}")
        asyncio.run(async_sign_in_MSC(user_name, password))
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)
