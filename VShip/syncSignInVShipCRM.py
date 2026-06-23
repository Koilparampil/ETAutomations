import requests

VSHIP_LOGIN_URL = "https://vship2000-prod-api.azurewebsites.net/api/Auth/login"

def get_access_token(username, password) -> str:
    print(f"  [VShip] Sending login request for user '{username}'...")
    resp = requests.post(VSHIP_LOGIN_URL, json={"username": username, "password": password})
    resp.raise_for_status()
    token = resp.json().get("value", {}).get("token")
    if not token:
        raise ValueError(f"VShip login succeeded but no token in response: {resp.text[:200]}")
    return token


def sign_in_vshipcrm(user, password):
    token = get_access_token(user, password)
    with open('auth_for_VshipCRM.txt', 'w') as f:
        f.write(token)
    print("  [VShip] Token saved to auth_for_VshipCRM.txt")

if __name__ == "__main__":
    print("Signing in to VShipCRM(new)")
    sign_in_vshipcrm("chris@vship2000.com", "V$hipNYC2026CK")