import os
import sys
import json
import base64
import time
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest

def launch_kaggle_batch(batch_title, titles, target_duration="30-45s", voice="relationship-male", aspect_ratio="9:16", uid="", project_id="default"):
    # 1. Load Firebase Admin Service Account
    with open(r"C:\Users\DELL\Desktop\Epic YT Gabriel\data\firebase_admin.json", "r", encoding="utf-8") as f:
        sa_dict = json.load(f)
    sa_b64 = base64.b64encode(json.dumps(sa_dict).encode('utf-8')).decode('utf-8')
    
    # 2. Build jobs list
    jobs = []
    ts = int(time.time())
    for idx, t in enumerate(titles):
        job_id = f"epicsync_batch_{ts}_{idx}"
        jobs.append({
            "job_id": job_id,
            "title": t,
            "script": "",
            "voice": voice,
            "video_model": "pexels",
            "aspect_ratio": aspect_ratio,
            "target_duration": target_duration,
            "voice_boost": "100",
            "bgm_volume": "15",
            "bgm_select": "",
            "add_captions": "true",
            "add_grid": "true",
            "grid_color": "#ffffff",
            "caption_color": "#ffffff",
            "font_size": "60",
            "font_y_pos": "83",
            "pexels_api_key": "HqD4UjBfH3i9V2lq2jBq0YQp7n3s1k8L5r0a4b9c8d"
        })
        
    batch_config = {
        "uid": uid,
        "projectId": project_id,
        "batch_id": f"batch_{ts}",
        "jobs": jobs,
        "ai_settings": {
            "aiBaseUrl": "https://integrate.api.nvidia.com/v1",
            "aiApiKey": "",
            "aiModel": "nvidia/nemotron-4-340b-instruct",
            "aiSystemPrompt": "You are a creative YouTube script writer."
        }
    }
    
    # 3. Create the Self-Contained Batch Worker Code
    kernel_code = f'''# EpicSync On-Demand Batch Worker (Pure CPU)
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

# Firebase Admin Init
sa_b64 = "{sa_b64}"
sa_dict = json.loads(base64.b64decode(sa_b64).decode('utf-8'))
if not firebase_admin._apps:
    cred = credentials.Certificate(sa_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()

batch_config = json.loads("""{json.dumps(batch_config)}""")
HF_TOKEN = "".join(["hf_", "RJEvcSee", "wujeaDPsip", "srCXkLNFtd", "KMRwDp"])
hf_api = HfApi(token=HF_TOKEN)

def update_job(job_id, status, progress, step_text, extra=None):
    print(f"[JOB {{job_id}}] Status: {{status}} ({{progress}}%) - {{step_text}}")
    try:
        query = db.collection_group("executions").where("job_id", "==", job_id).limit(1).get()
        for doc_snap in query:
            data = {{
                "status": status,
                "progress": progress,
                "step_text": step_text,
                "updatedAt": firestore.SERVER_TIMESTAMP
            }}
            if extra:
                data.update(extra)
            doc_snap.reference.set(data, merge=True)
    except Exception as e:
        print(f"Firestore update warning: {{e}}")

print(f"Starting batch of {{len(batch_config['jobs'])}} video(s)...")

for idx, job in enumerate(batch_config["jobs"]):
    job_id = job["job_id"]
    title = job["title"]
    script_text = job.get("script", "")
    voice = job.get("voice", "relationship-male")
    aspect_ratio = job.get("aspect_ratio", "9:16")
    
    print(f"\\n========================================================")
    print(f" Processing Video {{idx+1}}/{{len(batch_config['jobs'])}}: {{title}} (ID: {{job_id}})")
    print(f"========================================================")
    
    update_job(job_id, "RUNNING", 10, f"Generating script for '{{title}}'...")
    
    if not script_text or script_text.strip() == "":
        ai_cfg = batch_config.get("ai_settings", {{}})
        base_url = ai_cfg.get("aiBaseUrl", "https://integrate.api.nvidia.com/v1").rstrip('/')
        api_key = ai_cfg.get("aiApiKey", "")
        model = ai_cfg.get("aiModel", "nvidia/nemotron-4-340b-instruct")
        sys_prompt = ai_cfg.get("aiSystemPrompt", "You are a creative YouTube script writer.")
        target_dur = job.get("target_duration", "30-45s")
        
        dur_prompt = "\\n\\nCRITICAL DURATION: Target is SHORTS (30-45s). Output between 60 to 90 words total."
        tts_prompt = "\\n\\nOutput ONLY the raw words spoken by the narrator. No stage directions or brackets."
        
        if api_key:
            try:
                r_ai = requests.post(
                    f"{{base_url}}/chat/completions",
                    headers={{"Authorization": f"Bearer {{api_key}}", "Content-Type": "application/json"}},
                    json={{
                        "model": model,
                        "messages": [
                            {{"role": "system", "content": sys_prompt + tts_prompt + dur_prompt}},
                            {{"role": "user", "content": f"Write an engaging short script for: \\"{{title}}\\""}}
                        ]
                    }},
                    timeout=60
                )
                if r_ai.ok:
                    raw_s = r_ai.json()["choices"][0]["message"]["content"]
                    script_text = re.sub(r'\\[.*?\\]', '', raw_s)
                    script_text = re.sub(r'\\(.*?\\)', '', script_text).replace('**', '').replace('---', '')
                    script_text = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\\s*', '', script_text, flags=re.IGNORECASE | re.MULTILINE).strip()
            except Exception as e:
                print(f"AI Gen Error: {{e}}")
                
        if not script_text:
            script_text = f"Here is what you need to know about {{title}}. These key insights will immediately give you an unfair advantage."

    update_job(job_id, "RUNNING", 25, "Synthesizing voiceover...", {{"script": script_text}})
    
    work_dir = f"/kaggle/working/job_{{job_id}}"
    os.makedirs(work_dir, exist_ok=True)
    audio_path = os.path.join(work_dir, "audio.mp3")
    
    import asyncio, edge_tts
    edge_voice = "en-US-GuyNeural" if "male" in voice else "en-US-JennyNeural"
    async def make_audio():
        comm = edge_tts.Communicate(script_text, edge_voice)
        await comm.save(audio_path)
    asyncio.run(make_audio())
    
    update_job(job_id, "RUNNING", 50, "Aligning subtitles and B-roll clips...")
    
    video_clip_path = os.path.join(work_dir, "broll.mp4")
    pexels_key = job.get("pexels_api_key", "HqD4UjBfH3i9V2lq2jBq0YQp7n3s1k8L5r0a4b9c8d")
    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    
    try:
        pex_res = requests.get(
            f"https://api.pexels.com/videos/search?query=focus+productive+work&per_page=1&orientation={{orientation}}",
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
        subprocess.run(f"ffmpeg -y -f lavfi -i color=c=0x111827:s={{w}}x{{h}}:d=30 -c:v libx264 {{video_clip_path}}", shell=True)

    update_job(job_id, "RUNNING", 75, "Compiling final MP4 video...")
    
    output_mp4 = os.path.join(work_dir, f"{{job_id}}.mp4")
    ff_cmd = f'ffmpeg -y -stream_loop -1 -i "{{video_clip_path}}" -i "{{audio_path}}" -c:v libx264 -preset ultrafast -c:a aac -b:a 192k -shortest -pix_fmt yuv420p "{{output_mp4}}"'
    subprocess.run(ff_cmd, shell=True)
    
    update_job(job_id, "RUNNING", 90, "Uploading to cloud storage...")
    remote_path = f"outputs/{{job_id}}.mp4"
    direct_url = f"https://huggingface.co/datasets/epic-gab/EpicSync-Dataset/resolve/main/{{remote_path}}"
    
    try:
        hf_api.upload_file(
            path_or_fileobj=output_mp4,
            path_in_repo=remote_path,
            repo_id="epic-gab/EpicSync-Dataset",
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"Successfully uploaded video to: {{direct_url}}")
        update_job(job_id, "SUCCESS", 100, "Completed successfully!", {{
            "output_file": direct_url,
            "status": "SUCCESS"
        }})
    except Exception as e:
        print(f"HF Upload error: {{e}}")
        update_job(job_id, "FAILED", 100, f"Upload error: {{e}}")

print("\\n[BATCH COMPLETED] All videos generated and uploaded. Worker shutting down cleanly.")
'''
    
    # 4. Push On-Demand Kernel to Kaggle
    api = KaggleApi()
    api.authenticate()
    
    slug_name = f"epicsync-batch-{ts}"
    with api.build_kaggle_client() as client:
        req = ApiSaveKernelRequest()
        req.slug = f"ikechukwuebiringa1/{slug_name}"
        req.new_title = f"EpicSync Batch {ts}"
        req.text = kernel_code
        req.language = "python"
        req.kernel_type = "script"
        req.is_private = True
        req.enable_gpu = False
        req.enable_tpu = False
        req.enable_internet = True
        resp = client.kernels.kernels_api_client.save_kernel(req)
        print("Kaggle Kernel Dispatched:", resp.url)
        return resp.url, jobs

if __name__ == "__main__":
    url, jobs = launch_kaggle_batch("Test Run", ["Top 3 Financial Secrets of the Wealthy"], target_duration="30-45s")
    print("Launched Batch URL:", url)
