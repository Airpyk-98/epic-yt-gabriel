import os
from huggingface_hub import HfApi

TOKEN = "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"
SPACE_ID = "epic-gab/EpicSync"

api = HfApi(token=TOKEN)

print(f"Creating Space {SPACE_ID} if it doesn't exist...")
try:
    api.create_repo(
        repo_id=SPACE_ID,
        repo_type="space",
        space_sdk="gradio",
        private=True,
        exist_ok=True
    )
    print("Space exists or was created successfully.")
except Exception as e:
    print(f"Warning on create_repo: {e}")

print("Uploading files to the Space...")
ignore_patterns = [
    ".git/*",
    ".git",
    "__pycache__/*",
    "data/staging/*",
    "data/outputs/*",
    "deploy_hf.py"
]

api.upload_folder(
    folder_path=".",
    repo_id=SPACE_ID,
    repo_type="space",
    ignore_patterns=ignore_patterns,
    commit_message="Deploying EpicSync FastAPI + Static UI"
)
print(f"Deployed successfully to https://huggingface.co/spaces/{SPACE_ID}")
