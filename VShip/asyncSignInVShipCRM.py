from playwright.async_api import async_playwright
import requests

VSHIP_LOGIN_URL = "https://vship2000-prod-api.azurewebsites.net/api/Auth/login"

def get_access_token(username, password) -> str:
    resp = requests.post(VSHIP_LOGIN_URL,
                         json = {"username":username,"password":password})
    return resp.json().get("value").get("token")
if __name__ == "__main__":
    print("Signing in to VShipCRM(new)")

