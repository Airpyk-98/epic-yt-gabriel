import json

with open("data/jobs.json") as f:
    jobs = json.load(f)

for job_id, job in jobs.items():
    print(f"JOB: {job_id}")
    print(f"STATUS: {job.get('status')}")
    print(f"STEP: {job.get('step_text')}")
    print("LOGS:")
    for line in job.get('logs', []):
        print(line)
    print("="*40)
