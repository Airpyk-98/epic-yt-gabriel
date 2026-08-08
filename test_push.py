import os
import json
import subprocess

def setup_kaggle_auth(username, key):
    env = os.environ.copy()
    env['KAGGLE_USERNAME'] = username
    env['KAGGLE_KEY'] = key
    env['KAGGLE_API_TOKEN'] = key
    d = os.path.expanduser('~/.kaggle')
    os.makedirs(d, exist_ok=True)
    creds_file = os.path.join(d, 'kaggle.json')
    try:
        with open(creds_file, 'w') as f:
            json.dump({'username': username, 'key': key}, f)
        os.chmod(creds_file, 0o600)
    except:
        pass
    return env

staging = 'test_staging'
os.makedirs(staging, exist_ok=True)
with open(os.path.join(staging, 'run_epicsync.py'), 'w') as f:
    f.write('print("Hello World")')

meta = {
    'id': 'gabrielnjoku/epicsync-test-push-123',
    'title': 'EpicSync Test Push 123',
    'code_file': 'run_epicsync.py',
    'language': 'python',
    'kernel_type': 'script',
    'is_private': True,
    'enable_gpu': True,
    'enable_tpu': False,
    'enable_internet': True,
    'keywords': ['gpu', 'diffusion', 'ltx'],
    'dataset_sources': [
        'mikerozer/wan2gp-shared-models',
        'trailtalknick/ltx-23-22b-q4-gguf'
    ],
    'competition_sources': [],
    'kernel_sources': [],
    'model_sources': [],
    'machine_shape': 'NvidiaTeslaT4'
}

with open(os.path.join(staging, 'kernel-metadata.json'), 'w') as f:
    json.dump(meta, f, indent=2)

env = setup_kaggle_auth('gabrielnjoku', 'KGAT_011c8a0cd3f10cfd9fb0e092d1ff678e')

print('Running kaggle kernels push...')
res = subprocess.run(f'kaggle kernels push -p {staging}', shell=True, capture_output=True, text=True, env=env)
print('RC:', res.returncode)
print('STDOUT:', res.stdout)
print('STDERR:', res.stderr)
