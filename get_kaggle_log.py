import zipfile
import requests
import io
import os
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
api.authenticate()

# The python method is `kernels_output`, which downloads to a folder, but we can't easily capture the URL in python 3 KaggleApi without overriding.
# Wait, KaggleApi doesn't return the URL from kernels_output_with_http_info in newer versions?
# Let's just download it via `kaggle kernels output` into a dir, but we will ignore the UnicodeEncodeError by overriding sys.stdout!
import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    api.kernels_output_cli('gabrielnjoku/epicsync-proj-qnwnf2ihpchlsfo', path='kaggle_debug4')
except Exception as e:
    print(f"Error downloading: {e}")

# Now let's print the log files inside it!
for root, dirs, files in os.walk('kaggle_debug4'):
    for file in files:
        if file.endswith('.log') or file == '__results__.html':
            print(f"--- {file} ---")
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                print(content[-3000:])
