// EpicSync Complete Application Logic

// Global state
let currentUnit = 'seconds';
let multiSelectMode = false;
const selectedJobs = new Map(); // jobId -> { title, output_file, aspect_ratio }
let allExecutionsList = [];

// 1. Tab Navigation
const tabStudioBtn = document.getElementById('tabStudioBtn');
const tabLogsBtn = document.getElementById('tabLogsBtn');
const studioView = document.getElementById('studioView');
const logsView = document.getElementById('logsView');

function switchView(target) {
    if (target === 'studioView') {
        tabStudioBtn?.classList.add('active');
        tabLogsBtn?.classList.remove('active');
        studioView?.classList.add('active');
        logsView?.classList.remove('active');
    } else {
        tabLogsBtn?.classList.add('active');
        tabStudioBtn?.classList.remove('active');
        logsView?.classList.add('active');
        studioView?.classList.remove('active');
    }
}

tabStudioBtn?.addEventListener('click', () => switchView('studioView'));
tabLogsBtn?.addEventListener('click', () => switchView('logsView'));

// 2. Duration Unit Toggle & Dynamic Word Estimate
const unitSecBtn = document.getElementById('unitSecBtn');
const unitMinBtn = document.getElementById('unitMinBtn');
const durationNumberInput = document.getElementById('durationNumberInput');
const durationHint = document.getElementById('durationHint');

function updateDurationEstimate() {
    const val = parseFloat(durationNumberInput.value) || 0;
    if (currentUnit === 'seconds') {
        const words = Math.max(20, Math.round(val * 2.2));
        durationHint.innerText = `≈ ${words} spoken words (${val}s duration)`;
    } else {
        const words = Math.max(50, Math.round(val * 135));
        durationHint.innerText = `≈ ${words} spoken words (${val} min duration)`;
    }
}

unitSecBtn?.addEventListener('click', () => {
    currentUnit = 'seconds';
    unitSecBtn.classList.add('active');
    unitMinBtn.classList.remove('active');
    if (parseFloat(durationNumberInput.value) <= 10) {
        durationNumberInput.value = 45;
    }
    updateDurationEstimate();
});

unitMinBtn?.addEventListener('click', () => {
    currentUnit = 'minutes';
    unitMinBtn.classList.add('active');
    unitSecBtn.classList.remove('active');
    if (parseFloat(durationNumberInput.value) > 10) {
        durationNumberInput.value = 3;
    }
    updateDurationEstimate();
});

durationNumberInput?.addEventListener('input', updateDurationEstimate);

// 3. UI Sliders & Manual Script Toggle
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

// 4. Firestore Realtime Feeds (Current Batch Feed & All Logs Feed)
function initRealtimeFeeds() {
    if (!window.db || !window.FirebaseUtils) {
        setTimeout(initRealtimeFeeds, 200);
        return;
    }

    const { collection, onSnapshot, query, limit } = window.FirebaseUtils;
    const currentContainer = document.getElementById('currentBatchLogsContainer');
    const allContainer = document.getElementById('allLogsContainer');
    const totalLogsBadge = document.getElementById('totalLogsCount');
    
    // Listen to executions collection
    const q = query(collection(window.db, 'executions'), limit(100));
    
    onSnapshot(q, (snapshot) => {
        const docs = [];
        snapshot.forEach(doc => docs.push({ id: doc.id, ...doc.data() }));
        
        // Sort by timestamp desc
        docs.sort((a, b) => {
            const timeA = a.createdAt?.toMillis ? a.createdAt.toMillis() : (a.updatedAt?.toMillis ? a.updatedAt.toMillis() : 0);
            const timeB = b.createdAt?.toMillis ? b.createdAt.toMillis() : (b.updatedAt?.toMillis ? b.updatedAt.toMillis() : 0);
            return timeB - timeA;
        });

        allExecutionsList = docs;
        if (totalLogsBadge) totalLogsBadge.innerText = docs.length;

        // Render All Execution Logs
        renderAllLogs(docs, allContainer);

        // Determine Active Batch ID for Studio Live Feed
        let activeBatchId = localStorage.getItem('epicsync_active_batch_id');
        if (!activeBatchId && docs.length > 0) {
            // Default to most recent batch
            activeBatchId = docs[0].batch_id || '';
            if (activeBatchId) localStorage.setItem('epicsync_active_batch_id', activeBatchId);
        }

        // Filter and Render Current Batch Feed
        const currentBatchDocs = activeBatchId ? docs.filter(d => d.batch_id === activeBatchId) : [];
        renderCurrentBatch(currentBatchDocs, currentContainer, activeBatchId);

    }, (error) => {
        console.error("Firestore feed listener error:", error);
    });
}

// Render Current Batch Live Feed
function renderCurrentBatch(docs, container, batchId) {
    if (!container) return;
    
    const subtitle = document.getElementById('currentBatchSubtitle');
    if (subtitle && batchId) {
        subtitle.innerText = `Showing Batch: ${batchId}`;
    }

    if (docs.length === 0) {
        container.innerHTML = '<div class="empty-state">No batch currently active. Launch a new batch above!</div>';
        return;
    }

    container.innerHTML = '';
    docs.forEach(data => {
        const card = createVideoCard(data, false);
        container.appendChild(card);
    });
}

// Render All Execution Logs
function renderAllLogs(docs, container) {
    if (!container) return;
    
    if (docs.length === 0) {
        container.innerHTML = '<div class="empty-state">No execution logs found.</div>';
        return;
    }

    container.innerHTML = '';
    docs.forEach(data => {
        const card = createVideoCard(data, true);
        container.appendChild(card);
    });
    
    updateSelectionBar();
}

// Create Card DOM Element
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

    // Card selection event in multi-select mode
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

    // Individual Push to YouTube handler
    const singleYtBtn = card.querySelector('.btn-yt-single');
    if (singleYtBtn) {
        singleYtBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pushSingleToYouTube(data);
        });
    }

    return card;
}

// 5. Multi-Select & Batch Actions
const toggleMultiSelectBtn = document.getElementById('toggleMultiSelectBtn');
const batchSelectionBar = document.getElementById('batchSelectionBar');
const selectedCountText = document.getElementById('selectedCountText');
const pushBatchYtBtn = document.getElementById('pushBatchYtBtn');
const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');

toggleMultiSelectBtn?.addEventListener('click', () => {
    multiSelectMode = !multiSelectMode;
    toggleMultiSelectBtn.classList.toggle('active', multiSelectMode);
    if (!multiSelectMode) {
        selectedJobs.clear();
    }
    renderAllLogs(allExecutionsList, document.getElementById('allLogsContainer'));
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
    renderAllLogs(allExecutionsList, document.getElementById('allLogsContainer'));
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

// 6. Push to YouTube Webhook Handler
function getWebhookUrl() {
    return localStorage.getItem('epicsync_yt_webhook') || '';
}

async function dispatchVideosToWebhook(videosList) {
    const webhookUrl = getWebhookUrl();
    
    if (!webhookUrl) {
        const input = prompt('Please enter your YouTube Dispatch Webhook URL:', 'https://');
        if (input && input.trim()) {
            localStorage.setItem('epicsync_yt_webhook', input.trim());
            return dispatchVideosToWebhook(videosList);
        } else {
            return;
        }
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
            alert(`Webhook returned status ${res.status}: ${await res.text()}`);
        }
    } catch (err) {
        console.error("Webhook push error:", err);
        // Fallback display if webhook is offline
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

// Delete Selected from Firestore
deleteSelectedBtn?.addEventListener('click', async () => {
    if (!confirm(`Are you sure you want to delete ${selectedJobs.size} selected execution(s)?`)) return;
    
    const { doc, deleteDoc, writeBatch } = window.FirebaseUtils;
    try {
        const batch = writeBatch(window.db);
        selectedJobs.forEach((_, jobId) => {
            batch.delete(doc(window.db, 'executions', jobId));
        });
        await batch.commit();
        selectedJobs.clear();
        alert('Selected logs deleted successfully.');
    } catch (e) {
        console.error("Error deleting selected logs:", e);
        alert('Failed to delete: ' + e.message);
    }
});

// Clear Current Feed Only
const clearCurrentFeedBtn = document.getElementById('clearCurrentFeedBtn');
if (clearCurrentFeedBtn) {
    clearCurrentFeedBtn.addEventListener('click', () => {
        localStorage.removeItem('epicsync_active_batch_id');
        document.getElementById('currentBatchLogsContainer').innerHTML = '<div class="empty-state">Current feed cleared. Launch a new batch above!</div>';
        const subtitle = document.getElementById('currentBatchSubtitle');
        if (subtitle) subtitle.innerText = 'Feed cleared.';
    });
}

// Clear All Execution Logs
const clearAllLogsBtn = document.getElementById('clearAllLogsBtn');
if (clearAllLogsBtn) {
    clearAllLogsBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to permanently clear ALL historical execution logs?')) return;
        
        const { collection, getDocs, writeBatch } = window.FirebaseUtils;
        try {
            const snap = await getDocs(collection(window.db, 'executions'));
            const batch = writeBatch(window.db);
            snap.forEach(d => batch.delete(d.ref));
            await batch.commit();
            selectedJobs.clear();
            localStorage.removeItem('epicsync_active_batch_id');
            alert('All logs cleared successfully.');
        } catch (e) {
            console.error("Error clearing all logs:", e);
            alert('Failed to clear logs: ' + e.message);
        }
    });
}

// 7. Webhook Modal Handlers
const webhookSettingsBtn = document.getElementById('webhookSettingsBtn');
const webhookModal = document.getElementById('webhookModal');
const webhookUrlInput = document.getElementById('webhookUrlInput');
const saveWebhookBtn = document.getElementById('saveWebhookBtn');
const closeWebhookBtn = document.getElementById('closeWebhookBtn');

webhookSettingsBtn?.addEventListener('click', () => {
    if (webhookUrlInput) webhookUrlInput.value = getWebhookUrl();
    if (webhookModal) webhookModal.style.display = 'flex';
});

closeWebhookBtn?.addEventListener('click', () => {
    if (webhookModal) webhookModal.style.display = 'none';
});

saveWebhookBtn?.addEventListener('click', () => {
    const val = webhookUrlInput?.value?.trim() || '';
    localStorage.setItem('epicsync_yt_webhook', val);
    alert('Webhook URL saved successfully!');
    if (webhookModal) webhookModal.style.display = 'none';
});

// 8. Form Submission (Launch Batch)
const createBatchForm = document.getElementById('createBatchForm');
const submitBatchBtn = document.getElementById('submitBatchBtn');

if (createBatchForm) {
    createBatchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const titlesRaw = document.getElementById('videoTitles').value.trim();
        if (!titlesRaw) return alert('Please enter at least one title.');
        
        const titles = titlesRaw.split('\n').map(t => t.trim()).filter(t => t.length > 0);
        if (titles.length === 0) return alert('Please enter valid titles.');
        
        const isManual = manualScriptToggle?.checked;
        const manualScript = document.getElementById('manualScriptText')?.value?.trim() || '';
        if (isManual && !manualScript) return alert('Please enter your manual script.');
        
        const durVal = document.getElementById('durationNumberInput').value || '45';
        const formattedDuration = `${durVal} ${currentUnit}`;
        
        const payload = {
            titles: titles,
            script: isManual ? manualScript : '',
            aspect_ratio: document.getElementById('aspectRatioSelect').value,
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
                // Save new active batch ID to lock the Current Batch Live Feed
                localStorage.setItem('epicsync_active_batch_id', data.batch_id);
                
                // Clear feed container and display loading state
                const currentContainer = document.getElementById('currentBatchLogsContainer');
                if (currentContainer) {
                    currentContainer.innerHTML = '<div class="empty-state">🚀 Batch queued! Kaggle CPU worker is initializing...</div>';
                }
                
                alert(`🚀 Successfully launched batch of ${titles.length} video(s)! Watching real-time progress below.`);
                document.getElementById('videoTitles').value = '';
                if (manualScriptArea) document.getElementById('manualScriptText').value = '';
            } else {
                alert(`Failed to launch batch: ${data.error || 'Unknown error'}`);
            }
        } catch (err) {
            console.error("Batch launch error:", err);
            alert(`Network error launching batch: ${err.message}`);
        } finally {
            submitBatchBtn.innerText = '🚀 Launch EpicSync Pexels Run';
            submitBatchBtn.disabled = false;
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initial calls
updateDurationEstimate();
initRealtimeFeeds();
