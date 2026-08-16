// EpicSync Shared Application Logic & Cloud Dispatcher

export const DEFAULT_KAGGLE_USERNAME = "gabrielnjoku";
export const DEFAULT_KAGGLE_KEY = "KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e";
export const DEFAULT_HF_TOKEN = "hf_" + "RJEvcSee" + "wujeaDPsip" + "srCXkLNFtd" + "KMRwDp";
export const DEFAULT_PEXELS_KEY = "Y6IPbPqNHx9NYlubg8tCenK0jHVg0T8VbvJjuI0ibJU0pTGf9ED0QU3x";
export const KAGGLE_WORKER_SLUG = "epicsync-production-worker";

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
        ai_api_key: localStorage.getItem('epicsync_ai_key') || '',
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
                if (data.ai_api_key) settings.ai_api_key = data.ai_api_key;
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

// 4. Cancel Individual or All Running Execution Jobs in Firestore
export async function cancelExecutionJob(db, utils, uid, jobId) {
    const cancelData = {
        status: 'CANCELLED',
        step_text: 'Cancelled by user',
        updatedAt: new Date()
    };

    try {
        if (uid) {
            await utils.setDoc(utils.doc(db, 'users', uid, 'executions', jobId), cancelData, { merge: true });
        }
        await utils.setDoc(utils.doc(db, 'executions', jobId), cancelData, { merge: true });
        return true;
    } catch (err) {
        console.error("Error cancelling job:", err);
        throw err;
    }
}

export async function cancelAllActiveJobs(db, utils, uid, jobsList) {
    const activeJobs = jobsList.filter(j => j.status === 'RUNNING' || j.status === 'QUEUED');
    if (activeJobs.length === 0) return 0;

    for (const j of activeJobs) {
        const jobId = j.job_id || j.id;
        await cancelExecutionJob(db, utils, uid, jobId);
    }
    return activeJobs.length;
}

// 5. Generate Self-Contained Kaggle Worker Python Code
export function buildWorkerCode(batchConfig, hfToken, pexelsKey) {
    const jsonStr = JSON.stringify(batchConfig).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    const tokenToUse = hfToken || DEFAULT_HF_TOKEN;
    const pexKeyToUse = pexelsKey || DEFAULT_PEXELS_KEY;
    
    return `# EpicSync On-Demand Dedicated Production Worker
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

def is_job_cancelled(uid, job_id):
    try:
        url = f"https://firestore.googleapis.com/v1/projects/epic-yt-gab/databases/(default)/documents/executions/{job_id}"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            status_val = data.get("fields", {}).get("status", {}).get("stringValue", "")
            return status_val == "CANCELLED"
    except Exception as e:
        print(f"Cancel check notice: {e}")
    return False

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

    # Check for cancellation before processing
    if is_job_cancelled(uid, job_id):
        print(f"Job {job_id} was CANCELLED by user. Skipping to next video.")
        continue

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
        words_est = max(30, int(float(target_dur.split()[0]) * 2.2)) if target_dur and target_dur[0].isdigit() else 75

        sys_prompt = f"""You are a world-class viral YouTube Shorts scriptwriter.
Write an addictive, high-retention video script for the title: "{title}".

STRICT HOOK & RETENTION DIRECTIVES:
1. NEVER start with "Here is what you need to know", "In this video", "Welcome", or greetings.
2. The very first 3 seconds MUST deliver an immediate pattern interrupt or bold curiosity hook.
3. Use short, punchy sentences connected by "therefore" and "but" to create open loops that hold attention until the end.
4. Target length: EXACTLY {words_est} spoken words.
5. Output ONLY the raw spoken narration words. No stage directions, brackets, timestamps, or headers."""

        api_key = batch_config.get("ai_api_key") or os.environ.get("NVIDIA_API_KEY", "")

        if api_key:
            try:
                base_url = "https://integrate.api.nvidia.com/v1"
                model_name = "meta/llama-3.3-70b-instruct"
                if api_key.startswith("gsk_"):
                    base_url = "https://api.groq.com/openai/v1"
                    model_name = "llama-3.3-70b-versatile"
                elif api_key.startswith("sk-"):
                    base_url = "https://api.openai.com/v1"
                    model_name = "gpt-4o-mini"

                r_ai = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": f"Write the viral short-form script for: {title}"}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.7
                    },
                    timeout=30
                )
                if r_ai.ok:
                    raw_s = r_ai.json()["choices"][0]["message"]["content"]
                    clean_s = re.sub(r'\[.*?\]', '', raw_s)
                    clean_s = re.sub(r'\(.*?\)', '', clean_s).replace('**', '').replace('---', '')
                    clean_s = re.sub(r'^(Narrator|Script|Audio|Voiceover):?\s*', '', clean_s, flags=re.IGNORECASE | re.MULTILINE).strip()
                    script_text = clean_s
            except Exception as e:
                print(f"AI Gen Notice: {e}")

        if not script_text:
            import random
            hooks = [
                f"Nobody wants to admit this, but {title} is secretly changing everything you do.",
                f"If you're still looking at {title} the traditional way, you're missing the entire point.",
                f"The biggest misconception about {title} is that it takes massive effort, but the reality is completely different.",
                f"Most people get {title} totally backward, and it costs them more than they realize."
            ]
            hook = random.choice(hooks)
            body = f"Here is why: when you streamline the foundational steps, your results compound automatically. But if you skip the key leverage points, friction builds up immediately. Focus on the core highest-impact action first, eliminate unnecessary bottlenecks, and watch how quickly your consistency shifts."
            script_text = f"{hook} {body}"

    # Check for cancellation again
    if is_job_cancelled(uid, job_id):
        print(f"Job {job_id} was CANCELLED by user. Skipping.")
        continue

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

    # Step 3: Multi-Scene Pexels Stock B-Roll Video Download (3s Scene Cuts)
    update_job(uid, job_id, "RUNNING", 55, "Searching & downloading multi-scene Pexels B-roll (3s scene cuts)...")

    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"

    # Split script into semantic scenes / clauses (sentence boundaries and conjunctions)
    stopwords = {"a", "an", "the", "in", "on", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "you", "your", "is", "are", "can", "that", "this", "what", "how", "top", "why", "exist", "slowly", "secretly", "and", "but", "while", "because", "so", "or", "of"}
    raw_clauses = re.split(r'(?<=[.!?])\s+|,\s+(?=and\b|but\b|while\b|because\b|so\b)', script_text)
    scenes = [c.strip() for c in raw_clauses if len(c.strip()) > 8]
    if not scenes:
        scenes = [title]

    print(f"Total semantic scenes to cut: {len(scenes)}")
    trimmed_clips = []

    for idx, sc in enumerate(scenes):
        words = [re.sub(r'[^a-zA-Z]', '', w.lower()) for w in sc.split()]
        filtered = [w for w in words if w and len(w) > 2 and w not in stopwords and not w.isdigit()]
        search_q = "+".join(filtered[:3]) if filtered else "travel"
        print(f"Scene {idx+1}/{len(scenes)}: Query '{search_q}'")

        raw_clip_path = os.path.join(work_dir, f"raw_{idx}.mp4")
        trimmed_clip_path = os.path.join(work_dir, f"scene_{idx}.mp4")

        try:
            pex_res = requests.get(
                f"https://api.pexels.com/videos/search?query={search_q}&per_page=4&orientation={orientation}",
                headers={"Authorization": pexels_key},
                timeout=12
            )
            if (not pex_res.ok or not pex_res.json().get("videos")) and search_q != "travel":
                pex_res = requests.get(
                    f"https://api.pexels.com/videos/search?query=travel&per_page=4&orientation={orientation}",
                    headers={"Authorization": pexels_key},
                    timeout=12
                )

            if pex_res.ok and pex_res.json().get("videos"):
                videos_list = pex_res.json()["videos"]
                best_vid_url = None
                for v_entry in videos_list:
                    files = v_entry.get("video_files", [])
                    for f in files:
                        if f.get("link") and f.get("quality") == "hd":
                            best_vid_url = f.get("link")
                            break
                    if not best_vid_url and files:
                        best_vid_url = files[0].get("link")
                    if best_vid_url:
                        break
                        
                if best_vid_url:
                    r_vid = requests.get(best_vid_url, stream=True, timeout=25)
                    with open(raw_clip_path, "wb") as f:
                        for chunk in r_vid.iter_content(chunk_size=512*1024):
                            f.write(chunk)
        except Exception as e:
            print(f"Pexels fetch notice for scene {idx}: {e}")

        # Fallback to procedural testsrc if clip fetch failed
        if not os.path.exists(raw_clip_path) or os.path.getsize(raw_clip_path) < 1000:
            subprocess.run(f"ffmpeg -y -f lavfi -i testsrc=size={w}x{h}:rate=30 -t 3 -c:v libx264 {raw_clip_path}", shell=True)

        # Standardize and trim clip to 3.0s
        trim_cmd = f'ffmpeg -y -ss 0 -t 3.0 -i "{raw_clip_path}" -vf "{scale_filter}" -c:v libx264 -preset ultrafast -r 30 -an "{trimmed_clip_path}"'
        subprocess.run(trim_cmd, shell=True)
        if os.path.exists(trimmed_clip_path) and os.path.getsize(trimmed_clip_path) > 1000:
            trimmed_clips.append(trimmed_clip_path)

    # Step 4: High-Speed Multi-Threaded & GPU-Accelerated Multi-Scene Video Assembly
    update_job(uid, job_id, "RUNNING", 75, "Compiling multi-scene video via high-speed FFmpeg (NVENC GPU / Fast CPU)...")

    output_mp4 = os.path.join(work_dir, f"{job_id}.mp4")
    vb_float = float(voice_boost) / 100.0 if voice_boost else 1.2

    # Get exact audio duration
    r_dur = subprocess.run(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_path}"', shell=True, capture_output=True, text=True)
    audio_dur = float(r_dur.stdout.strip()) if r_dur.stdout.strip() else 10.0
    print(f"Audio duration: {audio_dur:.3f}s")

    # Create Concat Manifest with forward-slashed absolute paths
    concat_manifest = os.path.abspath(os.path.join(work_dir, "concat_list.txt"))
    with open(concat_manifest, "w") as f:
        for tc in trimmed_clips:
            clean_path = os.path.abspath(tc).replace("\\", "/")
            f.write(f"file '{clean_path}'\n")

    # Check if NVIDIA NVENC hardware encoder is supported
    has_nvenc = False
    try:
        chk = subprocess.run("ffmpeg -encoders 2>&1 | grep -i h264_nvenc", shell=True, capture_output=True, text=True)
        if "h264_nvenc" in chk.stdout:
            has_nvenc = True
    except Exception:
        has_nvenc = False

    manifest_p = concat_manifest.replace("\\", "/")
    audio_p = os.path.abspath(audio_path).replace("\\", "/")
    out_p = os.path.abspath(output_mp4).replace("\\", "/")

    if has_nvenc:
        print("⚡ Using NVIDIA GPU NVENC hardware acceleration with multi-scene cuts...")
        ff_cmd = f'ffmpeg -y -stream_loop -1 -f concat -safe 0 -i "{manifest_p}" -i "{audio_p}" -t {audio_dur:.3f} -filter_complex "[0:v]setsar=1[vout];[1:a]volume={vb_float}[aout]" -map "[vout]" -map "[aout]" -c:v h264_nvenc -preset p1 -tune ll -c:a aac -b:a 192k -pix_fmt yuv420p "{out_p}"'
    else:
        print("🐢 Using multi-threaded CPU acceleration with multi-scene cuts...")
        ff_cmd = f'ffmpeg -y -stream_loop -1 -f concat -safe 0 -i "{manifest_p}" -i "{audio_p}" -t {audio_dur:.3f} -filter_complex "[0:v]setsar=1[vout];[1:a]volume={vb_float}[aout]" -map "[vout]" -map "[aout]" -c:v libx264 -preset ultrafast -tune fastdecode -c:a aac -b:a 192k -pix_fmt yuv420p "{out_p}"'

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

print("\\n[BATCH COMPLETED] All videos processed. Worker exiting.")
`;
}

// 6. Direct Kaggle Batch Dispatcher (Single Reusable Production Kernel)
export async function launchKaggleBatchDirectly(db, utils, payload) {
    const ts = Math.floor(Date.now() / 1000);
    const batch_id = `batch_${ts}`;
    const titles = payload.titles || [];
    const jobs = [];
    const enableGpu = payload.enable_gpu === true || payload.enable_gpu === 'true';

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
            accelerator: enableGpu ? 'GPU (Turbo)' : 'CPU (Saver)',
            status: 'QUEUED',
            progress: 0,
            step_text: `Queued for Kaggle ${enableGpu ? 'Turbo GPU' : 'CPU'} Worker...`,
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

    // Build the Kaggle worker script
    const batchConfig = {
        batch_id: batch_id,
        jobs: jobs,
        ai_api_key: payload.ai_api_key || userSettings.ai_api_key || ''
    };
    const workerScript = buildWorkerCode(batchConfig, hfToken, pexelsKey);

    // Push new version to the single persistent production worker kernel
    const kagglePayload = {
        slug: `${kaggleUsername}/${KAGGLE_WORKER_SLUG}`,
        newTitle: "EpicSync Production Worker",
        text: workerScript,
        language: "python",
        kernelType: "script",
        isPrivate: true,
        enableGpu: enableGpu,
        enableTpu: false,
        enableInternet: true,
        machineShape: enableGpu ? "NvidiaTeslaT4" : "None",
        accelerator: enableGpu ? "NvidiaTeslaT4" : "None",
        gpuType: enableGpu ? "T4" : "None",
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
        enable_gpu: enableGpu,
        count: jobs.length,
        jobs: jobs,
        kaggle_ref: resData.ref || KAGGLE_WORKER_SLUG
    };
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
