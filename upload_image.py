import requests
import os

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
RICHMENU_ID = "richmenu-2cfad97cc5a5d06f6419a14d75e7777a"
IMAGE_PATH = "richmenu.png"

url = f"https://api.line.me/v2/bot/richmenu/{RICHMENU_ID}/content"

headers = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "image/png"
}

with open(IMAGE_PATH, "rb") as f:
    r = requests.post(url, headers=headers, data=f)

print("status:", r.status_code)
print("response:", r.text)
