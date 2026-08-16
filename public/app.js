// EpicSync Production-Grade Application Logic

let currentUser = null;
let currentDurationUnit = 'seconds';
let multiSelectMode = false;
const selectedJobs = new Map(); // jobId -> { title, output_file, aspect_ratio }
let allUserExecutions = [];

// 1. Navigation & Page View Switching
const navStudioBtn = document.getElementById('navStudioBtn');
const navLogsBtn = document.getElementById('navLogsBtn');
const navSettingsBtn = document.getElementById('navSettingsBtn');

const studioView = document.getElementById('studioView');
const logsView = document.getElementById('logsView');
const settingsView = document.getElementById('settingsView');

function switchPage(target) {
    [navStudioBtn, navLogsBtn, navSettingsBtn].forEach(btn => btn?.classList.remove('active'));
    [studioView, logsView, settingsView].forEach(view => view?.classList.remove('active'));

    if (target === 'studio') {
        navStudioBtn?.classList.add('active');
        studioView?.classList.add('active');
    } else if (target === 'logs') {
        navLogsBtn?.classList.add('active');
        logsView?.classList.add('active');
    } else if (target === 'settings') {
        navSettingsBtn?.classList.add('active');
        settingsView?.classList.add('active');
    }
}

navStudioBtn?.addEventListener('click', () => switchPage('studio'));
navLogsBtn?.addEventListener('click', () => switchPage('logs'));
navSettingsBtn?.addEventListener('click', () => switchPage('settings'));

// 2. Aspect Ratio Selector (Card UI)
const aspectCards = document.querySelectorAll('.aspect-card');
aspectCards.forEach(card => {
    card.addEventListener('click', () => {
        aspectCards.forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        const radio = card.querySelector('input[type="radio"]');
        if (radio) radio.checked = true;
    });
});

// 3. Duration Selector (Seconds vs Minutes + Stepper + Dynamic Calculation)
const unitSecondsBtn = document.getElementById('unitSecondsBtn');
const unitMinutesBtn = document.getElementById('unitMinutesBtn');
const durationValueInput = document.getElementById('durationValueInput');
const durationCalcBadge = document.getElementById('durationCalcBadge');
const stepDownBtn = document.getElementById('stepDownBtn');
const stepUpBtn = document.getElementById('stepUpBtn');

function calculateDurationWords() {
    const val = parseFloat(durationValueInput.value) || 0;
    if (currentDurationUnit === 'seconds') {
        const words = Math.max(25, Math.round(val * 2.2));
        durationCalcBadge.innerText = `🎯 ~${words} words (Viral ${val}s Shorts)`;
    } else {
        const words = Math.max(50, Math.round(val * 135));
        durationCalcBadge.innerText = `🎯 ~${words} words (${val} min Explainer)`;
    }
}

unitSecondsBtn?.addEventListener('click', () => {
    currentDurationUnit = 'seconds';
    unitSecondsBtn.classList.add('active');
    unitMinutesBtn.classList.remove('active');
    if (parseFloat(durationValueInput.value) <= 10) durationValueInput.value = 45;
    calculateDurationWords();
});

unitMinutesBtn?.addEventListener('click', () => {
    currentDurationUnit = 'minutes';
    unitMinutesBtn.classList.add('active');
    unitSecondsBtn.classList.remove('active');
    if (parseFloat(durationValueInput.value) > 10) durationValueInput.value = 3;
    calculateDurationWords();
});

stepDownBtn?.addEventListener('click', () => {
    const current = parseFloat(durationValueInput.value) || 1;
    const step = currentDurationUnit === 'seconds' ? 5 : 1;
    durationValueInput.value = Math.max(1, current - step);
    calculateDurationWords();
});

stepUpBtn?.addEventListener('click', () => {
    const current = parseFloat(durationValueInput.value) || 1;
    const step = currentDurationUnit === 'seconds' ? 5 : 1;
    durationValueInput.value = current + step;
    calculateDurationWords();
});

durationValueInput?.addEventListener('input', calculateDurationWords);

// 4. Visual Presets Sliders & Script Toggle
const fontYPosInput = document.getElementById('fontYPosInput');
const fontYPosVal = document.getElementById('fontYPosVal');
if (fontYPosInput && fontYPosVal) {
    fontYPosInput.addEventListener('input', (e) => fontYPosVal.innerText = `${e.target.value}%`);
}

const voiceBoostInput = document.getElementById('voiceBoostInput');
const voiceBoostVal = document.getElementById('voiceBoostVal');
if (voiceBoostInput && voiceBoostVal) {
    voiceBoostInput.addEventListener('input', (e) => voiceBoostVal.innerText = `${e.target.value}%`);
}

const bgmVolumeInput = document.getElementById('bgmVolumeInput');
const bgmVolumeVal = document.getElementById('bgmVolumeVal');
if (bgmVolumeInput && bgmVolumeVal) {
    bgmVolumeInput.addEventListener('input', (e) => bgmVolumeVal.innerText = `${e.target.value}%`);
}

const manualScriptToggle = document.getElementById('manualScriptToggle');
const manualScriptArea = document.getElementById('manualScriptArea');
if (manualScriptToggle && manualScriptArea) {
    manualScriptToggle.addEventListener('change', (e) => {
        manualScriptArea.style.display = e.target.checked ? 'block' : 'none';
    });
}

// 5. Firebase Auth State & Modal Handlers
const openAuthModalBtn = document.getElementById('openAuthModalBtn');
const signOutBtn = document.getElementById('signOutBtn');
const authModal = document.getElementById('authModal');
const closeAuthModalBtn = document.getElementById('closeAuthModalBtn');
const tabSignIn = document.getElementById('tabSignIn');
const tabSignUp = document.getElementById('tabSignUp');
const authForm = document.getElementById('authForm');
const authEmail = document.getElementById('authEmail');
const authPassword = document.getElementById('authPassword');
const authSubmitBtn = document.getElementById('authSubmitBtn');
const authErrorMsg = document.getElementById('authErrorMsg');
const userEmailDisplay = document.getElementById('userEmailDisplay');

let isSignUpMode = false;

tabSignIn?.addEventListener('click', () => {
    isSignUpMode = false;
    tabSignIn.classList.add('active');
    tabSignUp.classList.remove('active');
    authSubmitBtn.innerText = 'Sign In';
});

tabSignUp?.addEventListener('click', () => {
    isSignUpMode = true;
    tabSignUp.classList.add('active');
    tabSignIn.classList.remove('active');
    authSubmitBtn.innerText = 'Create Account';
});

openAuthModalBtn?.addEventListener('click', () => {
    if (!currentUser && authModal) {
        authModal.style.display = 'flex';
        authErrorMsg.style.display = 'none';
    }
});

closeAuthModalBtn?.addEventListener('click', () => {
    if (authModal) authModal.style.display = 'none';
});

authForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = authEmail.value.trim();
    const pass = authPassword.value.trim();
    if (!email || !pass) return;

    authSubmitBtn.disabled = true;
    authErrorMsg.style.display = 'none';

    try {
        if (isSignUpMode) {
            await window.FirebaseAuth.createUserWithEmailAndPassword(window.auth, email, pass);
        } else {
            await window.FirebaseAuth.signInWithEmailAndPassword(window.auth, email, pass);
        }
        if (authModal) authModal.style.display = 'none';
    } catch (err) {
        authErrorMsg.innerText = err.message;
        authErrorMsg.style.display = 'block';
    } finally {
        authSubmitBtn.disabled = false;
    }
});

signOutBtn?.addEventListener('click', async () => {
    if (confirm('Are you sure you want to sign out?')) {
        await window.FirebaseAuth.signOut(window.auth);
    }
});

function initAuthObserver() {
    if (!window.auth || !window.FirebaseAuth) {
        setTimeout(initAuthObserver, 200);
        return;
    }

    window.FirebaseAuth.onAuthStateChanged(window.auth, (user) => {
        currentUser = user;
        if (user) {
            userEmailDisplay.innerText = user.email || 'User Account';
            signOutBtn.style.display = 'block';
            loadUserSettings(user.uid);
            listenToUserExecutions(user.uid);
        } else {
            userEmailDisplay.innerText = 'Sign In / Register';
            signOutBtn.style.display = 'none';
            // Listen to public executions if logged out
            listenToUserExecutions(null);
        }
    });
}

// 6. Real-time Firestore Listeners
let activeUnsubscribe = null;

function listenToUserExecutions(uid) {
    if (!window.db || !window.FirebaseUtils) {
        setTimeout(() => listenToUserExecutions(uid), 200);
        return;
    }

    if (activeUnsubscribe) {
        activeUnsubscribe();
        activeUnsubscribe = null;
    }

    const { collection, onSnapshot, query, limit } = window.FirebaseUtils;
    const currentContainer = document.getElementById('currentBatchLogsContainer');
    const allContainer = document.getElementById('allLogsContainer');
    const totalLogsBadge = document.getElementById('totalLogsBadge');

    const colRef = uid 
        ? collection(window.db, 'users', uid, 'executions')
        : collection(window.db, 'executions');

    const q = query(colRef, limit(100));

    activeUnsubscribe = onSnapshot(q, (snapshot) => {
        const docs = [];
        snapshot.forEach(doc => docs.push({ id: doc.id, ...doc.data() }));

        docs.sort((a, b) => {
            const timeA = a.createdAt?.toMillis ? a.createdAt.toMillis() : (a.updatedAt?.toMillis ? a.updatedAt.toMillis() : 0);
            const timeB = b.createdAt?.toMillis ? b.createdAt.toMillis() : (b.updatedAt?.toMillis ? b.updatedAt.toMillis() : 0);
            return timeB - timeA;
        });

        allUserExecutions = docs;
        if (totalLogsBadge) totalLogsBadge.innerText = docs.length;

        // Render All Execution Logs
        renderAllLogs(docs, allContainer);

        // Get Active Batch ID from LocalStorage
        const storageKey = uid ? `epicsync_batch_${uid}` : 'epicsync_active_batch_id';
        let activeBatchId = localStorage.getItem(storageKey);
        if (!activeBatchId && docs.length > 0) {
            activeBatchId = docs[0].batch_id || '';
            if (activeBatchId) localStorage.setItem(storageKey, activeBatchId);
        }

        const currentBatchDocs = activeBatchId ? docs.filter(d => d.batch_id === activeBatchId) : [];
        renderCurrentBatch(currentBatchDocs, currentContainer, activeBatchId);
    }, (err) => {
        console.error("Executions listener error:", err);
    });
}

function renderCurrentBatch(docs, container, batchId) {
    if (!container) return;
    const subtitle = document.getElementById('currentBatchSubtitle');
    if (subtitle && batchId) {
        subtitle.innerText = `Active Batch: ${batchId}`;
    }

    if (docs.length === 0) {
        container.innerHTML = '<div class="empty-state">No batch currently active. Launch a batch above!</div>';
        return;
    }

    container.innerHTML = '';
    docs.forEach(data => {
        container.appendChild(createVideoCard(data, false));
    });
}

function renderAllLogs(docs, container) {
    if (!container) return;
    if (docs.length === 0) {
        container.innerHTML = '<div class="empty-state">No execution logs found for this account.</div>';
        return;
    }

    container.innerHTML = '';
    docs.forEach(data => {
        container.appendChild(createVideoCard(data, true));
    });
    updateSelectionBar();
}

function createVideoCard(data, isAllLogsView) {
    const status = data.status || 'QUEUED';
    const progress = data.progress !== undefined ? data.progress : (status === 'SUCCESS' ? 100 : 0);
    const stepText = data.step_text || 'Waiting for runner...';
    const outputUrl = data.output_file || '';
    const jobId = data.job_id || data.id;
    const isSelected = selectedJobs.has(jobId);

    const card = document.createElement('div');
    card.className = `video-card ${isSelected ? 'selected' : ''}`;
    card.dataset.jobId = jobId;

    let checkboxHtml = '';
    if (isAllLogsView && multiSelectMode) {
        checkboxHtml = `<input type="checkbox" class="card-checkbox" ${isSelected ? 'checked' : ''}>`;
    }

    card.innerHTML = `
        <div class="video-card-top">
            ${checkboxHtml}
            <div class="video-info">
                <span class="video-title">${escapeHtml(data.title || 'Untitled Video')}</span>
                <span class="status-badge badge-${status}">${status}</span>
            </div>
        </div>
        
        <div class="progress-bar-wrap">
            <div class="progress-bar-fill" style="width: ${progress}%;"></div>
        </div>
        
        <div class="step-text">${escapeHtml(stepText)} (${progress}%)</div>
        
        ${outputUrl ? `
            <div class="player-container">
                <video src="${outputUrl}" controls playsinline preload="metadata"></video>
                <div class="player-actions">
                    <a href="${outputUrl}" target="_blank" download class="btn-download">⬇️ Download</a>
                    <button class="btn-yt-single" data-job-id="${jobId}">📺 Push to YouTube</button>
                </div>
            </div>
        ` : ''}
    `;

    if (isAllLogsView && multiSelectMode) {
        card.addEventListener('click', (e) => {
            if (e.target.tagName === 'VIDEO' || e.target.tagName === 'A' || e.target.tagName === 'BUTTON') return;
            toggleJobSelection(jobId, data);
        });
        const chk = card.querySelector('.card-checkbox');
        if (chk) {
            chk.addEventListener('change', (e) => {
                e.stopPropagation();
                toggleJobSelection(jobId, data);
            });
        }
    }

    const singleYtBtn = card.querySelector('.btn-yt-single');
    if (singleYtBtn) {
        singleYtBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pushSingleToYouTube(data);
        });
    }

    return card;
}

// 7. Multi-Select & Batch Actions
const toggleMultiSelectBtn = document.getElementById('toggleMultiSelectBtn');
const batchSelectionBar = document.getElementById('batchSelectionBar');
const selectedCountText = document.getElementById('selectedCountText');
const pushBatchYtBtn = document.getElementById('pushBatchYtBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');

toggleMultiSelectBtn?.addEventListener('click', () => {
    multiSelectMode = !multiSelectMode;
    toggleMultiSelectBtn.classList.toggle('active', multiSelectMode);
    if (!multiSelectMode) selectedJobs.clear();
    renderAllLogs(allUserExecutions, document.getElementById('allLogsContainer'));
});

function toggleJobSelection(jobId, data) {
    if (selectedJobs.has(jobId)) {
        selectedJobs.delete(jobId);
    } else {
        selectedJobs.set(jobId, {
            job_id: jobId,
            title: data.title || '',
            video_url: data.output_file || '',
            aspect_ratio: data.aspect_ratio || '9:16'
        });
    }
    renderAllLogs(allUserExecutions, document.getElementById('allLogsContainer'));
}

function updateSelectionBar() {
    if (!batchSelectionBar) return;
    const count = selectedJobs.size;
    if (multiSelectMode && count > 0) {
        batchSelectionBar.style.display = 'flex';
        selectedCountText.innerText = `${count} video${count > 1 ? 's' : ''} selected`;
    } else {
        batchSelectionBar.style.display = 'none';
    }
}

// 8. YouTube Webhook Dispatch & Settings
let userSavedWebhookUrl = '';

async function loadUserSettings(uid) {
    if (!uid || !window.db || !window.FirebaseUtils) return;
    try {
        const { doc, getDoc } = window.FirebaseUtils;
        const snap = await getDoc(doc(window.db, 'users', uid, 'settings', 'config'));
        if (snap.exists()) {
            userSavedWebhookUrl = snap.data().webhook_url || '';
            const input = document.getElementById('webhookUrlSetting');
            if (input) input.value = userSavedWebhookUrl;
        }
    } catch (e) {
        console.error("Load settings error:", e);
    }
}

const settingsForm = document.getElementById('settingsForm');
const settingsStatusMsg = document.getElementById('settingsStatusMsg');

settingsForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = document.getElementById('webhookUrlSetting').value.trim();
    userSavedWebhookUrl = url;

    if (currentUser) {
        try {
            const { doc, setDoc } = window.FirebaseUtils;
            await setDoc(doc(window.db, 'users', currentUser.uid, 'settings', 'config'), {
                webhook_url: url,
                updatedAt: new Date()
            }, { merge: true });
            
            settingsStatusMsg.innerText = '✅ Settings saved successfully!';
            settingsStatusMsg.style.color = 'var(--accent)';
            settingsStatusMsg.style.display = 'block';
            setTimeout(() => settingsStatusMsg.style.display = 'none', 3000);
        } catch (err) {
            alert('Failed to save settings: ' + err.message);
        }
    } else {
        localStorage.setItem('epicsync_yt_webhook', url);
        alert('Settings saved locally. Sign in to sync across devices!');
    }
});

const testWebhookBtn = document.getElementById('testWebhookBtn');
testWebhookBtn?.addEventListener('click', async () => {
    const url = document.getElementById('webhookUrlSetting').value.trim() || userSavedWebhookUrl;
    if (!url) return alert('Please enter a Webhook URL first.');

    testWebhookBtn.innerText = '🧪 Testing...';
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event: 'test_connection',
                source: 'EpicSync Studio',
                timestamp: Date.now()
            })
        });
        alert(`✅ Webhook test sent! Status: ${res.status}`);
    } catch (err) {
        alert(`Webhook test notice: ${err.message}\n(Ensure your n8n / server supports CORS or is active)`);
    } finally {
        testWebhookBtn.innerText = '🧪 Test Webhook';
    }
});

async function dispatchVideosToWebhook(videosList) {
    const webhookUrl = userSavedWebhookUrl || document.getElementById('webhookUrlSetting')?.value?.trim() || localStorage.getItem('epicsync_yt_webhook');
    
    if (!webhookUrl) {
        if (confirm('No YouTube Webhook URL configured! Would you like to open Settings to add it now?')) {
            switchPage('settings');
        }
        return;
    }

    const payload = {
        event: 'youtube_publish_request',
        timestamp: Date.now(),
        count: videosList.length,
        videos: videosList.map(v => ({
            title: v.title,
            video_download_link: v.video_url || v.output_file,
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
            selectedJobs.clear();
            updateSelectionBar();
        } else {
            alert(`Webhook returned status ${res.status}`);
        }
    } catch (err) {
        console.error("Webhook push error:", err);
        alert(`Payload generated for ${videosList.length} video(s):\n\n` + JSON.stringify(payload, null, 2));
    }
}

function pushSingleToYouTube(data) {
    if (!data.output_file) return alert('Video has not finished generating yet.');
    dispatchVideosToWebhook([data]);
}

pushBatchYtBtn?.addEventListener('click', () => {
    const list = Array.from(selectedJobs.values()).filter(v => v.video_url);
    if (list.length === 0) return alert('None of the selected videos have finished generating yet.');
    dispatchVideosToWebhook(list);
});

// Delete Selected
deleteSelectedBtn?.addEventListener('click', async () => {
    if (!confirm(`Are you sure you want to delete ${selectedJobs.size} selected execution(s)?`)) return;
    const { doc, deleteDoc, writeBatch } = window.FirebaseUtils;
    try {
        const batch = writeBatch(window.db);
        selectedJobs.forEach((_, jobId) => {
            if (currentUser) {
                batch.delete(doc(window.db, 'users', currentUser.uid, 'executions', jobId));
            }
            batch.delete(doc(window.db, 'executions', jobId));
        });
        await batch.commit();
        selectedJobs.clear();
        alert('Selected logs deleted.');
    } catch (e) {
        alert('Error deleting: ' + e.message);
    }
});

// Clear Current Feed
const clearCurrentFeedBtn = document.getElementById('clearCurrentFeedBtn');
clearCurrentFeedBtn?.addEventListener('click', () => {
    const storageKey = currentUser ? `epicsync_batch_${currentUser.uid}` : 'epicsync_active_batch_id';
    localStorage.removeItem(storageKey);
    document.getElementById('currentBatchLogsContainer').innerHTML = '<div class="empty-state">Current feed cleared. Launch a batch above!</div>';
    const subtitle = document.getElementById('currentBatchSubtitle');
    if (subtitle) subtitle.innerText = 'Feed cleared.';
});

// Clear All Logs
const clearAllLogsBtn = document.getElementById('clearAllLogsBtn');
clearAllLogsBtn?.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to delete ALL execution history for this account?')) return;
    const { doc, writeBatch } = window.FirebaseUtils;
    try {
        const batch = writeBatch(window.db);
        allUserExecutions.forEach(d => {
            if (currentUser) {
                batch.delete(doc(window.db, 'users', currentUser.uid, 'executions', d.id));
            }
            batch.delete(doc(window.db, 'executions', d.id));
        });
        await batch.commit();
        selectedJobs.clear();
        const storageKey = currentUser ? `epicsync_batch_${currentUser.uid}` : 'epicsync_active_batch_id';
        localStorage.removeItem(storageKey);
        alert('All execution logs cleared.');
    } catch (e) {
        alert('Failed to clear logs: ' + e.message);
    }
});

// 9. Batch Creation Submit
const createBatchForm = document.getElementById('createBatchForm');
const submitBatchBtn = document.getElementById('submitBatchBtn');

createBatchForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const titlesRaw = document.getElementById('videoTitles').value.trim();
    if (!titlesRaw) return alert('Please enter at least one title.');

    const titles = titlesRaw.split('\n').map(t => t.trim()).filter(t => t.length > 0);
    if (titles.length === 0) return alert('Please enter valid titles.');

    const isManual = manualScriptToggle?.checked;
    const manualScript = document.getElementById('manualScriptText')?.value?.trim() || '';
    if (isManual && !manualScript) return alert('Please enter your manual script.');

    const durationVal = document.getElementById('durationValueInput').value || '45';
    const formattedDuration = `${durationVal} ${currentDurationUnit}`;
    const selectedAspect = document.querySelector('input[name="aspectRatio"]:checked')?.value || '9:16';

    const payload = {
        uid: currentUser?.uid || '',
        titles: titles,
        script: isManual ? manualScript : '',
        aspect_ratio: selectedAspect,
        target_duration: formattedDuration,
        voice: document.getElementById('voiceSelect').value,
        grid_color: document.getElementById('gridColorInput').value,
        caption_color: document.getElementById('captionColorInput').value,
        font_size: document.getElementById('fontSizeInput').value,
        font_y_pos: document.getElementById('fontYPosInput').value,
        voice_boost: document.getElementById('voiceBoostInput').value,
        bgm_volume: document.getElementById('bgmVolumeInput').value,
        add_grid: document.getElementById('addGridToggle').checked ? 'true' : 'false',
        add_captions: 'true'
    };

    submitBatchBtn.innerText = `🚀 Launching ${titles.length} Video(s)...`;
    submitBatchBtn.disabled = true;

    try {
        const res = await fetch('/api/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok && data.success) {
            const storageKey = currentUser ? `epicsync_batch_${currentUser.uid}` : 'epicsync_active_batch_id';
            localStorage.setItem(storageKey, data.batch_id);

            const currentContainer = document.getElementById('currentBatchLogsContainer');
            if (currentContainer) {
                currentContainer.innerHTML = '<div class="empty-state">🚀 Batch queued! Kaggle CPU worker is running...</div>';
            }

            alert(`🚀 Successfully launched batch of ${titles.length} video(s)! Watching real-time stream.`);
            document.getElementById('videoTitles').value = '';
            if (manualScriptArea) document.getElementById('manualScriptText').value = '';
        } else {
            alert(`Failed to launch: ${data.error || 'Unknown error'}`);
        }
    } catch (err) {
        console.error("Batch launch error:", err);
        alert(`Network error launching batch: ${err.message}`);
    } finally {
        submitBatchBtn.innerText = '🚀 Launch EpicSync Pexels Run';
        submitBatchBtn.disabled = false;
    }
});

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initial setup
calculateDurationWords();
initAuthObserver();
