import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("data/firebase_admin.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

docs = db.collection('jobs').order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).stream()
for doc in docs:
    data = doc.to_dict()
    print("JOB:", doc.id)
    print("STATUS:", data.get('status'))
    print("STEP TEXT:", data.get('step_text'))
    print("LOG:")
    for line in data.get('logs', []):
        print(line)
