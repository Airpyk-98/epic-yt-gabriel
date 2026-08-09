import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("data/firebase_admin.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

users = db.collection('users').stream()
found = False
for user in users:
    projects = db.collection('users').document(user.id).collection('projects').stream()
    for proj in projects:
        executions = db.collection('users').document(user.id).collection('projects').document(proj.id).collection('executions').stream()
        for exec_doc in executions:
            data = exec_doc.to_dict()
            if 'logs' in data:
                print(f"USER: {user.id} PROJ: {proj.id} EXEC: {exec_doc.id}")
                print(f"STATUS: {data.get('status')}")
                print(f"STEP: {data.get('step_text')}")
                print("LOGS:")
                for line in data.get('logs', [])[-50:]: # last 50 lines
                    print(line)
                print("="*40)
                found = True

if not found:
    print("NO JOBS FOUND in users collection.")
