import os
import sys
import time
import base64
from huggingface_hub import HfApi

def run_cmd(cmd):
    print(f"Executing: {cmd}", flush=True)
    res = os.system(cmd)
    if res != 0:
        print(f"Command failed with code {res}", flush=True)

print("=== STARTING APTAVATAR (14B) PIPELINE ===", flush=True)

# 1. SETUP SWAP (For 14B Model memory buffering on T4)
# Note: Kaggle containers don't allow swapon (Operation not permitted).
# We must rely on standard memory management.

# 2. HF AUTH & ENV
hf_token = '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'
os.environ["HF_TOKEN"] = hf_token

# 3. INSTALL DEPENDENCIES
# We remove flash_attn compilation because it takes 45 mins to build on Kaggle's newer PyTorch versions.
# Most models gracefully fallback to PyTorch native SDPA.
run_cmd("pip install -q huggingface_hub edge-tts soundfile ffmpeg-python")
run_cmd("pip install ninja")

# 4. GENERATE AUDIO VOICEOVER VIA TTS
script_text = 'The crash happens because Kaggle’s T4 GPUs are based on the older Turing architecture, which fundamentally does not support Flash Attention 2 (it requires Ampere GPUs or newer, like A100 or RTX 30/40 series).'
voice = 'en-US-ChristopherNeural'
print(f"Generating studio voiceover with voice: {voice}...", flush=True)
with open("/kaggle/working/tts_script.txt", "w", encoding="utf-8") as f:
    f.write(script_text)
run_cmd(f'edge-tts --voice "{voice}" -f /kaggle/working/tts_script.txt --write-media /kaggle/working/input.wav')

# 5. DECODE INPUT IMAGE
ib64 = ''
if ib64:
    with open("/kaggle/working/input.png", "wb") as f:
        f.write(base64.b64decode(ib64))
else:
    # Fetch from HF if not embedded
    job_id = 'epicsync_premium_1786282383'
    hf_repo = 'epic-gab/EpicSync-Dataset'
    with open('/kaggle/working/download_input.py', 'w') as f:
        f.write(f"from huggingface_hub import hf_hub_download\nhf_hub_download(repo_id='{hf_repo}', filename='inputs/{job_id}.png', repo_type='dataset', local_dir='/kaggle/working')")
    run_cmd("python /kaggle/working/download_input.py")
    run_cmd(f"mv /kaggle/working/inputs/{job_id}.png /kaggle/working/input.png")

from PIL import Image, ImageOps
aspect_ratio_mode = '16:9'
if aspect_ratio_mode == "16:9":
    target_w, target_h = 1280, 720
elif aspect_ratio_mode == "1:1":
    target_w, target_h = 768, 768
else:
    target_w, target_h = 768, 1280

img = Image.open("/kaggle/working/input.png").convert("RGB")
img = ImageOps.fit(img, (target_w, target_h), Image.Resampling.LANCZOS)
img.save("/kaggle/working/input.png")

# 6. WRITE STRUCTURED ACTION PROMPT
structured_prompt = ''
with open("/kaggle/working/action_prompt.txt", "w", encoding="utf-8") as f:
    f.write(structured_prompt)

# 7. CLONE REPO & FETCH WEIGHTS
run_cmd("git clone https://github.com/TaoLiveAIGC/AptAvatar.git /kaggle/working/AptAvatar")
os.chdir("/kaggle/working/AptAvatar")
run_cmd("sed -i '/torch/d' requirements.txt")
run_cmd("sed -i 's/xformers==.*/xformers/g' requirements.txt")
run_cmd("pip install -q -r requirements.txt")
run_cmd("pip install -q --no-deps xfuser yunchang distvae")

# Download 14B Weights and Audio Encoder into /tmp which has 73GB free space, then symlink it
with open('/kaggle/working/download_models.py', 'w') as f:
    f.write("import os\nos.environ['HF_HOME'] = '/tmp/.cache/huggingface'\nfrom huggingface_hub import snapshot_download\nsnapshot_download(repo_id='TaoLiveAIGC/AptAvatar', local_dir='/tmp/models/AptAvatar')\nsnapshot_download(repo_id='TencentGameMate/chinese-wav2vec2-base', local_dir='/tmp/models/chinese-wav2vec2-base')")
run_cmd("python /kaggle/working/download_models.py")
run_cmd("mkdir -p /kaggle/working/AptAvatar/models")
run_cmd("ln -s /tmp/models/AptAvatar /kaggle/working/AptAvatar/models/AptAvatar")
run_cmd("ln -s /tmp/models/chinese-wav2vec2-base /kaggle/working/AptAvatar/models/chinese-wav2vec2-base")

# 7.5 PATCH FOR 16GB GPUs — download standalone patch from repo (no string nesting)
print("Downloading and applying AptAvatar patches for Kaggle dual T4...", flush=True)
run_cmd("curl -sL https://raw.githubusercontent.com/Airpyk-98/epic-yt-gabriel/main/patches/aptavatar_patch.py -o /kaggle/working/aptavatar_patch.py")
run_cmd("python /kaggle/working/aptavatar_patch.py")

# 8. INFERENCE (2-Step NFE)
print("Starting 2-Step NFE Generation...", flush=True)
with open("/kaggle/working/run_gen.py", "w") as f:
    f.write("import os\nos.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'\nimport subprocess\nprompt=open('/kaggle/working/action_prompt.txt').read()\nsubprocess.run(['python', 'generate_video.py', '--cond_image', '/kaggle/working/input.png', '--audio_path', '/kaggle/working/input.wav', '--input_prompt', prompt, '--save_file', '/kaggle/working/raw_aptavatar.mp4', '--cpu_offload', '--ckpt_dir', '/kaggle/working/AptAvatar/models/AptAvatar', '--wav2vec_dir', '/kaggle/working/AptAvatar/models/chinese-wav2vec2-base'], check=True)")
run_cmd("python /kaggle/working/run_gen.py")

# 9. DOWNSCALE/UPSCALE & UPLOAD
resolution = '720p'
os.chdir("/kaggle/working")
if resolution == "480p":
    run_cmd('ffmpeg -y -i /kaggle/working/AptAvatar/raw_aptavatar.mp4 -vf scale=480:-2 -c:v libx264 -preset fast -crf 23 -c:a aac /kaggle/working/result.mp4')
elif resolution == "960p":
    run_cmd('ffmpeg -y -i /kaggle/working/AptAvatar/raw_aptavatar.mp4 -vf scale=960:-2 -c:v libx264 -preset fast -crf 23 -c:a aac /kaggle/working/result.mp4')
else:
    run_cmd('mv /kaggle/working/AptAvatar/raw_aptavatar.mp4 /kaggle/working/result.mp4')

print("Uploading to Hugging Face dataset...", flush=True)
try:
    api = HfApi(token=hf_token)
    api.upload_file(
        path_or_fileobj="/kaggle/working/result.mp4",
        path_in_repo=f"outputs/'epicsync_premium_1786282383'.mp4",
        repo_id='epic-gab/EpicSync-Dataset',
        repo_type="dataset"
    )
    print("SUCCESS: Uploaded to HF Hub!")
except Exception as e:
    print(f"Failed to upload to HF Hub: {e}", flush=True)
