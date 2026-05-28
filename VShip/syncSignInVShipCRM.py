from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
import requests

VSHIP_LOGIN_URL = "https://vship2000-prod-api.azurewebsites.net/api/Auth/login"
OLD_VSHIP_LOGIN_URL = "https://vshipcrm.com/Home/Index"

def get_access_token(username, password) -> str:
    resp = requests.post(VSHIP_LOGIN_URL,
                         json = {"username":username,"password":password})
    return resp.json().get("value").get("token")


def sign_in_vshipcrm(user, password):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        
        page.goto(VSHIP_LOGIN_URL)
        page.fill('input[name="LOGIN_NAME"]', user)
        page.fill('input[name="PASSWORD"]', password)
        page.click("button[type='submit']")
        
        page.wait_for_load_state("networkidle")
        page.context.storage_state(path="auth_for_VShipCRM.json")
        print("Signed in and saved authentication state.")
        browser.close()
if __name__ == "__main__":
    print("Signing in to VShipCRM(new)")

