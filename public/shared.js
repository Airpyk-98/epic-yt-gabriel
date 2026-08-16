// EpicSync Shared Application Logic & Firebase Client

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

export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
