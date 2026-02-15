#!/usr/bin/env python3
"""Test Enlighten login flow."""

import requests
import json
from urllib.parse import urlencode

session = requests.Session()

# Browser-like headers to avoid 401 rejection
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://enlighten.enphaseenergy.com',
    'Referer': 'https://enlighten.enphaseenergy.com/login',
})

# Test login
login_url = "https://enlighten.enphaseenergy.com/login/login.json"
login_data = {
    "user[email]": "dani.apanoia@gmail.com",
    "user[password]": "3!7ZUr5ba@85KjQ"
}

# Explicitly URL-encode the payload
encoded_payload = urlencode(login_data)

print("Testing login to:", login_url)
print("Data:", {k: "***" if "password" in k else v for k, v in login_data.items()})

response = session.post(
    login_url,
    data=encoded_payload,
    timeout=10,
    allow_redirects=True
)

print("\nLogin Response:")
print(f"Status: {response.status_code}")
print(f"Cookies: {dict(session.cookies)}")

if response.status_code != 200:
    print(f"Login failed with status {response.status_code}")
    print(f"Response text (first 500 chars): {response.text[:500]}")
    exit(1)

# Extract session_id from login response
login_response = response.json()
session_id = login_response.get("session_id")
print(f"Login successful, session_id: {session_id}")

if not session_id:
    print("No session_id in login response")
    print(f"Response: {login_response}")
    exit(1)

# Step 2: Fetch token from entrez.enphaseenergy.com/tokens
user = "dani.apanoia@gmail.com"
envoy_serial = "122140070291"
token_url = "https://entrez.enphaseenergy.com/tokens"

token_payload = json.dumps({
    "session_id": session_id,
    "serial_num": envoy_serial,
    "envoy_serial": envoy_serial,
    "username": user,
})

print(f"\n\nFetching token from: {token_url}")
token_response = session.post(
    token_url,
    data=token_payload,
    headers={"Content-Type": "application/json"},
    timeout=10,
)
print(f"Token Response Status: {token_response.status_code}")

if token_response.status_code != 200:
    print(f"Token fetch failed: {token_response.text[:500]}")
    exit(1)

# The response should be the JWT token
token = token_response.text.strip()
parts = token.split('.')
print(f"\nToken parts: {len(parts)}")

if len(parts) == 3:
    print("✅ Valid JWT format!")
    print(f"Token: {token[:80]}...")
else:
    print("❌ Not a JWT")
    print(f"Response: {token[:200]}")
