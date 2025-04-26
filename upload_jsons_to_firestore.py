import firebase_admin
from firebase_admin import credentials, firestore
import zipfile
import json
import tempfile
from pathlib import Path
from tqdm import tqdm

# --- CONFIG ---

# Path to your zip file containing all JSON folders
zip_path = "/Users/Chloe/Downloads/JSONs-20250424T060428Z-001.zip"

# Path to your Firebase private key JSON
firebase_key_path = "/Users/Chloe/Downloads/valence-acsi-dashboard-firebase-adminsdk-fbsvc-e8065d1b80.json"

# Name of the Firestore collection where data will be uploaded
collection_name = "calls"

# --- Initialize Firebase ---

print("✅ Initializing Firebase...")
cred = credentials.Certificate(firebase_key_path)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Unzip JSON files ---
print("✅ Unzipping JSON files...")
with tempfile.TemporaryDirectory() as tmpdir:
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(tmpdir)

    json_files = list(Path(tmpdir).rglob("*.json"))
    print(f"✅ Found {len(json_files)} JSON files.")

    # --- Upload each JSON to Firestore ---
    print("✅ Uploading data to Firestore...")
    for json_file in tqdm(json_files, desc="Uploading JSONs"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Skipping bad JSON file: {json_file}")
            continue

        # --- Parse Metadata Safely ---
        metadata = data.get("metadata", {})

        doc_data = {
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

        # --- Upload each doc ---
        try:
            doc_ref = db.collection(collection_name).document(json_file.stem)
            doc_ref.set(doc_data)
        except Exception as e:
            print(f"❌ Failed to upload {json_file}: {e}")

print("🎉 All JSON files successfully uploaded to Firestore!")
