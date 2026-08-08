import firebase_admin
from firebase_admin import credentials, firestore
import json

try:
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
except:
    pass

db = firestore.client()
users = db.collection('users').stream()
for user in users:
    projects = db.collection('users').document(user.id).collection('projects').stream()
    for proj in projects:
        executions = db.collection('users').document(user.id).collection('projects').document(proj.id).collection('executions').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(1).stream()
        for ex in executions:
            print(f"User: {user.id}, Project: {proj.id}")
            print(f"Latest Execution ID: {ex.id}")
            print(f"Status: {ex.to_dict().get('status')}")
            print(f"Step Text (Error): {ex.to_dict().get('step_text')}")
            print("-" * 20)
