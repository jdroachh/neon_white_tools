import requests
import json

# ── Config ─────────────────────────────────────────────────────────────────
SHEET_ID = "1awYTwm47wF8CjriTiYJRAtNI4SS5tVdyCpEa40hN0S0"
TAB      = "Test Sheet"
RANGE    = f"'{TAB}'!B1:B5"

TEST_VALUES = [
    ["I like pie"],
    ["123"],
    ["Hello World"],
    ["Neon White"],
    ["Test entry 5"],
]

# ── Test 1: No auth at all ─────────────────────────────────────────────────
print("=" * 50)
print("TEST 1: Write with no authentication")
print("=" * 50)

url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{RANGE}?valueInputOption=USER_ENTERED"
r = requests.put(url, json={"values": TEST_VALUES})
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")

if r.status_code == 200:
    print("\n✓ SUCCESS — write works with no auth at all!")
    print("No API key needed.")
else:
    print("\n✗ Failed without auth — trying with API key...\n")

    # ── Test 2: With API key ───────────────────────────────────────────────
    print("=" * 50)
    print("TEST 2: Write with API key")
    print("=" * 50)
    print()

    API_KEY = input("Paste your Google API key and press Enter: ").strip()

    if API_KEY:
        url_with_key = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{RANGE}"
            f"?valueInputOption=USER_ENTERED&key={API_KEY}"
        )
        r2 = requests.put(url_with_key, json={"values": TEST_VALUES})
        print(f"\nStatus: {r2.status_code}")
        print(f"Response: {r2.text[:300]}")

        if r2.status_code == 200:
            print("\n✓ SUCCESS — write works with API key!")
            print("Users will need to provide their own API key.")
        else:
            print("\n✗ Failed with API key too.")
            print("Check that:")
            print("  1. The Sheets API is enabled in your GCP project")
            print("  2. The sheet is set to 'Anyone with the link can edit'")
            print("  3. The API key has no IP or referrer restrictions")
    else:
        print("No API key entered — skipping test 2.")
