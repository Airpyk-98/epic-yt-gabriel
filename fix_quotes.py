with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_key = 'pexels_key = os.environ.get("PEXELS_API_KEY", "y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K")'
new_key = 'pexels_key = os.environ.get("PEXELS_API_KEY", "y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K").strip().strip(\'"\').strip(\"'\")'

if old_key in content:
    content = content.replace(old_key, new_key)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Stripped quotes from PEXELS_API_KEY")
else:
    print("Could not find the exact line.")
