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
        data = proj.to_dict()
        if 'job' in data:
            job = data['job']
            print(f"USER: {user.id} PROJ: {proj.id}")
            print(f"STATUS: {job.get('status')}")
            print(f"STEP: {job.get('step_text')}")
            print("LOGS:")
            for line in job.get('logs', [])[-30:]: # last 30 lines
                print(line)
            print("="*40)
            found = True

if not found:
    print("NO JOBS FOUND in users collection.")
