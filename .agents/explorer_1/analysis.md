# EpicSync Studio V2 — End-to-End QA & Feature Audit Report

**Target URL**: https://epic-yt-gab.web.app  
**Backend URL**: https://epic-yt-gabriel.onrender.com  
**Audit Date**: August 6, 2026  
**Auditor**: Explorer Subagent (`explorer_1`)  
**Test Account Used**: `gabrielyoutubeautomation@gmail.com`  

---

## Executive Summary

An End-to-End Functional, Code, and UX Audit was performed on the live web application **EpicSync Studio V2** (`https://epic-yt-gab.web.app`).

### Overall Status: **CRITICAL BUG BLOCKERS DETECTED**
While the application displays a modern UI structure and successfully authenticates users via Firebase Auth (credentials `gabrielyoutubeautomation@gmail.com` / `Airpyk98`), **critical code bugs currently render core features (YouTube connection, script generation, video rendering, and execution log viewing) non-functional**.

---

## 1. Confirmed Bugs & Critical Code Defects

### Bug #1: Connect YouTube Button Throws Uncaught Exception & Crashes Flow
- **Severity**: **CRITICAL**
- **Affected File**: `static/app.js` (lines 257–270) & `static/index.html`
- **Verbatim Error**: `[UNCAUGHT EXCEPTION] TypeError: Cannot read properties of null (reading 'value')`
- **Step-by-step Reproduction**:
  1. Log in to EpicSync Studio.
  2. Open Navigation Drawer and click **Projects**.
  3. Click **▶️ Connect YouTube** on any project card.
- **Expected Behavior**: The application reads YouTube client credentials from Settings or redirects the user to the YouTube OAuth consent page.
- **Actual Behavior**: `app.js` executes `document.getElementById('ytClientId').value.trim()`. Because `id="ytClientId"` and `id="ytClientSecret"` DO NOT EXIST anywhere in `index.html`, `document.getElementById` returns `null`, throwing an uncaught JS exception. The connection flow halts completely.

---

### Bug #2: FastAPI Route Mounting Order Causes `405 Method Not Allowed` on Script Generation
- **Severity**: **CRITICAL**
- **Affected File**: `main.py` (lines 1625 & 1630)
- **Verbatim Response**: `HTTP 405 Method Not Allowed` | Alert: `Error generating script: Method Not Allowed`
- **Step-by-step Reproduction**:
  1. Log in and select/create a project.
  2. Navigate to **Studio** view.
  3. Enter a title under **1. Generate Script** and click **✨ Generate Script**.
- **Expected Behavior**: The backend API (`POST /api/generate-script`) processes the title with the configured OpenAI/Groq API and returns a generated script.
- **Actual Behavior**: The server returns `405 Method Not Allowed`.
- **Root Cause Analysis**:
  In `main.py`:
  - Line 1625: `app.mount("/", StaticFiles(directory="static", html=True), name="static")`
  - Line 1630: `@app.post("/api/generate-script")`
  Because `app.mount("/", ...)` was mounted BEFORE `@app.post("/api/generate-script")` and OAuth routes, Starlette's `StaticFiles` middleware intercepts all incoming HTTP requests starting with `/`. For POST requests, `StaticFiles` returns `405 Method Not Allowed`.

---

### Bug #3: Video Generation Submit Button Permanently Disabled
- **Severity**: **CRITICAL**
- **Affected File**: `static/index.html` (line 121) & `static/app.js` (line 304)
- **Step-by-step Reproduction**:
  1. Navigate to **Studio**.
  2. Select/upload a portrait image file.
  3. Observe the **🚀 Launch EpicSync GPU** submit button.
- **Expected Behavior**: Once a portrait image is uploaded and script text is available, the button becomes active so users can render videos.
- **Actual Behavior**: The button is hardcoded with `disabled` in HTML. In `app.js`, `submitVideoBtn.disabled = false` is ONLY executed inside the `if (res.ok)` block of script generation. Because script generation fails with Bug #2, the launch button remains permanently disabled. Users cannot launch video generation.

---

### Bug #4: Execution Logs DOM Append Missing (`logsContainer.appendChild`)
- **Severity**: **HIGH**
- **Affected File**: `static/app.js` (lines 322–340)
- **Step-by-step Reproduction**:
  1. Create execution records in Firestore under `users/{uid}/projects/{projId}/executions`.
  2. Open Navigation Drawer and click **Execution Logs**.
- **Expected Behavior**: Execution log cards render dynamically in the UI.
- **Actual Behavior**: In `app.js` `loadLogs()`, log cards are created (`document.createElement('div')`) and populated with HTML, but `logsContainer.appendChild(div)` was omitted. The DOM container remains perpetually showing `<div class="empty-state">No videos generated yet in this project.</div>`.

---

### Bug #5: Invalid Credential Misinterpretation in Hybrid Auth Handler
- **Severity**: **MEDIUM**
- **Affected File**: `static/app.js` (lines 67–78)
- **Step-by-step Reproduction**:
  1. Open the login overlay.
  2. Enter an existing user's email (`gabrielyoutubeautomation@gmail.com`) with an incorrect password.
  3. Click **Sign In / Register**.
- **Expected Behavior**: UI displays "Invalid email or password".
- **Actual Behavior**: `signInWithEmailAndPassword` fails with code `auth/invalid-credential`. The frontend catches `auth/invalid-credential` and misinterprets it as "user does not exist", attempting `createUserWithEmailAndPassword`. This throws `auth/email-already-in-use`, displaying `Firebase: Error (auth/email-already-in-use).` to the user.

---

### Bug #6: Unhandled Firestore Snapshot Listeners on Logout
- **Severity**: **LOW**
- **Affected File**: `static/app.js` (`onSnapshot` listeners)
- **Verbatim Error**: `Firestore (10.12.2): Uncaught Error in snapshot listener: FirebaseError: [code=permission-denied]`
- **Observation**: When a user logs out, active Firestore snapshot subscriptions (`loadProjects()`, `loadLogs()`) are not unsubscribed, causing permission errors when `auth.currentUser` becomes null.

---

## 2. UX & Interface Flaws

1. **Desktop Drawer Backdrop Pointer Interception**:
   - In desktop viewports (>768px width), opening the drawer keeps a full-screen semi-transparent backdrop (`.drawer-backdrop`). Switching views does not automatically close the backdrop, causing subsequent clicks on header buttons to be intercepted by `#closeDrawerBtn` or backdrop elements.
2. **Missing Manual Script Input Option**:
   - Users cannot paste an existing script into the Studio without first invoking the automated generator.
3. **No Loading Spinners or Visual Async Feedback**:
   - Long async calls (e.g. saving settings, fetching models) lack spinner animations or status feedback cards.
4. **YouTube Settings Missing in Settings View**:
   - No inputs exist in Settings for `ytClientId` or `ytClientSecret`, despite being referenced in `app.js`.

---

## 3. Crucial Missing Features for Production YouTube Automation SaaS

To transform EpicSync into a commercial-grade YouTube Automation SaaS, the following feature modules must be built:

| Feature Area | Description & Requirements | Priority |
|---|---|---|
| **YouTube Channel Management** | Add UI settings for YouTube OAuth credentials, channel selector per project, multiple channel support, and token status indicators. | **P0 (Blocker)** |
| **Video Scheduling & Queue** | Content calendar, scheduled publishing (date/time picker), publishing queue, and privacy settings (Public / Unlisted / Private). | **P0 (Blocker)** |
| **Thumbnail Generator Engine** | AI image prompt generation for thumbnails, custom text overlay editor, and template selector. | **P1 (High)** |
| **Expanded Voice TTS Library** | Integration with ElevenLabs, OpenAI TTS, audio preview player, pitch/speed controls, and multilingual voice selection. | **P1 (High)** |
| **Analytics Dashboard** | Views, watch time, CTR, subscriber growth analytics, and video performance metrics breakdown. | **P1 (High)** |
| **Prompt Template Library** | Niche-specific prompt templates (True Crime, Finance, Tech, Motivational, Horror), script length toggle (Shorts vs Long-form), and language selector. | **P2 (Medium)** |
| **Export & Cloud Integration** | Direct sync/export to Google Drive, Dropbox, bulk ZIP download, and webhook notifications. | **P2 (Medium)** |

---

## 4. Summary Matrix of Findings

| ID | Category | Component | Status | Impact |
|---|---|---|---|---|
| BUG-01 | Code Defect | YouTube OAuth (`app.js`) | Confirmed | Connect YT crashes app |
| BUG-02 | Code Defect | Script Gen API (`main.py`) | Confirmed | HTTP 405 Method Not Allowed |
| BUG-03 | Code Defect | Studio Submit (`index.html`/`app.js`) | Confirmed | Submit button permanently disabled |
| BUG-04 | Code Defect | Execution Logs (`app.js`) | Confirmed | Logs never render in UI |
| BUG-05 | Code Defect | Hybrid Auth (`app.js`) | Confirmed | Misleading error message on bad pass |
| BUG-06 | Code Defect | Firestore Listeners (`app.js`) | Confirmed | Uncaught permission error on logout |
| UX-01 | UX Flaw | Drawer Navigation | Confirmed | Backdrop intercepts desktop clicks |
| FEAT-01 | Missing Feature | YouTube Credentials UI | Missing | Required for OAuth flow |
| FEAT-02 | Missing Feature | Video Scheduling Engine | Missing | Required for SaaS automation |
| FEAT-03 | Missing Feature | AI Thumbnail Generator | Missing | Critical for YouTube CTR |
