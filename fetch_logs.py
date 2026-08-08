import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

try:
    cred = credentials.Certificate('firebase_admin.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # Get all users
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
                if data.get('status') == 'FAILED':
                    found_errors.append(f"Project: {pid} | Job: {data.get('job_id')} | Status: {data.get('status')} | Step: {data.get('step_text')}")
    
    for err in found_errors[:10]:
        print(err)
except Exception as e:
    print(f"Error fetching from Firestore: {e}")
