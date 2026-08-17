import json, re

def parse_ai_response(resp_c, finish_reason="stop", model_name="z-ai/glm-5.2"):
    ai_scenes = []
    # Strip markdown code blocks
    clean_c = re.sub(r'```(?:json)?\s*', '', resp_c).strip()
    
    # 1. Try standard full JSON parse first
    json_match = re.search(r'\{[\s\S]*"scenes"[\s\S]*\}', clean_c)
    if json_match:
        try:
            parsed_j = json.loads(json_match.group(0))
            for sc_item in parsed_j.get("scenes", []):
                l_val = str(sc_item.get("line", "")).strip()
                q_val = str(sc_item.get("pexels_query", "")).strip()
                if l_val:
                    ai_scenes.append({"line": l_val, "pexels_query": q_val})
            if ai_scenes:
                print(f"✅ Method 1 (json.loads) parsed {len(ai_scenes)} scenes")
                return ai_scenes
        except Exception as e:
            print("Method 1 notice:", e)

    # 2. Try truncated / partial JSON repair if JSON was cut off
    if not ai_scenes:
        # Find all complete {"line": ..., "pexels_query": ...} items
        items = re.findall(r'\{\s*"line"\s*:\s*"((?:\\.|[^"\\])*)"\s*,\s*"pexels_query"\s*:\s*"((?:\\.|[^"\\])*)"\s*\}', clean_c)
        for l_val, q_val in items:
            l_val = l_val.replace('\\"', '"').replace('\\n', ' ').strip()
            q_val = q_val.replace('\\"', '"').strip()
            if l_val:
                ai_scenes.append({"line": l_val, "pexels_query": q_val})
        if ai_scenes:
            print(f"✅ Method 2 (regex repair) parsed {len(ai_scenes)} scenes")
            return ai_scenes

    return ai_scenes

# Test with various outputs
sample_glm = """```json
{
  "scenes": [
    {
      "line": "8 signs someone is secretly jealous of you. Number 8: They give you backhanded compliments.",
      "pexels_query": "two women fake smiling"
    },
    {
      "line": "They'll say \\"You're brave\\", which is why you shouldn't trust them.",
      "pexels_query": "whispering secret office"
    }
  ]
}
```"""

sample_truncated = """{
  "scenes": [
    {
      "line": "8 signs someone is secretly jealous of you. Number 1: They copy your style.",
      "pexels_query": "person shopping clothes"
    },
    {
      "line": "Meanwhile, they pretend it was their idea all along.",
      "pexels_query": "confident businesswoman"
    },
    {
      "line": "They secretly"
"""

print("Testing sample GLM:")
res1 = parse_ai_response(sample_glm)
print("Result 1 scenes:", len(res1))

print("\nTesting sample truncated:")
res2 = parse_ai_response(sample_truncated, finish_reason="length")
print("Result 2 scenes:", len(res2))
