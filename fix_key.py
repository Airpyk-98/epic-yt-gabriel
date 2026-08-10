import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update PEXELS_API_KEY in the kernel template
old_key = 'PEXELS_API_KEY = "y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K"'
new_key = 'PEXELS_API_KEY = ___PEXELS_API_KEY___'
content = content.replace(old_key, new_key)

# 2. Update prepare_and_launch_premium_job to inject the key
old_inject = 'script_content = PEXELS_KERNEL_TEMPLATE.replace("___SCRIPT_TEXT___", repr(spoken_script)).replace("___VOICE___", repr(voice)).replace("___HF_REPO___", repr(hf_repo)).replace("___JOB_ID___", repr(job_id)).replace("___HF_TOKEN___", repr(hf_token)).replace("___ASPECT_RATIO___", repr(aspect_ratio)).replace("___RESOLUTION___", repr(resolution)).replace("___ADD_CAPTIONS___", repr(str(add_captions))).replace("___BGM_REPO_PATH___", repr(bgm_repo_path)).replace("___VIDEO_SPEED___", repr(str(video_speed))).replace("___PEXELS_SEGMENTS_JSON___", repr(pexels_segments_json))'

new_inject = '''import os
            pexels_key = os.environ.get("PEXELS_API_KEY", "y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K")
            script_content = PEXELS_KERNEL_TEMPLATE.replace("___SCRIPT_TEXT___", repr(spoken_script)).replace("___VOICE___", repr(voice)).replace("___HF_REPO___", repr(hf_repo)).replace("___JOB_ID___", repr(job_id)).replace("___HF_TOKEN___", repr(hf_token)).replace("___ASPECT_RATIO___", repr(aspect_ratio)).replace("___RESOLUTION___", repr(resolution)).replace("___ADD_CAPTIONS___", repr(str(add_captions))).replace("___BGM_REPO_PATH___", repr(bgm_repo_path)).replace("___VIDEO_SPEED___", repr(str(video_speed))).replace("___PEXELS_SEGMENTS_JSON___", repr(pexels_segments_json)).replace("___PEXELS_API_KEY___", repr(pexels_key))'''

content = content.replace(old_inject, new_inject)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated main.py locally for Pexels key injection.")
