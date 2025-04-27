import os
import json
import zipfile
from pathlib import Path
from datetime import datetime
from dateutil import parser as date_parser  # pip install python-dateutil
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
    for f in temp_dir.rglob("*"):
        if f.is_file():
            f.unlink()
else:
    temp_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as z:
    z.extractall(temp_dir)

# --- PROCESS & UPLOAD ---
skipped_files = []
uploaded_count = 0

for file_path in temp_dir.rglob("*.json"):
    try:
        data = json.loads(file_path.read_text())
    except Exception as e:
        skipped_files.append((file_path.name, f"JSON load error: {e}"))
        continue

    # --- Flatten metadata ---
    metadata    = data.get("metadata", {})
    document_id = metadata.get("call_id", file_path.stem)
    agent       = metadata.get("agent")
    company     = metadata.get("company")
    time_of_day = metadata.get("time")
    date_raw    = metadata.get("date")  # MMDDYYYY string

    # --- Parse the real timestamp from top-level call_date ---
    raw_call_date = metadata.get("date")  # e.g. "04112025"
    try:
        parsed_call_date = datetime.strptime(raw_call_date, "%m%d%Y")
    except Exception:
        parsed_call_date = None

    # --- Flatten emotion_counts dict ---
    ec      = data.get("emotion_counts", {})
    angry   = ec.get("angry",   0)
    happy   = ec.get("happy",   0)
    neutral = ec.get("neutral", 0)
    sad     = ec.get("sad",     0)

    # --- Speaking times (optional) ---
    speaking = data.get("speaking_time_per_speaker", {})

    # --- Build the payload ---
    upload_payload = {
        "call_id":                  document_id,
        "agent":                    agent,
        "company":                  company,
        "time":                     time_of_day,
        "date_raw":                 date_raw,
        "call_date":                parsed_call_date,
        "average_happiness_value":  data.get("average_happiness_value"),
        "low_confidences":          metadata.get("low_confidences", data.get("low_confidences", 0)),
        "angry":                    angry,
        "happy":                    happy,
        "neutral":                  neutral,
        "sad":                      sad,
        "speaking_time_per_speaker": speaking,
        # ... add other top-level fields if needed ...
    }

    # --- Upload to Firestore ---
    try:
        db.collection(collection_name).document(document_id).set(upload_payload)
        uploaded_count += 1
        if uploaded_count % 100 == 0:
            print(f"✅ Uploaded {uploaded_count} calls...")
    except Exception as e:
        skipped_files.append((file_path.name, f"Firestore error: {e}"))

# --- LOG SKIPPED FILES ---
if skipped_files:
    with open(skipped_log_path, "w") as f:
        for fn, reason in skipped_files:
            f.write(f"{fn} — {reason}\n")
    print(f"⚠️ Skipped {len(skipped_files)} files. Details logged to {skipped_log_path}")
else:
    print("✅ No skipped files.")

print(f"🎉 Upload complete: {uploaded_count} calls uploaded successfully.")
