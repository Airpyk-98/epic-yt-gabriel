// EpicSync Public App Logic (No-Auth, Mobile-First)

// 1. UI Slider Listeners
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

// 2. Real-time Firestore Feed Listener
function initRealtimeFeed() {
    if (!window.db || !window.FirebaseUtils) {
        setTimeout(initRealtimeFeed, 200);
        return;
    }

    const { collection, onSnapshot, query, orderBy, limit } = window.FirebaseUtils;
    const container = document.getElementById('videoLogsContainer');
    
    // Listen to executions collection
    const q = query(collection(window.db, 'executions'), limit(30));
    
    onSnapshot(q, (snapshot) => {
        if (snapshot.empty) {
            container.innerHTML = '<div class="empty-state">No videos launched yet. Submit titles above to start!</div>';
            return;
        }

        // Sort by createdAt desc if available
        const docs = [];
        snapshot.forEach(doc => docs.push({ id: doc.id, ...doc.data() }));
        docs.sort((a, b) => {
            const timeA = a.createdAt?.toMillis ? a.createdAt.toMillis() : (a.updatedAt?.toMillis ? a.updatedAt.toMillis() : 0);
            const timeB = b.createdAt?.toMillis ? b.createdAt.toMillis() : (b.updatedAt?.toMillis ? b.updatedAt.toMillis() : 0);
            return timeB - timeA;
        });

        container.innerHTML = '';
        
        docs.forEach(data => {
            const status = data.status || 'QUEUED';
            const progress = data.progress !== undefined ? data.progress : (status === 'SUCCESS' ? 100 : 0);
            const stepText = data.step_text || 'Waiting for runner...';
            const outputUrl = data.output_file || '';
            
            const card = document.createElement('div');
            card.className = 'video-card';
            card.innerHTML = `
                <div class="video-card-top">
                    <span class="video-title">${escapeHtml(data.title || 'Untitled Video')}</span>
                    <span class="status-badge badge-${status}">${status}</span>
                </div>
                
                <div class="progress-bar-wrap">
                    <div class="progress-bar-fill" style="width: ${progress}%;"></div>
                </div>
                
                <div class="step-text">${escapeHtml(stepText)} (${progress}%)</div>
                
                ${outputUrl ? `
                    <div class="player-container">
                        <video src="${outputUrl}" controls playsinline preload="metadata"></video>
                        <a href="${outputUrl}" target="_blank" download class="btn-download">⬇️ Download MP4</a>
                    </div>
                ` : ''}
            `;
            container.appendChild(card);
        });
    }, (error) => {
        console.error("Firestore feed listener error:", error);
    });
}

// 3. Form Submission Handler
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
        
        const payload = {
            titles: titles,
            script: isManual ? manualScript : '',
            aspect_ratio: document.getElementById('aspectRatioSelect').value,
            target_duration: document.getElementById('targetDurationSelect').value,
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
                alert(`🚀 Successfully launched batch of ${titles.length} video(s)! Watch real-time progress below.`);
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

// 4. Clear Logs Button Handler
const clearLogsBtn = document.getElementById('clearLogsBtn');
if (clearLogsBtn) {
    clearLogsBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to clear all video logs?')) return;
        
        const { collection, getDocs, writeBatch } = window.FirebaseUtils;
        try {
            const snap = await getDocs(collection(window.db, 'executions'));
            const batch = writeBatch(window.db);
            snap.forEach(doc => batch.delete(doc.ref));
            await batch.commit();
            document.getElementById('videoLogsContainer').innerHTML = '<div class="empty-state">Logs cleared successfully.</div>';
        } catch (e) {
            console.error("Error clearing logs:", e);
            alert('Failed to clear logs: ' + e.message);
        }
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on page load
initRealtimeFeed();
