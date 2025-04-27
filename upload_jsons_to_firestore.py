import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
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
        if file.is_file():
            file.unlink()
else:
    temp_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

json_files = list(temp_dir.rglob("*.json"))
print(f"✅ Found {len(json_files)} JSON files.")

# --- FUNCTIONS ---
def is_valid_json(filepath):
    if ".mp3.json" in filepath.name:
        return False, "Filename is an mp3"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False, "JSON parsing error"

    metadata = data.get("metadata", {})
    required_fields = ["agent", "company", "time", "date"]
    for field in required_fields:
        if not metadata.get(field):
            return False, f"Missing metadata field: {field}"

    if data.get("average_happiness_value") is None:
        return False, "Missing average_happiness_value"

    return True, data

# --- UPLOAD ---
skipped_files = []
uploaded_count = 0

print("✅ Uploading data to Firestore...")
for idx, filepath in enumerate(json_files, 1):
    valid, result = is_valid_json(filepath)
    if not valid:
        skipped_files.append((filepath.name, result))
        continue

    data = result

    # Safe-guard missing emotion counts
    emotion_counts = data.get("emotion_counts", {})
    for emotion in ["happy", "angry", "sad", "neutral"]:
        if emotion not in emotion_counts:
            emotion_counts[emotion] = 0

    document_id = filepath.stem

    # --- Process Dates Safely ---
    date_raw = data["metadata"].get("date", None)
    parsed_date = None

    if isinstance(date_raw, str):
        try:
            parsed_date = datetime.strptime(date_raw, "%m%d%Y")
        except ValueError:
            parsed_date = None
    elif isinstance(date_raw, datetime):
        parsed_date = date_raw

    upload_payload = {
        "call_id": document_id,
        "agent": data["metadata"]["agent"],
        "company": data["metadata"]["company"],
        "time": data["metadata"]["time"],
        "date_raw": date_raw,
        "call_date": parsed_date,
        "average_happiness_value": data["average_happiness_value"],
        "low_confidences": data["metadata"].get("low_confidences", 0),
        **emotion_counts
    }

    db.collection(collection_name).document(document_id).set(upload_payload)
    uploaded_count += 1

    if uploaded_count % 100 == 0:
        print(f"✅ Uploaded {uploaded_count} calls...")

# --- LOG SKIPPED FILES ---
if skipped_files:
    with open(skipped_log_path, "w") as f:
        for filename, reason in skipped_files:
            f.write(f"{filename} — {reason}\n")
    print(f"⚠️ Skipped {len(skipped_files)} files. Logged to {skipped_log_path}")
else:
    print("✅ No skipped files.")

print(f"🎉 Upload complete. {uploaded_count} calls uploaded successfully.")
