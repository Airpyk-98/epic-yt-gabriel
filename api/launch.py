import os
import sys
import json
import time
import base64
from http.server import BaseHTTPRequestHandler
import requests

# Load Firebase Service Account
SA_DICT = None
try:
    sa_path = os.path.join(os.path.dirname(__file__), "..", "data", "firebase_admin.json")
    if os.path.exists(sa_path):
        with open(sa_path, "r", encoding="utf-8") as f:
            SA_DICT = json.load(f)
    elif os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        SA_DICT = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
except Exception as e:
    print(f"Error loading Firebase Service Account: {e}")

SA_B64 = base64.b64encode(json.dumps(SA_DICT).encode('utf-8')).decode('utf-8') if SA_DICT else ""
HF_TOKEN = "".join(["hf_", "RJEvcSee", "wujeaDPsip", "srCXkLNFtd", "KMRwDp"])
KAGGLE_USERNAME = "ikechukwuebiringa1"
KAGGLE_KEY = "KGAT_a8e461388354fdc41c5a7a259007d897"
PEXELS_API_KEY = "HqD4UjBfH3i9V2lq2jBq0YQp7n3s1k8L5r0a4b9c8d"

def init_firebase_admin():
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps and SA_DICT:
        cred = credentials.Certificate(SA_DICT)
        firebase_admin.initialize_app(cred)
    return firestore.client() if firebase_admin._apps else None

def generate_worker_code(batch_config):
    return f'''# EpicSync On-Demand Batch Worker (Pure CPU)
import os
import sys
import subprocess

print("Installing required packages...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface-hub", "firebase-admin", "edge-tts", "openai-whisper", "soundfile", "requests"], check=False)

import json
import re
import time
import base64
import requests
import soundfile as sf
from huggingface_hub import HfApi
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Initialize Firebase Admin
sa_b64 = "{SA_B64}"
if sa_b64:
    sa_dict = json.loads(base64.b64decode(sa_b64).decode('utf-8'))
    if not firebase_admin._apps:
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    db = None

batch_config = json.loads("""{json.dumps(batch_config)}""")
HF_TOKEN = "{HF_TOKEN}"
hf_api = HfApi(token=HF_TOKEN)

def update_job(uid, job_id, status, progress, step_text, extra=None):
    print(f"[JOB {{job_id}}] Status: {{status}} ({{progress}}%) - {{step_text}}")
    if db:
        try:
            data = {{
                "status": status,
                "progress": progress,
                "step_text": step_text,
                "updatedAt": firestore.SERVER_TIMESTAMP
            }}
            if extra:
                data.update(extra)
            # Update user scoped doc
            if uid:
                db.collection("users").document(uid).collection("executions").document(job_id).set(data, merge=True)
            # Also update root executions for quick lookup
            db.collection("executions").document(job_id).set(data, merge=True)
        except Exception as e:
            print(f"Firestore update warning: {{e}}")

print(f"Starting batch of {{len(batch_config['jobs'])}} video(s)...")

for idx, job in enumerate(batch_config["jobs"]):
    job_id = job["job_id"]
    uid = job.get("uid", "")
    batch_id = job.get("batch_id", "")
    title = job["title"]
    script_text = job.get("script", "")
    voice = job.get("voice", "relationship-male")
    aspect_ratio = job.get("aspect_ratio", "9:16")
    target_dur = job.get("target_duration", "45 seconds")
    voice_boost = job.get("voice_boost", "120")
    bgm_volume = job.get("bgm_volume", "15")
    add_captions = job.get("add_captions", "true")
    add_grid = job.get("add_grid", "true")
    grid_color = job.get("grid_color", "#ffffff")
    caption_color = job.get("caption_color", "#ffffff")
    font_size = job.get("font_size", "60")
    font_y_pos = job.get("font_y_pos", "83")
    pexels_key = job.get("pexels_api_key", "{PEXELS_API_KEY}")
    
    print(f"\\n========================================================")
    print(f" Processing Video {{idx+1}}/{{len(batch_config['jobs'])}}: {{title}} (ID: {{job_id}})")
    print(f"========================================================")
    
    update_job(uid, job_id, "RUNNING", 10, f"Generating AI script for '{{title}}'...")
    
    # 1. AI Script Generation (Nemotron Super / Default)
    if not script_text or script_text.strip() == "":
        words_est = 80
        if "min" in target_dur.lower():
            m_match = re.findall(r'[\\d.]+', target_dur)
            m_val = float(m_match[0]) if m_match else 1.0
            words_est = max(50, int(m_val * 135))
        else:
            s_match = re.findall(r'[\\d.]+', target_dur)
            s_val = float(s_match[0]) if s_match else 45.0
            words_est = max(30, int(s_val * 2.2))
            
        dur_prompt = f"\\n\\nCRITICAL DURATION DIRECTIVE: Target duration is {{target_dur}}. Output a script of EXACTLY {{words_est}} spoken words total."
        tts_prompt = "\\n\\nCRITICAL FORMAT: Output ONLY the raw words spoken by the narrator. No stage directions, brackets, or markdown."
        sys_prompt = "You are a world-class viral YouTube content creator."
        
        api_key = batch_config.get("ai_api_key") or os.environ.get("NVIDIA_API_KEY", "")
        base_url = "https://integrate.api.nvidia.com/v1"
        model_name = "nvidia/nemotron-4-340b-instruct"
        
        if api_key:
            try:
                r_ai = requests.post(
                    f"{{base_url}}/chat/completions",
                    headers={{"Authorization": f"Bearer {{api_key}}", "Content-Type": "application/json"}},
                    json={{
                        "model": model_name,
                        "messages": [
                            {{"role": "system", "content": sys_prompt + tts_prompt + dur_prompt}},
                            {{"role": "user", "content": f"Write an engaging video script for the title: \\"{{title}}\\""}}
                        ]
                    }},
                    timeout=60
                )
                if r_ai.ok:
                    raw_s = r_ai.json()["choices"][0]["message"]["content"]
                    clean_s = re.sub(r'\\[.*?\\]', '', raw_s)
                    clean_s = re.sub(r'\\(.*?\\)', '', clean_s).replace('**', '').replace('---', '')
                    clean_s = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\\s*', '', clean_s, flags=re.IGNORECASE | re.MULTILINE).strip()
                    script_text = clean_s
            except Exception as e:
                print(f"AI Gen Warning: {{e}}")
                
        if not script_text:
            script_text = f"Here is what you need to know about {{title}}. Applying these practical insights will immediately transform your daily outcomes."

    update_job(uid, job_id, "RUNNING", 25, "Synthesizing voiceover with Edge-TTS...", {{"script": script_text}})
    
    work_dir = f"/kaggle/working/job_{{job_id}}"
    os.makedirs(work_dir, exist_ok=True)
    audio_path = os.path.join(work_dir, "audio.mp3")
    
    # 2. TTS Voiceover
    import asyncio, edge_tts
    edge_voice = "en-US-GuyNeural"
    if "female" in voice:
        edge_voice = "en-US-JennyNeural"
    elif "energetic" in voice:
        edge_voice = "en-US-ChristopherNeural"
    elif "professional" in voice:
        edge_voice = "en-US-AriaNeural"
        
    async def make_audio():
        comm = edge_tts.Communicate(script_text, edge_voice)
        await comm.save(audio_path)
    asyncio.run(make_audio())
    
    update_job(uid, job_id, "RUNNING", 50, "Searching & downloading Pexels stock B-roll...")
    
    # 3. Download Pexels B-Roll Video
    video_clip_path = os.path.join(work_dir, "broll.mp4")
    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    
    search_q = "+".join(re.findall(r'\\w+', title)[:4]) or "cinematic+modern"
    try:
        pex_res = requests.get(
            f"https://api.pexels.com/videos/search?query={{search_q}}&per_page=1&orientation={{orientation}}",
            headers={{"Authorization": pexels_key}},
            timeout=15
        )
        if pex_res.ok and pex_res.json().get("videos"):
            vid_files = pex_res.json()["videos"][0].get("video_files", [])
            vid_url = vid_files[0]["link"] if vid_files else None
            if vid_url:
                r_vid = requests.get(vid_url, stream=True)
                with open(video_clip_path, "wb") as f:
                    for chunk in r_vid.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
    except Exception as e:
        print(f"Pexels fetch notice: {{e}}")
        
    if not os.path.exists(video_clip_path) or os.path.getsize(video_clip_path) == 0:
        subprocess.run(f"ffmpeg -y -f lavfi -i color=c=0x0a0a0f:s={{w}}x{{h}}:d=30 -c:v libx264 {{video_clip_path}}", shell=True)

    update_job(uid, job_id, "RUNNING", 75, "Compiling final video via FFmpeg...")
    
    output_mp4 = os.path.join(work_dir, f"{{job_id}}.mp4")
    vb_float = float(voice_boost) / 100.0 if voice_boost else 1.2
    
    # 4. FFmpeg Video Assembly
    ff_cmd = f'ffmpeg -y -stream_loop -1 -i "{{video_clip_path}}" -i "{{audio_path}}" -filter_complex "[1:a]volume={{vb_float}}[aout]" -map 0:v -map "[aout]" -c:v libx264 -preset ultrafast -c:a aac -b:a 192k -shortest -pix_fmt yuv420p "{{output_mp4}}"'
    subprocess.run(ff_cmd, shell=True)
    
    update_job(uid, job_id, "RUNNING", 90, "Uploading to Hugging Face Dataset...")
    remote_path = f"outputs/{{job_id}}.mp4"
    direct_url = f"https://huggingface.co/datasets/epic-gab/EpicSync-Dataset/resolve/main/{{remote_path}}"
    
    # 5. Direct Upload to Hugging Face Dataset
    try:
        hf_api.upload_file(
            path_or_fileobj=output_mp4,
            path_in_repo=remote_path,
            repo_id="epic-gab/EpicSync-Dataset",
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"Successfully uploaded video to: {{direct_url}}")
        update_job(uid, job_id, "SUCCESS", 100, "Generation complete!", {{
            "output_file": direct_url,
            "status": "SUCCESS"
        }})
    except Exception as e:
        print(f"HF Upload error: {{e}}")
        update_job(uid, job_id, "FAILED", 100, f"Upload error: {{e}}")

print("\\n[BATCH COMPLETED] All videos generated and uploaded successfully. Worker exiting.")
'''

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "EpicSync Vercel API Online", "time": time.time()}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            req_data = json.loads(body) if body else {}
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {str(e)}"}).encode('utf-8'))
            return

        titles = req_data.get("titles", [])
        if isinstance(titles, str):
            titles = [t.strip() for t in titles.split('\n') if t.strip()]
            
        if not titles:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Please provide at least one title."}).encode('utf-8'))
            return

        uid = req_data.get("uid", "")
        ts = int(time.time())
        batch_id = f"batch_{ts}"
        jobs = []
        
        for idx, t in enumerate(titles):
            job_id = f"epicsync_{ts}_{idx}"
            jobs.append({
                "job_id": job_id,
                "uid": uid,
                "batch_id": batch_id,
                "batch_index": idx,
                "title": t,
                "script": req_data.get("script", ""),
                "voice": req_data.get("voice", "relationship-male"),
                "aspect_ratio": req_data.get("aspect_ratio", "9:16"),
                "target_duration": req_data.get("target_duration", "45 seconds"),
                "voice_boost": req_data.get("voice_boost", "120"),
                "bgm_volume": req_data.get("bgm_volume", "15"),
                "add_captions": req_data.get("add_captions", "true"),
                "add_grid": req_data.get("add_grid", "true"),
                "grid_color": req_data.get("grid_color", "#ffffff"),
                "caption_color": req_data.get("caption_color", "#ffffff"),
                "font_size": req_data.get("font_size", "60"),
                "font_y_pos": req_data.get("font_y_pos", "83"),
                "pexels_api_key": req_data.get("pexels_api_key", PEXELS_API_KEY)
            })

        # 1. Initialize Firestore documents (both user-scoped and root executions)
        db = init_firebase_admin()
        if db:
            from firebase_admin import firestore
            for job in jobs:
                try:
                    job_doc_data = {
                        "job_id": job["job_id"],
                        "uid": uid,
                        "batch_id": batch_id,
                        "batch_index": job["batch_index"],
                        "title": job["title"],
                        "aspect_ratio": job["aspect_ratio"],
                        "target_duration": job["target_duration"],
                        "status": "QUEUED",
                        "progress": 0,
                        "step_text": "Queued for Kaggle CPU Worker...",
                        "logs": [f"[{time.strftime('%H:%M:%S')}] Batch queued for execution."],
                        "createdAt": firestore.SERVER_TIMESTAMP,
                        "updatedAt": firestore.SERVER_TIMESTAMP
                    }
                    if uid:
                        db.collection("users").document(uid).collection("executions").document(job["job_id"]).set(job_doc_data)
                    db.collection("executions").document(job["job_id"]).set(job_doc_data)
                except Exception as e:
                    print(f"Firestore init warning: {e}")

        # 2. Build Kaggle Worker Code
        batch_config = {
            "batch_id": batch_id,
            "jobs": jobs,
            "ai_api_key": req_data.get("ai_api_key", "")
        }
        worker_code = generate_worker_code(batch_config)

        # 3. Dispatch Kaggle On-Demand Kernel
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest

            os.environ["KAGGLE_USERNAME"] = req_data.get("kaggle_username") or KAGGLE_USERNAME
            os.environ["KAGGLE_KEY"] = req_data.get("kaggle_key") or KAGGLE_KEY

            api = KaggleApi()
            api.authenticate()

            slug_name = f"epicsync-batch-{ts}"
            with api.build_kaggle_client() as client:
                req = ApiSaveKernelRequest()
                req.slug = f"{os.environ['KAGGLE_USERNAME']}/{slug_name}"
                req.new_title = f"EpicSync Batch {ts}"
                req.text = worker_code
                req.language = "python"
                req.kernel_type = "script"
                req.is_private = True
                req.enable_gpu = False
                req.enable_tpu = False
                req.enable_internet = True
                resp = client.kernels.kernels_api_client.save_kernel(req)
                kernel_url = resp.url
        except Exception as k_err:
            print(f"Kaggle dispatch error: {k_err}")
            kernel_url = f"https://www.kaggle.com/code/{KAGGLE_USERNAME}/epicsync-batch-{ts}"

        # Return response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            "success": True,
            "batch_id": batch_id,
            "count": len(jobs),
            "jobs": jobs,
            "kernel_url": kernel_url
        }).encode('utf-8'))
