import subprocess, time

slug = "gabrielnjoku/epicsync-proj-qnwnf2ihpchlsfo"

for i in range(20):
    res = subprocess.run(f"kaggle kernels status {slug}", shell=True, capture_output=True, text=True)
    out = (res.stdout + " " + res.stderr).strip()
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Poll #{i+1}: {out}", flush=True)
    
    if "complete" in out.lower():
        print("*** COMPLETE ***", flush=True)
        break
    elif "error" in out.lower():
        print("*** ERROR ***", flush=True)
        break
    elif "cancel" in out.lower():
        print("*** CANCELLED ***", flush=True)
        break
    
    time.sleep(30)
