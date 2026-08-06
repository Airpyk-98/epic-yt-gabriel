import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, setDoc, getDoc, collection, getDocs, onSnapshot, addDoc, serverTimestamp, query, orderBy } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

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
        if (err.code === 'auth/user-not-found' || err.code === 'auth/invalid-credential') {
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
const scriptGenForm = document.getElementById('scriptGenForm');
const genScriptBtn = document.getElementById('genScriptBtn');
const scriptResultArea = document.getElementById('scriptResultArea');
const generatedScriptText = document.getElementById('generatedScriptText');
const submitVideoBtn = document.getElementById('submitVideoBtn');

scriptGenForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentProject) return alert('Select a project first!');
    
    const titles = document.getElementById('videoTitles').value.trim();
    genScriptBtn.innerText = 'Generating...';
    genScriptBtn.disabled = true;
    
    // Get current user token for auth
    const token = await currentUser.getIdToken();
    
    try {
        const res = await fetch(`${BACKEND_URL}/api/generate-script`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ titles: titles })
        });
        
        const data = await res.json();
        if (res.ok) {
            generatedScriptText.value = data.script;
            scriptResultArea.style.display = 'block';
            checkVideoSubmitState();
        } else {
            alert('Error generating script: ' + data.detail);
        }
    } catch (err) {
        console.error(err);
        alert('Failed to connect to backend for script generation.');
    } finally {
        genScriptBtn.innerText = '✨ Generate Script';
        genScriptBtn.disabled = false;
    }
});

function checkVideoSubmitState() {
    const hasScript = generatedScriptText.value.trim().length > 0;
    const imageInput = document.getElementById('imageInput');
    const hasImage = imageInput && imageInput.files.length > 0;
    submitVideoBtn.disabled = !(hasScript && hasImage);
}

generatedScriptText.addEventListener('input', checkVideoSubmitState);
document.getElementById('imageInput').addEventListener('change', checkVideoSubmitState);

function loadLogs() {
    if (!currentProject) return;
    const logsContainer = document.getElementById('executionLogsList');
    logsContainer.innerHTML = '<div class="empty-state">Loading logs...</div>';
    
    if (unsubscribeLogs) { unsubscribeLogs(); }
    const q = query(collection(db, 'users', currentUser.uid, 'projects', currentProject, 'executions'), orderBy('createdAt', 'desc'));
    unsubscribeLogs = onSnapshot(q, (snapshot) => {
        logsContainer.innerHTML = '';
        if (snapshot.empty) {
            logsContainer.innerHTML = '<div class="empty-state">No videos generated yet in this project.</div>';
            return;
        }
        snapshot.forEach(docSnap => {
            const data = docSnap.data();
            const div = document.createElement('div');
            div.className = 'log-card';
            div.innerHTML = `
                <h4>${data.title || 'Untitled Video'}</h4>
                <p class="text-sm mt-2 text-muted">Status: ${data.status}</p>
                ${data.videoUrl ? `
                <div style="margin-top: 10px; display: flex; gap: 8px;">
                    <a href="${data.videoUrl}" target="_blank" class="btn-primary">Download / View</a>
                    <button class="btn-secondary" onclick="alert('Export to Google Drive coming soon!')">☁️ GDrive</button>
                    <button class="btn-secondary" onclick="alert('Export to Dropbox coming soon!')">☁️ Dropbox</button>
                </div>
                ` : ''}
            `;
            logsContainer.appendChild(div);
        });
    });
}

const videoGenForm = document.getElementById('videoGenForm');
videoGenForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentProject) return alert('Select a project first!');
    
    const mediaFile = document.getElementById('mediaFile').files[0];
    const voiceModel = document.getElementById('voiceModelSelect').value;
    const scriptText = document.getElementById('generatedScriptText').value;
    
    if (!mediaFile || !scriptText) return alert("Missing image or script");

    submitVideoBtn.innerText = 'Uploading & Launching...';
    submitVideoBtn.disabled = true;
    
    const token = await currentUser.getIdToken();
    const formData = new FormData();
    formData.append('script_text', scriptText);
    formData.append('voice', voiceModel);
    formData.append('image', mediaFile); // For premium
    formData.append('video', mediaFile); // For standard
    formData.append('projectId', currentProject);
    // You can also append other settings like add_captions etc if added to UI
    
    try {
        const res = await fetch(`${BACKEND_URL}/api/run_premium`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const data = await res.json();
        if (res.ok) {
            alert('Job started! Check Execution Logs.');
            // Save execution stub to Firestore
            await setDoc(doc(db, 'users', currentUser.uid, 'projects', currentProject, 'executions', data.job_id), {
                title: scriptText.substring(0, 30) + '...',
                status: 'STAGING',
                job_id: data.job_id,
                createdAt: serverTimestamp()
            });
            document.querySelector('[data-target="view-logs"]').click();
        } else {
            alert('Error starting job: ' + (data.detail || 'Unknown error'));
        }
    } catch (err) {
        console.error(err);
        alert('Failed to connect to backend for video generation.');
    } finally {
        submitVideoBtn.innerText = '🚀 Launch EpicSync GPU';
        submitVideoBtn.disabled = false;
    }
});
