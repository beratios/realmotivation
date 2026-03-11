#!/usr/bin/env python3
"""
YouTube OAuth Setup Helper
Run this ONCE locally to get your refresh token.
Then add it as YOUTUBE_REFRESH_TOKEN in GitHub Secrets.

Usage:
  pip install google-auth-oauthlib
  python scripts/setup_youtube_auth.py
"""

import os
import json

def setup_oauth():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ Run: pip install google-auth-oauthlib")
        return

    CLIENT_ID     = input("Enter your YouTube CLIENT_ID: ").strip()
    CLIENT_SECRET = input("Enter your YouTube CLIENT_SECRET: ").strip()

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=8080)

    print("\n✅ Authentication successful!")
    print("\nAdd these to your GitHub Secrets:")
    print(f"  YOUTUBE_CLIENT_ID     = {CLIENT_ID}")
    print(f"  YOUTUBE_CLIENT_SECRET = {CLIENT_SECRET}")
    print(f"  YOUTUBE_REFRESH_TOKEN = {credentials.refresh_token}")

if __name__ == "__main__":
    setup_oauth()
