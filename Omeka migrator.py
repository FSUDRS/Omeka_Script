import requests
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_SOURCE_API = "https://english3.fsu.edu/fsucardarchive/api"
DEFAULT_DEST_API = "https://fsucardarchive.create.fsu.edu/api"

try:
    with open("known_identifiers.json", "r", encoding="utf-8") as f:
        EXPORTED_IDENTIFIERS = set(json.load(f))
except FileNotFoundError:
    EXPORTED_IDENTIFIERS = set()

def map_metadata_to_omeka_s(classic_data):
    element_texts = classic_data.get("element_texts", [])
    omeka_s_data = {}
    for field in element_texts:
        element_set = field.get("element_set", {}).get("name")
        element_name = field.get("element", {}).get("name")
        text_value = field.get("text")
        if element_set == "Dublin Core":
            key = f"dcterms:{element_name.lower()}"
            if key not in omeka_s_data:
                omeka_s_data[key] = []
            omeka_s_data[key].append({"@value": text_value, "@language": "en"})
    return omeka_s_data

def fetch_classic_item(source_base, item_id):
    url = f"{source_base}/items/{item_id}"
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_file_urls(item_data):
    file_urls = []
    files = item_data.get("files", [])
    for file in files:
        if isinstance(file, dict):
            url = file.get("file_urls", {}).get("original") or file.get("file")
        elif isinstance(file, str):
            url = file
        else:
            url = None
        if url:
            file_urls.append(url)
    return file_urls

def get_auth_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    

def check_duplicate_item(dest_base, api_key, identifier):
    if identifier in EXPORTED_IDENTIFIERS:
        return True

    url = f"{dest_base}/items"
    params = {"per_page": 1000, "sort_by": "id", "sort_order": "desc"}
    headers = get_auth_headers(api_key)
    response = requests.get(url, params=params, headers=headers, verify=False)
    if response.status_code == 200:
        items = response.json()
        for item in items:
            for value in item.get("dcterms:identifier", []):
                if value.get("@value") == identifier:
                    return True
    return False

def create_item_omeka_s(dest_base, api_key, metadata):
    url = f"{dest_base}/items"
    response = requests.post(url, headers=get_auth_headers(api_key), data=json.dumps(metadata), verify=False)
    print(f"DEBUG: {response.status_code} - {response.text}")
    if response.status_code == 201:
        return response.json().get("o:id")
    return None

def upload_media_to_item(dest_base, api_key, file_url, item_id):
    media_url = f"{dest_base}/media"
    data = {
        "o:item": {"o:id": item_id},
        "o:source": file_url
    }
    response = requests.post(media_url, data=data, headers=get_auth_headers(api_key), verify=False)
    return response.status_code == 201

def save_known_identifier(identifier):
    EXPORTED_IDENTIFIERS.add(identifier)
    with open("known_identifiers.json", "w", encoding="utf-8") as f:
        json.dump(list(EXPORTED_IDENTIFIERS), f, indent=2)

class OmekaMigratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Omeka Classic → Omeka S Migrator")

        tk.Label(root, text="Source Omeka Classic API URL:").grid(row=0, column=0, sticky="w")
        self.source_entry = tk.Entry(root, width=50)
        self.source_entry.insert(0, DEFAULT_SOURCE_API)
        self.source_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(root, text="Destination Omeka S API URL:").grid(row=1, column=0, sticky="w")
        self.dest_entry = tk.Entry(root, width=50)
        self.dest_entry.insert(0, DEFAULT_DEST_API)
        self.dest_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(root, text="API Key:").grid(row=2, column=0, sticky="w")
        self.api_key_entry = tk.Entry(root, show="*", width=50)
        self.api_key_entry.grid(row=2, column=1, sticky="w", padx=5)

        tk.Label(root, text="Item ID Range or List (e.g., 100-102,110):").grid(row=3, column=0, sticky="w")
        self.range_entry = tk.Entry(root, width=25)
        self.range_entry.grid(row=3, column=1, sticky="w", padx=5)

        self.dry_run = tk.BooleanVar()
        self.dry_check = tk.Checkbutton(root, text="Dry Run (don't upload)", variable=self.dry_run)
        self.dry_check.grid(row=4, column=1, sticky="w", padx=5)

        self.preview_btn = tk.Button(root, text="Preview Metadata", command=self.preview_metadata)
        self.preview_btn.grid(row=5, column=0, pady=10)

        self.migrate_btn = tk.Button(root, text="Migrate Range", command=self.migrate_range)
        self.migrate_btn.grid(row=5, column=1, pady=10)

        self.log_output = scrolledtext.ScrolledText(root, width=100, height=20)
        self.log_output.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

        self.log_output.tag_config("success", foreground="green")
        self.log_output.tag_config("fail", foreground="red")
        self.log_output.tag_config("info", foreground="blue")

    def preview_metadata(self):
        self.log_output.delete(1.0, tk.END)
        ids = self.parse_id_range()
        source_url = self.source_entry.get()
        for item_id in ids:
            classic_data = fetch_classic_item(source_url, item_id)
            if classic_data:
                mapped = map_metadata_to_omeka_s(classic_data)
                self.log_output.insert(tk.END, f"Item {item_id} mapped:\n", "info")
                self.log_output.insert(tk.END, json.dumps(mapped, indent=2) + "\n\n")
            else:
                self.log_output.insert(tk.END, f"Item {item_id} not found or inaccessible.\n", "fail")

    def migrate_range(self):
        self.log_output.delete(1.0, tk.END)
        ids = self.parse_id_range()
        source_url = self.source_entry.get()
        dest_url = self.dest_entry.get()
        api_key = self.api_key_entry.get()

        for item_id in ids:
            classic_data = fetch_classic_item(source_url, item_id)
            if not classic_data:
                self.log_output.insert(tk.END, f"Item {item_id} not found. Skipping.\n", "fail")
                continue

            mapped_metadata = map_metadata_to_omeka_s(classic_data)
            identifier_entries = mapped_metadata.get("dcterms:identifier", [])
            identifier = identifier_entries[0]["@value"] if identifier_entries else (
                f"Fallback:{item_id}-{classic_data.get('added', 'no-date')}"
            )

            if identifier and check_duplicate_item(dest_url, api_key, identifier):
                self.log_output.insert(tk.END, f"Item {item_id} (identifier: {identifier}) already exists. Skipping.\n", "info")
                continue

            file_urls = fetch_file_urls(classic_data)

            if self.dry_run.get():
                self.log_output.insert(tk.END, f"[Dry Run] Would create item {item_id} with metadata and {len(file_urls)} media file(s).\n", "info")
                continue

            item_id_created = create_item_omeka_s(dest_url, api_key, mapped_metadata)
            if item_id_created:
                self.log_output.insert(tk.END, f"Item {item_id} created as new item ID {item_id_created} in Omeka S.\n", "success")
                save_known_identifier(identifier)
                for file_url in file_urls:
                    success = upload_media_to_item(dest_url, api_key, file_url, item_id_created)
                    if success:
                        self.log_output.insert(tk.END, f" → Media uploaded: {file_url}\n", "success")
                    else:
                        self.log_output.insert(tk.END, f" → Failed to upload media: {file_url}\n", "fail")
            else:
                self.log_output.insert(tk.END, f"Failed to create item {item_id} in Omeka S.\n", "fail")

    def parse_id_range(self):
        try:
            raw = self.range_entry.get().strip()
            parts = re.split(r'[;,\s]+', raw)
            ids = []
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    ids.extend(range(start, end + 1))
                else:
                    ids.append(int(part))
            return ids
        except Exception as e:
            messagebox.showerror("Invalid Range", f"Please enter a valid ID list like 100-102,105,110\n\nError: {e}")
            return []

if __name__ == "__main__":
    root = tk.Tk()
    app = OmekaMigratorApp(root)
    root.mainloop()
