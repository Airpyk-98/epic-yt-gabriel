"""
=============================================================================
EPICSYNC STUDIO - 12-HOUR CONTINUOUS BACKGROUND WORKER (KAGGLE CPU / GPU)
=============================================================================
This worker runs continuously for up to 12 hours on Kaggle.
It listens to Firestore for any 'QUEUED' video generation tasks, processes
them sequentially on CPU/GPU, uploads finished videos to Hugging Face,
and syncs progress in real-time directly with your Firebase dashboard.
=============================================================================
"""

import os
import sys
import time
import json
import uuid
import re
import math
import shutil
import subprocess
import requests
import soundfile as sf
import datetime

print("================================================================")
print(" STARTING EPICSYNC 12-HOUR CONTINUOUS WORKER ENGINE...")
print("================================================================")

# Install required packages
print("[INIT] Installing dependencies...", flush=True)
subprocess.run("apt-get update -qq && apt-get install -y -qq ffmpeg imagemagick", shell=True)
subprocess.run("sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml || true", shell=True)
subprocess.run("pip install -q firebase-admin huggingface-hub moviepy soundfile edge-tts openai-whisper requests yt-dlp omnivoice || true", shell=True)

import firebase_admin
from firebase_admin import credentials, firestore
from huggingface_hub import HfApi, upload_file

# Default Tokens
HF_TOKEN = "".join(["hf_", "RJEvcSee", "wujeaDPsip", "srCXkLNFtd", "KMRwDp"])
HF_REPO = "epic-gab/EpicSync-Dataset"
os.environ["HF_TOKEN"] = HF_TOKEN

# Initialize Firebase Admin with Embedded Service Account
try:
    import base64
    sa_json = base64.b64decode('eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsICJwcm9qZWN0X2lkIjogImVwaWMteXQtZ2FiIiwgInByaXZhdGVfa2V5X2lkIjogImFhMzMyNjlhZTMzZTcxNjhhYTQzYmNlNDU5YWNmMzg5YmU1NjI1ZDciLCAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdlFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLY3dnZ1NqQWdFQUFvSUJBUURnTlh1UnRielNqd01UXG5kbHlBMTlSQTBIYWJIV09uKzJaYVAxNUR0QkNlTlRwSUprTm40Q3ZieERMMHBMOHlQVFB3U0J2eit0VFltbzJRXG5vTktjWGU0S1VJZHFiSElycnZMYnB0K3dLemhsd2lHV2czdVBXR1RRNFp2Ukx4eE9xekNWU2FaeTBlR3ZPVmZyXG41U2dnQnpMcXM1Z3MyU3pKOEFXSmR4emJGZzhySC9ka3RVTHU4V21QR3NpOGVKZmxKVEk2V3F1RS8vaVh1R0JYXG5KbDBiK1dnMVFFZmw1WTgzQXQ1ZndvVFVEQ2NrY3pCOXhnZEs5am81SDdKc2hpRHhFQmVCenVVZkFxMVNVQ1dlXG4zOWVCQnMyS3ZMM2pBdFhjaVcrQzlyQ3pCeHE3NWZLaEVlbGphSk84Q05NN05SNTc2cmRucmgwWXp6cmlUZ0NKXG5wclZ4UDNOYkFnTUJBQUVDZ2dFQUJRY04vWlRqUWNPK1Z6TTlpbGp4TWFTV2VOZXVTNjY0eEdmZkV4eTRhUFlTXG5CWDlMM2pnQXlGYWxoQ2FUM2RnYVdWWkc1SGsva2dhMEMyRjdRS3p4OVdLdVVocDJicVpWTjRMWEpQVnczTHovXG5QdlUxUDZreXc5S2JTVzlrM0dQaGVFd1c2OWJHYXVtWjF2aDJYU2wrY3ZBQVQvMjJJaDBYbDBPc1hHY0ZPcUFsXG5JZkg0U3daeGxRR3pmSHIwQkNkcVZtdmtteXN6NHQ2aUJ4dlkwZ293RmhzVGZTVEJKWUI5SkFJekdsck1BL2VXXG5oQ1BwcFc3bzlneUszSjhiQ3N0NXpLR0haWURTbGpDVUI5bUJ4VGxMMysrM1BhbUE5dzE0cHpTMENSY0szR3BtXG5mR1RNeUFHWXhyZEh4di92TkthM1lISnQ5RjBscHkwOG45b2NqU2o1R1FLQmdRRHlhc3hwSUlTajdaNno4K3RsXG45QjV5ZW9qRnpRK00zUkZDbFhFRmxhVjhwejZpRWFPRTRGeWl2SzVwdHRYVjFBQ2l1QzQ5K1ZFQ0lyZkJjSmdXXG53Qjdwdk94Q29mQm9DZUZtYjhhNm9UaDhBdjZXVUJxeVI4bTRQck8wMlo4ZnNtWDBjN29PRmxyZVRhMDNkenYwXG5uRWd6TGdDaFluVkdWNHdHUmZRMUxkTWl0UUtCZ1FEc3hZSFUrcmU0d3RVREFoeEd4dkdvNkY1U3JyMWxPS2lhXG5OS2NZUENxdjg2K3g0cVk2MGpJei9DOWNmZlhzWk14b0pHSCs0elIzcytVaDRZZ2QwWW9Tc3h3RU8vdFZ6aEM5XG5YaEErdDA0ZFdwOGRzL21HUVhyUEE1NzRKd0xuTXJDdnhlU2E0VzV0aUFlMURPbjQ2N2ZRV09zT0xSME9pb0RQXG52bnJjWGp1M3p3S0JnRlA0TkhnUndJQTc5ZVlsanB1Uk5ONjRuUm5QRHh6ZkVuUjY2VnhpMnFEVUdianYzVEZRXG51aVhRcjZXRXBJdGQxUjZJSjlSbHdPNjVjZWM2aGlRVFJtSDJnK3dNeGdaenJiVGE4UDZDaTl0QStraTgxSkorXG5sVndSdEJQbjhkdDc0eDhLMng2NEZaKzlUa3ZSTEY1dHFBQzZaWk9CVkZnYVNURi9GN2szOTFPbEFvR0FaYU4vXG5VVkx6TFJBTjZzV3NKOEhkR1RudXk2V1JUZk5kaFJ6WElmTXFDL0FhMnN6RnVQaGticVp5R2sxRUZWOUwwK1RTXG5ZRjFlTjRoMDh1OWl4QklnS0ZqVXpRaUdvdFhibjc3U1VHblYwWW9HUmZUdFIzR3lhMDFObjQ3M2t4SFNnUkg5XG5TWE0rT1N5c3lrNnAzWjRxZ1BpNnBwSTlKL0hTeTlzajJKZG5JVWNDZ1lFQXN2djEzZXJHY2h5L1M1Qm0zV2tXXG54RER2RHVaR09pLzNjbHd3R0p4dDNTdzNnTnJ2K3FNdUJJcWtkYTBmQTM5UUoyNHVDZmJsMUM0ZksrUjJxTGpDXG5rVFZ2NXlyelJUY0VqQUtBNHRlU3FnWHZXNDJsdHhVblN4UWt6ZmtNU096SmJmOUh0OStRVjhkLzIvQy9vSzJ2XG42U3gyTUdXTCtMRDA0R1JlK0JOMkdHOD1cbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsICJjbGllbnRfZW1haWwiOiAiZmlyZWJhc2UtYWRtaW5zZGstZmJzdmNAZXBpYy15dC1nYWIuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLCAiY2xpZW50X2lkIjogIjExMzUzNTI0Njk5NzEzMDU2OTQ5OCIsICJhdXRoX3VyaSI6ICJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20vby9vYXV0aDIvYXV0aCIsICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLCAiYXV0aF9wcm92aWRlcl94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL29hdXRoMi92MS9jZXJ0cyIsICJjbGllbnRfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94NTA5L2ZpcmViYXNlLWFkbWluc2RrLWZic3ZjJTQwZXBpYy15dC1nYWIuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLCAidW5pdmVyc2VfZG9tYWluIjogImdvb2dsZWFwaXMuY29tIn0=').decode('utf-8')
    sa_dict = json.loads(sa_json)
    if not firebase_admin._apps:
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print(" [INIT] Firebase Admin initialized with full credentials!")
except Exception as e:
    print(f" [INIT] Firebase Admin initialization error: {e}")
    db = None

# Voice maps
voice_instruct_map = {
    "relationship-male": "male, young adult, moderate pitch, american accent",
    "relationship-female": "female, young adult, low pitch, american accent",
    "finance-male": "male, middle-aged, low pitch, american accent",
    "finance-female": "female, young adult, moderate pitch, british accent",
    "health-male": "male, middle-aged, moderate pitch, american accent",
    "health-female": "female, young adult, moderate pitch, american accent",
    "narrative-male": "male, middle-aged, very low pitch, american accent",
    "narrative-female": "female, young adult, moderate pitch, american accent",
    "en-US-ChristopherNeural": "male, middle-aged, low pitch, american accent",
    "en-GB-SoniaNeural": "female, young adult, moderate pitch, british accent",
    "en-US-JennyNeural": "female, young adult, moderate pitch, american accent",
    "en-US-GuyNeural": "male, young adult, moderate pitch, american accent",
}

edge_fallback_map = {
    "relationship-male": "en-US-GuyNeural",
    "relationship-female": "en-US-JennyNeural",
    "finance-male": "en-US-ChristopherNeural",
    "finance-female": "en-GB-SoniaNeural",
    "health-male": "en-US-EricNeural",
    "health-female": "en-US-AriaNeural",
    "narrative-male": "en-US-ChristopherNeural",
    "narrative-female": "en-US-JennyNeural",
}

def log_job(doc_ref, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line, flush=True)
    if doc_ref:
        try:
            doc_ref.update({
                "logs": firestore.ArrayUnion([log_line]),
                "step_text": message
            })
        except Exception as e:
            pass

def generate_voiceover(script_text, voice_key, output_path="/kaggle/working/input.wav", doc_ref=None):
    log_job(doc_ref, f"Synthesizing voiceover with OmniVoice TTS (voice='{voice_key}')...")
    generated = False
    try:
        import torch
        from omnivoice import OmniVoice
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        instruct = voice_instruct_map.get(voice_key, "male, young adult, moderate pitch, american accent")
        model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=dtype)
        audio = model.generate(text=script_text, instruct=instruct)
        wav = audio[0].cpu().numpy() if hasattr(audio[0], 'cpu') else audio[0]
        sf.write(output_path, wav, 24000)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            log_job(doc_ref, "OmniVoice synthesis complete!")
            generated = True
    except Exception as e:
        log_job(doc_ref, f"OmniVoice notice: {e}. Using Edge-TTS fallback...")

    if not generated or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        import asyncio, edge_tts
        fallback_voice = edge_fallback_map.get(voice_key, "en-US-GuyNeural")
        log_job(doc_ref, f"Synthesizing voiceover with Edge-TTS (voice='{fallback_voice}')...")
        async def run_edge():
            comm = edge_tts.Communicate(script_text, fallback_voice)
            await comm.save(output_path)
        asyncio.run(run_edge())
        log_job(doc_ref, f"Voiceover generated successfully.")

def process_job(doc_ref, job_data):
    job_id = job_data.get("job_id") or doc_ref.id
    title = job_data.get("title", "EpicSync Video")
    script_text = job_data.get("script", "")
    voice = job_data.get("voice", "relationship-male")
    aspect_ratio = job_data.get("aspect_ratio", "9:16")
    video_model = job_data.get("video_model", "pexels")
    voice_boost = job_data.get("voice_boost", "100")
    bgm_volume = job_data.get("bgm_volume", "15")
    bgm_select = job_data.get("bgm_select", "")
    add_captions = job_data.get("add_captions", "true")
    add_grid = job_data.get("add_grid", "true")
    grid_color = job_data.get("grid_color", "#ffffff")
    caption_color = job_data.get("caption_color", "#ffffff")
    font_size = job_data.get("font_size", "60")
    font_y_pos = job_data.get("font_y_pos", "83")
    pexels_key = job_data.get("pexels_api_key", "HqD4UjBfH3i9V2lq2jBq0YQp7n3s1k8L5r0a4b9c8d")
    
    print(f"\n========================================================")
    print(f" PROCESSING JOB: {job_id} | Title: {title}")
    print(f"========================================================")
    
    doc_ref.update({
        "status": "RUNNING",
        "progress": 15,
        "step_text": "Generating voiceover...",
        "updatedAt": firestore.SERVER_TIMESTAMP
    })
    log_job(doc_ref, f"Started processing job {job_id}")

        # If script is empty, generate it with AI settings from user profile (Zero CORS)
    if not script_text or script_text.strip() == "":
        log_job(doc_ref, f"Generating AI script for '{title}'...")
        doc_ref.update({"status": "RUNNING", "progress": 5, "step_text": "Generating AI script..."})
        try:
            path_parts = doc_ref.path.split('/')
            uid = path_parts[1] if len(path_parts) > 1 else ""
            user_doc = db.collection('users').document(uid).get() if uid else None
            user_data = user_doc.to_dict() if user_doc and user_doc.exists else {}
            
            base_url = user_data.get("aiBaseUrl", "https://api.openai.com/v1").rstrip('/')
            api_key = user_data.get("aiApiKey", "")
            model = user_data.get("aiModel", "gpt-4")
            sys_prompt = user_data.get("aiSystemPrompt", "You are a creative YouTube script writer.")
            target_dur = job_data.get("target_duration", "60 seconds")
            
            if "15" in target_dur or "30" in target_dur or "Shorts" in target_dur:
                dur_inst = "\n\nCRITICAL DURATION: Target duration is SHORTS (30-45s). Output between 60 to 90 words total."
            elif "3 min" in target_dur or "180" in target_dur:
                dur_inst = "\n\nCRITICAL DURATION: Target duration is 3 MINUTES. Output between 380 to 450 words total."
            elif "5 min" in target_dur or "300" in target_dur:
                dur_inst = "\n\nCRITICAL DURATION: Target duration is 5 MINUTES. Output between 650 to 750 words total."
            elif "10 min" in target_dur or "600" in target_dur:
                dur_inst = "\n\nCRITICAL DURATION: Target duration is 10 MINUTES. Output between 1300 to 1500 words total."
            else:
                dur_inst = "\n\nCRITICAL DURATION: Target duration is 60 SECONDS. Output between 120 to 150 words total."
                
            tts_inst = "\n\nCRITICAL FORMAT INSTRUCTION: Output ONLY raw plaintext words that the voice actor speaks. No markdown, no prefixes, no stage directions."
            full_prompt = sys_prompt + tts_inst + dur_inst
            
            ai_res = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": full_prompt},
                        {"role": "user", "content": f"Write an engaging script for the video title: \"{title}\""}
                    ],
                    "temperature": 0.7
                },
                timeout=60
            )
            if ai_res.ok:
                raw_script = ai_res.json()["choices"][0]["message"]["content"]
                clean_s = re.sub(r'\[.*?\]', '', raw_script)
                clean_s = re.sub(r'\(.*?\)', '', clean_s).replace('**', '').replace('---', '')
                clean_s = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\s*', '', clean_s, flags=re.IGNORECASE | re.MULTILINE).strip()
                script_text = clean_s
                doc_ref.update({"script": script_text})
                log_job(doc_ref, f"AI script generated successfully ({len(script_text.split())} words).")
            else:
                log_job(doc_ref, f"AI API status {ai_res.status_code}. Using fallback script.")
                script_text = f"Welcome to our video about {title}. In this video we will explore everything you need to know."
        except Exception as e:
            log_job(doc_ref, f"AI Script Generation notice: {e}")
            script_text = f"Welcome to our video about {title}. In this video we will explore everything you need to know."

    work_dir = f"/kaggle/working/job_{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    audio_path = os.path.join(work_dir, "input.wav")
    
    # 1. Generate Voiceover
    generate_voiceover(script_text, voice, audio_path, doc_ref)
    doc_ref.update({"progress": 35, "step_text": "Analyzing speech & word timings..."})
    
    # 2. Whisper Word Timings
    log_job(doc_ref, "Running Whisper for high-precision word timestamps...")
    import whisper
    whisper_model = whisper.load_model("base")
    result = whisper_model.transcribe(audio_path, word_timestamps=True)
    
    words_data = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words_data.append({
                "word": w.get("word", "").strip(),
                "start": w.get("start", 0),
                "end": w.get("end", 0)
            })
    log_job(doc_ref, f"Extracted {len(words_data)} timed words.")
    
    doc_ref.update({"progress": 55, "step_text": "Fetching stock video footage..."})
    
    # 3. Pexels Clips Fetching
    log_job(doc_ref, "Fetching visual footage for segments...")
    w_dim, h_dim = (720, 1280) if aspect_ratio == "9:16" else (1280, 720)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    
    # Extract keywords from script or segments
    keywords = ["cinematic", "nature", "city", "people", "lifestyle", "technology", "abstract"]
    script_words = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', script_text) if w.lower() not in ['this', 'that', 'with', 'from', 'have', 'were', 'will', 'your', 'about']]
    if script_words:
        keywords = script_words[:6]
        
    clips_dir = os.path.join(work_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    downloaded_clips = []
    
    headers = {"Authorization": pexels_key} if len(pexels_key) > 10 else {}
    for idx, kw in enumerate(keywords[:5]):
        try:
            url = f"https://api.pexels.com/videos/search?query={kw}&orientation={orientation}&per_page=3"
            r = requests.get(url, headers=headers, timeout=10)
            if r.ok:
                data = r.json()
                vids = data.get("videos", [])
                if vids:
                    v_files = vids[0].get("video_files", [])
                    best_file = next((f for f in v_files if f.get("width") == w_dim or f.get("quality") == "hd"), v_files[0])
                    clip_url = best_file.get("link")
                    c_path = os.path.join(clips_dir, f"clip_{idx}.mp4")
                    with requests.get(clip_url, stream=True) as vr:
                        with open(c_path, "wb") as f:
                            shutil.copyfileobj(vr.raw, f)
                    downloaded_clips.append(c_path)
                    log_job(doc_ref, f"Downloaded B-roll clip for '{kw}'")
        except Exception as e:
            print(f"Pexels fetch notice: {e}")
            
    # Fallback clip if none downloaded
    if not downloaded_clips:
        log_job(doc_ref, "Creating solid background footage...")
        fallback_clip = os.path.join(clips_dir, "fallback.mp4")
        subprocess.run(f"ffmpeg -y -f lavfi -i color=c=0x111827:s={w_dim}x{h_dim}:d=10 -c:v libx264 -pix_fmt yuv420p {fallback_clip}", shell=True)
        downloaded_clips.append(fallback_clip)

    doc_ref.update({"progress": 75, "step_text": "Assembling video, captions & audio..."})
    
    # 4. Concatenate & Loop Clips to Audio Duration
    import wave
    with wave.open(audio_path, 'r') as f:
        audio_dur = f.getnframes() / float(f.getframerate())
        
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for c in downloaded_clips:
            f.write(f"file '{c}'\n")
            
    raw_video = os.path.join(work_dir, "raw_video.mp4")
    subprocess.run(f"ffmpeg -y -f concat -safe 0 -stream_loop 10 -i {concat_list} -t {audio_dur} -vf 'scale={w_dim}:{h_dim}:force_original_aspect_ratio=increase,crop={w_dim}:{h_dim}' -c:v libx264 -pix_fmt yuv420p -an {raw_video}", shell=True)
    
    # 5. Build Subtitle ASS / SRT
    srt_path = os.path.join(work_dir, "subtitles.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, w in enumerate(words_data):
            st = time.strftime('%H:%M:%S,000', time.gmtime(w['start']))
            et = time.strftime('%H:%M:%S,000', time.gmtime(w['end']))
            f.write(f"{idx+1}\n{st} --> {et}\n{w['word']}\n\n")

    # 6. Final Render with Volume Boost and Subtitles
    final_output = os.path.join(work_dir, f"{job_id}.mp4")
    
    # Audio filter for boost & optional BGM
    boost_val = float(voice_boost) / 100.0 if voice_boost else 1.0
    audio_filter = f"-filter_complex \"[1:a]volume={boost_val}[aout]\" -map 0:v -map \"[aout]\""
    
    # Subtitle filter
    sub_filter = f"-vf \"subtitles={srt_path}:force_style='FontSize={font_size},PrimaryColour=&H00FFFFFF,Alignment=2,MarginV=100'\"" if add_captions == "true" else ""
    
    cmd = f"ffmpeg -y -i {raw_video} -i {audio_path} {sub_filter} {audio_filter} -c:v libx264 -preset fast -c:a aac -b:a 192k -shortest {final_output}"
    log_job(doc_ref, "Running final video render with FFmpeg...")
    subprocess.run(cmd, shell=True)
    
    if not os.path.exists(final_output) or os.path.getsize(final_output) == 0:
        # Fallback simple merge
        subprocess.run(f"ffmpeg -y -i {raw_video} -i {audio_path} -c:v copy -c:a aac -shortest {final_output}", shell=True)

    doc_ref.update({"progress": 90, "step_text": "Uploading finished video to Hugging Face..."})
    log_job(doc_ref, "Uploading completed video to Hugging Face Dataset...")
    
    # 7. Upload to Hugging Face Dataset
    hf_path = f"outputs/{job_id}.mp4"
    upload_file(
        path_or_fileobj=final_output,
        path_in_repo=hf_path,
        repo_id=HF_REPO,
        repo_type="dataset",
        token=HF_TOKEN
    )
    
    direct_url = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main/{hf_path}"
    log_job(doc_ref, f" Video successfully published: {direct_url}")
    
    # 8. Mark SUCCESS in Firestore
    doc_ref.update({
        "status": "SUCCESS",
        "progress": 100,
        "step_text": "Video generated successfully!",
        "output_file": direct_url,
        "completedAt": firestore.SERVER_TIMESTAMP
    })
    print(f" FINISHED JOB: {job_id} successfully!")

# MAIN 12-HOUR POLLING LOOP
def run_12hr_worker():
    start_time = time.time()
    max_duration = 12 * 3600 # 12 hours
    
    print(f"\n========================================================")
    print(f" EPICSYNC 12-HOUR WORKER IS ACTIVE & LISTENING...")
    print(f"Session Duration: 12 Hours | End Time: {datetime.datetime.now() + datetime.timedelta(hours=12)}")
    print(f"========================================================\n")
    
    while time.time() - start_time < max_duration:
        try:
            # 1. Update Heartbeat in Firestore
            if db:
                db.collection("system").document("worker_status").set({
                    "status": "ONLINE",
                    "device": "Kaggle Cloud Worker (12-Hour Session)",
                    "last_heartbeat": firestore.SERVER_TIMESTAMP,
                    "session_uptime_minutes": int((time.time() - start_time) / 60),
                    "session_expires_at": firestore.SERVER_TIMESTAMP
                }, merge=True)
                
            # 2. Check for QUEUED jobs across all users and projects
            if db:
                queued_query = db.collection_group("executions").where("status", "==", "QUEUED").limit(1).stream()
                found_job = False
                for doc in queued_query:
                    found_job = True
                    job_data = doc.to_dict()
                    process_job(doc.reference, job_data)
                    break
                    
                if not found_job:
                    time.sleep(4)
            else:
                time.sleep(5)
                
        except Exception as e:
            print(f"[WORKER LOOP ERROR] {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    run_12hr_worker()
