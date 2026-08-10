import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the fallback logic for JSON parsing in the template
old_json_fallback = '''try:
    segments = json.loads(segments_json)
except Exception as e:
    print(f"Failed to parse segments JSON: {e}. Falling back to default split.", flush=True)
    segments = [{"text": script_text, "keyword": "cinematic"}]'''

new_json_fallback = '''try:
    segments = json.loads(segments_json)
    if not segments: raise ValueError("Empty segments")
except Exception as e:
    print(f"Failed to parse segments JSON: {e}. Falling back to heuristic split.", flush=True)
    import re
    sentences = re.split(r'(?<=[.!?]) +', script_text)
    segments = []
    for s in sentences:
        if not s.strip(): continue
        words = [w for w in s.replace(",", "").replace(".", "").split() if len(w) > 4]
        kw = words[0] if words else "cinematic"
        segments.append({"text": s, "keyword": kw})
    if not segments:
        segments = [{"text": script_text, "keyword": "cinematic"}]'''

content = content.replace(old_json_fallback, new_json_fallback)

# 2. Update the word_timings logic in the template
old_timings_logic = '''print("Calculating precise segment durations...", flush=True)
current_word_idx = 0
for i, seg in enumerate(segments):
    seg_words = seg['text'].split()
    if not seg_words or current_word_idx >= len(word_timings):
        seg['start'] = word_timings[-1]['end'] if word_timings else 0
        seg['end'] = word_timings[-1]['end'] if word_timings else 0
        seg['duration'] = 0.1
        continue
        
    start_time = word_timings[current_word_idx]['start']
    end_word_idx = min(current_word_idx + len(seg_words) - 1, len(word_timings) - 1)
    end_time = word_timings[end_word_idx]['end']
    
    if i == len(segments) - 1:
        end_time = word_timings[-1]['end']
        
    seg['start'] = start_time
    seg['end'] = end_time
    seg['duration'] = max(0.5, end_time - start_time)
    current_word_idx = end_word_idx + 1'''

new_timings_logic = '''print("Calculating precise segment durations...", flush=True)
from moviepy.editor import AudioFileClip
audio_clip = AudioFileClip("/kaggle/working/input.wav")
total_dur = audio_clip.duration

if not word_timings:
    print("WARNING: Edge-TTS emitted no WordBoundary events. Using proportional duration fallback.", flush=True)
    total_words = sum(len(seg['text'].split()) for seg in segments)
    current_time = 0
    for seg in segments:
        seg_dur = (len(seg['text'].split()) / max(total_words, 1)) * total_dur
        seg['start'] = current_time
        seg['end'] = current_time + seg_dur
        seg['duration'] = max(0.5, seg_dur)
        current_time += seg_dur
else:
    current_word_idx = 0
    for i, seg in enumerate(segments):
        seg_words = seg['text'].split()
        if not seg_words or current_word_idx >= len(word_timings):
            seg['start'] = word_timings[-1]['end'] if word_timings else 0
            seg['end'] = word_timings[-1]['end'] if word_timings else 0
            seg['duration'] = 0.1
            continue
            
        start_time = word_timings[current_word_idx]['start']
        end_word_idx = min(current_word_idx + len(seg_words) - 1, len(word_timings) - 1)
        end_time = word_timings[end_word_idx]['end']
        
        if i == len(segments) - 1:
            end_time = word_timings[-1]['end']
            
        seg['start'] = start_time
        seg['end'] = end_time
        seg['duration'] = max(0.5, end_time - start_time)
        current_word_idx = end_word_idx + 1'''

content = content.replace(old_timings_logic, new_timings_logic)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated main.py locally.")
