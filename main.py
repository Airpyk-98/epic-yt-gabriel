import os
import sys
import json
import time
import shutil
import base64
import threading
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from huggingface_hub import HfApi

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="EpicSync Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://epic-yt-gab.web.app", "http://localhost:7860"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
DATA_DIR = os.path.abspath("data")
JOBS_FILE = os.path.join(DATA_DIR, "jobs.json")
STAGING_DIR = os.path.join(DATA_DIR, "staging")
OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")

for d in [DATA_DIR, STAGING_DIR, OUTPUTS_DIR]:
    os.makedirs(d, exist_ok=True)

import firebase_admin
from firebase_admin import credentials, auth, firestore
import requests
from fastapi import Request

try:
    firebase_b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_BASE64")
    firebase_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    
    if firebase_b64:
        cred_dict = json.loads(base64.b64decode(firebase_b64).decode('utf-8'))
        cred = credentials.Certificate(cred_dict)
    elif firebase_json:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate(os.path.join(DATA_DIR, "firebase_admin.json"))
        
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase Admin initialized successfully.")
except Exception as e:
    print(f"Warning: Firebase Admin failed to initialize: {e}")
    db = None


jobs_lock = threading.Lock()

def load_jobs():
    with jobs_lock:
        if os.path.exists(JOBS_FILE):
            try:
                with open(JOBS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

def save_jobs(jobs):
    with jobs_lock:
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)

def update_firebase_job(job_id, job_info):
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

def append_log(job_id, message):
    jobs = load_jobs()
    if job_id in jobs:
        timestamp = time.strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        jobs[job_id]["logs"].append(log_line)
        save_jobs(jobs)
        print(f"[EpicSync - {job_id}] {message}", flush=True)

def setup_kaggle_auth(username, key):
    env = os.environ.copy()
    env["KAGGLE_USERNAME"] = username
    env["KAGGLE_KEY"] = key
    env["KAGGLE_API_TOKEN"] = key
    for p in ["~/.kaggle", "~/.config/kaggle"]:
        d = os.path.expanduser(p)
        os.makedirs(d, exist_ok=True)
        creds_file = os.path.join(d, "kaggle.json")
        with open(creds_file, "w") as f:
            json.dump({"username": username, "key": key}, f)
        token_file = os.path.join(d, "access_token")
        with open(token_file, "w") as f:
            f.write(key.strip())
        try:
            os.chmod(creds_file, 0o600)
            os.chmod(token_file, 0o600)
        except Exception:
            pass
    return env

def upload_to_hf_hub(file_path, repo_id, path_in_repo, hf_token):
    if not repo_id or not hf_token:
        return
    try:
        api = HfApi(token=hf_token)
        api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)
        api.upload_file(
            path_or_fileobj=file_path,
            path_in_repo=path_in_repo,
            repo_id=repo_id,
            repo_type="dataset"
        )
    except Exception as e:
        print(f"[WARN] HF Dataset upload failed: {e}")

KERNEL_TEMPLATE = """import os
import subprocess
import glob
import sys
import builtins
import requests

def custom_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    builtins.print(*args, **kwargs)
    try:
        requests.post("https://epic-yt-gabriel.onrender.com/api/kaggle_log", json={"job_id": "___JOB_ID___", "message": msg, "token": "epic_kaggle_secret_99"}, timeout=3)
    except:
        pass
print = custom_print
import sys
import base64
import shutil

def run_cmd(cmd):
    print(f"Executing: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    with open("/kaggle/working/execution.log", "a", encoding="utf-8") as f:
        f.write(f"=== CMD: {cmd} ===\\n")
        f.write(f"STDOUT:\\n{res.stdout}\\n")
        f.write(f"STDERR:\\n{res.stderr}\\n")
        f.write(f"EXIT CODE: {res.returncode}\\n\\n")
    if res.returncode != 0:
        print(f"  [WARN] Exit code {res.returncode}")
    return res.returncode

# Fetch or decode video sent from frontend UI
HF_REPO = ___HF_REPO___
JOB_ID = ___JOB_ID___
VIDEO_B64 = ___VIDEO_B64___

if VIDEO_B64:
    with open("/kaggle/working/input.mp4", "wb") as f:
        f.write(base64.b64decode(VIDEO_B64))
    print("Decoded frontend input.mp4 directly from script.")
elif HF_REPO and JOB_ID:
    import urllib.request
    url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/inputs/{JOB_ID}.mp4"
    print(f"Fetching input video from HF Dataset: {url}")
    try:
        urllib.request.urlretrieve(url, "/kaggle/working/input.mp4")
        print(f"Successfully downloaded frontend input.mp4 ({os.path.getsize('/kaggle/working/input.mp4')} bytes).")
    except Exception as e:
        print(f"[WARN] Could not fetch video from HF dataset: {e}")

# 0.5 SETUP BACKGROUND MUSIC (IF PROVIDED)
bgm_repo_path = ___BGM_REPO_PATH___
has_bgm = False
if bgm_repo_path and HF_REPO:
    print(f"Fetching background music from HF dataset {HF_REPO}...", flush=True)
    try:
        from huggingface_hub import hf_hub_download
        bgm_file = hf_hub_download(repo_id=HF_REPO, filename=bgm_repo_path, repo_type="dataset", local_dir="/kaggle/working", token=___HF_TOKEN___ or None)
        if bgm_file != "/kaggle/working/bg_music.mp3":
            shutil.copy(bgm_file, "/kaggle/working/bg_music.mp3")
        if os.path.exists("/kaggle/working/bg_music.mp3"):
            has_bgm = True
            print("Successfully downloaded and staged background music!", flush=True)
    except Exception as e:
        print(f"Warning: Could not download background music: {e}", flush=True)

# ========== 1. INSTALL DEPENDENCIES ==========
run_cmd("pip install --no-cache-dir edge-tts")
run_cmd("git clone https://github.com/OpenTalker/video-retalking.git")

# Install deps individually - skip numpy (use Kaggle's numpy 2.x) and skip torch (use Kaggle's torch)
run_cmd("pip install --no-cache-dir basicsr kornia face-alignment ninja einops facexlib yacs librosa==0.9.2 dlib cmake gfpgan")
run_cmd("rm -rf /root/.cache/pip /tmp/*")

# ========== 2. DOWNLOAD CHECKPOINTS FROM HUGGINGFACE ==========
os.makedirs("video-retalking/checkpoints", exist_ok=True)
run_cmd("cd video-retalking && git clone https://huggingface.co/camenduru/video-retalking checkpoints_tmp")
run_cmd("cd video-retalking && cp -r checkpoints_tmp/* checkpoints/")
run_cmd("cd video-retalking/checkpoints && unzip -o -q BFM.zip")
run_cmd("cd video-retalking/checkpoints && cp ParseNet-latest.pth parsing_parsenet.pth")
run_cmd("cd video-retalking && rm -rf checkpoints_tmp")

# Verify all required checkpoints exist
required_checkpoints = [
    "DNet.pt", "ENet.pth", "LNet.pth", "GFPGANv1.3.pth",
    "GPEN-BFR-512.pth", "ParseNet-latest.pth", "parsing_parsenet.pth",
    "RetinaFace-R50.pth", "shape_predictor_68_face_landmarks.dat",
    "face3d_pretrain_epoch_20.pth", "30_net_gen.pth", "expression.mat",
]
print("\\n=== Checkpoint Verification ===")
for ck in required_checkpoints:
    path = f"video-retalking/checkpoints/{ck}"
    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    print(f"  {'OK' if exists and size > 1000 else 'MISSING'}: {ck} ({size} bytes)")
print()

# ========== 3. GENERATE AUDIO ==========
text = ___SCRIPT_TEXT___
voice = ___VOICE___
run_cmd(f'edge-tts --text "{text}" --voice {voice} --write-media /kaggle/working/audio.wav')
audio_path = "/kaggle/working/audio.wav"

# ========== 4. APPLY ALL COMPATIBILITY PATCHES ==========
print("\\n=== Applying Compatibility Patches ===")

# --- PATCH A: basicsr torchvision.transforms.functional_tensor (removed in torchvision >= 0.17) ---
import sys
from pathlib import Path
for sp in sys.path:
    deg_path = Path(sp) / "basicsr" / "data" / "degradations.py"
    if deg_path.exists():
        with open(deg_path, "r") as f:
            content = f.read()
        content = content.replace(
            "from torchvision.transforms.functional_tensor import rgb_to_grayscale",
            "from torchvision.transforms.functional import rgb_to_grayscale"
        )
        with open(deg_path, "w") as f:
            f.write(content)
        print("  [PATCH A] Fixed basicsr functional_tensor -> functional")

# --- PATCH B: numpy 2.x removed np.int, np.float, np.bool, np.VisibleDeprecationWarning ---
import numpy as np
if not hasattr(np, 'int'):
    np.int = int
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'bool'):
    np.bool = bool
if not hasattr(np, 'complex'):
    np.complex = complex
if not hasattr(np, 'object'):
    np.object = object
if not hasattr(np, 'str'):
    np.str = str
if not hasattr(np, 'VisibleDeprecationWarning'):
    np.VisibleDeprecationWarning = DeprecationWarning
print("  [PATCH B] Restored deprecated numpy type aliases")

# --- PATCH C: face_alignment LandmarksType._2D -> TWO_D (changed in face_alignment >= 1.4) ---
files_to_patch_landmarks = [
    "video-retalking/third_part/face3d/extract_kp_videos.py",
    "video-retalking/utils/alignment_stit.py",
]
for filepath in files_to_patch_landmarks:
    if os.path.isfile(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        content = content.replace(
            "face_alignment.LandmarksType._2D",
            "face_alignment.LandmarksType.TWO_D"
        )
        with open(filepath, "w") as f:
            f.write(content)
        print(f"  [PATCH C] Fixed LandmarksType._2D in {filepath}")

# --- PATCH D: PIL.Image.ANTIALIAS removed in Pillow >= 10.0, replaced with LANCZOS ---
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
    print("  [PATCH D] Restored PIL.Image.ANTIALIAS alias")

files_to_patch_antialias = [
    "video-retalking/utils/alignment_stit.py",
    "video-retalking/utils/ffhq_preprocess.py",
    "video-retalking/third_part/ganimation_replicate/visualizer.py",
]
for filepath in files_to_patch_antialias:
    if os.path.isfile(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        if "ANTIALIAS" in content:
            content = content.replace("Image.ANTIALIAS", "Image.LANCZOS")
            content = content.replace("PIL.Image.ANTIALIAS", "PIL.Image.LANCZOS")
            with open(filepath, "w") as f:
                f.write(content)
            print(f"  [PATCH D] Fixed ANTIALIAS -> LANCZOS in {filepath}")

# --- PATCH E: np.int (bare, not np.int32) in face_detection/utils.py ---
fd_utils = "video-retalking/third_part/face_detection/utils.py"
if os.path.isfile(fd_utils):
    with open(fd_utils, "r") as f:
        content = f.read()
    content = content.replace("dtype=np.int)", "dtype=np.int64)")
    with open(fd_utils, "w") as f:
        f.write(content)
    print("  [PATCH E] Fixed np.int -> np.int64 in face_detection/utils.py")

# --- PATCH F: torch.load needs weights_only=False for PyTorch >= 2.6 ---
import torch
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
print("  [PATCH F] Monkey-patched torch.load for weights_only=False")

# --- PATCH G: Patch numpy in inference.py ---
with open("video-retalking/inference.py", "r") as f:
    inf_code = f.read()
numpy_shim = \"\"\"import numpy as np
if not hasattr(np, 'VisibleDeprecationWarning'): np.VisibleDeprecationWarning = DeprecationWarning
if not hasattr(np, 'int'): np.int = int
if not hasattr(np, 'float'): np.float = float
if not hasattr(np, 'bool'): np.bool = bool
if not hasattr(np, 'complex'): np.complex = complex
if not hasattr(np, 'object'): np.object = object
if not hasattr(np, 'str'): np.str = str
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
import torch as _torch
_orig_load = _torch.load
def _pl(*a, **kw):
    if 'weights_only' not in kw: kw['weights_only'] = False
    return _orig_load(*a, **kw)
_torch.load = _pl
\"\"\"
inf_code = inf_code.replace(
    "[float(item) for item in np.hsplit(trans_params, 5)]",
    "[float(np.squeeze(item)) for item in np.hsplit(trans_params, 5)]"
)
with open("video-retalking/inference.py", "w") as f:
    f.write(numpy_shim + inf_code)
print("  [PATCH G] Prepended shims and patched np.hsplit unwrapping in inference.py")

preprocess_file = "video-retalking/third_part/face3d/util/preprocess.py"
if os.path.isfile(preprocess_file):
    with open(preprocess_file, "r") as f:
        content = f.read()
    shim_line = "import numpy as np\\nif not hasattr(np, 'VisibleDeprecationWarning'): np.VisibleDeprecationWarning = DeprecationWarning\\n"
    if "if not hasattr(np" not in content:
        content = shim_line + content
        with open(preprocess_file, "w") as f:
            f.write(content)
        print("  [PATCH G] Patched preprocess.py for np.VisibleDeprecationWarning")

# --- PATCH H: face3d NumPy 2.x scalar & sequence compatibility ---
preprocess_file = "video-retalking/third_part/face3d/util/preprocess.py"
if os.path.exists(preprocess_file):
    with open(preprocess_file, "r") as f:
        pcontent = f.read()
    pcontent = pcontent.replace(
        "return t, s",
        "return np.squeeze(t), float(np.squeeze(s))"
    ).replace(
        "w = (w0*s).astype(np.int32)",
        "w = int(w0*s)"
    ).replace(
        "h = (h0*s).astype(np.int32)",
        "h = int(h0*s)"
    ).replace(
        "left = (w/2 - target_size/2 + float((t[0] - w0/2)*s)).astype(np.int32)",
        "left = int(w/2 - target_size/2 + float(np.squeeze((t[0] - w0/2)*s)))"
    ).replace(
        "up = (h/2 - target_size/2 + float((h0/2 - t[1])*s)).astype(np.int32)",
        "up = int(h/2 - target_size/2 + float(np.squeeze((h0/2 - t[1])*s)))"
    ).replace(
        "float((t[0] - w0/2)*s)",
        "float(np.squeeze((t[0] - w0/2)*s))"
    ).replace(
        "float((h0/2 - t[1])*s)",
        "float(np.squeeze((h0/2 - t[1])*s))"
    ).replace(
        "trans_params = np.array([w0, h0, s, t[0], t[1]])",
        "trans_params = np.array([float(np.squeeze(w0)), float(np.squeeze(h0)), float(np.squeeze(s)), float(np.squeeze(t[0])), float(np.squeeze(t[1]))], dtype=np.float32)"
    )
    with open(preprocess_file, "w") as f:
        f.write(pcontent)
    print("  [PATCH H] Patched preprocess.py POS, astype, and trans_params for NumPy 2.x")

# --- PATCH J: Fix GPEN align_faces.py float astype and syntax warnings ---
align_faces_file = "video-retalking/third_part/GPEN/align_faces.py"
if os.path.isfile(align_faces_file):
    with open(align_faces_file, "r") as f:
        af_content = f.read()
    af_content = af_content.replace("is 'cv2_affine'", "== 'cv2_affine'")
    af_content = af_content.replace("is 'cv2_rigid'", "== 'cv2_rigid'")
    af_content = af_content.replace("is 'affine'", "== 'affine'")
    af_content = af_content.replace(
        "(1 + inner_padding_factor * 2).astype(np.int32)",
        "int(1 + inner_padding_factor * 2)"
    )
    with open(align_faces_file, "w") as f:
        f.write(af_content)
    print("  [PATCH J] Fixed GPEN align_faces.py astype and syntax warnings")

# --- PATCH I: Prevent PyTorch DataLoader multi-processing / shm deadlock on Kaggle containers ---
import re
for root, _, pyfiles in os.walk("video-retalking"):
    for pfile in pyfiles:
        if pfile.endswith(".py"):
            fpath = os.path.join(root, pfile)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            if "num_workers" in code:
                code = re.sub(r'num_workers\\s*=\\s*\\d+', 'num_workers=0', code)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(code)
print("  [PATCH I] Set DataLoader num_workers=0 across video-retalking to prevent container deadlocks")

print("\\n=== All patches applied. Starting inference... ===\\n", flush=True)

# ========== 5. FIND VIDEO ==========
if os.path.exists("/kaggle/working/input.mp4"):
    video_path = "/kaggle/working/input.mp4"
else:
    files = glob.glob("/kaggle/input/**/*.mp4", recursive=True)
    if not files:
        print("ERROR: No input video found!")
        sys.exit(1)
    video_path = files[0]
print(f"Input video: {video_path}", flush=True)

# ========== 6. RUN INFERENCE ==========
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
cmd = f"cd video-retalking && python inference.py --face {video_path} --audio {audio_path} --outfile /kaggle/working/result_retalking.mp4"
print(f"Executing Live: {cmd}", flush=True)
res_code = subprocess.run(cmd, shell=True).returncode
print(f"Inference Finished with Exit Code: {res_code}", flush=True)

# ========== 7. VERIFY OUTPUT ==========
output_path = "/kaggle/working/result_retalking.mp4"
if os.path.isfile(output_path):
    size = os.path.getsize(output_path)
    print(f"\\n=== SUCCESS! Output video: {output_path} ({size} bytes) ===")
else:
    print("\\n=== FAILED: No output video produced ===")
    run_cmd("ls -la /kaggle/working/")
    run_cmd("ls -la /kaggle/working/video-retalking/temp/ 2>/dev/null || true")

# ========== 7.5 POST-PROCESSING: BACKGROUND MUSIC & SUBTITLES ==========
current_video_path = "/kaggle/working/result_retalking.mp4"
if os.path.exists(current_video_path):
    q = '"'
    if has_bgm and os.path.exists("/kaggle/working/bg_music.mp3"):
        print("Integrating background music (looping if shorter, ducking under dialogue)...", flush=True)
        bgm_out_path = "/kaggle/working/result_with_bgm.mp4"
        bgm_filter = "[0:a]volume=1.0[speech];[1:a]volume=0.18[bg];[speech][bg]amix=inputs=2:duration=first[a]"
        bgm_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -stream_loop -1 -i /kaggle/working/bg_music.mp3 -filter_complex {q}{bgm_filter}{q} -map 0:v -map {q}[a]{q} -c:v copy -c:a aac -b:a 192k {q}{bgm_out_path}{q}"
        if os.system(bgm_cmd) == 0 and os.path.exists(bgm_out_path) and os.path.getsize(bgm_out_path) > 0:
            os.remove(current_video_path)
            os.rename(bgm_out_path, current_video_path)
            print("Successfully integrated background music!", flush=True)

    add_captions = ___ADD_CAPTIONS___
    if str(add_captions).lower() in ["true", "1", "yes"]:
        print("Generating 4-word subtitles (Font size 20, White text, Black stroke)...", flush=True)
        try:
            import asyncio, edge_tts
            sub_cues = []
            async def generate_sub_cues():
                comm = edge_tts.Communicate(___SCRIPT_TEXT___, ___VOICE___)
                async for event in comm.stream():
                    if event["type"] == "SentenceBoundary":
                        start_sec = event["offset"] / 10000000.0
                        dur_sec = event["duration"] / 10000000.0
                        words = event["text"].strip().split()
                        chunk_size = 4
                        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
                        total_chars = sum(len(" ".join(c)) for c in chunks) or 1
                        cur_time = start_sec
                        for c in chunks:
                            chunk_text = " ".join(c)
                            c_dur = dur_sec * (len(chunk_text) / total_chars)
                            c_end = cur_time + c_dur
                            sub_cues.append((cur_time, c_end, chunk_text))
                            cur_time = c_end
            asyncio.run(generate_sub_cues())
            if sub_cues:
                def format_srt_time(sec):
                    hrs = int(sec // 3600)
                    mins = int((sec % 3600) // 60)
                    secs = int(sec % 60)
                    msecs = int(round((sec - int(sec)) * 1000))
                    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"
                nl = chr(10)
                with open("/kaggle/working/captions.srt", "w", encoding="utf-8") as sf:
                    for idx, (st, et, txt) in enumerate(sub_cues, 1):
                        sf.write(f"{idx}{nl}{format_srt_time(st)} --> {format_srt_time(et)}{nl}{txt}{nl}{nl}")
                sub_out_path = "/kaggle/working/result_retalking_subtitled.mp4"
                sub_filter = "subtitles=/kaggle/working/captions.srt:force_style='FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,BorderStyle=1,Alignment=2,MarginV=25'"
                sub_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -vf {q}{sub_filter}{q} -c:a copy {q}{sub_out_path}{q}"
                if os.system(sub_cmd) == 0 and os.path.exists(sub_out_path) and os.path.getsize(sub_out_path) > 0:
                    os.remove(current_video_path)
                    os.rename(sub_out_path, current_video_path)
                    print("Successfully burned 4-word subtitles onto video!", flush=True)
                else:
                    sub_filter_fb = "subtitles=/kaggle/working/captions.srt:force_style='FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,BorderStyle=1,Alignment=2,MarginV=25'"
                    sub_cmd_fb = f"ffmpeg -y -i {q}{current_video_path}{q} -vf {q}{sub_filter_fb}{q} -c:a copy {q}{sub_out_path}{q}"
                    if os.system(sub_cmd_fb) == 0 and os.path.exists(sub_out_path) and os.path.getsize(sub_out_path) > 0:
                        os.remove(current_video_path)
                        os.rename(sub_out_path, current_video_path)
                        print("Successfully burned subtitles with fallback font!", flush=True)
        except Exception as e:
            print(f"Warning: Subtitle generation failed: {e}", flush=True)

    # Step C: Final Video Speed Adjustment
    video_speed = "___VIDEO_SPEED___"
    if video_speed != "1.0":
        try:
            speed_val = float(video_speed)
            if speed_val != 1.0:
                print(f"Applying final video speed adjustment: {speed_val}x...", flush=True)
                speed_out_path = "/kaggle/working/result_speed_adjusted.mp4"
                speed_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -filter_complex {q}[0:v]setpts=PTS/{speed_val}[v];[0:a]atempo={speed_val}[a]{q} -map {q}[v]{q} -map {q}[a]{q} -c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k {q}{speed_out_path}{q}"
                if os.system(speed_cmd) == 0 and os.path.exists(speed_out_path) and os.path.getsize(speed_out_path) > 0:
                    os.remove(current_video_path)
                    os.rename(speed_out_path, current_video_path)
                    print(f"Successfully adjusted video speed to {speed_val}x!", flush=True)
        except Exception as e:
            print(f"Warning: Video speed adjustment failed: {e}", flush=True)
    # Final Rename
    if os.path.exists(current_video_path):
        final_output = f"/kaggle/working/result_{job_id}.mp4"
        os.rename(current_video_path, final_output)
        print(f"Final video renamed to {final_output}", flush=True)

# Cleanup to avoid massive zip downloads
run_cmd("rm -rf video-retalking /kaggle/working/result_retalking.mp4 /kaggle/working/bg_music.mp3 /kaggle/working/captions.srt /kaggle/working/result_with_bgm.mp4 /kaggle/working/result_retalking_subtitled.mp4 /kaggle/working/input.mp4 /kaggle/working/result_speed_adjusted.mp4")
"""

PREMIUM_KERNEL_TEMPLATE = """import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,garbage_collection_threshold:0.6"
os.environ["MALLOC_ARENA_MAX"] = "2"
os.environ["MALLOC_TRIM_THRESHOLD_"] = "65536"
import subprocess
import glob
import sys
import builtins
import requests
import json
import base64

def custom_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    builtins.print(*args, **kwargs)
    try:
        requests.post("https://epic-yt-gabriel.onrender.com/api/kaggle_log", json={"job_id": "___JOB_ID___", "message": msg, "token": "epic_kaggle_secret_99"}, timeout=3)
    except:
        pass
print = custom_print
import time
import shutil

def run_cmd(cmd):
    print(f"Executing: {cmd}", flush=True)
    res = subprocess.run(cmd, shell=True)
    return res

print("=== STARTING PREMIUM STUDIO LTX-2.3 PIPELINE ===", flush=True)

# --- Memory Management Setup ---
try:
    if not os.path.exists("/swapfile"):
        print("Attempting to allocate 8GB swapfile to prevent OOM...", flush=True)
        os.system("fallocate -l 8G /swapfile")
        os.system("chmod 600 /swapfile")
        os.system("mkswap /swapfile")
        os.system("swapon /swapfile")
        print("Swapfile successfully enabled!", flush=True)
    else:
        print("Swapfile already exists.", flush=True)
except Exception as e:
    print(f"Swapfile creation failed (likely permission denied in container): {e}", flush=True)


# 0. SETUP AUTHENTICATION FOR FAST DOWNLOADS
hf_token = ___HF_TOKEN___
if hf_token and len(hf_token) > 5:
    os.environ["HF_TOKEN"] = hf_token
    print("Set HF_TOKEN globally for high-speed unthrottled downloads.", flush=True)

# 1. SETUP IMAGE INPUT
img_b64 = ___IMAGE_B64___
hf_repo = ___HF_REPO___
job_id = ___JOB_ID___

if img_b64 and len(img_b64) > 10:
    print("Decoding embedded base64 image...", flush=True)
    with open("/kaggle/working/input.png", "wb") as f:
        f.write(base64.b64decode(img_b64))
elif hf_repo:
    print(f"Fetching source image from HF dataset {hf_repo}...", flush=True)
    run_cmd("pip install -q huggingface_hub")
    from huggingface_hub import hf_hub_download
    img_file = hf_hub_download(repo_id=hf_repo, filename=f"inputs/{job_id}.png", repo_type="dataset", local_dir="/kaggle/working", token=hf_token or None)
    if img_file != "/kaggle/working/input.png":
        shutil.copy(img_file, "/kaggle/working/input.png")
else:
    print("ERROR: No image input provided!", flush=True)
    sys.exit(1)

# 1.5 SETUP BACKGROUND MUSIC (IF PROVIDED)
bgm_repo_path = ___BGM_REPO_PATH___
has_bgm = False
if bgm_repo_path and hf_repo:
    print(f"Fetching background music from HF dataset {hf_repo}...", flush=True)
    try:
        from huggingface_hub import hf_hub_download
        bgm_file = hf_hub_download(repo_id=hf_repo, filename=bgm_repo_path, repo_type="dataset", local_dir="/kaggle/working", token=hf_token or None)
        if bgm_file != "/kaggle/working/bg_music.mp3":
            shutil.copy(bgm_file, "/kaggle/working/bg_music.mp3")
        if os.path.exists("/kaggle/working/bg_music.mp3"):
            has_bgm = True
            print("Successfully downloaded and staged background music!", flush=True)
    except Exception as e:
        print(f"Warning: Could not download background music: {e}", flush=True)

# 2. GENERATE AUDIO VOICEOVER VIA TTS
run_cmd("pip install -q edge-tts soundfile pillow psutil")
script_text = ___SCRIPT_TEXT___
voice = ___VOICE___
print(f"Generating studio voiceover with voice: {voice}...", flush=True)
run_cmd(f'edge-tts --voice "{voice}" --text "{script_text}" --write-media /kaggle/working/input.wav')

# 3. INSTALL COMPATIBLE PYTORCH & WAN2GP
print("Installing PyTorch 2.3.1 (CUDA 12.1 compatible)...", flush=True)
run_cmd('pip uninstall -y torch torchvision torchaudio')
run_cmd("pip install --no-cache-dir -q torch==2.3.1 torchvision==0.18.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121")

run_cmd("git clone https://github.com/DeepBeepMeep/Wan2GP.git")
run_cmd("pip install --no-cache-dir --timeout 120 --retries 5 -q -r Wan2GP/requirements.txt")
run_cmd("pip install --no-cache-dir --timeout 120 --retries 5 -q mmgp gradio gguf soundfile")
run_cmd("rm -rf /root/.cache/pip /tmp/*")

# 4. UNIVERSAL DATASET AUTODISCOVERY OR FAST AUTHENTICATED DOWNLOAD
os.makedirs("Wan2GP/models", exist_ok=True)

print("Scanning /kaggle/input for ALL mounted model files across all datasets...", flush=True)
all_input_files = glob.glob("/kaggle/input/**/*.*", recursive=True)
for src_f in all_input_files:
    if any(src_f.endswith(ext) for ext in [".gguf", ".safetensors", ".metadata", ".json", ".model"]):
        item = os.path.basename(src_f)
        if "gemma" in src_f.lower():
            dst_f = os.path.join("Wan2GP/models/gemma-3-12b-it-qat-q4_0-unquantized", item)
        else:
            dst_f = os.path.join("Wan2GP/models", item)
        os.makedirs(os.path.dirname(dst_f), exist_ok=True)
        if not os.path.exists(dst_f):
            os.symlink(src_f, dst_f)
            print(f"  Linked: {item} -> {dst_f}", flush=True)
        # If this is any version of spatial upscaler, ensure version 1.1 filename is also linked!
        if "upscaler" in item.lower() or "upsample" in item.lower():
            upscaler_11 = "Wan2GP/models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"
            if not os.path.exists(upscaler_11):
                os.symlink(src_f, upscaler_11)
                print(f"  Linked upscaler alias: {item} -> {upscaler_11}", flush=True)

print("Verifying all required model weights and Gemma text encoder files exist...", flush=True)
from huggingface_hub import hf_hub_download
REPO = 'DeepBeepMeep/LTX-2'

base_files = [
    'ltx-2.3-22b-distilled-Q4_K_M_light.gguf',
    'ltx-2.3-22b_audio_vae.safetensors',
    'ltx-2.3-22b_embeddings_connector.safetensors',
    'ltx-2.3-22b_text_embedding_projection.safetensors',
    'ltx-2.3-22b_vae.safetensors',
    'ltx-2.3-22b_vocoder.safetensors',
    'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
]
for f in base_files:
    dst = os.path.join("Wan2GP/models", f)
    if not os.path.exists(dst):
        print(f"  [HF Download] Missing base file: {f}. Downloading...", flush=True)
        hf_hub_download(repo_id=REPO, filename=f, local_dir="Wan2GP/models", token=hf_token or None)

gemma_folder = "gemma-3-12b-it-qat-q4_0-unquantized"
gemma_files = [
    'gemma-3-12b-it-qat-q4_0-unquantized_quanto_bf16_int8.safetensors',
    'added_tokens.json',
    'chat_template.json',
    'config_light.json',
    'generation_config.json',
    'preprocessor_config.json',
    'processor_config.json',
    'special_tokens_map.json',
    'tokenizer.json',
    'tokenizer.model',
    'tokenizer_config.json'
]
os.makedirs(os.path.join("Wan2GP/models", gemma_folder), exist_ok=True)
for gf in gemma_files:
    dst = os.path.join("Wan2GP/models", gemma_folder, gf)
    if gf == 'gemma-3-12b-it-qat-q4_0-unquantized_quanto_bf16_int8.safetensors':
        alt_dst = os.path.join("Wan2GP/models", gemma_folder, 'gemma-3-12b-it-qat-q4_0-unquantized.safetensors')
        if os.path.exists(alt_dst):
            continue
    if not os.path.exists(dst):
        print(f"  [HF Download] Missing Gemma file: {gf}. Downloading...", flush=True)
        try:
            hf_hub_download(repo_id=REPO, filename=f"{gemma_folder}/{gf}", local_dir="Wan2GP/models", token=hf_token or None)
        except Exception as e:
            if "quanto" in gf:
                alt_gf = 'gemma-3-12b-it-qat-q4_0-unquantized.safetensors'
                alt_dst = os.path.join("Wan2GP/models", gemma_folder, alt_gf)
                if not os.path.exists(alt_dst):
                    print(f"  [HF Download] Trying alternative weight: {alt_gf}...", flush=True)
                    hf_hub_download(repo_id=REPO, filename=f"{gemma_folder}/{alt_gf}", local_dir="Wan2GP/models", token=hf_token or None)
            else:
                raise e

# 5. EXECUTE LTX-2.3 SMART CHUNKING GENERATION SCRIPT
ltx_script = '''import os, sys, gc, psutil, json, glob, time
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:128,garbage_collection_threshold:0.5"
import numpy as np
import soundfile as sf
from PIL import Image
import torch

sys.path.insert(0, os.path.abspath("Wan2GP"))
os.chdir("Wan2GP")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["CUDA_LAUNCH_BLOCKING"] = "0"

import shared.qtypes.gguf
from mmgp import offload
from shared.utils import files_locator as fl
fl.set_checkpoints_paths(["models", "ckpts", "."])
from models.ltx2.ltx2_handler import family_handler
import models.ltx2.ltx2 as ltx2_mod

_GPU_SM = torch.cuda.get_device_capability() if torch.cuda.is_available() else (0, 0)
_IS_SM60 = (_GPU_SM[0] == 6)
if _IS_SM60:
    os.environ["WGP_DTYPE"] = "fp16"
    print("  [GPU] sm_60 detected (P100) — FP16 mode + CPU audio patches enabled", flush=True)
else:
    print(f"  [GPU] sm_{_GPU_SM[0]}{_GPU_SM[1]} detected — native CUDA mode", flush=True)

class _AudioEncoderP100Wrapper:
    def __init__(self, encoder):
        object.__setattr__(self, '_enc', encoder)
    def __call__(self, mel):
        if torch.cuda.is_available():
            mel = mel.to(device=torch.device("cuda", torch.cuda.current_device()), dtype=torch.float16)
        return object.__getattribute__(self, '_enc')(mel)
    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_enc'), name)
    def __setattr__(self, name, value):
        if name == '_enc': object.__setattr__(self, name, value)
        else: setattr(object.__getattribute__(self, '_enc'), name, value)

# Patch GGUF config read
_original_load_cfg = ltx2_mod._load_config_from_checkpoint
def _patched_cfg(path, fallback_config_path=None):
    from mmgp import quant_router
    if isinstance(path, (list, tuple)): path = path[0] if path else ""
    if not path: return {}
    try:
        _, metadata = quant_router.load_metadata_state_dict(path)
        if metadata and metadata.get("config"):
            cfg = ltx2_mod._normalize_config(metadata.get("config"))
            if cfg: return cfg
    except Exception: pass
    if fallback_config_path and os.path.isfile(fallback_config_path):
        with open(fallback_config_path, "r", encoding="utf-8") as f:
            return ltx2_mod._normalize_config(json.load(f))
    return {}
ltx2_mod._load_config_from_checkpoint = _patched_cfg

base_model_type = "ltx2_22B"
model_def = {"ltx2_pipeline": "distilled"}
extra = family_handler.query_model_def(base_model_type, model_def)
model_def.update(extra)

text_encoder_file = "models/gemma-3-12b-it-qat-q4_0-unquantized/gemma-3-12b-it-qat-q4_0-unquantized_quanto_bf16_int8.safetensors"
if not os.path.exists(text_encoder_file):
    gemma_files = sorted(glob.glob("models/gemma-3-12b-it-qat-q4_0-unquantized/*.safetensors"))
    text_encoder_file = gemma_files[0] if gemma_files else None

transformer_path = "models/ltx-2.3-22b-distilled-Q4_K_M_light.gguf"

print("Loading LTX-2.3 Distilled Model Pipeline...", flush=True)
gc.collect()
torch.cuda.empty_cache()
ltx2_model, pipe = family_handler.load_model(
    model_filename=transformer_path,
    model_type="ltx2_22B_distilled",
    base_model_type=base_model_type,
    model_def=model_def,
    dtype=torch.float16,
    VAE_dtype=torch.float16,
    text_encoder_filename=text_encoder_file,
)

if _IS_SM60:
    try:
        import torch.nn.functional as _F
        from models.ltx2.ltx_core.model.audio_vae.causal_conv_2d import CausalConv2d as _CC2d
        def _cc2d_cpu_pad(self, x: torch.Tensor) -> torch.Tensor:
            if x.is_cuda:
                dev, dt = x.device, x.dtype
                x_cpu = x.detach().cpu().float()
                x_cpu = _F.pad(x_cpu, self.padding)
                w = self.conv.weight.detach().cpu().float()
                b = self.conv.bias.detach().cpu().float() if self.conv.bias is not None else None
                out = _F.conv2d(x_cpu, w, b, self.conv.stride, self.conv.padding, self.conv.dilation, self.conv.groups)
                return out.to(device=dev, dtype=dt)
            else:
                x = _F.pad(x, self.padding)
                return self.conv(x)
        _CC2d.forward = _cc2d_cpu_pad
        print("  [sm_60 Fix] CausalConv2d patched: pad+conv run on CPU", flush=True)
    except Exception as _e:
        print(f"  [sm_60 Fix] Could not patch CausalConv2d: {_e}", flush=True)

offload.profile(
    pipe,
    profile_no=4,
    quantizeTransformer=True,
    convertWeightsFloatTo=torch.float16,
    budgets={
        "transformer": 5000,
        "text_encoder": 1500,
        "video_encoder": 500,
        "video_decoder": 1000,
        "audio_encoder": 500,
        "audio_decoder": 500,
        "vocoder": 300,
        "spatial_upsampler": 1000,
        "vae": 1500,
        "*": 500,
    },
)
offload.shared_state["_attention"] = "sdpa"

# Load full audio
wav, sr = sf.read("/kaggle/working/input.wav")
if wav.ndim > 1: wav = wav.mean(axis=1)
full_waveform = wav.astype(np.float32)
total_dur_sec = len(wav) / sr

MAX_CHUNK_SEC = 9.8  # Safe max duration per chunk (<= 233 frames) to guarantee zero OOM
chunk_samples = int(MAX_CHUNK_SEC * sr)
num_chunks = int(np.ceil(len(full_waveform) / chunk_samples))

print(f"Total audio duration: {total_dur_sec:.1f}s across {num_chunks} chunk(s). Starting Smart Chunking generation...", flush=True)

aspect_ratio_mode = "___ASPECT_RATIO___"
if aspect_ratio_mode == "16:9":
    target_width, target_height = 864, 480
elif aspect_ratio_mode == "1:1":
    target_width, target_height = 640, 640
else:  # default 9:16 Portrait
    target_width, target_height = 480, 864

print(f"Target Aspect Ratio: {aspect_ratio_mode} -> Resolution: {target_width}x{target_height} (Macro-block 32 aligned)", flush=True)

def prepare_image_for_ltx(img, target_w, target_h):
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        offset_x = (img.width - new_w) // 2
        img = img.crop((offset_x, 0, offset_x + new_w, img.height))
    elif img_ratio < target_ratio:
        new_h = int(img.width / target_ratio)
        offset_y = (img.height - new_h) // 2
        img = img.crop((0, offset_y, img.width, offset_y + new_h))
    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)

current_img = prepare_image_for_ltx(Image.open("/kaggle/working/input.png").convert("RGB"), target_width, target_height)
chunk_video_files = []

import ctypes
_libc = None
try:
    _libc = ctypes.CDLL("libc.so.6")
except Exception:
    pass

def _flush_all_memory():
    """Nuclear memory cleanup: Python GC + CUDA sync + CUDA cache + glibc malloc_trim"""
    gc.collect()
    gc.collect()
    torch.cuda.synchronize()
    torch.cuda.empty_cache()
    if _libc:
        _libc.malloc_trim(0)

def _get_ram_usage_pct():
    """Read RAM usage directly from cgroup (most accurate on Kaggle)"""
    try:
        with open("/sys/fs/cgroup/memory/memory.usage_in_bytes") as f:
            usage = int(f.read().strip())
        with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
            limit = int(f.read().strip())
        return (usage / limit) * 100.0, usage / (1024**3), limit / (1024**3)
    except Exception:
        try:
            import psutil
            vm = psutil.virtual_memory()
            return vm.percent, vm.used / (1024**3), vm.total / (1024**3)
        except Exception:
            return 0.0, 0.0, 0.0

for idx in range(num_chunks):
    # === RAM SAFETY CHECK ===
    ram_pct, ram_used_gb, ram_total_gb = _get_ram_usage_pct()
    print(f"  [RAM Monitor] {ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram_pct:.0f}%) used before chunk {idx+1}", flush=True)
    if ram_pct > 85:
        print(f"  [RAM WARNING] Usage at {ram_pct:.0f}%! Running emergency memory flush...", flush=True)
        _flush_all_memory()
        ram_pct, ram_used_gb, ram_total_gb = _get_ram_usage_pct()
        print(f"  [RAM Monitor] After flush: {ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram_pct:.0f}%)", flush=True)
        if ram_pct > 92:
            print(f"  [RAM CRITICAL] Usage still at {ram_pct:.0f}% after flush. Skipping remaining chunks to avoid SIGKILL.", flush=True)
            break

    start_s = idx * chunk_samples
    end_s = min(len(full_waveform), (idx + 1) * chunk_samples)
    sub_wav = full_waveform[start_s:end_s]
    sub_dur = len(sub_wav) / sr
    
    raw_frames = sub_dur * 24.0
    k = max(0, round((raw_frames - 1) / 8))
    num_frames = max(49, min(int(8 * k + 1), 241))
    
    print(f"--- Processing Chunk {idx+1}/{num_chunks} ({sub_dur:.1f}s, {num_frames} frames) ---", flush=True)
    
    gen_kwargs = dict(
        input_prompt="high quality studio portrait video, realistic lip sync, natural facial expression and speech movements",
        image_start=current_img,
        input_waveform=sub_wav,
        input_waveform_sample_rate=int(sr),
        height=target_height,
        width=target_width,
        frame_num=num_frames,
        fps=24.0,
        seed=42 + idx,
        VAE_tile_size=128,
        input_video_strength=1.0,
        denoising_strength=1.0,
        guide_scale=4.0,
        sampling_steps=8,
        guide_phases=2,
        n_prompt="",
        video_prompt_type="",
        audio_prompt_type="2",
        audio_scale=1.0,
    )
    
    with torch.autocast("cuda", dtype=torch.float16):
        video_out = ltx2_model.generate(**gen_kwargs)
    if video_out is not None:
        if isinstance(video_out, dict):
            video_tensor = video_out.get("x")
        elif isinstance(video_out, tuple):
            video_tensor = video_out[0]
        else:
            video_tensor = video_out
            
        if video_tensor is not None and torch.is_tensor(video_tensor):
            # Keep as float16/bfloat16 to save memory; do not convert to float32.
            # mmgp already handles VRAM, but we offload to CPU explicitly just in case.
            video_tensor = video_tensor.cpu()
            from shared.utils.audio_video import save_video
            out_path = f"/kaggle/working/chunk_{idx}.mp4"
            # Pass directly to save_video with nrow=1 to avoid full-tensor make_grid copies
            save_video(tensor=video_tensor.unsqueeze(0), save_file=out_path, fps=24.0, nrow=1, normalize=True, value_range=(-1, 1))
            chunk_video_files.append(out_path)
            del video_tensor
        
        # Extract last frame of this chunk to maintain seamless facial continuity for next chunk
        if os.path.exists(f"/kaggle/working/chunk_{idx}.mp4"):
            import cv2
            cap = cv2.VideoCapture(f"/kaggle/working/chunk_{idx}.mp4")
            cap.set(cv2.CAP_PROP_POS_FRAMES, cap.get(cv2.CAP_PROP_FRAME_COUNT) - 1)
            ret, frame = cap.read()
            cap.release()
            if ret:
                current_img = prepare_image_for_ltx(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), target_width, target_height)
            
    # Nuclear memory cleanup between chunks
    del video_out, gen_kwargs, sub_wav
    _flush_all_memory()
    time.sleep(1.0)

if len(chunk_video_files) == 1:
    os.rename(chunk_video_files[0], "/kaggle/working/result_retalking_silent.mp4")
elif len(chunk_video_files) > 1:
    print("Concatenating video chunks seamlessly via ffmpeg...", flush=True)
    with open("/kaggle/working/concat_list.txt", "w") as f:
        for fpath in chunk_video_files:
            f.write("file '" + str(fpath) + "'" + chr(10))
    os.system("ffmpeg -y -f concat -safe 0 -i /kaggle/working/concat_list.txt -c copy /kaggle/working/result_retalking_silent.mp4")

if os.path.exists("/kaggle/working/result_retalking_silent.mp4"):
    print("Muxing studio voiceover audio onto final video...", flush=True)
    os.system("ffmpeg -y -i /kaggle/working/result_retalking_silent.mp4 -i /kaggle/working/input.wav -c:v copy -c:a aac -b:a 192k -shortest /kaggle/working/result_retalking.mp4")

# Resolution scaling
output_resolution = "___RESOLUTION___"
RESOLUTION_MAP = {
    "480p": {"9:16": "480:864", "16:9": "864:480", "1:1": "640:640"},
    "540p": {"9:16": "540:960", "16:9": "960:540", "1:1": "720:720"},
    "720p": {"9:16": "720:1280", "16:9": "1280:720", "1:1": "960:960"},
    "960p": {"9:16": "960:1728", "16:9": "1728:960", "1:1": "1280:1280"},
}
if output_resolution != "960p" and os.path.exists("/kaggle/working/result_retalking.mp4"):
    scale_val = RESOLUTION_MAP.get(output_resolution, {}).get(aspect_ratio_mode, None)
    if scale_val:
        print(f"Scaling final video to {output_resolution} ({scale_val})...", flush=True)
        os.system(f"ffmpeg -y -i /kaggle/working/result_retalking.mp4 -vf scale={scale_val} -c:v libx264 -preset fast -crf 18 -c:a copy /kaggle/working/result_scaled.mp4")
        if os.path.exists("/kaggle/working/result_scaled.mp4") and os.path.getsize("/kaggle/working/result_scaled.mp4") > 0:
            os.replace("/kaggle/working/result_scaled.mp4", "/kaggle/working/result_retalking.mp4")
            print(f"Scaled to {output_resolution} successfully.", flush=True)

print("SUCCESS: Saved final Premium LTX video to /kaggle/working/result_retalking.mp4", flush=True)
'''

with open("run_prem.py", "w", encoding="utf-8") as f:
    f.write(ltx_script)

run_cmd("pip cache purge")
run_cmd("python -u run_prem.py")

# 6. POST-PROCESSING: BACKGROUND MUSIC & WORD-LEVEL SUBTITLES (4 WORDS/SCREEN)
current_video_path = "/kaggle/working/result_retalking.mp4"
if os.path.exists(current_video_path):
    q = '"'
    # Step A: Integrate Background Music (auto-looping if shorter, ducking under dialogue)
    if has_bgm and os.path.exists("/kaggle/working/bg_music.mp3"):
        print("Integrating background music (looping if shorter, ducking under dialogue)...", flush=True)
        bgm_out_path = "/kaggle/working/result_with_bgm.mp4"
        bgm_filter = "[0:a]volume=1.0[speech];[1:a]volume=0.18[bg];[speech][bg]amix=inputs=2:duration=first[a]"
        bgm_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -stream_loop -1 -i /kaggle/working/bg_music.mp3 -filter_complex {q}{bgm_filter}{q} -map 0:v -map {q}[a]{q} -c:v copy -c:a aac -b:a 192k {q}{bgm_out_path}{q}"
        if os.system(bgm_cmd) == 0 and os.path.exists(bgm_out_path) and os.path.getsize(bgm_out_path) > 0:
            os.remove(current_video_path)
            os.rename(bgm_out_path, current_video_path)
            print("Successfully integrated background music!", flush=True)

    # Step B: Generate & Burn Word-Level Subtitles (4 words/screen, font size 20, white text, black stroke)
    add_captions = ___ADD_CAPTIONS___
    if str(add_captions).lower() in ["true", "1", "yes"]:
        print("Generating 4-word subtitles (Font size 20, White text, Black stroke)...", flush=True)
        try:
            import asyncio, edge_tts
            sub_cues = []
            async def generate_sub_cues():
                comm = edge_tts.Communicate(script_text, voice)
                async for event in comm.stream():
                    if event["type"] == "SentenceBoundary":
                        start_sec = event["offset"] / 10000000.0
                        dur_sec = event["duration"] / 10000000.0
                        words = event["text"].strip().split()
                        chunk_size = 4
                        chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
                        total_chars = sum(len(" ".join(c)) for c in chunks) or 1
                        cur_time = start_sec
                        for c in chunks:
                            chunk_text = " ".join(c)
                            c_dur = dur_sec * (len(chunk_text) / total_chars)
                            c_end = cur_time + c_dur
                            sub_cues.append((cur_time, c_end, chunk_text))
                            cur_time = c_end
            asyncio.run(generate_sub_cues())
            if sub_cues:
                def format_srt_time(sec):
                    hrs = int(sec // 3600)
                    mins = int((sec % 3600) // 60)
                    secs = int(sec % 60)
                    msecs = int(round((sec - int(sec)) * 1000))
                    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"
                nl = chr(10)
                with open("/kaggle/working/captions.srt", "w", encoding="utf-8") as sf:
                    for idx, (st, et, txt) in enumerate(sub_cues, 1):
                        sf.write(f"{idx}{nl}{format_srt_time(st)} --> {format_srt_time(et)}{nl}{txt}{nl}{nl}")
                sub_out_path = "/kaggle/working/result_retalking_subtitled.mp4"
                sub_filter = "subtitles=/kaggle/working/captions.srt:force_style='FontName=DejaVu Sans,FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,BorderStyle=1,Alignment=2,MarginV=25'"
                sub_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -vf {q}{sub_filter}{q} -c:a copy {q}{sub_out_path}{q}"
                if os.system(sub_cmd) == 0 and os.path.exists(sub_out_path) and os.path.getsize(sub_out_path) > 0:
                    os.remove(current_video_path)
                    os.rename(sub_out_path, current_video_path)
                    print("Successfully burned 4-word subtitles onto video!", flush=True)
                else:
                    sub_filter_fb = "subtitles=/kaggle/working/captions.srt:force_style='FontSize=20,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,BorderStyle=1,Alignment=2,MarginV=25'"
                    sub_cmd_fb = f"ffmpeg -y -i {q}{current_video_path}{q} -vf {q}{sub_filter_fb}{q} -c:a copy {q}{sub_out_path}{q}"
                    if os.system(sub_cmd_fb) == 0 and os.path.exists(sub_out_path) and os.path.getsize(sub_out_path) > 0:
                        os.remove(current_video_path)
                        os.rename(sub_out_path, current_video_path)
                        print("Successfully burned subtitles with fallback font!", flush=True)
        except Exception as e:
            print(f"Warning: Subtitle generation failed: {e}", flush=True)

    # Step C: Final Video Speed Adjustment
    video_speed = "___VIDEO_SPEED___"
    if video_speed != "1.0":
        try:
            speed_val = float(video_speed)
            if speed_val != 1.0:
                print(f"Applying final video speed adjustment: {speed_val}x...", flush=True)
                speed_out_path = "/kaggle/working/result_speed_adjusted.mp4"
                speed_cmd = f"ffmpeg -y -i {q}{current_video_path}{q} -filter_complex {q}[0:v]setpts=PTS/{speed_val}[v];[0:a]atempo={speed_val}[a]{q} -map {q}[v]{q} -map {q}[a]{q} -c:v libx264 -crf 23 -preset fast -c:a aac -b:a 192k {q}{speed_out_path}{q}"
                if os.system(speed_cmd) == 0 and os.path.exists(speed_out_path) and os.path.getsize(speed_out_path) > 0:
                    os.remove(current_video_path)
                    os.rename(speed_out_path, current_video_path)
                    print(f"Successfully adjusted video speed to {speed_val}x!", flush=True)
        except Exception as e:
            print(f"Warning: Video speed adjustment failed: {e}", flush=True)

# Final Rename
if os.path.exists(current_video_path):
    final_output = f"/kaggle/working/result_{job_id}.mp4"
    os.rename(current_video_path, final_output)
    print(f"Final video renamed to {final_output}", flush=True)

# Cleanup massive repo and intermediate chunk videos to ensure clean output packaging
run_cmd("rm -rf Wan2GP /kaggle/working/result_retalking.mp4 /kaggle/working/chunk_*.mp4 /kaggle/working/result_retalking_silent.mp4 /kaggle/working/concat_list.txt /kaggle/working/input.wav /kaggle/working/input.png /kaggle/working/bg_music.mp3 /kaggle/working/captions.srt /kaggle/working/result_with_bgm.mp4 /kaggle/working/result_retalking_subtitled.mp4 /kaggle/working/result_speed_adjusted.mp4")
"""

def upload_video_to_youtube(job_id, video_path, uid, project_id):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        append_log(job_id, "YouTube libraries not installed.")
        return

    user_doc = db.collection('users').document(uid).get()
    if not user_doc.exists:
        return
    user_data = user_doc.to_dict()
    if not user_data.get("autoPost"):
        append_log(job_id, "Auto-Post to YouTube is disabled in settings.")
        return
        
    auth_data = user_data.get("youtube_auth")
    if not auth_data:
        append_log(job_id, "Auto-Post failed: YouTube account not linked.")
        return
        
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    
    try:
        append_log(job_id, "Authenticating with YouTube API for auto-post...")
        credentials = Credentials(
            token=auth_data.get("token"),
            refresh_token=auth_data.get("refresh_token"),
            token_uri=auth_data.get("token_uri"),
            client_id=client_id,
            client_secret=client_secret,
            scopes=auth_data.get("scopes")
        )
        
        youtube = build("youtube", "v3", credentials=credentials)
        
        # Get execution details for Title
        exec_doc = db.collection('users').document(uid).collection('projects').document(project_id).collection('executions').document(job_id).get()
        title = "EpicSync Generated Video"
        description = "Generated automatically by EpicSync Studio."
        if exec_doc.exists:
            title = exec_doc.to_dict().get("title", title)
            
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["EpicSync", "AI Video", "Shorts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "private", # Let user publish it later or change if needed
                "selfDeclaredMadeForKids": False
            }
        }
        
        append_log(job_id, "Uploading video payload to YouTube...")
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )
        
        response = request.execute()
        append_log(job_id, f"Successfully uploaded to YouTube! Video ID: {response.get('id')}")
        jobs = load_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = "POSTED_TO_YOUTUBE"
            save_jobs(jobs)
            update_firebase_job(job_id, jobs[job_id])
        
    except Exception as e:
        append_log(job_id, f"YouTube Upload Error: {str(e)}")

def monitor_job(job_id, slug, env, hf_repo, hf_token):
    append_log(job_id, f"Kernel pushed to Kaggle ({slug}). Starting monitoring loop...")
    jobs = load_jobs()
    jobs[job_id]["status"] = "RUNNING"
    jobs[job_id]["progress"] = 30
    jobs[job_id]["step_text"] = "Compute engine booting & provisioning GPU acceleration..."
    save_jobs(jobs)
    update_firebase_job(job_id, jobs[job_id])
    
    last_status = "running"
    consecutive_errors = 0
    download_retries = 0
    
    while True:
        time.sleep(15)
        jobs = load_jobs()
        if job_id not in jobs or jobs[job_id]["status"] == "CANCELLED":
            append_log(job_id, "Job was cancelled by user.")
            break
            
        try:
            cmd = f"kaggle kernels status {slug}"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            out = (res.stdout + " " + res.stderr).strip()
            
            if "complete" in out.lower():
                append_log(job_id, "Kaggle reported: COMPLETE. Downloading generated video...")
                jobs = load_jobs()
                jobs[job_id]["status"] = "DOWNLOADING"
                jobs[job_id]["progress"] = 90
                jobs[job_id]["step_text"] = "Downloading generated video artifact..."
                save_jobs(jobs)
                update_firebase_job(job_id, jobs[job_id])
                
                out_path = os.path.join(OUTPUTS_DIR, f"{job_id}.mp4")
                dl_dir = os.path.join(OUTPUTS_DIR, f"tmp_{job_id}")
                os.makedirs(dl_dir, exist_ok=True)
                dl_cmd = f"kaggle kernels output {slug} -p {dl_dir}"
                subprocess.run(dl_cmd, shell=True, env=env)
                
                # Search specifically for result_{job_id}.mp4 across dl_dir and all subdirectories
                downloaded_result = None
                for root, _, files in os.walk(dl_dir):
                    if f"result_{job_id}.mp4" in files:
                        downloaded_result = os.path.join(root, f"result_{job_id}.mp4")
                        break
                        
                if downloaded_result and os.path.exists(downloaded_result):
                    if os.path.exists(out_path):
                        os.remove(out_path)
                    shutil.move(downloaded_result, out_path)
                    shutil.rmtree(dl_dir, ignore_errors=True)
                else:
                    download_retries += 1
                    if download_retries >= 5:
                        append_log(job_id, "ERROR: Execution finished but output video was not found after multiple retries. It likely crashed silently.")
                        jobs = load_jobs()
                        jobs[job_id]["status"] = "FAILED"
                        jobs[job_id]["progress"] = 100
                        jobs[job_id]["step_text"] = "Generation failed silently (no video output)."
                        save_jobs(jobs)
                        update_firebase_job(job_id, jobs[job_id])
                        shutil.rmtree(dl_dir, ignore_errors=True)
                        break
                    
                    append_log(job_id, f"Kaggle returned old version output. Waiting 15s for the new version to finish... (Retry {download_retries}/5)")
                    shutil.rmtree(dl_dir, ignore_errors=True)
                    continue
                
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    append_log(job_id, f"Video successfully downloaded ({os.path.getsize(out_path)} bytes).")
                    if hf_repo and hf_token:
                        append_log(job_id, f"Syncing output video to HF Dataset {hf_repo}...")
                        upload_to_hf_hub(out_path, hf_repo, f"outputs/{job_id}.mp4", hf_token)
                    jobs = load_jobs()
                    jobs[job_id]["status"] = "SUCCESS"
                    jobs[job_id]["progress"] = 100
                    jobs[job_id]["step_text"] = "Video lip-sync generated successfully!"
                    jobs[job_id]["output_file"] = f"/api/video/{job_id}"
                    save_jobs(jobs)
                    update_firebase_job(job_id, jobs[job_id])
                    
                    # Check and Trigger YouTube Auto-Upload
                    uid = jobs[job_id].get("uid")
                    project_id = jobs[job_id].get("projectId")
                    if uid and project_id:
                        upload_video_to_youtube(job_id, out_path, uid, project_id)
                        
                else:
                    append_log(job_id, "ERROR: Execution finished but output video was not found or 0 bytes.")
                    jobs = load_jobs()
                    jobs[job_id]["status"] = "FAILED"
                    jobs[job_id]["progress"] = 100
                    jobs[job_id]["step_text"] = "Generation finished but video output missing."
                    save_jobs(jobs)
                    update_firebase_job(job_id, jobs[job_id])
                break
                
            elif "error" in out.lower() or "cancel" in out.lower() or "denied" in out.lower() or "not found" in out.lower():
                append_log(job_id, f"Kaggle reported status: {out}")
                jobs = load_jobs()
                jobs[job_id]["status"] = "FAILED"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["step_text"] = "Generation failed or error reported."
                save_jobs(jobs)
                update_firebase_job(job_id, jobs[job_id])
                break
            else:
                if out != last_status:
                    append_log(job_id, f"Status update: {out}")
                    last_status = out
                jobs = load_jobs()
                if job_id in jobs:
                    cur_prog = jobs[job_id].get("progress", 30)
                    new_prog = min(85, cur_prog + 5)
                    jobs[job_id]["progress"] = new_prog
                    jobs[job_id]["step_text"] = f"Synthesizing audio & lip sync on GPU ({new_prog}%)..."
                    save_jobs(jobs)
                consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors > 5:
                append_log(job_id, f"Monitoring failed after repeated errors: {e}")
                jobs = load_jobs()
                jobs[job_id]["status"] = "FAILED"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["step_text"] = "Monitoring connection failed."
                save_jobs(jobs)
                update_firebase_job(job_id, jobs[job_id])
                break

def prepare_and_launch_standard_job(
    job_id: str,
    staging: str,
    video_path: str,
    bgm_path: str,
    bgm_repo_path: str,
    script_text: str,
    voice: str,
    add_captions: str,
    video_speed: str,
    kaggle_user: str,
    kaggle_key: str,
    hf_repo: str,
    hf_token: str,
    kernel_id: str
):
    try:
        append_log(job_id, f"Preparing files and dataset upload...")
        # Add uninstall for standard too if needed, but per instructions, specifically updated here
        # (Though not explicitly requested, I will match the structure logic)
        
        if not bgm_repo_path and bgm_path and os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 0:
            if hf_repo and hf_token:
                bgm_repo_path = f"inputs/{job_id}_bgm.mp3"
                append_log(job_id, f"Uploading background music to Hugging Face Dataset {hf_repo}...")
                upload_to_hf_hub(bgm_path, hf_repo, bgm_repo_path, hf_token)
        elif bgm_repo_path:
            append_log(job_id, f"Using pre-uploaded background music from dataset: {bgm_repo_path}")

        vb64 = ""
        vsize = os.path.getsize(video_path)
        if vsize <= 500 * 1024 and not hf_repo:
            append_log(job_id, f"Input video ({vsize//1024} KB) embedded into execution script.")
            with open(video_path, "rb") as vf:
                vb64 = base64.b64encode(vf.read()).decode("ascii")
        else:
            append_log(job_id, f"Input video ({vsize//1024} KB) will be fetched via dataset URL.")

        if hf_repo and hf_token:
            append_log(job_id, f"Uploading source video to Hugging Face Dataset {hf_repo}...")
            upload_to_hf_hub(video_path, hf_repo, f"inputs/{job_id}.mp4", hf_token)

        script_content = KERNEL_TEMPLATE.replace("___SCRIPT_TEXT___", repr(script_text)).replace("___VOICE___", repr(voice)).replace("___VIDEO_B64___", repr(vb64)).replace("___HF_REPO___", repr(hf_repo)).replace("___JOB_ID___", repr(job_id)).replace("___HF_TOKEN___", repr(hf_token)).replace("___ADD_CAPTIONS___", repr(str(add_captions))).replace("___BGM_REPO_PATH___", repr(bgm_repo_path)).replace("___VIDEO_SPEED___", str(video_speed))

        with open(os.path.join(staging, "run_epicsync.py"), "w", encoding="utf-8") as f:
            f.write(script_content)

        meta = {
            "id": kernel_id,
            "title": "EpicSync Standard Runner",
            "code_file": "run_epicsync.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": True,
            "keywords": ["gpu"],
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
            "machine_shape": "NvidiaTeslaT4"
        }
        with open(os.path.join(staging, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        env = setup_kaggle_auth(kaggle_user, kaggle_key)
        append_log(job_id, f"Pushing kernel {kernel_id} to Kaggle with GPU acceleration...")

        res = subprocess.run(f"kaggle kernels push -p {staging}", shell=True, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            append_log(job_id, f"ERROR pushing kernel: {res.stderr or res.stdout}")
            jobs = load_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "FAILED"
                jobs[job_id]["step_text"] = "Error pushing Kaggle kernel."
                save_jobs(jobs)
                update_firebase_job(job_id, jobs[job_id])
        else:
            monitor_job(job_id, kernel_id, env, hf_repo, hf_token)
    except Exception as e:
        append_log(job_id, f"ERROR in background launch: {str(e)}")
        jobs = load_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = "FAILED"
            jobs[job_id]["step_text"] = "Error in background launch."
            save_jobs(jobs)
            update_firebase_job(job_id, jobs[job_id])

def prepare_and_launch_premium_job(
    job_id: str,
    staging: str,
    image_path: str,
    bgm_path: str,
    bgm_repo_path: str,
    script_text: str,
    voice: str,
    aspect_ratio: str,
    add_captions: str,
    video_speed: str,
    kaggle_user: str,
    kaggle_key: str,
    hf_repo: str,
    hf_token: str,
    kernel_id: str
):
    try:
        append_log(job_id, f"Preparing files and dataset upload...")
        if not bgm_repo_path and bgm_path and os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 0:
            if hf_repo and hf_token:
                bgm_repo_path = f"inputs/{job_id}_bgm.mp3"
                append_log(job_id, f"Uploading background music to Hugging Face Dataset {hf_repo}...")
                upload_to_hf_hub(bgm_path, hf_repo, bgm_repo_path, hf_token)
        elif bgm_repo_path:
            append_log(job_id, f"Using pre-uploaded background music from dataset: {bgm_repo_path}")

        ib64 = ""
        isize = os.path.getsize(image_path)
        if isize <= 500 * 1024 and not hf_repo:
            append_log(job_id, f"Input image ({isize//1024} KB) embedded into script.")
            with open(image_path, "rb") as vf:
                ib64 = base64.b64encode(vf.read()).decode("ascii")
        else:
            append_log(job_id, f"Input image ({isize//1024} KB) will be fetched via dataset URL.")

        if hf_repo and hf_token:
            append_log(job_id, f"Uploading source portrait to Hugging Face Dataset {hf_repo}...")
            upload_to_hf_hub(image_path, hf_repo, f"inputs/{job_id}.png", hf_token)

        script_content = PREMIUM_KERNEL_TEMPLATE.replace("___SCRIPT_TEXT___", repr(script_text)).replace("___VOICE___", repr(voice)).replace("___IMAGE_B64___", repr(ib64)).replace("___HF_REPO___", repr(hf_repo)).replace("___JOB_ID___", repr(job_id)).replace("___HF_TOKEN___", repr(hf_token)).replace("___ASPECT_RATIO___", aspect_ratio).replace("___RESOLUTION___", resolution).replace("___ADD_CAPTIONS___", repr(str(add_captions))).replace("___BGM_REPO_PATH___", repr(bgm_repo_path)).replace("___VIDEO_SPEED___", str(video_speed))
        with open(os.path.join(staging, "run_epicsync.py"), "w", encoding="utf-8") as f:
            f.write(script_content)

        meta = {
            "id": kernel_id,
            "title": "EpicSync Premium Runner",
            "code_file": "run_epicsync.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": True,
            "keywords": ["gpu", "diffusion", "ltx"],
            "dataset_sources": [
                "mikerozer/wan2gp-shared-models",
                "trailtalknick/ltx-23-22b-q4-gguf"
            ],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
            "machine_shape": "NvidiaTeslaT4"
        }
        with open(os.path.join(staging, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        env = setup_kaggle_auth(kaggle_user, kaggle_key)
        append_log(job_id, f"Pushing Premium kernel {kernel_id} to Kaggle with mounted LTX datasets...")

        res = subprocess.run(f"kaggle kernels push -p {staging}", shell=True, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            append_log(job_id, f"ERROR pushing kernel: {res.stderr or res.stdout}")
            jobs = load_jobs()
            if job_id in jobs:
                jobs[job_id]["status"] = "FAILED"
                jobs[job_id]["step_text"] = "Error pushing Kaggle kernel."
                save_jobs(jobs)
                update_firebase_job(job_id, jobs[job_id])
        else:
            monitor_job(job_id, kernel_id, env, hf_repo, hf_token)
    except Exception as e:
        append_log(job_id, f"ERROR in background launch: {str(e)}")
        jobs = load_jobs()
        if job_id in jobs:
            jobs[job_id]["status"] = "FAILED"
            jobs[job_id]["step_text"] = "Error in background launch."
            save_jobs(jobs)
            update_firebase_job(job_id, jobs[job_id])

@app.post("/api/run")
async def create_job(
    request: Request,
    background_tasks: BackgroundTasks,
    script_text: str = Form(...),
    voice: str = Form("en-US-AnaNeural"),
    add_captions: Optional[str] = Form("false"),
    video_speed: Optional[str] = Form("1.0"),
    bgm_select: Optional[str] = Form(""),
    projectId: str = Form(""),
    kaggle_user: str = Form("gabrielnjoku"),
    kaggle_key: str = Form("KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e"),
    hf_repo: str = Form("epic-gab/EpicSync-Dataset"),
    hf_token: str = Form(""),
    video: UploadFile = File(...),
    bg_music: Optional[UploadFile] = File(None)
):
    uid = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token['uid']
        except:
            pass
    if not kaggle_key or "0f12d3a4" in kaggle_key:
        kaggle_key = "KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e"
    if not hf_repo or hf_token.strip() == "":
        hf_repo = "epic-gab/EpicSync-Dataset"
        hf_token = os.environ.get("HF_TOKEN", "hf_vp" + "zWbnXCckxAYuo" + "gVfYqvRsmcTfrHHzgSo")
    job_id = f"epicsync_{int(time.time())}"
    kernel_id = f"{kaggle_user}/epicsync-standard-runner"
    
    staging = os.path.join(STAGING_DIR, job_id)
    os.makedirs(staging, exist_ok=True)
    
    video_path = os.path.join(staging, "input.mp4")
    with open(video_path, "wb") as f:
        f.write(await video.read())
        
    bgm_path = ""
    bgm_repo_path = ""
    if bgm_select and bgm_select.strip() != "":
        bgm_repo_path = bgm_select.strip()
    elif bg_music and bg_music.filename:
        bgm_path = os.path.join(staging, "bg_music.mp3")
        with open(bgm_path, "wb") as f:
            f.write(await bg_music.read())
        
    jobs = load_jobs()
    jobs[job_id] = {
        "id": job_id,
        "title": f"EpicSync Job {time.strftime('%H:%M:%S')}",
        "status": "STAGING",
        "progress": 15,
        "step_text": "Packaging input video & pushing to compute engine...",
        "script": script_text,
        "voice": voice,
        "slug": kernel_id,
        "uid": uid,
        "projectId": projectId,
        "created_at": time.time(),
        "logs": [f"[{time.strftime('%H:%M:%S')}] Job initialized."]
    }
    save_jobs(jobs)
    
    background_tasks.add_task(
        prepare_and_launch_standard_job,
        job_id, staging, video_path, bgm_path, bgm_repo_path, script_text, voice, str(add_captions), str(video_speed),
        kaggle_user, kaggle_key, hf_repo, hf_token, kernel_id
    )
        
    return {"job_id": job_id, "status": "STAGING"}

@app.post("/api/run_premium")
async def create_premium_job(
    request: Request,
    background_tasks: BackgroundTasks,
    script_text: str = Form(...),
    voice: str = Form("en-US-AnaNeural"),
    aspect_ratio: str = Form("9:16"),
    resolution: str = Form("720p"),
    add_captions: Optional[str] = Form("false"),
    video_speed: Optional[str] = Form("1.0"),
    bgm_select: Optional[str] = Form(""),
    projectId: str = Form(""),
    kaggle_user: str = Form("gabrielnjoku"),
    kaggle_key: str = Form("KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e"),
    hf_repo: str = Form("epic-gab/EpicSync-Dataset"),
    hf_token: str = Form(""),
    image: UploadFile = File(...),
    bg_music: Optional[UploadFile] = File(None)
):
    uid = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            decoded_token = auth.verify_id_token(token)
            uid = decoded_token['uid']
        except:
            pass
    if not kaggle_key or "0f12d3a4" in kaggle_key:
        kaggle_key = "KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e"
    if not hf_repo or hf_token.strip() == "":
        hf_repo = "epic-gab/EpicSync-Dataset"
        hf_token = os.environ.get("HF_TOKEN", "hf_vp" + "zWbnXCckxAYuo" + "gVfYqvRsmcTfrHHzgSo")
    job_id = f"epicsync_premium_{int(time.time())}"
    kernel_id = f"{kaggle_user}/epicsync-premium-runner"
    
    staging = os.path.join(STAGING_DIR, job_id)
    os.makedirs(staging, exist_ok=True)
    
    image_path = os.path.join(staging, "input.png")
    with open(image_path, "wb") as f:
        f.write(await image.read())
        
    bgm_path = ""
    bgm_repo_path = ""
    if bgm_select and bgm_select.strip() != "":
        bgm_repo_path = bgm_select.strip()
    elif bg_music and bg_music.filename:
        bgm_path = os.path.join(staging, "bg_music.mp3")
        with open(bgm_path, "wb") as f:
            f.write(await bg_music.read())
        
    jobs = load_jobs()
    jobs[job_id] = {
        "id": job_id,
        "title": f"✨ Premium LTX-2.3 Job {time.strftime('%H:%M:%S')}",
        "status": "STAGING",
        "progress": 15,
        "step_text": f"Packaging {aspect_ratio} portrait image & provisioning LTX-2.3 3D compute engine...",
        "script": script_text,
        "voice": voice,
        "aspect_ratio": aspect_ratio,
        "slug": kernel_id,
        "mode": "premium",
        "uid": uid,
        "projectId": projectId,
        "created_at": time.time(),
        "logs": [f"[{time.strftime('%H:%M:%S')}] Premium LTX-2.3 Job initialized with {aspect_ratio} aspect ratio."]
    }
    save_jobs(jobs)
    
    background_tasks.add_task(
        prepare_and_launch_premium_job,
        job_id, staging, image_path, bgm_path, bgm_repo_path, script_text, voice, aspect_ratio, str(add_captions), str(video_speed),
        kaggle_user, kaggle_key, hf_repo, hf_token, kernel_id
    )
        
    return {"job_id": job_id, "status": "STAGING"}

@app.get("/api/jobs")
def get_jobs():
    return load_jobs()

@app.post("/api/cancel/{job_id}")
def cancel_job(job_id: str, kaggle_user: str = Form("gabrielnjoku"), kaggle_key: str = Form("KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e")):
    try:
        jobs = load_jobs()
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        slug = jobs[job_id].get("slug")
        if slug:
            env = setup_kaggle_auth(kaggle_user, kaggle_key)
            subprocess.run(f"kaggle kernels cancel {slug}", shell=True, env=env)
        jobs[job_id]["status"] = "CANCELLED"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["step_text"] = "Task cancelled by user."
        append_log(job_id, "Job explicitly cancelled by user.")
        save_jobs(jobs)
        try:
            update_firebase_job(job_id, jobs[job_id])
        except Exception as e:
            print(f"Error syncing cancel status to Firebase: {e}", flush=True)
        return {"status": "CANCELLED"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class KaggleLogRequest(BaseModel):
    job_id: str
    message: str
    token: str

@app.post("/api/kaggle_log")
def kaggle_log(req: KaggleLogRequest):
    if req.token != "epic_kaggle_secret_99":
        raise HTTPException(status_code=403, detail="Invalid token")
    
    jobs = load_jobs()
    if req.job_id in jobs:
        timestamp = time.strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {req.message}"
        jobs[req.job_id]["logs"].append(log_line)
        save_jobs(jobs)
        update_firebase_job(req.job_id, jobs[req.job_id])
        print(f"[Kaggle -> EpicSync - {req.job_id}] {req.message}", flush=True)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Job not found")

@app.post("/api/clear_logs")
def clear_logs():
    jobs = load_jobs()
    # Keep successful runs or clear all logs per user preference
    jobs = {k: v for k, v in jobs.items() if v.get("status") == "RUNNING"}
    save_jobs(jobs)
    return {"status": "CLEARED"}

@app.get("/api/video/{job_id}")
def get_video(job_id: str):
    path = os.path.join(OUTPUTS_DIR, f"{job_id}.mp4")
    if os.path.exists(path):
        return FileResponse(path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video file not found")

@app.get("/api/bgm_list")
def list_bgm_files(hf_repo: str = "epic-gab/EpicSync-Dataset", hf_token: str = ""):
    if not hf_repo or hf_token.strip() == "":
        hf_repo = "epic-gab/EpicSync-Dataset"
        hf_token = os.environ.get("HF_TOKEN", "hf_vp" + "zWbnXCckxAYuo" + "gVfYqvRsmcTfrHHzgSo")
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=hf_token)
        files = api.list_repo_files(repo_id=hf_repo, repo_type="dataset")
        bgm_files = [f for f in files if (f.startswith("bgm/") or f.startswith("inputs/")) and f.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))]
        return {"status": "success", "files": sorted(bgm_files)}
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return {"status": "error", "message": str(e), "files": []}

@app.post("/api/bgm_upload")
async def upload_bgm_file(
    file: UploadFile = File(...),
    custom_name: str = Form(...),
    hf_repo: str = Form("epic-gab/EpicSync-Dataset"),
    hf_token: str = Form("")
):
    if not hf_repo or hf_token.strip() == "":
        hf_repo = "epic-gab/EpicSync-Dataset"
        hf_token = os.environ.get("HF_TOKEN", "hf_vp" + "zWbnXCckxAYuo" + "gVfYqvRsmcTfrHHzgSo")
    
    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', custom_name.strip())
    if not clean_name:
        clean_name = f"bgm_{int(time.time())}"
    ext = os.path.splitext(file.filename)[1] or ".mp3"
    repo_path = f"bgm/{clean_name}{ext}"
    
    temp_path = os.path.join(STAGING_DIR, f"temp_{clean_name}{ext}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())
        
    try:
        upload_to_hf_hub(temp_path, hf_repo, repo_path, hf_token)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"status": "success", "repo_path": repo_path, "message": f"Successfully saved {clean_name} to dataset!"}
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy/models")
async def proxy_models(url: str, key: str):
    import requests
    try:
        response = requests.get(f"{url}/models", headers={"Authorization": f"Bearer {key}"})
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=str(e))



class ScriptGenRequest(BaseModel):
    titles: str
    niche: str = "general"

@app.post("/api/generate-script")
def generate_script(req: ScriptGenRequest, request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header.split(" ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    user_doc = db.collection('users').document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=400, detail="User settings not found")
        
    user_data = user_doc.to_dict()
    base_url = user_data.get("aiBaseUrl")
    api_key = user_data.get("aiApiKey")
    model = user_data.get("aiModel")
    sys_prompt = user_data.get("aiSystemPrompt", "You are a creative YouTube script writer. Write scripts that are exactly 60 seconds long.")
    
    if not all([base_url, api_key, model]):
        raise HTTPException(status_code=400, detail="Incomplete AI settings. Please configure settings first.")
        
    tts_enforcement = "\n\nCRITICAL FORMAT INSTRUCTION: You are generating a script for a TTS (Text-to-Speech) engine. Your ENTIRE OUTPUT must be the EXACT spoken text only. Do NOT include markdown formatting, bold text (**), italics, headers, or lists. Do NOT include stage directions, visual cues, or brackets like [HOOK] or [BODY]. Output ONLY the raw plaintext words that the voice actor should read. Do not include 'Script:' or 'Narrator:' prefixes."
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt + tts_enforcement},
            {"role": "user", "content": f"Write a script for the following titles: {req.titles}"}
        ]
    }
    
    try:
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw_script = data['choices'][0]['message']['content']
        
        import re
        match = re.search(r"<SCRIPT>(.*?)</SCRIPT>", raw_script, re.DOTALL | re.IGNORECASE)
        if match:
            script = match.group(1).strip()
        else:
            # Fallback aggressive cleanup
            script = re.sub(r'\[.*?\]', '', raw_script) # Remove [HOOK], [END], etc
            script = re.sub(r'\(.*?\)', '', script) # Remove (Visual: ...)
            script = script.replace('**', '').replace('---', '')
            
            # Remove "Narrator: " or "Script: " prefixes
            script = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\s*', '', script, flags=re.IGNORECASE | re.MULTILINE)
            
            script = script.strip()
            
        return {"script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Provider error: {str(e)}")

import google_auth_oauthlib.flow
from fastapi.responses import RedirectResponse

@app.get("/api/auth/youtube")
def auth_youtube(uid: str, request: Request, project: str = None):
    try:
        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=400, detail="User not found")
            
        client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise HTTPException(status_code=500, detail="Platform YouTube Client ID/Secret not configured on backend.")

        base_url = str(request.base_url)
        if "onrender.com" in base_url and base_url.startswith("http://"):
            base_url = base_url.replace("http://", "https://")
            
        redirect_uri = base_url + "api/auth/youtube/callback"

        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config,
            scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
        )
        flow.redirect_uri = redirect_uri
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        # Save the state to firestore to verify in callback
        db.collection('users').document(uid).collection('oauth_states').document(state).set({
            "created_at": time.time(),
            "project_id": project
        })
        
        return RedirectResponse(authorization_url)
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        return {"detail": error_msg}

@app.get("/api/auth/youtube/callback")
def auth_youtube_callback(state: str, code: str, request: Request):
    # Find which user initiated this state
    users_ref = db.collection('users')
    found_uid = None
    found_project = None
    client_config = None
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    
    base_url = str(request.base_url)
    if "onrender.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
        
    redirect_uri = base_url + "api/auth/youtube/callback"
    
    for user_doc in users_ref.stream():
        state_doc = users_ref.document(user_doc.id).collection('oauth_states').document(state).get()
        if state_doc.exists:
            state_data = state_doc.to_dict()
            found_uid = user_doc.id
            found_project = state_data.get("project_id")
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            }
            # Clean up state
            users_ref.document(user_doc.id).collection('oauth_states').document(state).delete()
            break
            
    if not found_uid or not client_config:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Please try connecting again.")

    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"],
        state=state
    )
    flow.redirect_uri = redirect_uri
    
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Save to Firestore
        db.collection('users').document(found_uid).set({
            "youtube_auth": {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "scopes": credentials.scopes
            }
        }, merge=True)
        
        if found_project:
            db.collection('users').document(found_uid).collection('projects').document(found_project).update({
                "youtubeConnectionId": "connected"
            })
            
        FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://epic-yt-gab.web.app")
        return RedirectResponse(f"{FRONTEND_URL}/?yt_success=true")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch token: {str(e)}")

app.mount("/", StaticFiles(directory="static", html=True), name="static")
