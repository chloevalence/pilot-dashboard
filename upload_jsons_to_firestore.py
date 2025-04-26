import os
import json
import zipfile
import tempfile
import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

# --- Firebase Setup ---
cred = credentials.Certificate("/path/to/your/firebase-private-key.json")  # Change this to your real private key
firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Path to your local ZIP file ---
zip_path = "/path/to/your/jsons-folder.zip"  # Change this to your real ZIP path

# --- Extract the ZIP into a temp folder ---
with tempfile.TemporaryDirectory() as tmpdir:
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(tmpdir)

    root_path = Path(tmpdir)
    json_files = root_path.rglob("*.json")

    for file in json_files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)

        doc_id = file.stem  # Use filename without extension as Firestore document ID
        db.collection('calls').document(doc_id).set(data)

        print(f"✅ Uploaded {file.name}")
