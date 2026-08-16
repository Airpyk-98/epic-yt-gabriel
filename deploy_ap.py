import os
from huggingface_hub import HfApi

def deploy():
    token = "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"
    api = HfApi(token=token)
    
    user_info = api.whoami()
    username = user_info['name']
    space_name = "epic-activepieces"
    repo_id = f"{username}/{space_name}"
    
    print(f"Creating Space: {repo_id}...")
    try:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", private=True)
    except Exception as e:
        print(f"Space might already exist or error: {e}")
    
    dockerfile_content = """FROM activepieces/activepieces:latest

# Configure for Hugging Face Spaces
ENV AP_PORT=7860
ENV AP_EXECUTION_MODE=UNSANDBOXED
ENV AP_FRONTEND_URL="https://${SPACE_HOST}"
ENV AP_TELEMETRY_ENABLED=false

# Use SQLite for single-container deployment
ENV AP_DB_TYPE=SQLITE
ENV AP_SQLITE_DATABASE_FILE=/data/activepieces.sqlite

EXPOSE 7860
"""
    
    with open("Dockerfile_ap", "w") as f:
        f.write(dockerfile_content)
        
    print("Uploading Dockerfile...")
    api.upload_file(
        path_or_fileobj="Dockerfile_ap",
        path_in_repo="Dockerfile",
        repo_id=repo_id,
        repo_type="space"
    )
    
    # We also need to map the /data directory in HF spaces to persistent storage if possible,
    # but for an auth proxy, a standard deployment works.
    
    print(f"✅ Activepieces deployed! URL will be: https://{username}-{space_name}.hf.space")

if __name__ == "__main__":
    deploy()
