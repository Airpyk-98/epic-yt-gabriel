import re, json

# What JS template literal emitted to Python when given `[^"\\]`:
bad_regex = r'\{\s*"line"\s*:\s*"((?:\\.|[^"\])*)"'
try:
    re.compile(bad_regex)
except Exception as e:
    print("Caught exact error:", type(e), e)

# How to parse JSON safely without complex character sets:
def clean_and_parse(resp_c):
    ai_scenes = []
    # Strip markdown backticks
    clean = re.sub(r'```(?:json)?', '', resp_c).strip()
    
    # Locate first '{' and last '}'
    start_idx = clean.find('{')
    end_idx = clean.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = clean[start_idx:end_idx+1]
        try:
            parsed = json.loads(json_str)
            for item in parsed.get("scenes", []):
                l = str(item.get("line", "")).strip()
                q = str(item.get("pexels_query", "")).strip()
                if l:
                    ai_scenes.append({"line": l, "pexels_query": q})
        except Exception as err:
            print("Direct JSON error:", err)
            
    # Simple line-by-line fallback if JSON was broken
    if not ai_scenes:
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        for line in lines:
            if '"line":' in line and '"pexels_query":' in line:
                m_l = re.search(r'"line"\s*:\s*"([^"]+)"', line)
                m_q = re.search(r'"pexels_query"\s*:\s*"([^"]+)"', line)
                if m_l:
                    l_val = m_l.group(1).strip()
                    q_val = m_q.group(1).strip() if m_q else "lifestyle"
                    ai_scenes.append({"line": l_val, "pexels_query": q_val})
    return ai_scenes

sample = """```json
{
  "scenes": [
    {
      "line": "8 signs someone is secretly jealous of you. Number 1: They give you backhanded compliments.",
      "pexels_query": "two women fake smiling at each other"
    },
    {
      "line": "Meanwhile, they secretly celebrate when you stumble.",
      "pexels_query": "stressed businessman office"
    }
  ]
}
```"""

res = clean_and_parse(sample)
print("Parsed scenes count:", len(res))
for s in res:
    print(" ->", s)
