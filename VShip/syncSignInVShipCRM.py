import requests

VSHIP_LOGIN_URL = "https://vship2000-prod-api.azurewebsites.net/api/Auth/login"

def get_access_token(username, password) -> str:
    resp = requests.post(VSHIP_LOGIN_URL,
                         json = {"username":username,"password":password})
    return resp.json().get("value").get("token")


def sign_in_vshipcrm(user, password):
    with open('auth_for_VshipCRM.txt', 'w') as f:
        token = get_access_token(user, password)
        f.write(token)

if __name__ == "__main__":
    print("Signing in to VShipCRM(new)")
    sign_in_vshipcrm("user", "password")