# EpicSync Premium Flow - Setup & Replication Guide

This repository contains the standalone code required to replicate the **EpicSync Premium** orchestrated video generation pipeline. This pipeline uses a FastAPI frontend to take user input, syncs assets to a Hugging Face Dataset, and dispatches a highly-optimized Kaggle T4 GPU job to generate LTX-2.3 22B video.

## Architecture Overview
1. **Frontend (Hugging Face Space / Docker)**: A FastAPI server that provides a web UI (`/static/`). It receives a user script, image, and optional music.
2. **Asset Syncing**: The frontend uploads the image and music to a designated Hugging Face Dataset repository so the Kaggle backend can download them rapidly.
3. **Kaggle Orchestration**: The frontend creates a massive Python script from `main.py` (`PREMIUM_KERNEL_TEMPLATE`), wraps it in `kernel-metadata.json`, and pushes it to Kaggle via the `kaggle kernels push` command.
4. **Backend (Kaggle GPU)**: The Kaggle instance runs the script, downloads the 22B LTX model, generates TTS, runs smart-chunked inference, muxes audio/subtitles, and saves the final `.mp4`.
5. **Output Polling**: The frontend continuously polls Kaggle for the job status and downloads the `.mp4` when finished.

## Agent Instructions: How to Replicate this Flow

As an AI Agent, follow these exact steps to rebuild this pipeline on a new Hugging Face and Kaggle account:

### Step 1: Prepare the Hugging Face Dataset (Asset Store)
1. Log in to Hugging Face with the new account's token.
2. Create a new Dataset repository (e.g., `username/epicsync-assets`).
3. Ensure you have the `HF_TOKEN` with write permissions to this dataset.
4. Update `main.py`: Look for the `hf_repo = "..."` variable in the `PREMIUM_KERNEL_TEMPLATE` section and change it to the new Dataset repository name.

### Step 2: Prepare Kaggle Credentials
1. Log in to the target Kaggle account.
2. Go to Settings -> Create New API Token. This downloads `kaggle.json`.
3. Extract `username` and `key` from this file. These will be your `KAGGLE_USERNAME` and `KAGGLE_KEY` environment variables.

### Step 3: Deploy the Frontend (Hugging Face Space)
1. Create a new Hugging Face Space (Docker environment).
2. Push the contents of this repository (`main.py`, `Dockerfile`, `requirements.txt`, `static/`) to the Space.
3. Add the following **Secrets** to the Space settings:
   - `HF_TOKEN`: The Hugging Face write-access token.
   - `KAGGLE_USERNAME`: The Kaggle username.
   - `KAGGLE_KEY`: The Kaggle API key.
   - *(Optional)* `KAGGLE_PROXY`: If using a proxy for Kaggle API calls.

### Step 4: Verify the Setup
1. Once the Space builds, navigate to the Space's public URL.
2. The `static/index.html` UI should load.
3. Submit a test job (upload an image, enter a short script).
4. Monitor the Space's logs to verify it successfully pushes to Kaggle (`kaggle kernels push`) and starts polling.

### Key Files in this Repository
- `main.py`: The core FastAPI server and the embedded `PREMIUM_KERNEL_TEMPLATE` which runs on Kaggle.
- `static/`: Contains `index.html`, `style.css`, and `app.js` for the web UI.
- `Dockerfile`: Sets up the Python environment, installs the Kaggle CLI, and starts Uvicorn for Hugging Face Spaces.
- `requirements.txt`: Python dependencies for the frontend.
