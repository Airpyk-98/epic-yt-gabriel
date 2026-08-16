import os
from huggingface_hub import HfApi

def deploy():
    token = "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"
    api = HfApi(token=token)
    
    user_info = api.whoami()
    username = user_info['name']
    space_name = "epic-auth-hub"
    repo_id = f"{username}/{space_name}"
    
    print(f"Creating Free Gradio Space: {repo_id}...")
    try:
        api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="gradio", private=True)
    except Exception as e:
        print(f"Space might already exist or error: {e}")
    
    app_py_content = """import os
import subprocess
import time
import sys

def main():
    # 1. Download Node.js 20 Linux binary if it doesn't exist
    if not os.path.exists("node-v20.11.1-linux-x64"):
        print("Downloading Node.js...", flush=True)
        os.system("wget -q https://nodejs.org/dist/v20.11.1/node-v20.11.1-linux-x64.tar.xz")
        os.system("tar -xf node-v20.11.1-linux-x64.tar.xz")
        
    # 2. Add Node.js to PATH
    node_bin = os.path.abspath("node-v20.11.1-linux-x64/bin")
    os.environ["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"
    
    # 3. Configure Activepieces Environment
    env = os.environ.copy()
    env["AP_EXECUTION_MODE"] = "UNSANDBOXED"
    env["AP_DB_TYPE"] = "SQLITE"
    env["AP_SQLITE_DATABASE_FILE"] = "/home/user/app/activepieces.sqlite"
    env["AP_TELEMETRY_ENABLED"] = "false"
    env["AP_PORT"] = "7860"  # HF exposes this port
    
    # The SPACE_HOST is provided by HF, e.g., username-spacename.hf.space
    space_host = os.environ.get("SPACE_HOST", "")
    if space_host:
        env["AP_FRONTEND_URL"] = f"https://{space_host}"
    
    print("Starting Activepieces...", flush=True)
    # 4. Start Activepieces using npx
    subprocess.run(["npx", "-y", "activepieces@latest"], env=env)

if __name__ == "__main__":
    main()
"""
    
    with open("app_gradio.py", "w") as f:
        f.write(app_py_content)
        
    print("Uploading app.py to Hub...")
    api.upload_file(
        path_or_fileobj="app_gradio.py",
        path_in_repo="app.py",
        repo_id=repo_id,
        repo_type="space"
    )
    
    print(f"✅ Activepieces deployed via Gradio Hack! URL: https://{username}-{space_name}.hf.space")

if __name__ == "__main__":
    deploy()
