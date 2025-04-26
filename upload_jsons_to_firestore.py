import os
import json
import zipfile
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore

# --- CONFIGURATION ---
zip_path = "/Users/Chloe/Downloads/JSONs-20250424T060428Z-001.zip"
firebase_key_path = "/Users/Chloe/Downloads/valence-acsi-dashboard-firebase-adminsdk-fbsvc-e8065d1b80.json"
collection_name = "calls"
skipped_log_path = "skipped_files.txt"

# --- INITIALIZE FIREBASE ---
print("✅ Initializing Firebase...")
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key_path)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- UNZIP FILES ---
print("✅ Unzipping JSON files...")
temp_dir = Path("/tmp/json_upload")
if temp_dir.exists():
    for file in temp_dir.rglob("*"):
        file.unlink()
else:
    temp_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

json_files = list(temp_dir.rglob("*.json"))
print(f"✅ Found {len(json_files)} JSON files.")

# --- FUNCTIONS ---
def is_valid_json(filepath):
    """Check if a JSON has required fields and is not junk."""
    if ".mp3.json" in filepath.name:
        return False, "Filename is an mp3"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
