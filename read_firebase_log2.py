import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("data/firebase_admin.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

docs = list(db.collection('jobs').stream())
if not docs:
    print("NO DOCS")
else:
    docs.sort(key=lambda x: x.to_dict().get('created_at', ''), reverse=True)
    doc = docs[0]
    data = doc.to_dict()
    print("JOB:", doc.id)
    print("STATUS:", data.get('status'))
    print("STEP TEXT:", data.get('step_text'))
    print("LOG:")
    for line in data.get('logs', []):
        print(line)
