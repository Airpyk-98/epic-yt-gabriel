"""
AptAvatar source code patches for Kaggle dual-T4 (16GB GPU) environment.
Downloaded and executed during the Kaggle notebook pipeline.
No string nesting issues — this is a standalone file.
"""
import os
import re

print("=== Applying AptAvatar patches for Kaggle T4 ===", flush=True)

# 1. Patch multitalk_attention.py — make xformers import optional
attn_file = '/kaggle/working/AptAvatar/AptAvatar/infinite_talk/modules/multitalk_attention.py'
if os.path.exists(attn_file):
    with open(attn_file, 'r') as f:
        code = f.read()
    code = code.replace(
        'import xformers.ops',
        'try:\n    import xformers.ops\nexcept ImportError:\n    xformers = None'
    )
    with open(attn_file, 'w') as f:
        f.write(code)
    print("  [OK] multitalk_attention.py — xformers import made optional", flush=True)

# 2. Patch multitalk_model.py — add _no_split_modules for accelerate
model_file = '/kaggle/working/AptAvatar/AptAvatar/infinite_talk/modules/multitalk_model.py'
if os.path.exists(model_file):
    with open(model_file, 'r') as f:
        code = f.read()
    code = code.replace(
        'class AudioProjModel(ModelMixin, ConfigMixin):',
        'class AudioProjModel(ModelMixin, ConfigMixin):\n    _no_split_modules = []'
    )
    with open(model_file, 'w') as f:
        f.write(code)
    print("  [OK] multitalk_model.py — _no_split_modules added", flush=True)

# 3. Patch t5.py — prevent fp32 memory spike during T5 loading
t5_file = '/kaggle/working/AptAvatar/AptAvatar/wan/modules/t5.py'
if os.path.exists(t5_file):
    with open(t5_file, 'r') as f:
        code = f.read()
    code = re.sub(
        r"^(\s*)with torch\.device\(device\):",
        r"\1torch.set_default_dtype(dtype)\n\1with torch.device(device):",
        code,
        flags=re.MULTILINE
    )
    code = re.sub(
        r"^(\s*)model = model_cls\(\*\*kwargs\)",
        r"\1model = model_cls(**kwargs)\n\1torch.set_default_dtype(torch.float32)",
        code,
        flags=re.MULTILINE
    )
    with open(t5_file, 'w') as f:
        f.write(code)
    print("  [OK] t5.py — dtype management patched", flush=True)

# 4. Patch AptAvatar_pipeline.py — load T5 on CPU, use device_map auto
pipe_file = '/kaggle/working/AptAvatar/AptAvatar/src/pipeline/AptAvatar_pipeline.py'
if os.path.exists(pipe_file):
    with open(pipe_file, 'r') as f:
        code = f.read()

    # Use device_map auto with memory limits instead of loading everything on one GPU
    code = code.replace(
        'device_map={"": model_load_device},',
        'device_map="auto", max_memory={0: "2GiB", 1: "14GiB", "cpu": "30GiB"},'
    )

    # Load T5 text encoder on CPU to save GPU memory
    code = re.sub(
        r"self\.text_encoder = T5EncoderModel\([\s\S]*?device=self\.device,",
        "self.text_encoder = T5EncoderModel(\n            text_len=config.text_len,\n            dtype=config.t5_dtype,\n            device='cpu',",
        code
    )

    # Remove CPU offload toggling for self.model that causes errors with device_map
    # Replaces the method call with 'pass' to preserve python indentation
    code = re.sub(r"self\.model\.to\(self\.device\)", "pass", code)
    code = re.sub(r"self\.model\.cpu\(\)", "pass", code)

    # Patch set_input_prompt to encode on CPU and cache results
    new_prompt_func = """    @torch.no_grad()
    def set_input_prompt(self, input_prompt):
        context = self._prompt_context_cache.get(input_prompt)
        if context is None:
            context = self.text_encoder([input_prompt], "cpu")[0]
            context = context.to(self.device)
            self._prompt_context_cache[input_prompt] = context
        self.arg_c['context'] = [context]"""

    code = re.sub(
        r"    @torch\.no_grad\(\)\n    def set_input_prompt.*?self\.arg_c\['context'\] = \[context\]",
        new_prompt_func,
        code,
        flags=re.DOTALL
    )

    with open(pipe_file, 'w') as f:
        f.write(code)
    print("  [OK] AptAvatar_pipeline.py — T5 on CPU, device_map auto", flush=True)

# 5. Patch attention.py — fallback flash_attention to SDPA when unavailable
attn_mod = '/kaggle/working/AptAvatar/AptAvatar/wan/modules/attention.py'
if os.path.exists(attn_mod):
    with open(attn_mod, 'a') as f:
        f.write("""
# === Kaggle T4 Patch: Flash Attention fallback ===
_original_flash_attention = flash_attention
def _patched_flash_attention(*args, **kwargs):
    if not (FLASH_ATTN_2_AVAILABLE or FLASH_ATTN_3_AVAILABLE):
        kwargs.pop('version', None)
        return attention(*args, **kwargs)
    return _original_flash_attention(*args, **kwargs)

flash_attention = _patched_flash_attention
""")
    print("  [OK] attention.py — flash_attention fallback added", flush=True)

print("=== All patches applied successfully ===", flush=True)
