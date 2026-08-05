import os
import sys
import json
import urllib.request
import tarfile
import subprocess
import shutil
import time

def get_docker_token(repo):
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())["token"]

def get_manifest(repo, token, tag="latest"):
    url = f"https://registry.hub.docker.com/v2/{repo}/manifests/{tag}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    # Accept OCI or Docker v2 manifests
    req.add_header("Accept", "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        if "manifests" in data:
            # It's a manifest list (multi-arch), find linux/amd64
            for m in data["manifests"]:
                if m.get("platform", {}).get("architecture") == "amd64" and m.get("platform", {}).get("os") == "linux":
                    return get_manifest(repo, token, m["digest"])
        return data

def download_layer(repo, token, digest, filepath):
    url = f"https://registry.hub.docker.com/v2/{repo}/blobs/{digest}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    print(f"Downloading layer {digest[:12]}...")
    with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def extract_docker_image():
    repo = "activepieces/activepieces"
    extract_dir = "/home/user/app/ap_env"
    
    # If already extracted, skip
    if os.path.exists(os.path.join(extract_dir, "usr/src/app/dist/packages/server/api/main.js")):
        print("Activepieces already extracted!")
        return extract_dir
        
    os.makedirs(extract_dir, exist_ok=True)
    print("Fetching Docker Hub token...")
    token = get_docker_token(repo)
    print("Fetching manifest...")
    manifest = get_manifest(repo, token)
    
    layers = manifest.get("layers", [])
    for idx, layer in enumerate(layers):
        digest = layer["digest"]
        tar_path = f"/tmp/layer_{idx}.tar.gz"
        download_layer(repo, token, digest, tar_path)
        print(f"Extracting layer {idx+1}/{len(layers)}...")
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                # We only want to extract the app code and node_modules to save time and space
                members = []
                for m in tar.getmembers():
                    if m.name.startswith("usr/src/app") or m.name.startswith("./usr/src/app"):
                        members.append(m)
                if members:
                    tar.extractall(path=extract_dir, members=members)
        except Exception as e:
            print(f"Warning extracting layer {idx}: {e}")
        os.remove(tar_path)
        
    return extract_dir

def main():
    print("=== STARTING UI CTO ACTIVEPIECES BYPASS ===", flush=True)
    
    # 1. Download Node.js 20 Linux binary
    if not os.path.exists("node-v20.11.1-linux-x64"):
        print("Downloading Node.js 20...", flush=True)
        os.system("wget -q https://nodejs.org/dist/v20.11.1/node-v20.11.1-linux-x64.tar.xz")
        os.system("tar -xf node-v20.11.1-linux-x64.tar.xz")
    
    node_bin = os.path.abspath("node-v20.11.1-linux-x64/bin")
    os.environ["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"
    
    # 2. Extract Activepieces Docker Image manually via API
    extract_dir = extract_docker_image()
    
    # 3. Configure Activepieces Environment
    env = os.environ.copy()
    env["AP_EXECUTION_MODE"] = "UNSANDBOXED"
    env["AP_DB_TYPE"] = "SQLITE"
    env["AP_SQLITE_DATABASE_FILE"] = "/home/user/app/activepieces.sqlite"
    env["AP_TELEMETRY_ENABLED"] = "false"
    env["AP_PORT"] = "7860"  # HF exposes this port
    
    space_host = os.environ.get("SPACE_HOST", "")
    if space_host:
        env["AP_FRONTEND_URL"] = f"https://{space_host}"
        
    # 4. Start Activepieces
    main_js_path = os.path.join(extract_dir, "usr/src/app/dist/packages/server/api/main.js")
    # Some layers might strip the leading ./
    if not os.path.exists(main_js_path):
        main_js_path = os.path.join(extract_dir, "usr/src/app/dist/packages/server/api/main.js").replace("/usr/", "/./usr/")
        
    print(f"Executing Node.js on {main_js_path}...", flush=True)
    
    # Run the server
    cwd = os.path.join(extract_dir, "usr/src/app") if os.path.exists(os.path.join(extract_dir, "usr/src/app")) else os.getcwd()
    subprocess.run(["node", main_js_path], env=env, cwd=cwd)

if __name__ == "__main__":
    main()
