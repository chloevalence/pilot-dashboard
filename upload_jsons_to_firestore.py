
import zipfile
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path
from tqdm import tqdm

# --- Config (your updated paths) ---
zip_path = "/Users/Chloe/Downloads/JSONs-20250424T060428Z-001.zip"
private_key_path = "/Users/Chloe/Downloads/valence-acsi-dashboard-firebase-adminsdk-fbsvc-e8065d1b80.json"

# --- Initialize Firebase ---
print("✅ Initializing Firebase...")
cred = credentials.Certificate(private_key_path)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Unzip the files ---
print("✅ Unzipping JSON files...")
temp_dir = "/tmp/unzipped_jsons"
os.makedirs(temp_dir, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

# --- Find all JSON files ---
json_files = list(Path(temp_dir).rglob("*.json"))
print(f"✅ Found {len(json_files)} JSON files.")

if not json_files:
    print("❌ No JSON files found after unzipping. Check your zip_path.")
    exit()

# --- Upload each JSON to Firestore ---
print("✅ Uploading data to Firestore...")

for json_file in tqdm(json_files, desc="Uploading"):
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Skipping {json_file} due to decode error.")
            continue

    # Get metadata
    metadata = data.get("metadata", {})

    upload_data = {
        "Call ID": metadata.get("call_id", json_file.stem),
        "Agent": metadata.get("agent", "Unknown"),
        "Company": metadata.get("company", "Unknown"),
        "Call Time": metadata.get("time", "Unknown"),
        "Call Date": metadata.get("date", None),
        "Low Confidences": metadata.get("low_confidences", 0),
        "average_happiness_value": data.get("average_happiness_value", None),
        "speaking_time_per_speaker": data.get("speaking_time_per_speaker", {}),
        "emotion_counts": data.get("emotion_counts", {}),
        "emotion_graph": data.get("emotion_graph", [])
    }

    # Upload to Firestore
    doc_ref = db.collection("calls").document(json_file.stem)
    doc_ref.set(upload_data)

print("🎉 All JSON files successfully uploaded to Firestore!")
