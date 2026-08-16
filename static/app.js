import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, setDoc, getDoc, updateDoc, collection, getDocs, onSnapshot, addDoc, serverTimestamp, query, orderBy, writeBatch } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const firebaseConfig = {
    apiKey: "AIzaSyC2HIzjx4s11SSu_Ge3nB72T5Bfvl0yn-w",
    authDomain: "epic-yt-gab.firebaseapp.com",
    projectId: "epic-yt-gab",
    storageBucket: "epic-yt-gab.firebasestorage.app",
    messagingSenderId: "1019236923017",
    appId: "1:1019236923017:web:0d8acfdee28bbad8537858",
    measurementId: "G-MTK2W3WH9H"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

let currentUser = null;
let currentProject = null;
let unsubscribeProjects = null;
let unsubscribeLogs = null;
const BACKEND_URL = "https://epic-yt-gabriel.onrender.com";

async function fetchWithWakeupRetry(url, options = {}, maxRetries = 4) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s timeout for cold start
            const fetchOptions = { ...options, signal: controller.signal };
            
            const res = await fetch(url, fetchOptions);
            clearTimeout(timeoutId);
            return res;
        } catch (err) {
            console.warn(`Connection attempt ${attempt}/${maxRetries} failed:`, err);
            if (attempt === maxRetries) throw err;
            if (submitContentBtn) {
                submitContentBtn.innerText = `Waking up server (${attempt}/${maxRetries})...`;
            }
            await new Promise(r => setTimeout(r, 3000));
        }
    }
}



// Duration word counts helper
function getDurationDirective(targetDuration) {
    if (targetDuration.includes("15") || targetDuration.includes("30") || targetDuration.includes("Shorts")) {
        return "\n\nCRITICAL DURATION INSTRUCTION: Target duration is SHORTS (30-45s). Output between 60 to 90 words total.";
    } else if (targetDuration.includes("3 min") || targetDuration.includes("180")) {
        return "\n\nCRITICAL DURATION INSTRUCTION: Target duration is 3 MINUTES. Output between 380 to 450 words total.";
    } else if (targetDuration.includes("5 min") || targetDuration.includes("300")) {
        return "\n\nCRITICAL DURATION INSTRUCTION: Target duration is 5 MINUTES. Output between 650 to 750 words total.";
    } else if (targetDuration.includes("10 min") || targetDuration.includes("600")) {
        return "\n\nCRITICAL DURATION INSTRUCTION: Target duration is 10 MINUTES. Output between 1300 to 1500 words total.";
    } else {
        return "\n\nCRITICAL DURATION INSTRUCTION: Target duration is 60 SECONDS. Output between 120 to 150 words total.";
    }
}

// Generate script using client AI settings directly
async function generateScriptDirect(title, videoModel, targetDuration, uid) {
    const userDoc = await getDoc(doc(db, 'users', uid));
    if (!userDoc.exists()) throw new Error("User profile not found");
    const uData = userDoc.data();
    
    const baseUrl = uData.aiBaseUrl || "https://api.openai.com/v1";
    const apiKey = uData.aiApiKey || "";
    const model = uData.aiModel || "gpt-4";
    const sysPrompt = uData.aiSystemPrompt || "You are a creative YouTube script writer.";
    
    if (!apiKey) throw new Error("Please configure your AI API Key in Settings first.");
    
    const durationDirective = getDurationDirective(targetDuration);
    const ttsDirective = "\n\nCRITICAL FORMAT INSTRUCTION: Output ONLY raw plaintext words that the voice actor speaks. Do NOT include markdown, sound effects, or narrator tags.";
    const pexelsDirective = videoModel === "pexels" ? "\n\n<PEXELS_SEGMENTS>\n[\n  {\"text\": \"segment text\", \"keyword\": \"office worker\"}\n]\n</PEXELS_SEGMENTS>" : "";
    const aptavatarDirective = videoModel === "aptavatar" ? "\n\n<APTAVATAR_PROMPT>\n步骤1：*帧 0~30* talking naturally\n</APTAVATAR_PROMPT>" : "";
    
    const finalSysPrompt = sysPrompt + ttsDirective + durationDirective + pexelsDirective + aptavatarDirective;
    
    const res = await fetch(`${baseUrl.replace(/\/+$/, '')}/chat/completions`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: model,
            messages: [
                { role: "system", content: finalSysPrompt },
                { role: "user", content: `Write an engaging script for the video title: "${title}"` }
            ],
            temperature: 0.7
        })
    });
    
    if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error?.message || `AI API returned status ${res.status}`);
    }
    
    const data = await res.json();
    let raw = data.choices[0]?.message?.content || "";
    
    // Clean script
    let cleanScript = raw.replace(/\[.*?\]/g, '').replace(/\(.*?\)/g, '').replace(/\*\*/g, '').replace(/---/g, '');
    cleanScript = cleanScript.replace(/^(Narrator|Script|Audio|Voiceover):?\s*/gim, '').trim();
    return cleanScript;
}

// Listen to Kaggle Worker Heartbeat
function initWorkerHeartbeatListener() {
    onSnapshot(doc(db, 'system', 'worker_status'), (snap) => {
        const badge = document.getElementById('workerStatusBadge');
        const dot = document.getElementById('workerStatusDot');
        const txt = document.getElementById('workerStatusText');
        if (!badge) return;
        
        if (snap.exists()) {
            const data = snap.data();
            const lastHb = data.last_heartbeat?.toMillis ? data.last_heartbeat.toMillis() : Date.now();
            const diffSec = (Date.now() - lastHb) / 1000;
            
            if (diffSec < 120) {
                badge.style.background = "rgba(16, 185, 129, 0.1)";
                badge.style.borderColor = "rgba(16, 185, 129, 0.3)";
                badge.style.color = "#10b981";
                dot.style.background = "#10b981";
                dot.style.boxShadow = "0 0 8px #10b981";
                txt.innerText = "12h Worker: Active";
            } else {
                badge.style.background = "rgba(245, 158, 11, 0.1)";
                badge.style.borderColor = "rgba(245, 158, 11, 0.3)";
                badge.style.color = "#f59e0b";
                dot.style.background = "#f59e0b";
                dot.style.boxShadow = "none";
                txt.innerText = "12h Worker: Idle";
            }
        } else {
            badge.style.background = "rgba(239, 68, 68, 0.1)";
            badge.style.borderColor = "rgba(239, 68, 68, 0.3)";
            badge.style.color = "#ef4444";
            dot.style.background = "#ef4444";
            txt.innerText = "12h Worker: Offline";
        }
    });
}

// UI Elements
const authOverlay = document.getElementById('authOverlay');
const appContainer = document.getElementById('appContainer');
const authForm = document.getElementById('authForm');
const authEmail = document.getElementById('authEmail');
const authPassword = document.getElementById('authPassword');
const authError = document.getElementById('authError');
const authSubmitBtn = document.getElementById('authSubmitBtn');
const logoutBtn = document.getElementById('logoutBtn');

const hamburgerBtn = document.getElementById('hamburgerBtn');
const navDrawer = document.getElementById('navDrawer');
const closeDrawerBtn = document.getElementById('closeDrawerBtn');
const drawerBackdrop = document.getElementById('drawerBackdrop');
const navLinks = document.querySelectorAll('.nav-link');
const viewSections = document.querySelectorAll('.view-section');
const activeProjectBadge = document.getElementById('activeProjectBadge');

// Auth Listener
onAuthStateChanged(auth, (user) => {
    if (user) {
        currentUser = user;
        authOverlay.classList.remove('active');
        appContainer.style.display = 'block';
        loadUserSettings();
        loadProjects();
    } else {
        currentUser = null;
        if (unsubscribeProjects) { unsubscribeProjects(); unsubscribeProjects = null; }
        if (unsubscribeLogs) { unsubscribeLogs(); unsubscribeLogs = null; }
        currentProject = null;
        activeProjectBadge.innerText = "No Project Selected";
        authOverlay.classList.add('active');
        appContainer.style.display = 'none';
    }
});

// Auth Form Handler (Login/Register hybrid)
authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authError.innerText = '';
    authSubmitBtn.disabled = true;
    const email = authEmail.value.trim();
    const password = authPassword.value;
    
    try {
        await signInWithEmailAndPassword(auth, email, password);
    } catch (err) {
        if (err.code === 'auth/user-not-found' || err.code === 'auth/invalid-credential' || err.code === 'auth/invalid-login-credentials') {
            try {
                await createUserWithEmailAndPassword(auth, email, password);
            } catch (err2) {
                if (err2.code === 'auth/email-already-in-use') {
                    authError.innerText = "Invalid email or password.";
                } else {
                    authError.innerText = err2.message;
                }
            }
        } else {
            authError.innerText = err.message;
        }
    }
    authSubmitBtn.disabled = false;
});

logoutBtn.addEventListener('click', () => signOut(auth));

// Drawer Navigation
function toggleDrawer() {
    navDrawer.classList.toggle('open');
    drawerBackdrop.classList.toggle('open');
}
hamburgerBtn.addEventListener('click', toggleDrawer);
closeDrawerBtn.addEventListener('click', toggleDrawer);
drawerBackdrop.addEventListener('click', toggleDrawer);

navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
        if (link.id === 'logoutBtn') return;
        e.preventDefault();
        navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        const targetId = link.getAttribute('data-target');
        viewSections.forEach(sec => sec.classList.remove('active'));
        document.getElementById(targetId).classList.add('active');
        if (window.innerWidth < 768) toggleDrawer();
    });
});

document.getElementById('bgmVolumeInput').addEventListener('input', (e) => {
    document.getElementById('bgmVolumeDisplay').innerText = `${e.target.value}%`;
    const audio = document.getElementById('bgmPreview');
    if (audio) audio.volume = e.target.value / 100.0;
});

const voiceBoostInput = document.getElementById('voiceBoostInput');
if (voiceBoostInput) {
    voiceBoostInput.addEventListener('input', (e) => {
        const disp = document.getElementById('voiceBoostDisplay');
        if (disp) disp.innerText = `${e.target.value}%`;
    });
}

document.getElementById('bgmSelect').addEventListener('change', (e) => {
    const audio = document.getElementById('bgmPreview');
    if (e.target.value) {
        audio.src = `/bgm/${e.target.value}`;
        audio.style.display = 'block';
        audio.volume = document.getElementById('bgmVolumeInput').value / 100.0;
        audio.play();
    } else {
        audio.pause();
        audio.src = "";
    }
});

// Settings Management
const settingsForm = document.getElementById('settingsForm');
const aiBaseUrl = document.getElementById('aiBaseUrl');
const aiApiKey = document.getElementById('aiApiKey');
const aiModelSelect = document.getElementById('aiModelSelect');
const aiSystemPrompt = document.getElementById('aiSystemPrompt');
const autoPostToggle = document.getElementById('autoPostToggle');
const fetchModelsBtn = document.getElementById('fetchModelsBtn');
const fetchModelsStatus = document.getElementById('fetchModelsStatus');

async function loadUserSettings() {
    const docSnap = await getDoc(doc(db, 'users', currentUser.uid));
    if (docSnap.exists()) {
        const data = docSnap.data();
        aiBaseUrl.value = data.aiBaseUrl || '';
        aiApiKey.value = data.aiApiKey || '';
        aiSystemPrompt.value = data.aiSystemPrompt || '';
        autoPostToggle.checked = data.autoPost === true;
        
        if (data.aiBaseUrl && data.aiApiKey) {
            await fetchModels(data.aiModel);
        }
    }
}

settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('saveSettingsBtn');
    saveBtn.innerText = 'Saving...';
    saveBtn.disabled = true;
    
    try {
        await setDoc(doc(db, 'users', currentUser.uid), {
            aiBaseUrl: aiBaseUrl.value.trim(),
            aiApiKey: aiApiKey.value.trim(),
            aiModel: aiModelSelect.value,
            aiSystemPrompt: aiSystemPrompt.value,
            autoPost: autoPostToggle.checked,
            updatedAt: serverTimestamp()
        }, { merge: true });
        
        saveBtn.innerText = 'Save Settings';
        saveBtn.disabled = false;
        alert('Settings saved successfully.');
    } catch (error) {
        console.error("Error saving settings:", error);
        saveBtn.innerText = 'Save Settings';
        saveBtn.disabled = false;
        alert('Error saving settings: ' + error.message + '\n\nPlease ensure you have created a Cloud Firestore database in your Firebase project and that the security rules allow this write.');
    }
});

fetchModelsBtn.addEventListener('click', async () => {
    await fetchModels();
});

async function fetchModels(selectedModel = null) {
    const url = aiBaseUrl.value.trim();
    const key = aiApiKey.value.trim();
    if (!url || !key) {
        fetchModelsStatus.innerText = 'Please enter Base URL and API Key.';
        fetchModelsStatus.classList.add('text-danger');
        return;
    }
    
    fetchModelsStatus.innerText = 'Fetching...';
    fetchModelsStatus.classList.remove('text-danger');
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/proxy/models?url=${encodeURIComponent(url)}&key=${encodeURIComponent(key)}`);
        const data = await response.json();
        
        aiModelSelect.innerHTML = '';
        if (data && data.data && Array.isArray(data.data)) {
            data.data.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.innerText = m.id;
                aiModelSelect.appendChild(opt);
            });
            fetchModelsStatus.innerText = `Found ${data.data.length} models.`;
            if (selectedModel) aiModelSelect.value = selectedModel;
        } else {
            throw new Error("Invalid format");
        }
    } catch (err) {
        fetchModelsStatus.innerText = 'Error fetching models.';
        fetchModelsStatus.classList.add('text-danger');
        console.error(err);
    }
}

// Projects Management
const createProjectForm = document.getElementById('createProjectForm');
const newProjectName = document.getElementById('newProjectName');
const projectsList = document.getElementById('projectsList');

createProjectForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = newProjectName.value.trim();
    if (!name) return;
    
    const projectRef = await addDoc(collection(db, 'users', currentUser.uid, 'projects'), {
        name: name,
        createdAt: serverTimestamp(),
        youtubeConnectionId: null
    });
    newProjectName.value = '';
    loadProjects();
});

function loadProjects() {
    if (unsubscribeProjects) { unsubscribeProjects(); }
    const q = query(collection(db, 'users', currentUser.uid, 'projects'), orderBy('createdAt', 'desc'));
    unsubscribeProjects = onSnapshot(q, (snapshot) => {
        projectsList.innerHTML = '';
        snapshot.forEach(docSnap => {
            const data = docSnap.data();
            const div = document.createElement('div');
            div.className = 'project-card';
            const isSelected = currentProject === docSnap.id;
            
            div.innerHTML = `
                <h3>${data.name}</h3>
                <p class="text-sm text-muted mt-2">ID: ${docSnap.id}</p>
                <div class="mt-4 flex-row" style="gap: 10px;">
                    <button class="btn-primary select-project-btn" data-id="${docSnap.id}" data-name="${data.name}" ${isSelected ? 'disabled' : ''}>
                        ${isSelected ? 'Selected' : 'Select Project'}
                    </button>
                    <button class="btn-yt connect-yt-btn" data-id="${docSnap.id}">
                        ${data.youtubeConnectionId ? '✅ YT Connected' : '▶️ Connect YouTube'}
                    </button>
                </div>
                <div class="mt-4 form-group" style="background: var(--bg-card); padding: 10px; border-radius: 8px;">
                    <label style="font-size: 0.8rem; margin-bottom: 5px;">Kaggle Username</label>
                    <input type="text" class="kaggle-user-input" data-id="${docSnap.id}" value="${data.kaggleUsername || ''}" placeholder="e.g. gabrielnjoku" style="margin-bottom: 10px; padding: 0.5rem; width: 100%; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-base); color: white;">
                    
                    <label style="font-size: 0.8rem; margin-bottom: 5px;">Kaggle API Key</label>
                    <input type="password" class="kaggle-key-input" data-id="${docSnap.id}" value="${data.kaggleKey || ''}" placeholder="Kaggle API Token..." style="margin-bottom: 10px; padding: 0.5rem; width: 100%; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-base); color: white;">
                    
                    <button class="btn-accent save-kaggle-btn" data-id="${docSnap.id}" style="font-size: 0.8rem; padding: 0.5rem;">Save Kaggle Settings</button>
                </div>
            `;
            
            // Attach event listeners explicitly to avoid inline onclick CSP issues
            div.querySelector('.select-project-btn').addEventListener('click', (e) => {
                if (!isSelected) {
                    window.selectProject(e.target.getAttribute('data-id'), e.target.getAttribute('data-name'));
                }
            });
            
            div.querySelector('.connect-yt-btn').addEventListener('click', (e) => {
                window.connectYouTube(e.target.getAttribute('data-id') || e.currentTarget.getAttribute('data-id'));
            });
            
            div.querySelector('.save-kaggle-btn').addEventListener('click', async (e) => {
                const id = e.target.getAttribute('data-id');
                const user = div.querySelector('.kaggle-user-input').value.trim();
                const key = div.querySelector('.kaggle-key-input').value.trim();
                try {
                    await updateDoc(doc(db, 'users', currentUser.uid, 'projects', id), {
                        kaggleUsername: user,
                        kaggleKey: key
                    });
                    alert("Kaggle settings saved for this project!");
                } catch (err) {
                    console.error("Error saving Kaggle settings:", err);
                    alert("Failed to save settings.");
                }
            });
            
            projectsList.appendChild(div);
        });
        
        // Auto-select first if none selected
        if (!currentProject && snapshot.docs.length > 0) {
            const first = snapshot.docs[0];
            window.selectProject(first.id, first.data().name);
        }
    });
}

window.selectProject = (id, name) => {
    currentProject = id;
    activeProjectBadge.innerText = `Project: ${name}`;
    loadProjects(); // Re-render to update disabled button state
    loadLogs();
};

window.connectYouTube = (projectId) => {
    if (!currentUser) return alert("Please sign in first.");
    window.location.href = `${BACKEND_URL}/api/auth/youtube?uid=${currentUser.uid}&project=${projectId}`;
};

// Dashboard - Script Generation
const createContentForm = document.getElementById('createContentForm');
const videoTitlesInput = document.getElementById('videoTitles');
const previewScriptToggle = document.getElementById('previewScriptToggle');
const scriptResultArea = document.getElementById('scriptResultArea');
const generatedScriptText = document.getElementById('generatedScriptText');
const continueVideoBtn = document.getElementById('continueVideoBtn');
const submitContentBtn = document.getElementById('submitContentBtn');
const mediaFileInput = document.getElementById('mediaFile');

// Dynamic toggle logic based on titles
videoTitlesInput.addEventListener('input', () => {
    const lines = videoTitlesInput.value.split('\n').filter(line => line.trim().length > 0);
    if (lines.length > 1) {
        previewScriptToggle.checked = false;
        previewScriptToggle.disabled = true;
    } else {
        previewScriptToggle.disabled = false;
    }
});

// Helper to check if inputs are valid for video generation
function checkVideoSubmitState() {
    const videoModel = document.getElementById('videoModelSelect').value;
    const hasScript = generatedScriptText.value.trim().length > 0;
    const hasImage = mediaFileInput.files.length > 0 || videoModel === 'pexels';
    continueVideoBtn.disabled = !(hasScript && hasImage);
}

document.getElementById('videoModelSelect').addEventListener('change', (e) => {
    const model = e.target.value;
    const sourceImageGroup = document.getElementById('sourceImageGroup');
    if (sourceImageGroup) {
        if (model === 'pexels') {
            sourceImageGroup.style.display = 'none';
        } else {
            sourceImageGroup.style.display = 'block';
        }
    }
    checkVideoSubmitState();
});

generatedScriptText.addEventListener('input', checkVideoSubmitState);
mediaFileInput.addEventListener('change', checkVideoSubmitState);

const fontYPosInput = document.getElementById('fontYPosInput');
if (fontYPosInput) {
    fontYPosInput.addEventListener('input', (e) => {
        document.getElementById('fontYPosDisplay').innerText = e.target.value + '%';
    });
}

const clearLogsBtn = document.getElementById('clearLogsBtn');
if (clearLogsBtn) {
    clearLogsBtn.addEventListener('click', async () => {
        if (!currentProject) return alert('Select a project first!');
        if (!confirm("Are you sure you want to permanently clear all execution logs for this project?")) return;
        try {
            const token = currentUser ? await currentUser.getIdToken() : '';
            
            // 1. Direct Firestore batch delete client-side for immediate wipe
            if (currentUser && currentProject) {
                const execsRef = collection(db, 'users', currentUser.uid, 'projects', currentProject, 'executions');
                const snap = await getDocs(execsRef);
                const batch = writeBatch(db);
                snap.forEach(d => batch.delete(d.ref));
                await batch.commit();
            }
            
            // 2. Notify backend to clear memory & disk logs
            await fetchWithWakeupRetry(`${BACKEND_URL}/api/clear_logs`, {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ projectId: currentProject })
            });
            document.getElementById('executionLogsList').innerHTML = '<div class="empty-state">No videos generated yet in this project.</div>';
        } catch (e) {
            console.error("Failed to clear logs", e);
            alert('Failed to clear logs: ' + e.message);
        }
    });
}

// Main submission loop
// Helper to wait for a job to complete by listening to Firestore
function waitForJobCompletion(uid, projectId, jobId, uiStatusElement) {
    return new Promise((resolve) => {
        const unsubscribe = onSnapshot(doc(db, 'users', uid, 'projects', projectId, 'executions', jobId), (docSnap) => {
            if (docSnap.exists()) {
                const data = docSnap.data();
                if (uiStatusElement && data.status) {
                    uiStatusElement.innerText = data.status;
                }
                
                if (data.status === 'SUCCESS' || data.status === 'FAILED' || data.status === 'POSTED_TO_YOUTUBE') {
                    unsubscribe();
                    resolve(data.status);
                }
            }
        });
    });
}

createContentForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentProject) return alert('Select a project first!');
    
    let titles = [];
    let isManual = window.currentPromptMode === 'manual';
    let manualScript = '';
    
    if (isManual) {
        manualScript = document.getElementById('manualScript').value.trim();
        if (!manualScript) return alert('Please enter your manual script.');
        titles = ["Manual Video Generation"];
    } else {
        titles = videoTitlesInput.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        if (titles.length === 0) return alert('Please enter at least one title.');
    }
    
    const mediaFile = mediaFileInput.files[0];
    const voiceModel = document.getElementById('voiceModelSelect').value;
    const videoModel = document.getElementById('videoModelSelect').value;
    const aspectRatio = document.getElementById('aspectRatioSelect').value;
    const targetDuration = document.getElementById('targetDurationSelect').value;
    const resolution = document.getElementById('resolutionSelect').value;
    
    const gridColor = document.getElementById('gridColorInput')?.value || '#ffffff';
    const captionColor = document.getElementById('captionColorInput')?.value || '#ffffff';
    const fontSize = document.getElementById('fontSizeInput')?.value || '60';
    const fontYPos = document.getElementById('fontYPosInput')?.value || '83';
    const bgmSelect = document.getElementById('bgmSelect')?.value || '';
    const bgmVolume = document.getElementById('bgmVolumeInput')?.value || '15';
    const voiceBoost = document.getElementById('voiceBoostInput')?.value || '100';
    const addCaptions = document.getElementById('addCaptionsToggle')?.checked ? 'true' : 'false';
    const addGrid = document.getElementById('addGridToggle')?.checked ? 'true' : 'false';
    
    submitContentBtn.innerText = 'Queuing for 12h Worker...';
    submitContentBtn.disabled = true;
    
    const batchId = `epicsync_batch_${Date.now()}`;
    let queuedCount = 0;
    
    for (let i = 0; i < titles.length; i++) {
        const title = titles[i];
        const jobId = `epicsync_premium_${Date.now()}_${i}_${Math.random().toString(36).substring(2, 6)}`;
        
        submitContentBtn.innerText = `Generating script ${i+1}/${titles.length}...`;
        
        let scriptText = manualScript;
        if (!isManual) {
            try {
                scriptText = await generateScriptDirect(title, videoModel, targetDuration, currentUser.uid);
            } catch (err) {
                console.error("AI Generation Error:", err);
                alert(`AI Script Generation error on "${title}": ` + err.message);
                submitContentBtn.innerText = '🚀 Launch EpicSync GPU';
                submitContentBtn.disabled = false;
                return;
            }
        }
        
        // Write Job directly to Firestore
        try {
            await setDoc(doc(db, 'users', currentUser.uid, 'projects', currentProject, 'executions', jobId), {
                job_id: jobId,
                batch_id: batchId,
                batch_index: i,
                title: title.length > 40 ? title.substring(0, 37) + '...' : title,
                script: scriptText,
                voice: voiceModel,
                video_model: videoModel,
                aspect_ratio: aspectRatio,
                resolution: resolution,
                target_duration: targetDuration,
                voice_boost: voiceBoost,
                bgm_volume: bgmVolume,
                bgm_select: bgmSelect,
                add_captions: addCaptions,
                add_grid: addGrid,
                grid_color: gridColor,
                caption_color: captionColor,
                font_size: fontSize,
                font_y_pos: fontYPos,
                status: 'QUEUED',
                progress: 0,
                step_text: 'Queued for 12-Hour Kaggle Cloud Worker...',
                logs: [`[${new Date().toLocaleTimeString()}] Task queued for Kaggle worker execution.`],
                createdAt: serverTimestamp(),
                updatedAt: serverTimestamp()
            });
            queuedCount++;
        } catch (dbErr) {
            console.error("Firestore Write Error:", dbErr);
            alert("Database Error: " + dbErr.message);
        }
    }
    
    submitContentBtn.innerText = '🚀 Launch EpicSync GPU';
    submitContentBtn.disabled = false;
    
    if (queuedCount > 0) {
        alert(`🚀 Successfully queued ${queuedCount} video(s)! Your active 12-Hour Kaggle Worker will process them sequentially.`);
        document.querySelector('[data-target="view-logs"]')?.click();
    }
});

function loadLogs() {
    if (!currentProject) return;
    const logsContainer = document.getElementById('executionLogsList');
    logsContainer.innerHTML = '<div class="empty-state">Loading logs...</div>';
    
    if (unsubscribeLogs) { unsubscribeLogs(); }
    const q = query(collection(db, 'users', currentUser.uid, 'projects', currentProject, 'executions'), orderBy('createdAt', 'desc'));
    unsubscribeLogs = onSnapshot(q, (snapshot) => {
        logsContainer.innerHTML = '';
        
        let hasActiveTasks = false;
        const queueContainer = document.getElementById('bulkQueueContainer');
        const queueList = document.getElementById('bulkQueueList');
        
        // Only clear the queue list if we aren't actively injecting items in a loop during submission
        if (submitContentBtn.innerText !== 'Processing Queue...') {
            queueList.innerHTML = '';
        }

        if (snapshot.empty) {
            logsContainer.innerHTML = '<div class="empty-state">No videos generated yet in this project.</div>';
            
            if (submitContentBtn.innerText !== 'Processing Queue...' && submitContentBtn.innerText !== 'Confirm to Launch') {
                queueContainer.style.display = 'none';
                submitContentBtn.innerText = '🚀 Launch EpicSync GPU';
                submitContentBtn.disabled = false;
            }
            return;
        }
        
        snapshot.forEach(docSnap => {
            const data = docSnap.data();
            const div = document.createElement('div');
            div.className = 'log-card';
            const escapedTitle = (data.title || 'Untitled Video').replace(/'/g, "\\'");
            const isActive = !['SUCCESS', 'FAILED', 'CANCELLED', 'POSTED_TO_YOUTUBE'].includes(data.status);
            
            // Queue Persistence Logic
            if (isActive && submitContentBtn.innerText !== 'Processing Queue...' && submitContentBtn.innerText !== 'Confirm to Launch') {
                hasActiveTasks = true;
                const queueEl = document.createElement('div');
                queueEl.className = 'log-card';
                queueEl.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>${data.title || 'Untitled'}</strong>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <span style="color:#e5b300;">${data.status}</span>
                            <button class="btn-secondary" style="font-size: 12px; padding: 2px 6px; color: #ff4444;" onclick="cancelJob('${docSnap.id}')">🛑</button>
                        </div>
                    </div>
                `;
                queueList.appendChild(queueEl);
            }

            if (isActive && currentUser) {
                currentUser.getIdToken().then(t => {
                    fetch(`${BACKEND_URL}/api/sync_job/${docSnap.id}?projectId=${currentProject}`, {
                        headers: { 'Authorization': `Bearer ${t}` }
                    }).catch(e => console.log('Background sync notice:', e));
                });
            }

            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <h4>${data.title || 'Untitled Video'}</h4>
                        <p class="text-sm mt-2 text-muted">Status: ${data.status}</p>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        ${isActive ? `
                            <button class="btn-secondary" style="font-size: 12px; padding: 4px 8px; color: #4caf50;" onclick="syncJobStatus('${docSnap.id}')">🔄 Check Status</button>
                            <button class="btn-secondary" style="font-size: 12px; padding: 4px 8px; color: #ff4444;" onclick="cancelJob('${docSnap.id}')">🛑 Cancel</button>
                        ` : ''}
                        <button class="btn-secondary" style="font-size: 12px; padding: 4px 8px;" onclick="openLogModal('${docSnap.id}', '${escapedTitle}')">👁️ View Console</button>
                    </div>
                </div>
                ${data.output_file ? `
                <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                    <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: bold; color: #4CAF50;">✅ Generation Complete</p>
                    <video src="${data.output_file.startsWith('http') ? data.output_file : `${BACKEND_URL}${data.output_file}`}" controls style="width: 100%; max-width: 300px; border-radius: 8px; margin-bottom: 10px;"></video>
                    <div style="display: flex; gap: 8px;">
                        <a href="${data.output_file.startsWith('http') ? data.output_file : `${BACKEND_URL}${data.output_file}`}" target="_blank" download class="btn-primary" style="text-decoration: none; text-align: center;">⬇️ Download</a>
                        <button class="btn-secondary" onclick="alert('Export to Google Drive coming soon!')">☁️ GDrive</button>
                        <button class="btn-secondary" onclick="alert('Export to Dropbox coming soon!')">☁️ Dropbox</button>
                    </div>
                </div>
                ` : ''}
            `;
            logsContainer.appendChild(div);
        });
        
        // Finalize Queue State
        if (submitContentBtn.innerText !== 'Processing Queue...' && submitContentBtn.innerText !== 'Confirm to Launch') {
            if (hasActiveTasks) {
                queueContainer.style.display = 'block';
                submitContentBtn.innerText = 'Tasks Running...';
                submitContentBtn.disabled = true;
            } else {
                queueContainer.style.display = 'none';
                submitContentBtn.innerText = '🚀 Launch EpicSync GPU';
                submitContentBtn.disabled = false;
            }
        }
    });
}

let logModalUnsubscribe = null;

window.syncJobStatus = async function(jobId) {
    try {
        const token = currentUser ? await currentUser.getIdToken() : '';
        const res = await fetch(`${BACKEND_URL}/api/sync_job/${jobId}?projectId=${currentProject}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            alert('🎉 Video generation complete! The video player has been loaded.');
        } else {
            alert(`Job status on engine: ${data.status}. If Kaggle is still rendering, it will complete shortly.`);
        }
    } catch (err) {
        console.error(err);
        alert('Failed to connect to status check server.');
    }
};

window.cancelJob = async function(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) return;
    try {
        const formData = new FormData();
        formData.append('kaggle_user', 'gabrielnjoku');
        formData.append('kaggle_key', 'KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e');
        if (currentUser) formData.append('uid', currentUser.uid);
        if (currentProject) {
            formData.append('projectId', currentProject);
            try {
                const projDoc = await getDoc(doc(db, 'users', currentUser.uid, 'projects', currentProject));
                if (projDoc.exists()) {
                    const pData = projDoc.data();
                    if (pData.kaggleUsername) formData.set('kaggle_user', pData.kaggleUsername);
                    if (pData.kaggleKey) formData.set('kaggle_key', pData.kaggleKey);
                }
            } catch (e) {
                console.warn('Could not fetch project credentials for cancel', e);
            }
        }
        
        const res = await fetch(`${BACKEND_URL}/api/cancel/${jobId}`, {
            method: 'POST',
            body: formData
        });
        if (res.ok) {
            alert('Job cancelled successfully.');
        } else {
            const errorData = await res.json().catch(() => ({}));
            alert('Failed to cancel job. Backend returned an error: ' + (errorData.detail || res.statusText));
        }
    } catch (err) {
        console.error(err);
        alert('Failed to cancel job: ' + err.message);
    }
};

window.openLogModal = function(jobId, title) {
    document.getElementById('logModalTitle').innerText = title || 'Job ' + jobId;
    document.getElementById('logModal').style.display = 'flex';
    
    const content = document.getElementById('logModalContent');
    content.innerHTML = '<div style="color: #666;">Loading logs...</div>';
    
    if (logModalUnsubscribe) logModalUnsubscribe();
    
    const docRef = doc(db, 'users', currentUser.uid, 'projects', currentProject, 'executions', jobId);
    logModalUnsubscribe = onSnapshot(docRef, (docSnap) => {
        if (docSnap.exists()) {
            const data = docSnap.data();
            if (data.logs && data.logs.length > 0) {
                const reversedLogs = [...data.logs].reverse();
                content.innerHTML = reversedLogs.map(log => `<div>${log}</div>`).join('');
            } else {
                content.innerHTML = '<div style="color: #666;">Waiting for logs from Kaggle...</div>';
            }
        }
    });
};

document.getElementById('closeLogModal').addEventListener('click', () => {
    document.getElementById('logModal').style.display = 'none';
    if (logModalUnsubscribe) logModalUnsubscribe();
});

window.onclick = function(event) {
    const modal = document.getElementById('logModal');
    if (event.target === modal) {
        modal.style.display = "none";
        if (logModalUnsubscribe) logModalUnsubscribe();
    }
}
