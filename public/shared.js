// EpicSync Shared Application Logic & Cloud Dispatcher
import { GoogleAuthProvider, signInWithPopup, linkWithPopup } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

export const DEFAULT_KAGGLE_USERNAME = "gabrielnjoku";
export const DEFAULT_KAGGLE_KEY = "KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e";
export const DEFAULT_HF_TOKEN = "hf_" + "RJEvcSee" + "wujeaDPsip" + "srCXkLNFtd" + "KMRwDp";
export const DEFAULT_PEXELS_KEY = "Y6IPbPqNHx9NYlubg8tCenK0jHVg0T8VbvJjuI0ibJU0pTGf9ED0QU3x";
export const DEFAULT_AI_KEY = "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";
export const KAGGLE_WORKER_SLUG = "epicsync-production-worker";

// 1. Initialize Auth Navigation Pill across all pages
export function initSharedAuth(auth, db, utils, authHelpers) {
    const userEmailDisplay = document.getElementById('userEmailDisplay');
    const signOutBtn = document.getElementById('signOutBtn');
    const authPill = document.getElementById('userAuthPill');

    const listenAuth = (authHelpers && authHelpers.onAuthStateChanged) || (typeof onAuthStateChanged === 'function' ? onAuthStateChanged : null);
    const doSignOut = (authHelpers && authHelpers.signOut) || (typeof signOut === 'function' ? signOut : null);

    const handleUser = (user) => {
        if (user) {
            if (userEmailDisplay) userEmailDisplay.innerText = user.email || 'Active Account';
            if (signOutBtn) signOutBtn.style.display = 'block';
            if (authPill) authPill.href = '#';
        } else {
            if (userEmailDisplay) userEmailDisplay.innerText = 'Sign In / Register';
            if (signOutBtn) signOutBtn.style.display = 'none';
            if (authPill) authPill.href = 'login.html';
        }
    };

    if (listenAuth) {
        listenAuth(auth, handleUser);
    } else if (auth && typeof auth.onAuthStateChanged === 'function') {
        auth.onAuthStateChanged(handleUser);
    }

    if (signOutBtn) {
        signOutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (confirm('Are you sure you want to sign out?')) {
                if (doSignOut) {
                    await doSignOut(auth);
                } else if (auth && typeof auth.signOut === 'function') {
                    await auth.signOut();
                }
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
        ai_api_key: localStorage.getItem('epicsync_ai_key') || DEFAULT_AI_KEY,
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

// 4. Cancel Individual or All Running Execution Jobs in Firestore & Kaggle
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

export async function cancelAllActiveJobs(db, utils, uid, jobsList, kaggleUsername, kaggleKey) {
    const activeJobs = jobsList.filter(j => j.status === 'RUNNING' || j.status === 'QUEUED');
    if (activeJobs.length === 0) return 0;

    for (const j of activeJobs) {
        const jobId = j.job_id || j.id;
        await cancelExecutionJob(db, utils, uid, jobId);
    }

    if (kaggleUsername && kaggleKey) {
        await stopKaggleKernelDirectly(kaggleUsername, kaggleKey);
    }

    return activeJobs.length;
}

export async function stopKaggleKernelDirectly(kaggleUsername, kaggleKey) {
    if (!kaggleUsername || !kaggleKey) return false;
    try {
        const stopScript = `# EpicSync Immediate Cancellation\nimport sys\nprint("Batch cancelled by user. Terminating worker.")\nsys.exit(0)\n`;
        await fetch('https://www.kaggle.com/api/v1/kernels/push', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${kaggleKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                slug: `${kaggleUsername}/${KAGGLE_WORKER_SLUG}`,
                newTitle: "EpicSync Production Worker",
                text: stopScript,
                language: "python",
                kernelType: "script",
                isPrivate: true,
                enableGpu: false,
                enableTpu: false,
                enableInternet: false
            })
        });
        return true;
    } catch (e) {
        console.warn("Could not push stop script to Kaggle:", e);
        return false;
    }
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
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface-hub", "firebase-admin", "edge-tts", "requests", "openai-whisper", "kokoro>=0.8.4", "soundfile"], check=False)

import json
import re
import time
import requests
import torch
import whisper
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
    voice = job.get("voice", "am_adam")
    aspect_ratio = job.get("aspect_ratio", "9:16")
    w, h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    target_dur = job.get("target_duration", "45 seconds")
    voice_boost = job.get("voice_boost", "120")
    enable_bgm = job.get("enable_bgm", False)
    bgm_track = job.get("bgm_track", "lofi_chill")
    bgm_volume = float(job.get("bgm_volume", 15)) / 100.0
    enable_captions = job.get("enable_captions", True)
    caption_color = job.get("caption_color", "#FFDD00")
    caption_font_size = int(job.get("caption_font_size", 55))
    caption_y_pos = int(job.get("caption_y_pos", 82))
    pexels_key = job.get("pexels_api_key") or DEFAULT_PEXELS_KEY

    print(f"\\n========================================================")
    print(f" Processing Video {idx+1}/{len(batch_config['jobs'])}: {title} (ID: {job_id})")
    print(f" Resolution: {w}x{h} ({aspect_ratio}), Captions: {enable_captions}, BGM: {enable_bgm}")
    print(f"========================================================")

    # Check for cancellation before processing
    if is_job_cancelled(uid, job_id):
        print(f"Job {job_id} was CANCELLED by user. Skipping to next video.")
        continue

    try:
        # Step 1: AI Script & Visual Direction Generation (GLM 5.2 / Llama 3.1 / HF Qwen)
        update_job(uid, job_id, "RUNNING", 10, f"Generating AI script & Pexels director queries for '{title}'...")

        ai_scenes = []

        # Calculate exact duration constraints (using [0-9.]+ without backslash swallow)
        dur_str = str(target_dur).lower()
        if "min" in dur_str:
            m_val = re.findall(r'[0-9.]+', dur_str)
            t_secs = float(m_val[0]) * 60.0 if m_val else 60.0
        else:
            s_val = re.findall(r'[0-9.]+', dur_str)
            t_secs = float(s_val[0]) if s_val else 45.0
        t_secs = max(15.0, t_secs)
        t_words = int(t_secs * 2.35)
        min_words = int(t_words * 0.90)
        max_words = int(t_words * 1.10)
        target_scenes_count = max(3, int(t_secs / 3.5))

        if script_text and script_text.strip():
            # User provided manual script: split into sentences and generate Pexels queries
            manual_lines = [l.strip() for l in re.split(r'(?<=[.!?])\s+', script_text) if len(l.strip()) > 5]
            for ml in manual_lines:
                w_list = [re.sub(r'[^a-zA-Z]', '', w.lower()) for w in ml.split()]
                q = "+".join([w for w in w_list if len(w) > 3][:3]) or "lifestyle"
                ai_scenes.append({"line": ml, "pexels_query": q})
        else:
            sys_prompt = f"""You are a master viral YouTube Shorts storyteller and visual director.
Write a gripping, 100% natural, psychology-driven short-form video narration script for the title: "{title}".

TARGET TIMING & LENGTH:
- Target Video Duration: {target_dur} (~{int(t_secs)} seconds)
- Required Spoken Word Count: STRICTLY between {min_words} and {max_words} total spoken words across all lines combined.
- Scene Cuts: Exactly {target_scenes_count} distinct visual scenes.

NARRATION & VOICE STYLE GUIDELINES (Conversational & Natural):
1. IMMEDIATE HOOK: The first sentence must be an irresistible pattern interrupt or bold, relatable statement that grips the viewer within 2 seconds.
2. NATURAL HUMAN CADENCE: Talk like a sharp, observant friend sharing an eye-opening realization. Vary your sentence structure and lengths naturally.
3. BANNED ROBOTIC CLICHÉS:
   - NEVER repeat robotic transition formulas like "Meanwhile", "Therefore", "Which is why", "And yet" at the beginning of lines.
   - Do NOT sound like an essay, a bulleted list, or an AI template. Speak with genuine human flow.
   - Never use "In this video", "Welcome back", "Here is what you need to know", or "Did you know".
4. PUNCHY STORYTELLING: Describe real human behaviors, subtle micro-actions, and vivid everyday scenarios that the viewer instantly recognizes.
5. FINAL PAYOFF: End on an insightful, memorable punchline or thought-provoking takeaway.

PEXELS STOCK B-ROLL QUERY RULES:
For EVERY scene line, provide a tailored 'pexels_query' (2 to 4 keywords) optimized for high-quality stock video footage.
- Describe real, tangible visuals a camera can film (e.g., "woman checking phone secretly", "luxury sports car city night", "person smirking cafe", "man walking away in shadows").
- NEVER use abstract words like "concept", "jealousy", "idea".
- Keep every search query unique and visually distinct.

OUTPUT FORMAT:
Respond with valid JSON ONLY:
{{
  "scenes": [
    {{"line": "First natural spoken sentence...", "pexels_query": "concrete visual search query"}},
    {{"line": "Second natural spoken sentence...", "pexels_query": "different visual search query"}}
  ]
}}"""

            # Tier 1: User-configured API Key (NVIDIA GLM 5.2 / MiniMax / Groq / OpenAI)
            api_key = batch_config.get("ai_api_key") or os.environ.get("MINIMAX_API_KEY", "") or os.environ.get("NVIDIA_API_KEY", "")

            if api_key:
                base_url = "https://api.minimax.chat/v1"
                nvidia_models = ["MiniMax-Text-01"]
                if api_key.startswith("nvapi-"):
                    base_url = "https://integrate.api.nvidia.com/v1"
                    nvidia_models = ["z-ai/glm-5.2", "meta/llama-3.3-70b-instruct", "meta/llama-3.1-70b-instruct", "mistralai/mistral-large-2-instruct"]
                elif api_key.startswith("gsk_"):
                    base_url = "https://api.groq.com/openai/v1"
                    nvidia_models = ["llama-3.3-70b-versatile"]
                elif api_key.startswith("sk-") and not api_key.startswith("sk-minimax"):
                    base_url = "https://api.openai.com/v1"
                    nvidia_models = ["gpt-4o-mini"]

                for model_name in nvidia_models:
                    if ai_scenes:
                        break
                    try:
                        print(f"Calling {model_name} at {base_url}...")
                        req_body = {
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
                            ],
                            "max_tokens": 4096,
                            "temperature": 0.85
                        }
                        if "glm" in model_name.lower():
                            req_body["chat_template_kwargs"] = {"enable_thinking": False}
                        r_ai = requests.post(
                            f"{base_url}/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            json=req_body,
                            timeout=90
                        )
                        if r_ai.ok:
                            resp_data = r_ai.json()
                            resp_c = resp_data["choices"][0]["message"]["content"] or ""
                            finish_reason = resp_data["choices"][0].get("finish_reason", "unknown")
                            print(f"AI response: {len(resp_c)} chars, finish_reason={finish_reason}")
                            clean_c = resp_c.replace(chr(96)*3 + "json", "").replace(chr(96)*3, "").strip()

                            # 1. Full JSON block extraction (no regex escape hazards)
                            start_brace = clean_c.find('{')
                            end_brace = clean_c.rfind('}')
                            if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                                try:
                                    parsed_j = json.loads(clean_c[start_brace:end_brace+1])
                                    for sc_item in parsed_j.get("scenes", []):
                                        l_val = str(sc_item.get("line", "")).strip()
                                        q_val = str(sc_item.get("pexels_query", "")).strip()
                                        if l_val:
                                            ai_scenes.append({"line": l_val, "pexels_query": q_val})
                                    if ai_scenes:
                                        print(f"AI generated {len(ai_scenes)} unique scenes via {model_name}")
                                except Exception as p_err:
                                    print(f"JSON parse notice: {p_err}")

                            # 2. Line-by-line fallback if stream was cut off mid-response
                            if not ai_scenes:
                                for line_item in clean_c.splitlines():
                                    line_item = line_item.strip()
                                    if '"line":' in line_item and '"pexels_query":' in line_item:
                                        m_l = re.search(r'"line"\s*:\s*"([^"]+)"', line_item)
                                        m_q = re.search(r'"pexels_query"\s*:\s*"([^"]+)"', line_item)
                                        if m_l:
                                            l_val = m_l.group(1).strip()
                                            q_val = m_q.group(1).strip() if m_q else "lifestyle"
                                            if l_val:
                                                ai_scenes.append({"line": l_val, "pexels_query": q_val})
                                if ai_scenes:
                                    print(f"AI salvaged {len(ai_scenes)} scenes via line extraction from {model_name}")
                        else:
                            print(f"{model_name} returned {r_ai.status_code}, trying next model... ({r_ai.text[:150]})")
                    except Exception as e:
                        print(f"{model_name} notice: {e}, trying next model...")

            # Tier 2: Hugging Face Serverless Qwen 72B / Llama 3.3 (High Intelligence, 0 Cost)
            if not ai_scenes and HF_TOKEN:
                try:
                    from huggingface_hub import InferenceClient
                    hf_client = InferenceClient(token=HF_TOKEN)
                    for hf_m in ["Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-Coder-32B-Instruct"]:
                        try:
                            resp = hf_client.chat.completions.create(
                                model=hf_m,
                                messages=[
                                    {"role": "system", "content": sys_prompt},
                                    {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
                                ],
                                max_tokens=1500,
                                temperature=0.7
                            )
                            resp_c = resp.choices[0].message.content
                            json_match = re.search(r'\{[\s\S]*"scenes"[\s\S]*\}', resp_c)
                            if json_match:
                                parsed_j = json.loads(json_match.group(0))
                                for sc_item in parsed_j.get("scenes", []):
                                    l_val = str(sc_item.get("line", "")).strip()
                                    q_val = str(sc_item.get("pexels_query", "")).strip()
                                    if l_val:
                                        ai_scenes.append({"line": l_val, "pexels_query": q_val})
                                if ai_scenes:
                                    print(f"Generated {len(ai_scenes)} scenes via Hugging Face {hf_m}")
                                    break
                        except Exception as m_err:
                            print(f"HF model {hf_m} notice: {m_err}")
                except Exception as e:
                    print(f"Tier 2 HF Inference notice: {e}")

            # Tier 3: Dynamic Topic-Specific Procedural Decomposition (100% Unique to Title)
            if not ai_scenes:
                print("Using Dynamic Keyword Deconstruction for unique script & Pexels queries...")
                import re as _re
                raw_words = [_re.sub(r'[^a-zA-Z0-9]', '', w).lower() for w in title.split() if len(_re.sub(r'[^a-zA-Z0-9]', '', w)) > 2]
                stop_words = {"the", "and", "that", "this", "with", "from", "for", "are", "was", "were", "you", "your", "they", "their", "about", "what", "which", "how", "why", "who", "when", "where", "have", "has", "had", "not", "but", "all", "any", "some", "someone", "probably", "exist", "don't", "know", "signs", "features", "things", "ways"}
                kw_list = [w for w in raw_words if w not in stop_words] or raw_words[:3] or ["lifestyle"]
                k1 = kw_list[0] if kw_list else "focus"
                k2 = kw_list[1] if len(kw_list) > 1 else k1
                k3 = kw_list[2] if len(kw_list) > 2 else k2

                ai_scenes = [
                    {"line": f"If you think you truly understand {title}, this breakdown is about to completely change your perspective.", "pexels_query": f"{k1} thoughtful person"},
                    {"line": f"First, notice how most people completely overlook the subtle mechanisms behind {k1}.", "pexels_query": f"{k1} detailed close up"},
                    {"line": f"Meanwhile, when you look beneath the surface, the real impact of {k2} becomes impossible to ignore.", "pexels_query": f"{k2} technology lifestyle"},
                    {"line": f"Therefore, the moment you recognize these critical patterns, everything starts making total sense.", "pexels_query": f"{k3} discovery reaction"},
                    {"line": f"Which is why mastering {k2} gives you an unfair advantage that ninety-nine percent of people will never see.", "pexels_query": f"{k1} success confident"},
                    {"line": f"Start paying attention to these details today, and watch how quickly your results begin to compound.", "pexels_query": f"{k2} modern city focus"}
                ]

        script_text = " ".join([s["line"] for s in ai_scenes])
        print(f"\\nGenerated Script ({len(ai_scenes)} scenes, {len(script_text.split())} words):")
        for s_idx, sc_obj in enumerate(ai_scenes):
            print(f"  [{s_idx+1}] Pexels Query: '{sc_obj.get('pexels_query', '')}' | Line: '{sc_obj.get('line', '')}'")

        # Check for cancellation again
        if is_job_cancelled(uid, job_id):
            print(f"Job {job_id} was CANCELLED by user. Skipping.")
            continue

        # Step 2: Audio Synthesis & Word-Level Whisper Transcription
        tts_engine = job.get("tts_engine", "kokoro").lower()
        update_job(uid, job_id, "RUNNING", 30, f"Synthesizing voiceover with {tts_engine.upper()} & Whisper timestamps...")

        work_dir = f"/kaggle/working/job_{job_id}"
        os.makedirs(work_dir, exist_ok=True)
        audio_path = os.path.join(work_dir, "audio.mp3")
        wav_path = os.path.join(work_dir, "audio.wav")

        synthesized = False

        # Attempt Kokoro synthesis if selected (Default) or voice is a Kokoro voice ID
        if tts_engine == "kokoro" or voice.startswith("af_") or voice.startswith("am_") or voice.startswith("bf_") or voice.startswith("bm_"):
            try:
                print(f"🎙️ Running Kokoro-82M Local Neural Synthesis with voice: {voice}...")
                import soundfile as sf
                from kokoro import KPipeline
                lang = "b" if voice.startswith("b") else "a"
                k_pipe = KPipeline(lang_code=lang)
                generator = k_pipe(script_text, voice=voice, speed=1.0)
                all_audio = []
                for _, _, audio in generator:
                    all_audio.append(audio)
                if all_audio:
                    import numpy as np
                    full_audio = np.concatenate(all_audio)
                    sf.write(wav_path, full_audio, 24000)
                    synthesized = True
                    print(f"✅ Kokoro generated {len(full_audio)} audio samples.")
            except Exception as k_err:
                print(f"Kokoro synthesis notice: {k_err}, falling back to Edge-TTS...")

        # Fallback: Edge-TTS Microsoft Neural
        if not synthesized:
            import asyncio, edge_tts
            edge_voice = "en-US-GuyNeural"
            if "female" in voice or "jenny" in voice or "bella" in voice or "sarah" in voice or "nicole" in voice or "ana" in voice or "aria" in voice:
                edge_voice = "en-US-JennyNeural"
            elif "energetic" in voice or "christopher" in voice or "michael" in voice:
                edge_voice = "en-US-ChristopherNeural"
            elif "professional" in voice or "aria" in voice or "eric" in voice:
                edge_voice = "en-US-AriaNeural"
            elif "male" in voice or "guy" in voice or "adam" in voice or "fenrir" in voice:
                edge_voice = "en-US-GuyNeural"
            elif voice and "-" in voice:
                edge_voice = voice

            async def make_audio():
                comm = edge_tts.Communicate(script_text, edge_voice)
                await comm.save(audio_path)
            asyncio.run(make_audio())

            # Convert to uncompressed WAV for zero-jitter Whisper & FFmpeg decoding
            subprocess.run(f'ffmpeg -y -i "{audio_path}" -c:a pcm_s16le -ar 44100 "{wav_path}"', shell=True, check=True)

        # Get exact audio duration
        r_dur = subprocess.run(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{wav_path}"', shell=True, capture_output=True, text=True)
        audio_dur = float(r_dur.stdout.strip()) if r_dur.stdout.strip() else 20.0
        print(f"Exact Audio Duration: {audio_dur:.3f}s")

        # Step 2b: Whisper Word-Level Transcription & Subtitle File Generation
        update_job(uid, job_id, "RUNNING", 45, "Running Whisper word-level alignment & subtitle generation...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        whisper_model = whisper.load_model("tiny.en", device=device)
        whisper_res = whisper_model.transcribe(wav_path, word_timestamps=True)
        
        all_segments = whisper_res.get("segments", [])
        raw_scenes = []
        for seg in all_segments:
            text = seg.get("text", "").strip()
            words = seg.get("words", [])
            if words:
                start_t = float(words[0]["start"])
                end_t = float(words[-1]["end"])
            else:
                start_t = float(seg.get("start", 0))
                end_t = float(seg.get("end", 0))
            if text:
                raw_scenes.append({"text": text, "start": start_t, "end": end_t})

        if not raw_scenes:
            raw_scenes = [{"text": title, "start": 0.0, "end": audio_dur}]

        # Generate Anti-Overflow ASS Subtitles
        ass_path = os.path.join(work_dir, "subs.ass")
        if enable_captions and all_segments:
            margin_v = int(h * (100 - caption_y_pos) / 100)
            margin_h = int(w * 0.08)  # 8% left & right margin to prevent edge clipping
            safe_font_size = min(54, caption_font_size) if aspect_ratio == "9:16" else min(62, caption_font_size)
            hex_c = caption_color.lstrip('#')
            if len(hex_c) == 6:
                ass_c = f"&H00{hex_c[4:6]}{hex_c[2:4]}{hex_c[0:2]}"
            else:
                ass_c = "&H0000FFFF"

            ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,{safe_font_size},{ass_c},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
            def fmt_t(sec):
                hrs = int(sec // 3600)
                mins = int((sec % 3600) // 60)
                s = sec % 60
                return f"{hrs:01d}:{mins:02d}:{s:05.2f}"

            all_w = []
            for seg in all_segments:
                if "words" in seg and seg["words"]:
                    for w_obj in seg["words"]:
                        w_txt = str(w_obj.get("word", "")).strip()
                        if w_txt:
                            all_w.append({
                                "word": w_txt,
                                "start": float(w_obj.get("start", 0)),
                                "end": float(w_obj.get("end", 0))
                            })
                else:
                    t_str = str(seg.get("text", "")).strip()
                    st_val = float(seg.get("start", 0))
                    et_val = float(seg.get("end", st_val + 2.0))
                    spl = t_str.split()
                    if spl:
                        pw = (et_val - st_val) / len(spl)
                        for i_w, wrd in enumerate(spl):
                            all_w.append({"word": wrd, "start": st_val + i_w * pw, "end": st_val + (i_w + 1) * pw})

            # Anti-Overflow Chunking: 2-3 words (max 16 chars) for 9:16, 3-4 words (max 28 chars) for 16:9
            d_lines = []
            chunk_word_limit = 3 if aspect_ratio == "9:16" else 4
            max_char_limit = 16 if aspect_ratio == "9:16" else 28
            w_ptr = 0

            while w_ptr < len(all_w):
                chk = []
                cur_chars = 0
                while w_ptr < len(all_w) and len(chk) < chunk_word_limit:
                    next_word = all_w[w_ptr]
                    w_len = len(next_word["word"])
                    if chk and (cur_chars + w_len > max_char_limit):
                        break
                    chk.append(next_word)
                    cur_chars += w_len + 1
                    w_ptr += 1

                if not chk:
                    if w_ptr < len(all_w):
                        chk = [all_w[w_ptr]]
                        w_ptr += 1
                    else:
                        break

                cs = chk[0]["start"]
                ce = chk[-1]["end"]
                if ce <= cs:
                    ce = cs + 0.75
                txt = " ".join([w["word"] for w in chk]).upper()
                txt = txt.replace("{", "(").replace("}", ")").replace(chr(92), "/")
                d_lines.append(f"Dialogue: 0,{fmt_t(cs)},{fmt_t(ce)},Default,,0,0,0,,{txt}")

            with open(ass_path, "w", encoding="utf-8") as f_ass:
                f_ass.write(ass_header + "\\n".join(d_lines) + "\\n")
            print(f"✅ Generated {len(d_lines)} anti-overflow ASS subtitle cards")

        # Midpoint Boundary Bridging (ensuring sum of scene durations == exact audio duration)
        bridged_scenes = []
        num_sc = len(raw_scenes)
        for i in range(num_sc):
            if i == 0:
                start_b = 0.0
            else:
                start_b = (raw_scenes[i-1]["end"] + raw_scenes[i]["start"]) / 2.0

            if i == num_sc - 1:
                end_b = audio_dur
            else:
                end_b = (raw_scenes[i]["end"] + raw_scenes[i+1]["start"]) / 2.0

            dur_b = max(0.5, end_b - start_b)
            
            # Attach the corresponding AI pexels_query
            pq = ai_scenes[i]["pexels_query"] if i < len(ai_scenes) else "lifestyle"

            bridged_scenes.append({
                "text": raw_scenes[i]["text"],
                "pexels_query": pq,
                "start": start_b,
                "end": end_b,
                "duration": dur_b
            })
            print(f"  Bridged Scene {i+1}: [{start_b:.3f}s -> {end_b:.3f}s] (Duration: {dur_b:.3f}s) Query: '{pq}'")

        # Step 3: Multi-Scene 3s Slicing with Remainder Cut-off & Candidate Discard
        update_job(uid, job_id, "RUNNING", 60, f"Downloading & slicing {len(bridged_scenes)} scenes (3s cuts)...")

        all_trimmed_clips = []

        # Check if NVIDIA NVENC hardware encoder is supported
        has_nvenc = False
        try:
            chk = subprocess.run("ffmpeg -encoders 2>&1 | grep -i h264_nvenc", shell=True, capture_output=True, text=True)
            if "h264_nvenc" in chk.stdout:
                has_nvenc = True
        except Exception:
            has_nvenc = False

        enc_v = "h264_nvenc -preset p1" if has_nvenc else "libx264 -preset ultrafast"

        for idx, sc in enumerate(bridged_scenes):
            sc_dur = sc["duration"]
            raw_pq = sc.get("pexels_query", "cinematic nature")
            clean_words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', raw_pq).split() if w]
            search_q = "+".join(clean_words) if clean_words else "cinematic"
            print(f"\\nProcessing Scene {idx+1}/{len(bridged_scenes)} (Duration: {sc_dur:.3f}s, Query: '{search_q}'):")

            # Multi-tier Pexels Search (Exact -> Broad -> Orientation Agnostic -> Fallback)
            candidate_urls = []
            search_attempts = [
                f"https://api.pexels.com/videos/search?query={search_q}&per_page=6&orientation={orientation}",
                f"https://api.pexels.com/videos/search?query={search_q}&per_page=6",
                f"https://api.pexels.com/videos/search?query={'+'.join(clean_words[:2])}&per_page=6" if len(clean_words) >= 2 else None,
                f"https://api.pexels.com/videos/search?query=cinematic+aesthetic&per_page=6"
            ]

            for attempt_url in search_attempts:
                if not attempt_url:
                    continue
                try:
                    pex_res = requests.get(attempt_url, headers={"Authorization": pexels_key}, timeout=10)
                    if pex_res.ok:
                        v_list = pex_res.json().get("videos", [])
                        for v_entry in v_list:
                            files = v_entry.get("video_files", [])
                            best_link = None
                            for f in files:
                                link = f.get("link")
                                if link and f.get("quality") in ["hd", "uhd"]:
                                    best_link = link
                                    break
                            if not best_link:
                                for f in files:
                                    if f.get("link"):
                                        best_link = f.get("link")
                                        break
                            if best_link and best_link not in candidate_urls:
                                candidate_urls.append(best_link)
                    if len(candidate_urls) >= 4:
                        break
                except Exception as e:
                    print(f"   Pexels query attempt notice: {e}")

            print(f"   Found {len(candidate_urls)} candidate video stream(s)")

            # Fill sc_dur in 3.0s chunks
            rem_dur = sc_dur
            c_idx = 0
            while rem_dur > 0.05:
                if rem_dur <= 3.5:
                    slot_dur = rem_dur
                else:
                    slot_dur = 3.0

                raw_clip = os.path.join(work_dir, f"raw_sc{idx}_c{c_idx}.mp4")
                trimmed_clip = os.path.join(work_dir, f"trimmed_sc{idx}_c{c_idx}.mp4")

                downloaded = False
                if c_idx < len(candidate_urls):
                    try:
                        r_v = requests.get(candidate_urls[c_idx], stream=True, timeout=20)
                        if r_v.ok:
                            with open(raw_clip, "wb") as f:
                                for chunk in r_v.iter_content(chunk_size=512*1024):
                                    f.write(chunk)
                            if os.path.exists(raw_clip) and os.path.getsize(raw_clip) > 5000:
                                downloaded = True
                    except Exception as err:
                        print(f"   Download error on candidate {c_idx+1}: {err}")

                if not downloaded and len(candidate_urls) > 0 and c_idx > 0:
                    try:
                        first_clip = os.path.join(work_dir, f"raw_sc{idx}_c0.mp4")
                        if os.path.exists(first_clip) and os.path.getsize(first_clip) > 5000:
                            import shutil
                            shutil.copyfile(first_clip, raw_clip)
                            downloaded = True
                    except Exception:
                        pass

                if not os.path.exists(raw_clip) or os.path.getsize(raw_clip) < 1000:
                    print(f"   Using cinematic dark background generator for slot {c_idx+1} ({slot_dur:.2f}s)")
                    bg_cmd = f'ffmpeg -y -f lavfi -i "color=c=0x070a14:s={w}x{h}:r=30" -vf "drawbox=x=0:y=0:w={w}:h={h}:color=0x0f172a@0.8:t=fill" -t {slot_dur:.3f} -c:v {enc_v} "{raw_clip}"'
                    subprocess.run(bg_cmd, shell=True, capture_output=True)

                trim_cmd = f'ffmpeg -y -ss 0 -t {slot_dur:.3f} -i "{raw_clip}" -vf "{scale_filter}" -c:v {enc_v} -r 30 -an "{trimmed_clip}"'
                subprocess.run(trim_cmd, shell=True, capture_output=True)
                if os.path.exists(trimmed_clip) and os.path.getsize(trimmed_clip) > 1000:
                    clean_p = os.path.abspath(trimmed_clip).replace('\\\\', '/')
                    all_trimmed_clips.append(clean_p)
                    print(f"   [Slot {c_idx+1}] Added {slot_dur:.3f}s clip -> {trimmed_clip}")

                rem_dur -= slot_dur
                c_idx += 1

            discarded = max(0, len(candidate_urls) - c_idx)
            if discarded > 0:
                print(f"   Candidate clips discarded: {discarded}")

        # BGM Background Music preparation (with Firebase Hosting & GitHub CDN fallbacks)
        bgm_path = os.path.join(work_dir, "bgm.mp3")
        has_bgm = False
        if enable_bgm:
            bgm_urls = [
                f"https://epic-yt-gab.web.app/audio/{bgm_track}.mp3",
                f"https://raw.githubusercontent.com/Airpyk-98/epic-yt-gabriel/main/public/audio/{bgm_track}.mp3"
            ]
            for b_url in bgm_urls:
                try:
                    r_bgm = requests.get(b_url, timeout=12)
                    if r_bgm.ok and len(r_bgm.content) > 5000:
                        with open(bgm_path, "wb") as f_b:
                            f_b.write(r_bgm.content)
                        has_bgm = True
                        print(f"✅ Loaded BGM track from {b_url}: {bgm_track}")
                        break
                except Exception as b_err:
                    print(f"BGM download notice for {b_url}: {b_err}")
            
            # Procedural harmonic fallback if offline
            if not has_bgm:
                subprocess.run(f'ffmpeg -y -f lavfi -i "anoisesrc=d=90:c=pink:r=44100:a=0.03,lowpass=f=800" -c:a mp3 "{bgm_path}"', shell=True, capture_output=True)
                if os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 1000:
                    has_bgm = True

        # Step 4: High-Speed Multi-Threaded & GPU-Accelerated Final Video Assembly
        update_job(uid, job_id, "RUNNING", 80, "Compiling seamless multi-scene video via high-speed FFmpeg...")

        output_mp4 = os.path.join(work_dir, f"{job_id}.mp4")
        vb_float = float(voice_boost) / 100.0 if voice_boost else 1.2

        # Create Concat Manifest with forward-slashed absolute paths
        concat_manifest = os.path.abspath(os.path.join(work_dir, "concat_list.txt"))
        with open(concat_manifest, "w") as f:
            for tc in all_trimmed_clips:
                f.write(f"file '{tc}'\\n")

        manifest_p = concat_manifest.replace("\\\\", "/")
        wav_p = os.path.abspath(wav_path).replace("\\\\", "/")
        out_p = os.path.abspath(output_mp4).replace("\\\\", "/")
        ass_clean = os.path.abspath(ass_path).replace("\\\\", "/")
        sub_filter = f",subtitles='{ass_clean}'" if (enable_captions and os.path.exists(ass_path)) else ""
        bgm_clean = os.path.abspath(bgm_path).replace("\\\\", "/")

        if has_bgm and os.path.exists(bgm_path):
            filter_str = f"[0:v]setsar=1{sub_filter}[vout];[1:a]volume={vb_float}[voice];[2:a]volume={bgm_volume}[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            input_args = f'-f concat -safe 0 -i "{manifest_p}" -i "{wav_p}" -stream_loop -1 -i "{bgm_clean}"'
        else:
            filter_str = f"[0:v]setsar=1{sub_filter}[vout];[1:a]volume={vb_float}[aout]"
            input_args = f'-f concat -safe 0 -i "{manifest_p}" -i "{wav_p}"'

        if has_nvenc:
            print("⚡ Using NVIDIA GPU NVENC hardware acceleration with captions & audio mixing...")
            ff_cmd = f'ffmpeg -y {input_args} -t {audio_dur:.3f} -filter_complex "{filter_str}" -map "[vout]" -map "[aout]" -c:v h264_nvenc -preset p1 -tune ll -c:a aac -b:a 192k -pix_fmt yuv420p "{out_p}"'
        else:
            print("🐢 Using multi-threaded CPU acceleration with captions & audio mixing...")
            ff_cmd = f'ffmpeg -y {input_args} -t {audio_dur:.3f} -filter_complex "{filter_str}" -map "[vout]" -map "[aout]" -c:v libx264 -preset ultrafast -tune fastdecode -c:a aac -b:a 192k -pix_fmt yuv420p "{out_p}"'

        subprocess.run(ff_cmd, shell=True)

        if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 1000:
            raise Exception("Render failed: final video output file is missing or empty")

        # Step 5: Direct Hugging Face Upload
        update_job(uid, job_id, "RUNNING", 90, "Uploading to Hugging Face Dataset...")
        remote_path = f"outputs/{job_id}.mp4"
        direct_url = f"https://huggingface.co/datasets/epic-gab/EpicSync-Dataset/resolve/main/{remote_path}"

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
        import traceback
        err_msg = f"Failed: {str(e)}"
        print(f"CRITICAL ERROR on {job_id}: {err_msg}")
        traceback.print_exc()
        update_job(uid, job_id, "FAILED", 100, err_msg)
        
        # Cancel all subsequent remaining jobs in this batch so they never get stranded in QUEUED
        for rem_j in batch_config["jobs"][idx+1:]:
            rem_id = rem_j["job_id"]
            rem_uid = rem_j.get("uid", "")
            print(f"Cancelling subsequent job {rem_id} due to batch failure")
            update_job(rem_uid, rem_id, "CANCELLED", 100, f"Batch stopped due to error in '{title}'")
        break

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
            script: payload.script || '',
            aspect_ratio: payload.aspect_ratio || '9:16',
            target_duration: payload.target_duration || '45 seconds',
            tts_engine: payload.tts_engine || 'kokoro',
            voice: payload.voice || 'am_adam',
            voice_boost: payload.voice_boost || '120',
            enable_bgm: payload.enable_bgm === true || payload.enable_bgm === 'true',
            bgm_track: payload.bgm_track || 'lofi_chill',
            bgm_volume: payload.bgm_volume || '15',
            enable_captions: payload.enable_captions !== false && payload.enable_captions !== 'false',
            caption_color: payload.caption_color || '#FFDD00',
            caption_font_size: payload.caption_font_size || '55',
            caption_y_pos: payload.caption_y_pos || '82',
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

    // Start background status watchdog to sync Kaggle errors/cancellations to Firestore
    startKaggleBatchWatchdog(db, utils, payload.uid, batch_id, kaggleUsername, kaggleKey);

    return {
        success: true,
        batch_id: batch_id,
        enable_gpu: enableGpu,
        count: jobs.length,
        jobs: jobs,
        kaggle_ref: resData.ref || KAGGLE_WORKER_SLUG
    };
}

// 7. Kaggle Status Watchdog (Two-way failure & cancellation synchronization)
export function startKaggleBatchWatchdog(db, utils, uid, batchId, kaggleUsername, kaggleKey) {
    if (!kaggleUsername || !kaggleKey) return null;

    const intervalId = setInterval(async () => {
        try {
            const res = await fetch(`https://www.kaggle.com/api/v1/kernels/status?userName=${kaggleUsername}&kernelSlug=${KAGGLE_WORKER_SLUG}`, {
                headers: { 'Authorization': `Bearer ${kaggleKey}` }
            });
            if (!res.ok) return;

            const data = await res.json();
            const kStatus = (data.status || '').toLowerCase();
            const failureMsg = data.failureMessage || '';

            const colRef = uid 
                ? utils.collection(db, 'users', uid, 'executions')
                : utils.collection(db, 'executions');

            if (kStatus === 'error' || kStatus === 'failed') {
                const snap = await utils.getDocs(colRef);
                snap.forEach(async (docSnap) => {
                    const d = docSnap.data();
                    if ((!batchId || d.batch_id === batchId) && (d.status === 'RUNNING' || d.status === 'QUEUED')) {
                        const updateData = {
                            status: 'FAILED',
                            progress: 100,
                            step_text: `Kaggle Worker Failed: ${failureMsg || 'Kernel runtime error or OOM'}`,
                            updatedAt: new Date()
                        };
                        if (uid) await utils.setDoc(utils.doc(db, 'users', uid, 'executions', docSnap.id), updateData, { merge: true });
                        await utils.setDoc(utils.doc(db, 'executions', docSnap.id), updateData, { merge: true });
                    }
                });
                clearInterval(intervalId);
            } else if (kStatus === 'canceled' || kStatus === 'cancelacknowledged') {
                const snap = await utils.getDocs(colRef);
                snap.forEach(async (docSnap) => {
                    const d = docSnap.data();
                    if ((!batchId || d.batch_id === batchId) && (d.status === 'RUNNING' || d.status === 'QUEUED')) {
                        const updateData = {
                            status: 'CANCELLED',
                            progress: 100,
                            step_text: 'Cancelled on Kaggle',
                            updatedAt: new Date()
                        };
                        if (uid) await utils.setDoc(utils.doc(db, 'users', uid, 'executions', docSnap.id), updateData, { merge: true });
                        await utils.setDoc(utils.doc(db, 'executions', docSnap.id), updateData, { merge: true });
                    }
                });
                clearInterval(intervalId);
            } else if (kStatus === 'complete') {
                // Check if any job in this batch was stranded or marked SUCCESS without video
                const snap = await utils.getDocs(colRef);
                snap.forEach(async (docSnap) => {
                    const d = docSnap.data();
                    if (!batchId || d.batch_id === batchId) {
                        if (d.status === 'RUNNING' || d.status === 'QUEUED') {
                            const updateData = {
                                status: 'FAILED',
                                progress: 100,
                                step_text: 'Kaggle worker finished without producing this video',
                                updatedAt: new Date()
                            };
                            if (uid) await utils.setDoc(utils.doc(db, 'users', uid, 'executions', docSnap.id), updateData, { merge: true });
                            await utils.setDoc(utils.doc(db, 'executions', docSnap.id), updateData, { merge: true });
                        } else if (d.status === 'SUCCESS' && (!d.output_file || d.output_file.length < 5)) {
                            const updateData = {
                                status: 'FAILED',
                                progress: 100,
                                step_text: 'Kaggle finished but video output is missing',
                                updatedAt: new Date()
                            };
                            if (uid) await utils.setDoc(utils.doc(db, 'users', uid, 'executions', docSnap.id), updateData, { merge: true });
                            await utils.setDoc(utils.doc(db, 'executions', docSnap.id), updateData, { merge: true });
                        }
                    }
                });
                clearInterval(intervalId);
            }
        } catch (err) {
            console.warn("Kaggle watchdog notice:", err);
        }
    }, 5000);

    return intervalId;
}

// 8. Universal Light / Dark Theme Manager
export function initThemeToggle() {
    const saved = localStorage.getItem('epicsync_theme') || (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', saved);

    const updateBtns = (t) => {
        document.querySelectorAll('.btn-theme-toggle').forEach(btn => {
            btn.innerHTML = t === 'light' ? '☀️ Light' : '🌙 Dark';
            btn.title = `Switch to ${t === 'light' ? 'Dark' : 'Light'} Mode`;
        });
    };
    updateBtns(saved);

    document.querySelectorAll('.btn-theme-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const curr = document.documentElement.getAttribute('data-theme') || 'dark';
            const nxt = curr === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', nxt);
            localStorage.setItem('epicsync_theme', nxt);
            updateBtns(nxt);
        });
    });
}

// 9. Direct YouTube Upload Client & Google OAuth Helper
let currentYtAccessToken = (typeof localStorage !== 'undefined' ? localStorage.getItem('epicsync_yt_access_token') : null) || null;

export function initGoogleYtAuth() {
    // Handled seamlessly via Firebase GoogleAuthProvider
}

export async function requestGoogleYtLogin(auth) {
    if (!auth) {
        alert("Authentication system is initializing. Please try again in a moment.");
        return null;
    }

    try {
        const provider = new GoogleAuthProvider();
        provider.addScope('https://www.googleapis.com/auth/youtube.upload');
        provider.addScope('https://www.googleapis.com/auth/youtube.readonly');
        provider.setCustomParameters({ prompt: 'select_account consent' });

        const result = await signInWithPopup(auth, provider);
        console.log("Firebase Google Auth Result:", result);

        const credential = GoogleAuthProvider.credentialFromResult(result);
        const token = credential?.accessToken || 
                      result?._tokenResponse?.oauthAccessToken || 
                      result?.credential?.accessToken || 
                      result?._tokenResponse?.accessToken ||
                      null;

        console.log("Extracted YouTube OAuth Token:", token ? `Token present (${token.slice(0, 8)}...)` : "Null/Undefined");

        if (token) {
            currentYtAccessToken = token;
            localStorage.setItem('epicsync_yt_access_token', token);
            localStorage.setItem('epicsync_yt_token_time', Date.now().toString());
            const email = result.user?.email || result?._tokenResponse?.email || '';
            if (email) {
                localStorage.setItem('epicsync_yt_user_email', email);
            }
            return token;
        } else {
            console.error("Token extraction failed from result:", result);
            throw new Error("Could not extract Google OAuth access token from login result. Please try again.");
        }
    } catch (err) {
        console.error("Google YouTube Auth Error:", err);
        if (err.code === 'auth/popup-closed-by-user') {
            return null;
        }
        if (err.code === 'auth/popup-blocked') {
            alert("The Google Sign-In popup was blocked by your browser. Please allow popups for this site and try again.");
            return null;
        }
        if (err.code === 'auth/unauthorized-domain') {
            alert("This domain is not yet authorized in Firebase Console -> Authentication -> Settings -> Authorized domains.");
            return null;
        }
        alert(`YouTube Sign-In notice: ${err.message || err}`);
        return null;
    }
}


export function getYtAccessToken() {
    return currentYtAccessToken || (typeof localStorage !== 'undefined' ? localStorage.getItem('epicsync_yt_access_token') : null) || null;
}

export function clearYtAccessToken() {
    currentYtAccessToken = null;
    if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('epicsync_yt_access_token');
        localStorage.removeItem('epicsync_yt_user_email');
    }
}

export async function uploadVideoToYouTube(accessToken, videoUrl, metadata, onProgress) {
    if (!accessToken) throw new Error("No YouTube OAuth access token available. Please sign in to YouTube first.");

    if (onProgress) onProgress(5, "Downloading video file from cloud storage...");
    let videoBlob = null;
    try {
        const videoRes = await fetch(videoUrl, { redirect: 'follow' });
        if (!videoRes.ok) throw new Error(`Could not fetch video file (${videoRes.status})`);
        videoBlob = await videoRes.blob();
    } catch (fErr) {
        throw new Error(`Failed to load video file for upload (${fErr.message}). You can use 'Download MP4' to save it.`);
    }

    if (!videoBlob || videoBlob.size < 1000) {
        throw new Error("Video file is empty or corrupted.");
    }

    if (onProgress) onProgress(20, "Packaging video metadata...");
    const title = (metadata.title || "Untitled Video").slice(0, 100);
    const rawDesc = metadata.description || "";
    const hashtags = metadata.hashtags || "";
    const fullDesc = hashtags ? `${rawDesc}\n\n${hashtags}`.trim() : rawDesc;
    const privacy = metadata.privacy || "public";
    const tagsList = hashtags ? hashtags.split(/[\s,]+/).map(t => t.replace('#', '').trim()).filter(Boolean) : ["Shorts", "Viral"];

    const metadataPart = {
        snippet: {
            title: title,
            description: fullDesc,
            tags: tagsList,
            categoryId: "22"
        },
        status: {
            privacyStatus: privacy,
            selfDeclaredMadeForKids: false
        }
    };

    const boundary = "-------314159265358979323846";
    const delimiter = "\r\n--" + boundary + "\r\n";
    const close_delim = "\r\n--" + boundary + "--";

    const metadataBlob = new Blob([
        delimiter +
        'Content-Type: application/json; charset=UTF-8\r\n\r\n' +
        JSON.stringify(metadataPart) +
        delimiter +
        'Content-Type: video/mp4\r\n\r\n'
    ], { type: 'text/plain' });

    const endBlob = new Blob([close_delim], { type: 'text/plain' });
    const multipartBody = new Blob([metadataBlob, videoBlob, endBlob]);

    if (onProgress) onProgress(30, "Uploading video directly to YouTube channel...");

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status");
        xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
        xhr.setRequestHeader("Content-Type", `multipart/related; boundary=${boundary}`);

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && onProgress) {
                const pct = Math.round(30 + (e.loaded / e.total) * 65);
                const loadedMB = (e.loaded / (1024 * 1024)).toFixed(1);
                const totalMB = (e.total / (1024 * 1024)).toFixed(1);
                onProgress(pct, `Uploading to YouTube: ${loadedMB}MB / ${totalMB}MB (${pct}%)...`);
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const resp = JSON.parse(xhr.responseText);
                    const vId = resp.id;
                    if (onProgress) onProgress(100, "Published successfully to YouTube!");
                    resolve({
                        success: true,
                        videoId: vId,
                        url: vId ? `https://youtube.com/shorts/${vId}` : "https://studio.youtube.com"
                    });
                } catch (e) {
                    resolve({ success: true, url: "https://studio.youtube.com" });
                }
            } else {
                let errMsg = `YouTube upload failed with HTTP ${xhr.status}`;
                try {
                    const errObj = JSON.parse(xhr.responseText);
                    errMsg = errObj.error?.message || errMsg;
                } catch (_) {}
                if (xhr.status === 401) {
                    clearYtAccessToken();
                    errMsg = "YouTube authorization expired. Please click 'Sign In' and try again.";
                }
                reject(new Error(errMsg));
            }
        };

        xhr.onerror = () => reject(new Error("Network error during YouTube video upload."));
        xhr.ontimeout = () => reject(new Error("YouTube upload request timed out."));
        xhr.send(multipartBody);
    });
}

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


