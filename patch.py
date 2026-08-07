import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

helper = '''def update_firebase_job(job_id, job_info):
    if not db: return
    uid = job_info.get("uid")
    project_id = job_info.get("projectId")
    if not uid or not project_id: return
    try:
        db.collection("users").document(uid).collection("projects").document(project_id).collection("executions").document(job_id).set({
            "status": job_info.get("status", "STAGING"),
            "progress": job_info.get("progress", 0),
            "step_text": job_info.get("step_text", "")
        }, merge=True)
    except Exception as e:
        print(f"Firebase sync error: {e}", flush=True)

def append_log(job_id, message):'''

content = content.replace('def append_log(job_id, message):', helper)

replacements = [
    (
        '''        append_log(job_id, f"Successfully uploaded to YouTube! Video ID: {response.get('id')}")\n        \n    except Exception as e:''',
        '''        append_log(job_id, f"Successfully uploaded to YouTube! Video ID: {response.get('id')}")\n        jobs = load_jobs()\n        if job_id in jobs:\n            jobs[job_id]["status"] = "POSTED_TO_YOUTUBE"\n            save_jobs(jobs)\n            update_firebase_job(job_id, jobs[job_id])\n        \n    except Exception as e:'''
    ),
    (
        '''    jobs[job_id]["step_text"] = "Compute engine booting & provisioning GPU acceleration..."\n    save_jobs(jobs)\n    \n    last_status = "running"''',
        '''    jobs[job_id]["step_text"] = "Compute engine booting & provisioning GPU acceleration..."\n    save_jobs(jobs)\n    update_firebase_job(job_id, jobs[job_id])\n    \n    last_status = "running"'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Downloading generated video artifact..."\n                save_jobs(jobs)\n                \n                out_path = os.path.join(OUTPUTS_DIR, f"{job_id}.mp4")''',
        '''                jobs[job_id]["step_text"] = "Downloading generated video artifact..."\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                \n                out_path = os.path.join(OUTPUTS_DIR, f"{job_id}.mp4")'''
    ),
    (
        '''                    jobs[job_id]["step_text"] = "Video generated successfully!"\n                    save_jobs(jobs)\n                    append_log(job_id, "Job finished successfully.")''',
        '''                    jobs[job_id]["step_text"] = "Video generated successfully!"\n                    save_jobs(jobs)\n                    update_firebase_job(job_id, jobs[job_id])\n                    append_log(job_id, "Job finished successfully.")'''
    ),
    (
        '''                    jobs[job_id]["step_text"] = "Video lip-sync generated successfully!"\n                    jobs[job_id]["output_file"] = f"/api/video/{job_id}"\n                    save_jobs(jobs)\n                    \n                    # Check and Trigger YouTube Auto-Upload''',
        '''                    jobs[job_id]["step_text"] = "Video lip-sync generated successfully!"\n                    jobs[job_id]["output_file"] = f"/api/video/{job_id}"\n                    save_jobs(jobs)\n                    update_firebase_job(job_id, jobs[job_id])\n                    \n                    # Check and Trigger YouTube Auto-Upload'''
    ),
    (
        '''                    jobs[job_id]["step_text"] = "Failed to locate generated output video."\n                    save_jobs(jobs)\n                    break''',
        '''                    jobs[job_id]["step_text"] = "Failed to locate generated output video."\n                    save_jobs(jobs)\n                    update_firebase_job(job_id, jobs[job_id])\n                    break'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Generation finished but video output missing."\n                save_jobs(jobs)\n                break''',
        '''                jobs[job_id]["step_text"] = "Generation finished but video output missing."\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                break'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Kaggle reported: ERROR"\n                save_jobs(jobs)\n                break''',
        '''                jobs[job_id]["step_text"] = "Kaggle reported: ERROR"\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                break'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Generation failed or error reported."\n                save_jobs(jobs)\n                break''',
        '''                jobs[job_id]["step_text"] = "Generation failed or error reported."\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                break'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Consecutive API errors."\n                save_jobs(jobs)\n                break''',
        '''                jobs[job_id]["step_text"] = "Consecutive API errors."\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                break'''
    ),
    (
        '''                jobs[job_id]["step_text"] = "Monitoring connection failed."\n                save_jobs(jobs)\n                break''',
        '''                jobs[job_id]["step_text"] = "Monitoring connection failed."\n                save_jobs(jobs)\n                update_firebase_job(job_id, jobs[job_id])\n                break'''
    )
]

for old, new in replacements:
    content = content.replace(old, new)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("done")
