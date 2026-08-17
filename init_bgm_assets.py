import os, shutil, subprocess

os.makedirs("public/audio", exist_ok=True)

# 1. Copy burden_piano to dramatic_piano.mp3 if it exists
src_piano = r"C:\Users\DELL\.gemini\antigravity\brain\4f6f29a4-c6a5-4165-9458-b227d8a62073\burden_piano.mp3"
if os.path.exists(src_piano):
    shutil.copy(src_piano, "public/audio/dramatic_piano.mp3")
    print("Copied burden_piano to public/audio/dramatic_piano.mp3")

# 2. Generate atmospheric background synth audio for lofi, dark suspense, upbeat tech, ambient synth
tracks = {
    "lofi_chill.mp3": "anoisesrc=d=90:c=pink:r=44100:a=0.03,lowpass=f=800,volume=0.8",
    "dark_suspense.mp3": "sine=f=55:d=90,lowpass=f=200,volume=0.9",
    "upbeat_tech.mp3": "sine=f=220:d=90,volume=0.6",
    "ambient_synth.mp3": "sine=f=110:d=90,volume=0.7"
}

for name, filter_expr in tracks.items():
    out_p = os.path.join("public/audio", name)
    if not os.path.exists(out_p):
        cmd = f'ffmpeg -y -f lavfi -i "{filter_expr}" -c:a mp3 -b:a 128k "{out_p}"'
        subprocess.run(cmd, shell=True, capture_output=True)
        print(f"Generated {out_p}")

print("Audio directory contents:", os.listdir("public/audio"))
