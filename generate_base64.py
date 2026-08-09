import base64
patch_code = """import os
import re

# 1. Patch T5 memory spike
t5_path = '/kaggle/working/AptAvatar/AptAvatar/wan/modules/t5.py'
with open(t5_path, 'r') as f:
    t5_code = f.read()

t5_code = t5_code.replace('with torch.device(device):', 'torch.set_default_dtype(dtype)\\n    with torch.device(device):')
t5_code = t5_code.replace('model = model_cls(**kwargs)', 'model = model_cls(**kwargs)\\n    torch.set_default_dtype(torch.float32)')

with open(t5_path, 'w') as f:
    f.write(t5_code)

# 2. Patch Pipeline
pipe_path = '/kaggle/working/AptAvatar/AptAvatar/src/pipeline/AptAvatar_pipeline.py'
with open(pipe_path, 'r') as f:
    pipe_code = f.read()

pipe_code = re.sub(
    r"self\.text_encoder = T5EncoderModel\([\s\S]*?device=self\.device,",
    "self.text_encoder = T5EncoderModel(\\n            text_len=config.text_len,\\n            dtype=config.t5_dtype,\\n            device='cpu',",
    pipe_code
)

pipe_code = pipe_code.replace(
    'device_map={"": model_load_device},',
    'device_map="auto", max_memory={0: "2GiB", 1: "14GiB", "cpu": "30GiB"},'
)

pipe_code = pipe_code.replace('if self.cpu_offload:\\n            self.model.to(self.device)', '')
pipe_code = pipe_code.replace('if self.cpu_offload:\\n                self.model.cpu()', '')

new_prompt_func = \"\"\"    @torch.no_grad()
    def set_input_prompt(self, input_prompt):
        context = self._prompt_context_cache.get(input_prompt)
        if context is None:
            context = self.text_encoder([input_prompt], "cpu")[0]
            context = context.to(self.device)
            self._prompt_context_cache[input_prompt] = context
        self.arg_c['context'] = [context]\"\"\"

pipe_code = re.sub(
    r"    @torch\.no_grad\(\)\\n    def set_input_prompt.*?self\.arg_c\['context'\] = \[context\]",
    new_prompt_func,
    pipe_code,
    flags=re.DOTALL
)

with open(pipe_path, 'w') as f:
    f.write(pipe_code)

# 3. Patch multitalk_model.py for accelerate device_map compatibility
model_path = '/kaggle/working/AptAvatar/AptAvatar/infinite_talk/modules/multitalk_model.py'
if os.path.exists(model_path):
    with open(model_path, 'r') as f:
        model_code = f.read()

    model_code = model_code.replace(
        'class AudioProjModel(ModelMixin, ConfigMixin):',
        'class AudioProjModel(ModelMixin, ConfigMixin):\\n    _no_split_modules = []'
    )

    with open(model_path, 'w') as f:
        f.write(model_code)

# 4. Patch attention.py to gracefully fallback to SDPA when Flash Attention is unavailable
attn_path = '/kaggle/working/AptAvatar/AptAvatar/wan/modules/attention.py'
if os.path.exists(attn_path):
    with open(attn_path, 'r') as f:
        attn_code = f.read()

    attn_patch = '''
_original_flash_attention = flash_attention
def _patched_flash_attention(*args, **kwargs):
    if not (FLASH_ATTN_2_AVAILABLE or FLASH_ATTN_3_AVAILABLE):
        kwargs.pop('version', None)
        return attention(*args, **kwargs)
    return _original_flash_attention(*args, **kwargs)

flash_attention = _patched_flash_attention
'''
    with open(attn_path, 'a') as f:
        f.write(attn_patch)
"""

print(base64.b64encode(patch_code.encode('utf-8')).decode('utf-8'))
