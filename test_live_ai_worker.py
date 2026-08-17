import requests, json, re

API_KEY = "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"
base_url = "https://integrate.api.nvidia.com/v1"
title = "8 signs someone is secretly jealous of you."
sys_prompt = """You are an elite viral YouTube Shorts scriptwriter and visual director.
Write a completely original, high-retention, psychology-backed video narration script for the title: "8 signs someone is secretly jealous of you.".
Respond with valid JSON ONLY:
{
  "scenes": [
    {"line": "First spoken sentence...", "pexels_query": "concrete visual query"},
    {"line": "Second spoken sentence...", "pexels_query": "different visual query"}
  ]
}"""

nvidia_models = ["z-ai/glm-5.2", "meta/llama-3.3-70b-instruct", "meta/llama-3.1-70b-instruct", "mistralai/mistral-large-2-instruct"]
ai_scenes = []

for model_name in nvidia_models:
    if ai_scenes:
        break
    try:
        print(f"Calling {model_name} at {base_url}...")
        req_body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
            ],
            "max_tokens": 4096,
            "temperature": 0.85
        }
        if "glm" in model_name.lower():
            req_body["chat_template_kwargs"] = {"enable_thinking": False}
        r_ai = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=req_body,
            timeout=90
        )
        if r_ai.ok:
            resp_data = r_ai.json()
            resp_c = resp_data["choices"][0]["message"]["content"] or ""
            finish_reason = resp_data["choices"][0].get("finish_reason", "unknown")
            print(f"AI response: {len(resp_c)} chars, finish_reason={finish_reason}")
            clean_c = resp_c.replace(chr(96)*3 + "json", "").replace(chr(96)*3, "").strip()

            # 1. Full JSON block extraction (no regex escape hazards)
            start_brace = clean_c.find('{')
            end_brace = clean_c.rfind('}')
            if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                try:
                    parsed_j = json.loads(clean_c[start_brace:end_brace+1])
                    for sc_item in parsed_j.get("scenes", []):
                        l_val = str(sc_item.get("line", "")).strip()
                        q_val = str(sc_item.get("pexels_query", "")).strip()
                        if l_val:
                            ai_scenes.append({"line": l_val, "pexels_query": q_val})
                    if ai_scenes:
                        print(f"✅ AI generated {len(ai_scenes)} unique scenes via {model_name}")
                except Exception as p_err:
                    print(f"JSON parse notice: {p_err}")

            # 2. Line-by-line fallback if stream was cut off mid-response
            if not ai_scenes:
                for line_item in clean_c.splitlines():
                    line_item = line_item.strip()
                    if '"line":' in line_item and '"pexels_query":' in line_item:
                        m_l = re.search(r'"line"\s*:\s*"([^"]+)"', line_item)
                        m_q = re.search(r'"pexels_query"\s*:\s*"([^"]+)"', line_item)
                        if m_l:
                            l_val = m_l.group(1).strip()
                            q_val = m_q.group(1).strip() if m_q else "lifestyle"
                            if l_val:
                                ai_scenes.append({"line": l_val, "pexels_query": q_val})
                if ai_scenes:
                    print(f"✅ AI salvaged {len(ai_scenes)} scenes via line extraction from {model_name}")
        else:
            print(f"{model_name} returned {r_ai.status_code}, trying next model... ({r_ai.text[:150]})")
    except Exception as e:
        print(f"{model_name} notice: {e}, trying next model...")

print("\nFinal AI Scenes Result:")
for i, sc in enumerate(ai_scenes):
    print(f"  [{i+1}] Query: '{sc['pexels_query']}' | Line: '{sc['line']}'")
