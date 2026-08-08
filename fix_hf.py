import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix huggingface_hub imports and functions
content = content.replace('YOUR_HF_TOKEN_download', 'hf_hub_download')
content = content.replace('upload_to_YOUR_HF_TOKEN', 'upload_to_hf_hub')

# In the kernel templates, there are variables YOUR_HF_TOKEN and YOUR_HF_TOKEN2
# Let's see how they are used.

def replacer(match):
    return match.group(0)

# Replace token=YOUR_HF_TOKEN2 or None
content = content.replace('token=YOUR_HF_TOKEN2', 'token=hf_token')
content = content.replace('token=YOUR_HF_TOKEN ', 'token=hf_token ')

# Replace repo_id=YOUR_HF_TOKEN2
content = content.replace('repo_id=YOUR_HF_TOKEN2', 'repo_id=hf_repo')

# Replace YOUR_HF_TOKEN = ___HF_TOKEN___
content = content.replace('YOUR_HF_TOKEN = ___HF_TOKEN___', 'hf_token = ___HF_TOKEN___')
content = content.replace('YOUR_HF_TOKEN = ___HF_REPO___', 'hf_repo = ___HF_REPO___')

# Replace if YOUR_HF_TOKEN and len(YOUR_HF_TOKEN2) > 5:
content = content.replace('if YOUR_HF_TOKEN and len(YOUR_HF_TOKEN2) > 5:', 'if hf_token and len(hf_token) > 5:')
content = content.replace('os.environ["HF_TOKEN"] = YOUR_HF_TOKEN', 'os.environ["HF_TOKEN"] = hf_token')

# "Fetching source image from HF dataset {YOUR_HF_TOKEN}..."
content = content.replace('{YOUR_HF_TOKEN}', '{hf_repo}')
content = content.replace('if not repo_id or not YOUR_HF_TOKEN:', 'if not repo_id or not hf_token:')
content = content.replace('api = HfApi(token=YOUR_HF_TOKEN)', 'api = HfApi(token=hf_token)')

content = content.replace('if bgm_repo_path and YOUR_HF_TOKEN:', 'if bgm_repo_path and hf_repo:')
content = content.replace('elif YOUR_HF_TOKEN:', 'elif hf_repo:')

# Fix the FastAPI endpoint signatures:
content = content.replace('YOUR_HF_TOKEN: str,', 'hf_repo: str,')
content = content.replace('YOUR_HF_TOKEN2: str,', 'hf_token: str,')
content = content.replace('YOUR_HF_TOKEN: str = Form("Airpyk98/EpicSync-Dataset"),', 'hf_repo: str = Form("Airpyk98/EpicSync-Dataset"),')
content = content.replace('YOUR_HF_TOKEN2: str = Form(""),', 'hf_token: str = Form(""),')
content = content.replace('if not YOUR_HF_TOKEN or YOUR_HF_TOKEN2.strip() == "":', 'if not hf_repo or hf_token.strip() == "":')

# replace any remaining YOUR_HF_TOKEN2 with hf_token and YOUR_HF_TOKEN with hf_repo
content = content.replace('YOUR_HF_TOKEN2', 'hf_token')
content = content.replace('YOUR_HF_TOKEN', 'hf_repo')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed main.py')
