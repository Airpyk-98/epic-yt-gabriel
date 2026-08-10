
> PEXELS_KERNEL_TEMPLATE = """import os
  import subprocess
  import sys
  import builtins
  import requests
  import json
  import time
  import shutil
  
  def custom_print(*args, **kwargs):
      msg = " ".join(str(a) for a in args)
      builtins.print(*args, **kwargs)
      try:
          requests.post("https://epic-yt-gabriel.onrender.com/api/kaggle_log", json={"job_id": "___JOB_ID___", 
"message": msg, "token": "epic_kaggle_secret_99"}, timeout=3)
      except:
          pass
  print = custom_print
  
  def run_cmd(cmd):
      print(f"Executing: {cmd}", flush=True)
      res = subprocess.run(cmd, shell=True)
      return res
  
  print("=== STARTING PEXELS STOCK B-ROLL PIPELINE ===", flush=True)
  
  hf_token = ___HF_TOKEN___
  if hf_token and len(hf_token) > 5:
      os.environ["HF_TOKEN"] = hf_token
  
  hf_repo = ___HF_REPO___
  job_id = ___JOB_ID___
  script_text = ___SCRIPT_TEXT___
  voice = ___VOICE___
  segments_json = ___PEXELS_SEGMENTS_JSON___
  PEXELS_API_KEY = ___PEXELS_API_KEY___
  
  # 1. SETUP AUDIO AND CAPTURE WORD TIMINGS
  run_cmd("pip install -q edge-tts moviepy")
  print(f"Generating studio voiceover and extracting word boundaries...", flush=True)
  
  with open("/kaggle/working/tts_script.txt", "w", encoding="utf-8") as f:
      f.write(script_text)
  
  import asyncio, edge_tts
  word_timings = []
  
  async def generate_audio_and_timings():
      comm = edge_tts.Communicate(script_text, voice)
      await comm.save("/kaggle/working/input.wav")
      
      comm_events = edge_tts.Communicate(script_text, voice)
      async for event in comm_events.stream():
          if event["type"] == "WordBoundary":
              start_sec = event["offset"] / 10000000.0
              word_dur = event["duration"] / 10000000.0
              word_timings.append({"word": event["text"], "start": start_sec, "end": start_sec + word_dur})
              
  asyncio.run(generate_audio_and_timings())
  print(f"Captured {len(word_timings)} word timings.", flush=True)
  
  # 2. MATCH SEGMENTS TO AUDIO TIMINGS
  try:
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
          segments = [{"text": script_text, "keyword": "cinematic"}]
  
  print("Calculating precise segment durations...", flush=True)
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
          current_word_idx = end_word_idx + 1
  
  # 3. FETCH PEXELS VIDEOS
  print("Fetching B-Roll from Pexels API...", flush=True)
  headers = {"Authorization": PEXELS_API_KEY}
  video_files = []
  
  aspect = ___ASPECT_RATIO___
  orientation = "portrait" if aspect == "9:16" else "landscape" if aspect == "16:9" else "square"
  
  for i, seg in enumerate(segments):
      kw = seg['keyword']
      dur = seg['duration']
      print(f"Searching Pexels for: '{kw}' (Duration: {dur:.2f}s)", flush=True)
      
      url = f"https://api.pexels.com/videos/search?query={kw}&per_page=5&orientation={orientation}&size=medium"
      try:
          resp = requests.get(url, headers=headers, timeout=10)
          resp.raise_for_status()
          data = resp.json()
          if not data.get("videos"):
              resp = 
requests.get(f"https://api.pexels.com/videos/search?query=nature&per_page=1&orientation={orientation}", 
headers=headers)
              data = resp.json()
              
          video_url = None
          for v in data.get("videos", []):
              if v["duration"] >= dur:
                  for file_obj in v["video_files"]:
                      if file_obj["quality"] == "hd":
                          video_url = file_obj["link"]
                          break
                  if video_url: break
                  
          if not video_url and data.get("videos"):
              video_url = data["videos"][0]["video_files"][0]["link"]
              
          out_name = f"/kaggle/working/clip_{i}.mp4"
          v_data = requests.get(video_url).content
          with open(out_name, "wb") as f:
              f.write(v_data)
              
          video_files.append((out_name, dur))
      except Exception as e:
          print(f"Failed to fetch video for '{kw}': {e}", flush=True)
  
  # 4. ASSEMBLE WITH MOVIEPY
  print("Assembling timeline with MoviePy...", flush=True)
  from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, vfx
  
  clips = []
  target_w, target_h = (1080, 1920) if orientation == "portrait" else (1920, 1080)
  
  for fpath, dur in video_files:
      if not os.path.exists(fpath): continue
      clip = VideoFileClip(fpath)
      if clip.duration < dur:
          clip = clip.fx(vfx.loop, duration=dur)
      else:
          clip = clip.subclip(0, dur)
          
      clip = clip.resize(height=target_h)
      if clip.w < target_w:
          clip = clip.resize(width=target_w)
      
      x_center = clip.w / 2
      y_center = clip.h / 2
      clip = clip.crop(x1=x_center - target_w/2, y1=y_center - target_h/2, x2=x_center + target_w/2, y2=y_center + 
target_h/2)
      clips.append(clip)
  
  if not clips:
      print("ERROR: No clips were successfully generated.", flush=True)
      sys.exit(1)
  
  final_video = concatenate_videoclips(clips, method="compose")
  audio_clip = AudioFileClip("/kaggle/working/input.wav")
  final_video = final_video.set_audio(audio_clip)
  
  final_output = "/kaggle/working/raw_pexels.mp4"
  final_video.write_videofile(final_output, fps=24, codec="libx264", audio_codec="aac")
  
  for c in clips: c.close()
  final_video.close()
  audio_clip.close()
  
  # 5. POST-PROCESSING (Subtitles, BGM)
  current_video_path = final_output
  has_bgm = False
  bgm_repo_path = ___BGM_REPO_PATH___
  if bgm_repo_path and hf_repo:


