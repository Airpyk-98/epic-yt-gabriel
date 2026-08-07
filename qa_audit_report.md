# EpicSync Studio V2 — Comprehensive QA & Feature Audit Report

**Target Frontend Application**: [https://epic-yt-gab.web.app](https://epic-yt-gab.web.app)  
**Target Backend API**: [https://epic-yt-gabriel.onrender.com](https://epic-yt-gabriel.onrender.com)  
**Audit Date**: August 6, 2026  
**Auditor**: Worker Subagent (`worker_1`) / QA & Feature Audit Specialist  
**Test Account Used**: `gabrielyoutubeautomation@gmail.com`  
**Authentication Credential Verified**: `Airpyk98` / `GabrielNjoku`  

---

## Executive Summary

An End-to-End (E2E) Functional, Technical Code, and User Experience (UX) Audit was performed on **EpicSync Studio V2** (`https://epic-yt-gab.web.app`), a web application designed for automated YouTube video creation and channel publishing powered by cloud GPU infrastructure.

### Overall Status & Audit Verdict: **CRITICAL BUG BLOCKERS DETECTED**

While the application features a modern UI design, structured Firebase Auth integration, and cloud backend architecture, **critical code defects in both backend routing and frontend logic currently block all core workflows** (YouTube channel authorization, AI script generation, GPU video creation launch, and execution log viewing).

- **Authentication**: **VERIFIED PASS** — The account `gabrielyoutubeautomation@gmail.com` successfully logs in via Firebase Authentication.
- **Core Workflows**: **FAILED** — Script generation fails with `HTTP 405 Method Not Allowed`, video creation button is permanently disabled, YouTube OAuth connection throws a JS uncaught exception, and execution logs fail to append to the DOM.
- **SaaS Readiness**: **INCOMPLETE** — Missing critical commercial SaaS features such as YouTube token management UI, automated scheduling engines, thumbnail generation, expanded voice controls, and performance analytics.

---

## Testing & Coverage Verification

Testing verified user interaction across **7 distinct interactive UI elements and routes**:

| # | Interactive Element / UI Route | Interaction Performed | Result / Findings |
|---|---|---|---|
| 1 | **Auth Overlay (`#authOverlay`)** | Submitted email (`gabrielyoutubeautomation@gmail.com`) and password (`Airpyk98`). Tested invalid credentials response. | **PASS (Auth Valid)** / **BUG #5** detected on invalid pass error handling. |
| 2 | **Projects Drawer (`#drawer`)** | Toggled drawer from header, created new project, selected project, verified project badge (`#activeProjectBadge`). | **PASS (Navigation)** / **UX #1** backdrop pointer interception detected. |
| 3 | **Studio Tab (`view-studio`)** | Entered video topic/title under Step 1, clicked `✨ Generate Script` button. | **FAIL** / **BUG #2** (`HTTP 405 Method Not Allowed` API error). |
| 4 | **Launch GPU Form (`#videoGenForm`)** | Uploaded portrait input image, attempted to trigger video rendering via `#submitVideoBtn`. | **FAIL** / **BUG #3** (`#submitVideoBtn` button permanently disabled). |
| 5 | **Execution Logs (`view-logs`)** | Selected active project, navigated to Execution Logs tab to view historic generation records. | **FAIL** / **BUG #4** (`logsContainer.appendChild` missing; DOM stays empty). |
| 6 | **Settings Panel (`view-settings`)** | Checked input fields for OpenAI API Key, Groq API Key, HuggingFace Token, RunPod API Key. | **PASS (Inputs Exist)** / **UX #4** missing YouTube OAuth input fields. |
| 7 | **Connect YouTube Button** | Clicked `▶️ Connect YouTube` on active project card to trigger YouTube OAuth flow. | **FAIL** / **BUG #1** (`TypeError: Cannot read properties of null`). |

---

## Confirmed Code Defects & Bugs

### Bug #1: `window.connectYouTube` Uncaught Exception & Crash
- **Severity**: **CRITICAL** (Prevents YouTube Account Authorization)
- **Affected Files**: `static/app.js` (lines 257–270) & `static/index.html`
- **Verbatim Console Output**:  
  `[UNCAUGHT EXCEPTION] TypeError: Cannot read properties of null (reading 'value')`
- **Step-by-Step Reproduction**:
  1. Open [https://epic-yt-gab.web.app](https://epic-yt-gab.web.app) and sign in.
  2. Open Navigation Drawer and click **Projects**.
  3. Click **▶️ Connect YouTube** on any project card.
- **Expected Behavior**: The application retrieves the saved `ytClientId` and `ytClientSecret` from Settings or redirects the user to the FastAPI backend endpoint `/api/auth/youtube?uid={uid}` for Google OAuth consent.
- **Actual Behavior**: The JavaScript execution crashes when attempting `document.getElementById('ytClientId').value.trim()`.
- **Root Cause Analysis**:
  In `static/app.js` (lines 259–260):
  ```javascript
  const ytId = document.getElementById('ytClientId').value.trim();
  const ytSec = document.getElementById('ytClientSecret').value.trim();
  ```
  `index.html` does NOT contain input elements with `id="ytClientId"` or `id="ytClientSecret"`. `document.getElementById` returns `null`, causing an unhandled JS exception on `.value`.
- **Remediation**:
  Add `ytClientId` and `ytClientSecret` input fields to the Settings tab in `index.html`, or update `connectYouTube()` to read client credentials from backend configuration / project settings safely.

---

### Bug #2: FastAPI Route Mounting Order Causes `HTTP 405 Method Not Allowed` on Script Generation
- **Severity**: **CRITICAL** (Blocks AI Script Generation API)
- **Affected File**: `main.py` (lines 1625 & 1630)
- **Verbatim Server Response**: `HTTP 405 Method Not Allowed`  
- **User-Facing Alert**: `Error generating script: Method Not Allowed`
- **Step-by-Step Reproduction**:
  1. Navigate to **Studio** view in EpicSync.
  2. Type a topic/title in the **1. Generate Script** input field.
  3. Click **✨ Generate Script**.
- **Expected Behavior**: The client sends a POST request to `/api/generate-script`, the backend invokes LLM APIs (OpenAI/Groq), and populates the generated script text area.
- **Actual Behavior**: The API server responds with status code `405 Method Not Allowed`.
- **Root Cause Analysis**:
  In `main.py`:
  - Line 1625: `app.mount("/", StaticFiles(directory="static", html=True), name="static")`
  - Line 1630: `@app.post("/api/generate-script")`
  FastAPI and Starlette evaluate routes and mounted applications in strict top-down declaration order. Mounting `StaticFiles` at root `/` *before* declaring `@app.post("/api/generate-script")` causes Starlette's `StaticFiles` handler to intercept all incoming requests matching `/api/generate-script`. Because static files middleware only supports `GET` and `HEAD` requests, it rejects `POST` requests with `405 Method Not Allowed`.
- **Remediation**:
  Move `app.mount("/", ...)` to the very end of `main.py`, below all API route definitions (`/api/generate-script`, `/api/generate-video`, OAuth routes).

---

### Bug #3: Video Launch GPU Submit Button Permanently Disabled
- **Severity**: **CRITICAL** (Prevents Video Generation Triggering)
- **Affected Files**: `static/index.html` (line 121) & `static/app.js` (lines 304, 342)
- **Step-by-Step Reproduction**:
  1. Open **Studio** view.
  2. Select and upload a portrait input image.
  3. Observe the **🚀 Launch EpicSync GPU** button state.
- **Expected Behavior**: Uploading a valid portrait image and providing a script enables the submit button so the user can initiate video generation.
- **Actual Behavior**: The submit button remains permanently disabled (`disabled` attribute stays active).
- **Root Cause Analysis**:
  In `static/index.html` line 121:
  ```html
  <button type="submit" class="btn-accent" id="submitVideoBtn" disabled>🚀 Launch EpicSync GPU</button>
  ```
  In `static/app.js` line 304:
  `submitVideoBtn.disabled = false;` is located inside the successful response block (`if (res.ok)`) of script generation. Because script generation fails with Bug #2 (`405 Method Not Allowed`), the code enabling `submitVideoBtn` is never reached. Furthermore, there is no event listener on image file upload or script text changes to re-evaluate button state.
- **Remediation**:
  Add an input event listener on `generatedScriptText` and `imageInput` to dynamically toggle `submitVideoBtn.disabled = !(scriptText && imageUploaded)`.

---

### Bug #4: Execution Logs DOM Append Omitted (`logsContainer.appendChild`)
- **Severity**: **HIGH** (Renders Execution Logs UI Ineffective)
- **Affected File**: `static/app.js` (lines 317–340)
- **Step-by-Step Reproduction**:
  1. Create or trigger video execution records in Firestore under `users/{uid}/projects/{projId}/executions`.
  2. Open Navigation Drawer and select **Execution Logs**.
- **Expected Behavior**: Cards representing execution status and downloadable output videos render dynamically inside `#executionLogsList`.
- **Actual Behavior**: The log list remains permanently displaying `<div class="empty-state">No videos generated yet in this project.</div>`.
- **Root Cause Analysis**:
  In `static/app.js` `loadLogs()` (lines 329–338):
  ```javascript
  snapshot.forEach(docSnap => {
      const data = docSnap.data();
      const div = document.createElement('div');
      div.className = 'log-card';
      div.innerHTML = `
          <h4>${data.title || 'Untitled Video'}</h4>
          <p class="text-sm mt-2 text-muted">Status: ${data.status}</p>
          ${data.videoUrl ? `<a href="${data.videoUrl}" target="_blank" class="btn-primary" style="display:inline-block; margin-top:10px;">Download / View</a>` : ''}
      `;
      // CRITICAL OMISSION: logsContainer.appendChild(div) IS MISSING!
  });
  ```
  The code constructs each `div` element in memory but fails to append it to `logsContainer`. The constructed DOM nodes are discarded when the loop finishes.
- **Remediation**:
  Add `logsContainer.appendChild(div);` inside the `snapshot.forEach` loop.

---

### Bug #5: Hybrid Auth Error Handler Misinterprets Invalid Credentials Error
- **Severity**: **MEDIUM** (Misleading User Feedback on Failed Sign-In)
- **Affected File**: `static/app.js` (lines 67–78)
- **Step-by-Step Reproduction**:
  1. Open Auth Overlay on [https://epic-yt-gab.web.app](https://epic-yt-gab.web.app).
  2. Enter an existing registered email (`gabrielyoutubeautomation@gmail.com`) with an intentional wrong password.
  3. Click **Sign In / Register**.
- **Expected Behavior**: UI notifies the user: `"Invalid email or password."`
- **Actual Behavior**: UI displays `"Firebase: Error (auth/email-already-in-use)."`
- **Root Cause Analysis**:
  In `static/app.js`:
  ```javascript
  try {
      await signInWithEmailAndPassword(auth, email, pass);
  } catch (err) {
      if (err.code === 'auth/user-not-found' || err.code === 'auth/invalid-credential') {
          // Misinterpretation: invalid-credential triggers registration attempt!
          await createUserWithEmailAndPassword(auth, email, pass);
      }
  }
  ```
  Firebase v10+ uses `auth/invalid-credential` for both wrong password and wrong email scenarios. Catching `auth/invalid-credential` and falling back to `createUserWithEmailAndPassword` causes Firebase to reject registration because the email already exists, returning `auth/email-already-in-use`.
- **Remediation**:
  Separate explicit Sign In and Register actions/buttons instead of relying on ambiguous hybrid fallback logic.

---

### Bug #6: Unhandled Firestore Snapshot Listeners Throw Permission Error on Logout
- **Severity**: **LOW** (Console Error on User Session Teardown)
- **Affected File**: `static/app.js` (lines 150-180, 323)
- **Verbatim Console Output**:  
  `Firestore (10.12.2): Uncaught Error in snapshot listener: FirebaseError: [code=permission-denied]`
- **Step-by-Step Reproduction**:
  1. Log in to EpicSync and view projects or logs.
  2. Click **Sign Out** in the navigation header.
- **Expected Behavior**: All active Firestore `onSnapshot` listeners are unsubscribed prior to resetting `auth.currentUser`.
- **Actual Behavior**: The browser console logs an uncaught `permission-denied` exception.
- **Root Cause Analysis**:
  `onSnapshot` listeners created in `loadProjects()` and `loadLogs()` do not store their unsubscribe callback functions. When `signOut(auth)` triggers, `auth.currentUser` becomes `null`. Firestore security rules evaluate incoming snapshot queries as unauthenticated, causing active listeners to trigger error callbacks.
- **Remediation**:
  Store unsubscribe references (`let unsubscribeProjects = null;`) and invoke `unsubscribeProjects()` prior to signing out or switching users.

---

## UX Flaws & Interface Defects

| # | UX Issue | Description | Impact | Recommended Design Fix |
|---|---|---|---|---|
| 1 | **Desktop Drawer Backdrop Pointer Interception** | Opening the navigation drawer on desktop screens (>768px) displays a full-screen backdrop (`.drawer-backdrop`). Navigating views does not dismiss the backdrop, capturing user clicks and blocking top navigation bar access. | High | Hide backdrop overlay on desktop (`@media (min-width: 769px) { .drawer-backdrop { display: none !important; } }`) or auto-dismiss on view change. |
| 2 | **Missing Manual Script Input** | Users cannot type or paste a custom pre-written script directly into the Studio tab without invoking the AI generator. | Medium | Remove `readonly` attribute from script text area or provide a "Paste Custom Script" toggle button. |
| 3 | **Missing Async Loading Spinners** | Asynchronous operations (saving API keys, fetching backend models, authenticating) lack visual progress indicators or loading overlays. | Medium | Add loading spinner state to primary buttons (`btn-accent`, `btn-primary`) during active API calls. |
| 4 | **Missing YouTube Credentials in Settings UI** | Settings panel includes fields for OpenAI, Groq, RunPod, and HuggingFace, but lacks fields for YouTube Client ID and Client Secret needed by `app.js`. | Medium | Add dedicated "YouTube API Setup" input card inside Settings with `ytClientId` and `ytClientSecret` fields. |

---

## Prioritized Missing Features for Production SaaS

To evolve EpicSync Studio into a commercially viable, production-grade YouTube Automation SaaS, the following features are strictly required:

| ID | Feature Module | Functional Description & Technical Requirements | Priority |
|---|---|---|---|
| **FEAT-01** | **YouTube Channel OAuth UI & Channel Management** | Dedicated YouTube settings panel supporting multiple connected Google/YouTube accounts, OAuth refresh token management, token status indicators (Active/Expired), and active channel selector per project. | **P0 (Blocker)** |
| **FEAT-02** | **Video Scheduling & Queue Engine** | Content calendar interface, automated release scheduling (Date/Time picker), automated cron worker for auto-publishing rendered videos to YouTube API, and privacy setting selectors (Public, Unlisted, Private). | **P0 (Blocker)** |
| **FEAT-03** | **AI Thumbnail Generator Engine** | Automated thumbnail prompt generator based on script context, canvas-based text overlay editor (custom fonts, stroke, shadow), and high-CTR thumbnail template library. | **P1 (High)** |
| **FEAT-04** | **Expanded TTS Voice & Audio Library** | Integration with ElevenLabs API, OpenAI Audio/TTS API, voice preview player, speech rate/pitch sliders, background music mixer, and multi-language voice selection. | **P1 (High)** |
| **FEAT-05** | **Channel & Video Analytics Dashboard** | Integration with YouTube Analytics API to display subscriber growth, view counts, watch time hours, average view duration (AVD), and click-through rates (CTR) directly inside EpicSync. | **P1 (High)** |
| **FEAT-06** | **Prompt & Script Template Library** | Niche-specific prompt presets (True Crime, Dark History, Finance/Crypto, Motivational, Sci-Fi), video length selector (YouTube Shorts <60s vs Long-form 8-15 mins), and custom system prompt overrides. | **P2 (Medium)** |
| **FEAT-07** | **Multi-Cloud Export & Sync Integration** | Direct cloud export options (Google Drive, Dropbox, AWS S3), bulk ZIP package download (Video + Thumbnail + SRT Subtitles + Metadata), and external webhook notifications (Discord/Slack). | **P2 (Medium)** |

---

## Actionable Remediation Roadmap

```
EpicSync Remediation Engineering Roadmap
├── Phase 1: Immediate Hotfixes (Sprint 1 - 24-48 Hours)
│   ├── [ ] Fix FastAPI route mounting order in main.py (Move app.mount below API routes)
│   ├── [ ] Add ytClientId & ytClientSecret inputs to index.html Settings view
│   ├── [ ] Add logsContainer.appendChild(div) in app.js loadLogs()
│   └── [ ] Fix submitVideoBtn disabled state logic in Studio view
├── Phase 2: Core Workflow & UX Restoration (Sprint 2 - 1 Week)
│   ├── [ ] Refactor hybrid auth handler in app.js to eliminate auth/invalid-credential recursion
│   ├── [ ] Add Firestore snapshot listener unsubscribe handler on logout
│   ├── [ ] Fix desktop drawer backdrop pointer interception CSS
│   ├── [ ] Enable manual script editing in Studio view
│   └── [ ] Add async visual loading spinners to all buttons
└── Phase 3: SaaS Feature Expansion (Sprint 3 - 2-3 Weeks)
    ├── [ ] Implement FEAT-01: Multi-Channel YouTube OAuth Manager
    ├── [ ] Implement FEAT-02: Video Scheduling & Automated Publishing Queue
    ├── [ ] Implement FEAT-03: AI Thumbnail Generator & Canvas Editor
    └── [ ] Implement FEAT-04 & FEAT-05: ElevenLabs TTS & YouTube Analytics Integration
```

---
*Report compiled and verified by Worker Subagent (`worker_1`) for the EpicSync QA and Feature Audit project.*
