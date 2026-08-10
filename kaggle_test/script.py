import requests
print("Testing Pexels from Kaggle...")
res = requests.get('https://api.pexels.com/videos/search?query=test', headers={'Authorization': 'y8mqRFiw48HrLy8zgD6dQxdOvr2On4sjp8c22KbcFsakYnOPVK7rK0K'})
print(f'Status: {res.status_code}, Response: {res.text}')
