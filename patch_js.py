import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# I want to replace the whole createContentForm.addEventListener('submit', async (e) => { ... }); block
# The block starts at createContentForm.addEventListener('submit', async (e) => {
# and ends right before unction loadLogs() {

start_str = "createContentForm.addEventListener('submit', async (e) => {"
end_str = "function loadLogs() {"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx == -1 or end_idx == -1:
    print("Could not find the submit block.")
    exit(1)

new_logic = '''// Helper to wait for a job to complete by listening to Firestore
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
    
    const titles = videoTitlesInput.value.split('\\n').filter(line => line.trim().length > 0);
    if (titles.length === 0) return alert('Please enter at least one title.');
    
    const isPreviewOn = previewScriptToggle.checked && titles.length === 1;
    const mediaFile = mediaFileInput.files[0];
    const voiceModel = document.getElementById('voiceModelSelect').value;
    
    if (!mediaFile) return alert('Missing source image.');
    
    submitContentBtn.innerText = 'Processing Queue...';
    submitContentBtn.disabled = true;
    
    // Setup UI Queue
    const queueContainer = document.getElementById('bulkQueueContainer');
    const queueList = document.getElementById('bulkQueueList');
    queueContainer.style.display = 'block';
    queueList.innerHTML = '';
    
    const queueElements = [];
    titles.forEach((t, i) => {
        const el = document.createElement('div');
        el.className = 'log-card';
        el.innerHTML = 
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong>. </strong>
                <span id="queue-status-" style="color:#e5b300;">Pending</span>
            </div>
        ;
        queueList.appendChild(el);
        queueElements.push(document.getElementById(queue-status-));
    });

    const token = await currentUser.getIdToken();
    
    for (let i = 0; i < titles.length; i++) {
        const title = titles[i];
        const statusEl = queueElements[i];
        
        // 1. Generate Script
        let scriptText = '';
        try {
            statusEl.innerText = 'Generating Script...';
            const res = await fetch(${BACKEND_URL}/api/generate-script, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': Bearer 
                },
                body: JSON.stringify({ titles: title })
            });
            const data = await res.json();
            if (res.ok) {
                scriptText = data.script;
            } else {
                statusEl.innerText = Failed: ;
                statusEl.style.color = '#ff4444';
                continue;
            }
        } catch (err) {
            console.error(err);
            statusEl.innerText = 'Failed: Network Error';
            statusEl.style.color = '#ff4444';
            continue;
        }

        // 2. Handle Preview Mode vs Automatic Mode
        if (isPreviewOn) {
            statusEl.innerText = 'Waiting for User Approval...';
            generatedScriptText.value = scriptText;
            scriptResultArea.style.display = 'block';
            checkVideoSubmitState();
            submitContentBtn.innerText = 'Confirm to Launch';
            submitContentBtn.disabled = false;
            
            // Wait for user to click "Continue to Video"
            await new Promise(resolve => {
                const handler = () => {
                    continueVideoBtn.removeEventListener('click', handler);
                    resolve();
                };
                continueVideoBtn.addEventListener('click', handler);
            });
            scriptText = generatedScriptText.value.trim();
            scriptResultArea.style.display = 'none';
            submitContentBtn.innerText = 'Processing Queue...';
            submitContentBtn.disabled = true;
        }
        
        // 3. Launch Video Generation
        try {
            statusEl.innerText = 'Staging GPU...';
            const formData = new FormData();
            formData.append('script_text', scriptText);
            formData.append('voice', voiceModel);
            formData.append('image', mediaFile);
            formData.append('video', mediaFile);
            formData.append('projectId', currentProject);
            
            const res = await fetch(${BACKEND_URL}/api/run_premium, {
                method: 'POST',
                headers: { 'Authorization': Bearer  },
                body: formData
            });
            
            const data = await res.json();
            if (res.ok) {
                await setDoc(doc(db, 'users', currentUser.uid, 'projects', currentProject, 'executions', data.job_id), {
                    title: title.substring(0, 30) + '...',
                    status: 'STAGING',
                    job_id: data.job_id,
                    createdAt: serverTimestamp()
                });
                statusEl.innerText = 'STAGING';
                
                // 4. Wait for Job Completion Sequentially
                const finalStatus = await waitForJobCompletion(currentUser.uid, currentProject, data.job_id, statusEl);
                if (finalStatus === 'FAILED') {
                    statusEl.style.color = '#ff4444';
                } else {
                    statusEl.style.color = '#4caf50';
                }
            } else {
                statusEl.innerText = Launch Error: ;
                statusEl.style.color = '#ff4444';
            }
        } catch (err) {
            console.error(err);
            statusEl.innerText = 'Launch Failed';
            statusEl.style.color = '#ff4444';
        }
    }
    
    alert('Queue processing finished! Check Execution Logs.');
    document.querySelector('[data-target="view-logs"]').click();
    
    submitContentBtn.innerText = '🚀 Launch EpicSync GPU';
    submitContentBtn.disabled = false;
});

'''

content = content[:start_idx] + new_logic + content[end_idx:]

with open('static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("done")
