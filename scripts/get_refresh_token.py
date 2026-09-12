"""
Generate an OAuth2 refresh token for the Google Ads API.

Reads GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET from .env (a
"Desktop app" OAuth client created in Google Cloud Console), opens a browser
for consent, then prints the refresh token. Paste it into .env as
GOOGLE_ADS_REFRESH_TOKEN.

Usage:
  python3 scripts/get_refresh_token.py
"""

import os
import sys

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
if not client_id or not client_secret:
    print("GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET must be set in .env")
    sys.exit(1)

CLIENT_CONFIG = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

SCOPES = ["https://www.googleapis.com/auth/adwords"]

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
flow.run_local_server(port=int(os.environ.get("OAUTH_LOCAL_PORT", "9090")))

print("\n" + "=" * 60)
print("YOUR REFRESH TOKEN:")
print("=" * 60)
print(flow.credentials.refresh_token)
print("=" * 60)
print("\nCopy the refresh token above into .env as GOOGLE_ADS_REFRESH_TOKEN.")
