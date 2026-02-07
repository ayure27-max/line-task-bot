import requests
import os
import json

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

url = "https://api.line.me/v2/bot/richmenu"

headers = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

richmenu = {
    "size": {
        "width": 2500,
        "height": 1686
    },
    "selected": True,
    "name": "main-menu",
    "chatBarText": "メニュー",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=list"
            }
        },
        {
            "bounds": {"x": 1250, "y": 0, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=add"
            }
        },
        {
            "bounds": {"x": 0, "y": 843, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=check"
            }
        },
        {
            "bounds": {"x": 1250, "y": 843, "width": 1250, "height": 843},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=other"
            }
        }
    ]
}

r = requests.post(url, headers=headers, json=richmenu)

print("status:", r.status_code)
print("response:", r.text)

if r.status_code == 200:
    richmenu_id = r.json()["richMenuId"]
    print("RICHMENU_ID =", richmenu_id)
