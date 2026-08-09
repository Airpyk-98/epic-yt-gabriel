"""
Local monitor script: polls Kaggle for the current kernel's status,
downloads the output when complete, and updates Firebase.
"""
import subprocess, time, os, sys, shutil, json
import firebase_admin
from firebase_admin import credentials, firestore

SLUG = "gabrielnjoku/epicsync-proj-qnwnf2ihpchlsfo"
JOB_ID = "epicsync_premium_1786255193"
UID = "uUdxrezet9MWGH5yDuuhY30tiUU2"
PROJ_ID = "QnWnf2IhPCHLsfoEOsUC"

# Init Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("data/firebase_admin.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def update_fb(status, step, progress, logs_line=None):
    ref = db.collection('users').document(UID).collection('projects').document(PROJ_ID).collection('executions').document(JOB_ID)
    update = {"status": status, "step_text": step, "progress": progress}
    if logs_line:
        update["logs"] = firestore.ArrayUnion([logs_line])
    ref.update(update)
    print(f"  [Firebase] {status} | {step}")

def poll():
    res = subprocess.run(f"kaggle kernels status {SLUG}", shell=True, capture_output=True, text=True)
    return (res.stdout + " " + res.stderr).strip()

print(f"=== Local Monitor for {JOB_ID} ===")
print(f"Polling Kaggle kernel: {SLUG}")
print()

iteration = 0
while True:
    iteration += 1
    out = poll()
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Poll #{iteration}: {out}")

    if "complete" in out.lower():
        print("\n*** KERNEL COMPLETE! Downloading output... ***")
        update_fb("DOWNLOADING", "Downloading generated video artifact...", 90,
                  f"[{ts}] Kaggle reported: COMPLETE. Downloading generated video...")

        dl_dir = os.path.join("data", "outputs", f"tmp_{JOB_ID}")
        os.makedirs(dl_dir, exist_ok=True)
        subprocess.run(f"kaggle kernels output {SLUG} -p {dl_dir}", shell=True)

        # Find the result video
        result_file = None
        for root, _, files in os.walk(dl_dir):
            for f in files:
                if f.endswith(".mp4"):
                    result_file = os.path.join(root, f)
                    break
            if result_file:
                break

        if result_file and os.path.exists(result_file):
            out_path = os.path.join("data", "outputs", f"{JOB_ID}.mp4")
            shutil.move(result_file, out_path)
            size = os.path.getsize(out_path)
            print(f"\n*** SUCCESS! Video saved: {out_path} ({size} bytes) ***")
            update_fb("SUCCESS", "Video lip-sync generated successfully!", 100,
                      f"[{ts}] Video downloaded successfully ({size} bytes).")
        else:
            print("\n*** ERROR: Kernel completed but no .mp4 found in output ***")
            print(f"  Files in {dl_dir}:")
            for root, _, files in os.walk(dl_dir):
                for f in files:
                    print(f"    {os.path.join(root, f)}")
            update_fb("FAILED", "Generation finished but video output missing.", 100,
                      f"[{ts}] Kernel completed but no video file found in output.")

        shutil.rmtree(dl_dir, ignore_errors=True)
        break

    elif "error" in out.lower():
        print(f"\n*** KERNEL ERROR: {out} ***")
        update_fb("FAILED", "Generation failed or error reported.", 100,
                  f"[{ts}] Kaggle reported: {out}")
        break

    elif "cancel" in out.lower():
        print(f"\n*** KERNEL CANCELLED: {out} ***")
        update_fb("FAILED", "Kaggle kernel was cancelled.", 100,
                  f"[{ts}] Kaggle reported: {out}")
        break

    time.sleep(20)

print("\n=== Monitor finished ===")
