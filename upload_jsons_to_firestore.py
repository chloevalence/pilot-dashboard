
import zipfile
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

# --- Initialize Firebase ---
cred = credentials.Certificate("/Users/Chloe/Downloads/valence-acsi-dashboard-firebase-adminsdk-fbsvc-e8065d1b80.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Unzip and Parse ---
zip_path = "/Users/Chloe/Downloads/JSONs-20250424T060428Z-001.zip"
temp_dir = "/tmp/unzipped_jsons"
os.makedirs(temp_dir, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

# --- Upload to Firestore ---
json_files = list(Path(temp_dir).rglob("*.json"))

for json_file in json_files:
    with open(json_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Skipping {json_file} due to decode error.")
            continue

    # Metadata
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

    # Upload
    doc_ref = db.collection("calls").document(json_file.stem)
    doc_ref.set(upload_data)

print("✅ Finished uploading all call data to Firestore.")
