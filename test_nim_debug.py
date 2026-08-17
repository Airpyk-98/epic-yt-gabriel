import requests, json, time

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"

title = "8 signs someone is secretly jealous of you."
sys_prompt = """You are an elite viral YouTube Shorts scriptwriter. Respond with JSON ONLY:
{
  "scenes": [
    {"line": "First line...", "pexels_query": "visual search query 1"},
    {"line": "Second line...", "pexels_query": "visual search query 2"}
  ]
}"""

# Test 1: GLM-5.2 with chat_template_kwargs
print("=== Test 1: GLM-5.2 with chat_template_kwargs ===")
try:
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "z-ai/glm-5.2",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
            ],
            "max_tokens": 2048,
            "temperature": 0.7,
            "chat_template_kwargs": {"enable_thinking": False}
        },
        timeout=30
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:300]}")
except Exception as e:
    print("Error:", e)

# Test 2: GLM-5.2 pure standard OpenAI payload (no extra params)
print("\n=== Test 2: GLM-5.2 standard OpenAI payload ===")
try:
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "z-ai/glm-5.2",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
            ],
            "max_tokens": 2048,
            "temperature": 0.7
        },
        timeout=30
    )
    print(f"Status: {r.status_code}")
    if r.ok:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        finish = data["choices"][0].get("finish_reason")
        print(f"Finish: {finish}, Length: {len(content)}")
        print(f"Snippet: {content[:300]}...")
    else:
        print(f"Error: {r.text[:300]}")
except Exception as e:
    print("Error:", e)

# Test 3: Check all available models on NVIDIA NIM with 'llama' or 'mistral' or 'nemotron' or 'qwen'
print("\n=== Test 3: List fast models ===")
try:
    r = requests.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
    if r.ok:
        all_models = [m["id"] for m in r.json().get("data", [])]
        print(f"Total available models on NVIDIA NIM: {len(all_models)}")
        instruct_models = [m for m in all_models if "instruct" in m or "chat" in m or "glm" in m]
        print("Available Instruct Models:\n" + "\n".join(sorted(instruct_models)[:30]))
except Exception as e:
    print("Error:", e)
