import os

import requests

TOKEN_URL = "https://api.maersk.com/customer-identity/oauth/v2/access_token"
CLIENT_ID = os.getenv('MAERSK_CLIENT_ID') if not os.getenv('MAERSK_CLIENT_ID')==None else ""
CLIENT_ID = CLIENT_ID if CLIENT_ID is not None else ""

CLIENT_SECRET = os.getenv('MAERSK_CLIENT_SECRET') if not os.getenv('MAERSK_CLIENT_SECRET')==None else ""
CLIENT_SECRET = CLIENT_SECRET if CLIENT_SECRET is not None else ""


def sign_in_maersk() -> str:
    headers = {
        "Cache-Control": "no-cache",
        'Consumer-Key': f'{CLIENT_ID}',
        "Content-Type": "application/x-www-form-urlencoded"
    }

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=30)
    response.raise_for_status()

    token_data = response.json()
    access_token = token_data["access_token"]
    expires_in = token_data["expires_in"]

    print("Bearer token:", access_token)
    print("Expires in (seconds):", expires_in)
    return access_token