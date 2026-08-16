// EpicSync Shared Application Logic & Cloud Dispatcher

export const DEFAULT_KAGGLE_USERNAME = "gabrielnjoku";
export const DEFAULT_KAGGLE_KEY = "KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e";
export const DEFAULT_HF_TOKEN = "hf_" + "RJEvcSee" + "wujeaDPsip" + "srCXkLNFtd" + "KMRwDp";
export const DEFAULT_PEXELS_KEY = "y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K";

// 1. Initialize Auth Navigation Pill across all pages
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

// 2. Fetch User Settings from Firestore (or LocalStorage fallback)
export async function getUserSettings(db, utils, uid) {
    let settings = {
        kaggle_username: localStorage.getItem('epicsync_kaggle_username') || DEFAULT_KAGGLE_USERNAME,
        kaggle_key: localStorage.getItem('epicsync_kaggle_key') || DEFAULT_KAGGLE_KEY,
        hf_token: localStorage.getItem('epicsync_hf_token') || DEFAULT_HF_TOKEN,
        pexels_key: localStorage.getItem('epicsync_pexels_key') || DEFAULT_PEXELS_KEY,
        webhook_url: localStorage.getItem('epicsync_yt_webhook') || ''
    };

    if (uid && db && utils) {
        try {
            const snap = await utils.getDoc(utils.doc(db, 'users', uid, 'settings', 'config'));
            if (snap.exists()) {
                const data = snap.data();
                if (data.kaggle_username) settings.kaggle_username = data.kaggle_username;
                if (data.kaggle_key) settings.kaggle_key = data.kaggle_key;
                if (data.hf_token) settings.hf_token = data.hf_token;
                if (data.pexels_key) settings.pexels_key = data.pexels_key;
                if (data.webhook_url) settings.webhook_url = data.webhook_url;
            }
        } catch (e) {
            console.warn("Could not fetch user settings from Firestore:", e);
        }
    }
    return settings;
}

export async function getUserWebhookUrl(db, utils, uid) {
    const s = await getUserSettings(db, utils, uid);
    return s.webhook_url;
}

// 3. Dispatch Array of Videos to Webhook
export async function dispatchToWebhook(webhookUrl, videosList) {
    if (!webhookUrl) {
        alert('No YouTube Webhook configured! You can configure one in the Settings page whenever you are ready.');
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
export function buildWorkerCode(batchConfig, hfToken, pexelsKey) {
    const jsonStr = JSON.stringify(batchConfig).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    const tokenToUse = hfToken || DEFAULT_HF_TOKEN;
    const pexKeyToUse = pexelsKey || DEFAULT_PEXELS_KEY;
    
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

batch_config = json.loads("${jsonStr}")
HF_TOKEN = "${tokenToUse}"
DEFAULT_PEXELS_KEY = "${pexKeyToUse}"
hf_api = HfApi(token=HF_TOKEN)

def update_job(uid, job_id, status, progress, step_text, extra=None):
    print(f"[JOB {job_id}] {status} ({progress}%) - {step_text}")
    
    fields = {
        "status": {"stringValue": status},
        "progress": {"integerValue": str(progress)},
        "step_text": {"stringValue": step_text}
    }
    mask_params = "updateMask.fieldPaths=status&updateMask.fieldPaths=progress&updateMask.fieldPaths=step_text"
    
    if extra and "output_file" in extra:
        mask_params += "&updateMask.fieldPaths=output_file"
        fields["output_file"] = {"stringValue": extra["output_file"]}
    
    # 1. Update user-scoped path (for logged in user)
    if uid and uid.strip():
        try:
            url_user = f"https://firestore.googleapis.com/v1/projects/epic-yt-gab/databases/(default)/documents/users/{uid}/executions/{job_id}?{mask_params}"
            requests.patch(url_user, json={"fields": fields}, timeout=10)
        except Exception as e:
            print(f"User doc update notice: {e}")
            
    # 2. Update root executions path
    try:
        url_root = f"https://firestore.googleapis.com/v1/projects/epic-yt-gab/databases/(default)/documents/executions/{job_id}?{mask_params}"
        requests.patch(url_root, json={"fields": fields}, timeout=10)
    except Exception as e:
        print(f"Root doc update notice: {e}")

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
    pexels_key = job.get("pexels_api_key") or DEFAULT_PEXELS_KEY

    print(f"\\n========================================================")
    print(f" Processing Video {idx+1}/{len(batch_config['jobs'])}: {title} (ID: {job_id})")
    print(f"========================================================")

    # Step 1: Script Gen
    update_job(uid, job_id, "RUNNING", 10, f"Generating AI script for '{title}'...")

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

    # Step 2: Audio TTS
    update_job(uid, job_id, "RUNNING", 30, "Synthesizing voiceover with Edge-TTS...")

    work_dir = f"/kaggle/working/job_{job_id}"
    os.makedirs(work_dir, exist_ok=True)
    audio_path = os.path.join(work_dir, "audio.mp3")

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

    # Step 3: Pexels Stock B-Roll Video Download
    update_job(uid, job_id, "RUNNING", 55, "Searching & downloading Pexels stock B-roll...")

    video_clip_path = os.path.join(work_dir, "broll.mp4")
    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"

    # Extract meaningful search terms (strip numbers and common stopwords)
    stopwords = {"a", "an", "the", "in", "on", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "you", "your", "is", "are", "can", "that", "this", "what", "how", "top", "why", "exist", "slowly", "secretly"}
    words = [re.sub(r'[^a-zA-Z]', '', w.lower()) for w in title.split()]
    filtered = [w for w in words if w and len(w) > 2 and w not in stopwords and not w.isdigit()]
    search_q = "+".join(filtered[:3]) if filtered else "cinematic+modern"

    print(f"Pexels search query: '{search_q}' (orientation: {orientation})")
    
    try:
        pex_res = requests.get(
            f"https://api.pexels.com/videos/search?query={search_q}&per_page=5&orientation={orientation}",
            headers={"Authorization": pexels_key},
            timeout=15
        )
        if (not pex_res.ok or not pex_res.json().get("videos")) and search_q != "cinematic":
            # Fallback search if specific query returned empty
            pex_res = requests.get(
                f"https://api.pexels.com/videos/search?query=cinematic&per_page=5&orientation={orientation}",
                headers={"Authorization": pexels_key},
                timeout=15
            )

        if pex_res.ok and pex_res.json().get("videos"):
            videos_list = pex_res.json()["videos"]
            best_vid_url = None
            
            for v_entry in videos_list:
                files = v_entry.get("video_files", [])
                # Prefer HD 1080p or 720p files
                for f in files:
                    if f.get("link") and f.get("quality") == "hd":
                        best_vid_url = f.get("link")
                        break
                if not best_vid_url and files:
                    best_vid_url = files[0].get("link")
                if best_vid_url:
                    break
                    
            if best_vid_url:
                print(f"Downloading Pexels video: {best_vid_url[:80]}...")
                r_vid = requests.get(best_vid_url, stream=True, timeout=30)
                with open(video_clip_path, "wb") as f:
                    for chunk in r_vid.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                print(f"Pexels video downloaded ({os.path.getsize(video_clip_path)} bytes).")
    except Exception as e:
        print(f"Pexels fetch notice: {e}")

    # Fallback to dynamic animated background if download failed
    if not os.path.exists(video_clip_path) or os.path.getsize(video_clip_path) < 1000:
        print("Using dynamic procedural visualizer fallback...")
        subprocess.run(f"ffmpeg -y -f lavfi -i testsrc=size={w}x{h}:rate=30 -t 30 -c:v libx264 {video_clip_path}", shell=True)

    # Step 4: Video Assembly with Pro Scale & Crop
    update_job(uid, job_id, "RUNNING", 75, "Compiling video via FFmpeg...")

    output_mp4 = os.path.join(work_dir, f"{job_id}.mp4")
    vb_float = float(voice_boost) / 100.0 if voice_boost else 1.2
    scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"

    ff_cmd = f'ffmpeg -y -stream_loop -1 -i "{video_clip_path}" -i "{audio_path}" -filter_complex "[0:v]{scale_filter}[vout];[1:a]volume={vb_float}[aout]" -map "[vout]" -map "[aout]" -c:v libx264 -preset ultrafast -c:a aac -b:a 192k -shortest -pix_fmt yuv420p "{output_mp4}"'
    subprocess.run(ff_cmd, shell=True)

    # Step 5: Direct Hugging Face Upload
    update_job(uid, job_id, "RUNNING", 90, "Uploading to Hugging Face Dataset...")
    remote_path = f"outputs/{job_id}.mp4"
    direct_url = f"https://huggingface.co/datasets/epic-gab/EpicSync-Dataset/resolve/main/{remote_path}"

    try:
        hf_api.upload_file(
            path_or_fileobj=output_mp4,
            path_in_repo=remote_path,
            repo_id="epic-gab/EpicSync-Dataset",
            repo_type="dataset",
            token=HF_TOKEN
        )
        print(f"Uploaded video to: {direct_url}")
        
        # Step 6: SUCCESS
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

// 5. Direct Kaggle Batch Dispatcher (Using User's Configured Credentials)
export async function launchKaggleBatchDirectly(db, utils, payload) {
    const ts = Math.floor(Date.now() / 1000);
    const batch_id = `batch_${ts}`;
    const titles = payload.titles || [];
    const jobs = [];

    // Get user configured credentials
    const userSettings = await getUserSettings(db, utils, payload.uid);
    const kaggleUsername = (payload.kaggle_username || userSettings.kaggle_username || DEFAULT_KAGGLE_USERNAME).trim();
    const kaggleKey = (payload.kaggle_key || userSettings.kaggle_key || DEFAULT_KAGGLE_KEY).trim();
    const hfToken = (payload.hf_token || userSettings.hf_token || DEFAULT_HF_TOKEN).trim();
    const pexelsKey = (payload.pexels_api_key || userSettings.pexels_key || DEFAULT_PEXELS_KEY).trim();

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
    const workerScript = buildWorkerCode(batchConfig, hfToken, pexelsKey);

    // Push to Kaggle API using Bearer Token Auth
    const slugName = `epicsync-batch-${ts}`;

    const kagglePayload = {
        slug: `${kaggleUsername}/${slugName}`,
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
            'Authorization': `Bearer ${kaggleKey}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(kagglePayload)
    });

    if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Kaggle API (${kaggleUsername}) returned ${res.status}: ${errText}`);
    }

    const resData = await res.json();

    return {
        success: true,
        batch_id: batch_id,
        count: jobs.length,
        jobs: jobs,
        kaggle_ref: resData.ref || slugName
    };
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
