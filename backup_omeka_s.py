import requests
from requests.auth import HTTPBasicAuth
import json
import urllib3

# Disable warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OMEKA_S_API_URL = "https://fsucardarchive.create.fsu.edu/api"
USERNAME = "fsucardarchiver"
PASSWORD = "spring2025"
OUTPUT_FILE = "omeka_s_backup.json"

def fetch_all_items(base_url, auth):
    all_items = []
    page = 1
    while True:
        response = requests.get(
            f"{base_url}/items",
            params={"page": page, "per_page": 100},
            auth=auth,
            verify=False
        )
        if response.status_code != 200:
            print(f"❌ Error fetching page {page}")
            break
        page_items = response.json()
        if not page_items:
            break
        all_items.extend(page_items)
        print(f"✅ Fetched page {page} with {len(page_items)} items")
        page += 1
    return all_items

def main():
    auth = HTTPBasicAuth(USERNAME, PASSWORD)
    print("📦 Starting Omeka S backup...")
    items = fetch_all_items(OMEKA_S_API_URL, auth)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    print(f"✅ Backup completed. {len(items)} items saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
