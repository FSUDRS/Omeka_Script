import requests
import json

# Omeka Classic API endpoint (adjusted for destination)
DEST_API = "https://fsucardarchive.create.fsu.edu/api/items"
PER_PAGE = 50

# 🔐 Your login credentials for the destination site
AUTH = ("fsucardarchiver", "spring2025")

def export_identifiers():
    page = 1
    all_identifiers = []

    while True:
        url = f"{DEST_API}?page={page}&per_page={PER_PAGE}"
        response = requests.get(url, auth=AUTH, verify=False)
        if response.status_code != 200:
            print("Error fetching page", page, ":", response.status_code)
            break

        items = response.json()
        if not items:
            break

        for item in items:
            for elem in item.get("element_texts", []):
                if elem.get("element", {}).get("name") == "Identifier":
                    all_identifiers.append(elem.get("text"))

        page += 1

    with open("known_identifiers.json", "w", encoding="utf-8") as f:
        json.dump(all_identifiers, f, indent=2)

    print(f"✅ Exported {len(all_identifiers)} identifiers.")

export_identifiers()
