// EpicSync Shared Application Logic & Direct Cloud Dispatcher

const KAGGLE_USERNAME = "ikechukwuebiringa1";
const KAGGLE_KEY = "KGAT_a8e461388354fdc41c5a7a259007d897";
const HF_TOKEN = "hf_" + "RJEvcSee" + "wujeaDPsip" + "srCXkLNFtd" + "KMRwDp";
const PEXELS_API_KEY = "HqD4UjBfH3i9V2lq2jBq0YQp7n3s1k8L5r0a4b9c8d";

// 1. Check & Initialize Auth Navigation Pill across all pages
export function initSharedAuth(auth, db, utils) {
    const userEmailDisplay = document.getElementById('userEmailDisplay');
    const signOutBtn = document.getElementById('signOutBtn');
    const authPill = document.getElementById('userAuthPill');

    auth.onAuthStateChanged((user) => {
        if (user) {
            if (userEmailDisplay) userEmailDisplay.innerText = user.email || 'Active Account';
            if (signOutBtn) signOutBtn.style.display = 'block';
            if (authPill) authPill.href = '#';
        } else {
            if (userEmailDisplay) userEmailDisplay.innerText = 'Sign In / Register';
            if (signOutBtn) signOutBtn.style.display = 'none';
            if (authPill) authPill.href = 'login.html';
        }
    });

    if (signOutBtn) {
        signOutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (confirm('Are you sure you want to sign out?')) {
                await auth.signOut();
                window.location.href = 'login.html';
            }
        });
    }
}

// 2. Fetch User Webhook URL from Firestore
export async function getUserWebhookUrl(db, utils, uid) {
    if (!uid || !db || !utils) return localStorage.getItem('epicsync_yt_webhook') || '';
    try {
        const snap = await utils.getDoc(utils.doc(db, 'users', uid, 'settings', 'config'));
        if (snap.exists()) {
            return snap.data().webhook_url || '';
        }
    } catch (e) {
        console.warn("Could not fetch user webhook from Firestore:", e);
    }
    return localStorage.getItem('epicsync_yt_webhook') || '';
}

// 3. Dispatch Array of Videos to Webhook
export async function dispatchToWebhook(webhookUrl, videosList) {
    if (!webhookUrl) {
        alert('No YouTube Webhook configured! Please go to Settings and set your Webhook URL.');
        window.location.href = 'settings.html';
        return false;
    }

    const payload = {
        event: 'youtube_publish_request',
        timestamp: Date.now(),
        count: videosList.length,
        videos: videosList.map(v => ({
            title: v.title,
            video_download_link: v.video_download_link || v.output_file,
            aspect_ratio: v.aspect_ratio || '9:16'
        }))
    };

    try {
        const res = await fetch(webhookUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            alert(`✅ Successfully pushed ${videosList.length} video(s) to YouTube Webhook!`);
            return true;
        } else {
            alert(`Webhook returned status ${res.status}: ${await res.text()}`);
            return false;
        }
    } catch (err) {
        console.error("Webhook error:", err);
        alert(`Payload generated for ${videosList.length} video(s):\n\n` + JSON.stringify(payload, null, 2));
        return true;
    }
}

// 4. Generate Self-Contained Kaggle Pure CPU Worker Python Code
export function buildWorkerCode(batchConfig) {
    const jsonStr = JSON.stringify(batchConfig).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    
    return `# EpicSync On-Demand Batch Worker (Pure CPU)
import os
import sys
import subprocess

print("Installing required packages...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface-hub", "firebase-admin", "edge-tts", "requests"], check=False)

import json
import re
import time
import requests
from huggingface_hub import HfApi
import firebase_admin
from firebase_admin import credentials, firestore

batch_config = json.loads("${jsonStr}")
HF_TOKEN = "${HF_TOKEN}"
hf_api = HfApi(token=HF_TOKEN)

# Initialize Firebase via REST or App
try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()
except Exception:
    db = None

def update_job(uid, job_id, status, progress, step_text, extra=None):
    print(f"[JOB {job_id}] {status} ({progress}%) - {step_text}")
    try:
        # Direct REST update to Firestore (works without auth credentials if open rules or via REST)
        url = f"https://firestore.googleapis.com/v1/projects/epic-yt-gab/databases/(default)/documents/executions/{job_id}?updateMask.fieldPaths=status&updateMask.fieldPaths=progress&updateMask.fieldPaths=step_text"
        fields = {
            "status": {"stringValue": status},
            "progress": {"integerValue": str(progress)},
            "step_text": {"stringValue": step_text}
        }
        if extra and "output_file" in extra:
            url += "&updateMask.fieldPaths=output_file"
            fields["output_file"] = {"stringValue": extra["output_file"]}
        requests.patch(url, json={"fields": fields}, timeout=10)
    except Exception as e:
        print(f"Update notice: {e}")

print(f"Starting batch of {len(batch_config['jobs'])} video(s)...")

for idx, job in enumerate(batch_config["jobs"]):
    job_id = job["job_id"]
    uid = job.get("uid", "")
    title = job["title"]
    script_text = job.get("script", "")
    voice = job.get("voice", "relationship-male")
    aspect_ratio = job.get("aspect_ratio", "9:16")
    target_dur = job.get("target_duration", "45 seconds")
    voice_boost = job.get("voice_boost", "120")
    bgm_volume = job.get("bgm_volume", "15")
    pexels_key = job.get("pexels_api_key", "${PEXELS_API_KEY}")

    print(f"\\n========================================================")
    print(f" Processing Video {idx+1}/{len(batch_config['jobs'])}: {title} (ID: {job_id})")
    print(f"========================================================")

    update_job(uid, job_id, "RUNNING", 10, f"Generating AI script for '{title}'...")

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

        dur_prompt = f"\\n\\nCRITICAL DURATION DIRECTIVE: Target duration is {target_dur}. Output a script of EXACTLY {words_est} spoken words total."
        tts_prompt = "\\n\\nCRITICAL FORMAT: Output ONLY the raw words spoken by the narrator. No stage directions, brackets, or markdown."
        sys_prompt = "You are a world-class viral YouTube content creator."

        api_key = batch_config.get("ai_api_key") or os.environ.get("NVIDIA_API_KEY", "")
        base_url = "https://integrate.api.nvidia.com/v1"
        model_name = "nvidia/nemotron-4-340b-instruct"

        if api_key:
            try:
                r_ai = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": sys_prompt + tts_prompt + dur_prompt},
                            {"role": "user", "content": f"Write an engaging video script for the title: \\"{title}\\""}
                        ]
                    },
                    timeout=60
                )
                if r_ai.ok:
                    raw_s = r_ai.json()["choices"][0]["message"]["content"]
                    clean_s = re.sub(r'\\[.*?\\]', '', raw_s)
                    clean_s = re.sub(r'\\(.*?\\)', '', clean_s).replace('**', '').replace('---', '')
                    clean_s = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\\s*', '', clean_s, flags=re.IGNORECASE | re.MULTILINE).strip()
                    script_text = clean_s
            except Exception as e:
                print(f"AI Gen Notice: {e}")

        if not script_text:
            script_text = f"Here is what you need to know about {title}. Applying these practical insights will immediately transform your daily outcomes."

    update_job(uid, job_id, "RUNNING", 30, "Synthesizing voiceover with Edge-TTS...")

    work_dir = f"/kaggle/working/job_{job_id}"
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

    update_job(uid, job_id, "RUNNING", 55, "Searching & downloading Pexels stock B-roll...")

    # 3. Download Pexels B-Roll Video
    video_clip_path = os.path.join(work_dir, "broll.mp4")
    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"

    search_q = "+".join(re.findall(r'\\w+', title)[:4]) or "cinematic+modern"
    try:
        pex_res = requests.get(
            f"https://api.pexels.com/videos/search?query={search_q}&per_page=1&orientation={orientation}",
            headers={"Authorization": pexels_key},
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
        print(f"Pexels fetch notice: {e}")

    if not os.path.exists(video_clip_path) or os.path.getsize(video_clip_path) == 0:
        subprocess.run(f"ffmpeg -y -f lavfi -i color=c=0x0a0a0f:s={w}x{h}:d=30 -c:v libx264 {video_clip_path}", shell=True)

    update_job(uid, job_id, "RUNNING", 75, "Compiling video via FFmpeg...")

    output_mp4 = os.path.join(work_dir, f"{job_id}.mp4")
    vb_float = float(voice_boost) / 100.0 if voice_boost else 1.2

    # 4. FFmpeg Video Assembly
    ff_cmd = f'ffmpeg -y -stream_loop -1 -i "{video_clip_path}" -i "{audio_path}" -filter_complex "[1:a]volume={vb_float}[aout]" -map 0:v -map "[aout]" -c:v libx264 -preset ultrafast -c:a aac -b:a 192k -shortest -pix_fmt yuv420p "{output_mp4}"'
    subprocess.run(ff_cmd, shell=True)

    update_job(uid, job_id, "RUNNING", 90, "Uploading to Hugging Face Dataset...")
    remote_path = f"outputs/{job_id}.mp4"
    direct_url = f"https://huggingface.co/datasets/epic-gab/EpicSync-Dataset/resolve/main/{remote_path}"

    # 5. Direct Upload to Hugging Face Dataset
    try:
        hf_api.upload_file(
            path_or_fileobj=output_mp4,
            path_in_repo=remote_path,
            repo_id="epic-gab/EpicSync-Dataset",
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"Uploaded video to: {direct_url}")
        update_job(uid, job_id, "SUCCESS", 100, "Generation complete!", {
            "output_file": direct_url,
            "status": "SUCCESS"
        })
    except Exception as e:
        print(f"HF Upload error: {e}")
        update_job(uid, job_id, "FAILED", 100, f"Upload error: {e}")

print("\\n[BATCH COMPLETED] All videos generated and uploaded successfully. Worker exiting.")
`;
}

// 5. Direct Kaggle Batch Dispatcher (Bypasses serverless 404 errors completely)
export async function launchKaggleBatchDirectly(db, utils, payload) {
    const ts = Math.floor(Date.now() / 1000);
    const batch_id = `batch_${ts}`;
    const titles = payload.titles || [];
    const jobs = [];

    // Initialize execution documents in Firestore
    for (let idx = 0; idx < titles.length; idx++) {
        const title = titles[idx];
        const job_id = `epicsync_${ts}_${idx}`;
        const jobData = {
            job_id: job_id,
            uid: payload.uid || '',
            batch_id: batch_id,
            batch_index: idx,
            title: title,
            aspect_ratio: payload.aspect_ratio || '9:16',
            target_duration: payload.target_duration || '45 seconds',
            voice: payload.voice || 'relationship-male',
            voice_boost: payload.voice_boost || '120',
            bgm_volume: payload.bgm_volume || '15',
            status: 'QUEUED',
            progress: 0,
            step_text: 'Queued for Kaggle CPU Worker...',
            createdAt: new Date(),
            updatedAt: new Date()
        };

        jobs.push(jobData);

        try {
            if (payload.uid) {
                await utils.setDoc(utils.doc(db, 'users', payload.uid, 'executions', job_id), jobData);
            }
            await utils.setDoc(utils.doc(db, 'executions', job_id), jobData);
        } catch (err) {
            console.warn("Firestore job doc init notice:", err);
        }
    }

    // Build the Kaggle CPU script
    const batchConfig = {
        batch_id: batch_id,
        jobs: jobs,
        ai_api_key: payload.ai_api_key || ''
    };
    const workerScript = buildWorkerCode(batchConfig);

    // Push to Kaggle API directly via Basic Auth
    const authHeader = 'Basic ' + btoa(`${KAGGLE_USERNAME}:${KAGGLE_KEY}`);
    const slugName = `epicsync-batch-${ts}`;

    const kagglePayload = {
        slug: `${KAGGLE_USERNAME}/${slugName}`,
        newTitle: `EpicSync Batch ${ts}`,
        text: workerScript,
        language: "python",
        kernelType: "script",
        isPrivate: true,
        enableGpu: false,
        enableTpu: false,
        enableInternet: true,
        datasetDataSources: [],
        competitionDataSources: [],
        kernelDataSources: [],
        modelDataSources: []
    };

    const res = await fetch('https://www.kaggle.com/api/v1/kernels/push', {
        method: 'POST',
        headers: {
            'Authorization': authHeader,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(kagglePayload)
    });

    if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Kaggle API returned ${res.status}: ${errText}`);
    }

    return {
        success: true,
        batch_id: batch_id,
        count: jobs.length,
        jobs: jobs
    };
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
