import firebase_admin
from firebase_admin import credentials, firestore
import json

try:
    cred = credentials.Certificate('data/firebase_admin.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    users = db.collection('users').stream()
    found_errors = []
    
    for user in users:
        uid = user.id
        projects = db.collection('users').document(uid).collection('projects').stream()
        for proj in projects:
            pid = proj.id
            executions = db.collection('users').document(uid).collection('projects').document(pid).collection('executions').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(5).stream()
            for ex in executions:
                data = ex.to_dict()
                logs = data.get('logs', [])
                log_tail = logs[-3:] if logs else []
                found_errors.append(f"Project: {pid} | Job: {data.get('job_id')} | Status: {data.get('status')} | Step: {data.get('step_text')} | Logs: {log_tail}")
    
    for err in found_errors[:10]:
        print(err)
    if not found_errors:
        print('No FAILED executions found in the latest 5 per project.')
except Exception as e:
    print(f'Error fetching from Firestore: {e}')
