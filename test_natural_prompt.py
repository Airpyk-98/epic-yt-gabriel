import requests, json, time

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"

title1 = "8 signs someone is secretly jealous of you."
title2 = "10 amazing phone features you probably don't know exist"

def generate_test_script(title, target_dur="45s"):
    t_secs = 45.0
    t_words = int(t_secs * 2.35)
    min_words = int(t_words * 0.90)
    max_words = int(t_words * 1.10)
    target_scenes_count = 6

    sys_prompt = f"""You are a master viral YouTube Shorts storyteller and visual director.
Write a gripping, 100% natural, psychology-driven short-form video narration script for the title: "{title}".

TARGET TIMING & LENGTH:
- Target Video Duration: {target_dur} (~{int(t_secs)} seconds)
- Required Spoken Word Count: STRICTLY between {min_words} and {max_words} total spoken words across all lines combined.
- Scene Cuts: Exactly {target_scenes_count} distinct visual scenes.

NARRATION & VOICE STYLE GUIDELINES (Conversational & Natural):
1. IMMEDIATE HOOK: The first sentence must be an irresistible pattern interrupt or bold, relatable statement that grips the viewer within 2 seconds.
2. NATURAL HUMAN CADENCE: Talk like a sharp, observant friend sharing an eye-opening realization. Vary your sentence structure and lengths naturally.
3. BANNED ROBOTIC CLICHÉS:
   - NEVER repeat robotic transition formulas like "Meanwhile", "Therefore", "Which is why", "And yet" across lines.
   - Do NOT sound like an essay or an AI template. Speak with genuine human flow.
   - Never use "In this video", "Welcome back", "Here is what you need to know", or "Did you know".
4. PUNCHY STORYTELLING: Describe real human behaviors, subtle micro-actions, and vivid everyday scenarios that the viewer instantly recognizes.
5. FINAL PAYOFF: End on an insightful, memorable punchline or thought-provoking takeaway.

PEXELS STOCK B-ROLL QUERY RULES:
For EVERY scene line, provide a tailored 'pexels_query' (2 to 4 keywords) optimized for high-quality stock video footage.
- Describe real, tangible visuals a camera can film (e.g., "woman checking phone secretly", "luxury sports car city night", "person smirking cafe", "man walking away in shadows").
- NEVER use abstract words like "concept", "jealousy", "idea".
- Keep every search query unique and visually distinct.

OUTPUT FORMAT:
Respond with valid JSON ONLY:
{{
  "scenes": [
    {{"line": "First natural spoken sentence...", "pexels_query": "concrete visual search query"}},
    {{"line": "Second natural spoken sentence...", "pexels_query": "different visual search query"}}
  ]
}}"""

    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "z-ai/glm-5.2",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Write the viral short-form script with Pexels queries for: {title}"}
            ],
            "max_tokens": 4096,
            "temperature": 0.85,
            "chat_template_kwargs": {"enable_thinking": False}
        },
        timeout=90
    )
    if r.ok:
        data = r.json()
        raw = data["choices"][0]["message"]["content"]
        clean = raw.replace(chr(96)*3 + "json", "").replace(chr(96)*3, "").strip()
        start_b = clean.find('{')
        end_b = clean.rfind('}')
        parsed = json.loads(clean[start_b:end_b+1])
        return parsed.get("scenes", [])
    return []

print("=== Generating Script 1 (Jealousy) ===")
sc1 = generate_test_script(title1)
print(f"Generated {len(sc1)} scenes:")
for i, s in enumerate(sc1):
    print(f"  [{i+1}] ({s['pexels_query']}): {s['line']}")

print("\n=== Generating Script 2 (Phone Features) ===")
sc2 = generate_test_script(title2)
print(f"Generated {len(sc2)} scenes:")
for i, s in enumerate(sc2):
    print(f"  [{i+1}] ({s['pexels_query']}): {s['line']}")
