from flask import Flask, request
import requests
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
RICHMENU_ID = "richmenu-ece55e5bf2da5f4883b35325a8c99246"

url = "https://api.line.me/v2/bot/user/all/richmenu/" + RICHMENU_ID

headers = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
}

r = requests.post(url, headers=headers)

print(r.status_code)
print(r.text)

def send_reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    requests.post(url, headers=headers, json=data)

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()

    for event in body.get("events", []):
        if event["type"] != "message":
            continue
        if event["message"]["type"] != "text":
            continue

        text = event["message"]["text"]
        reply_token = event["replyToken"]

        # リッチメニューの message をそのまま拾う
        if text == "一覧":
            send_reply(reply_token, "📋 一覧を押したね")
        elif text == "追加":
            send_reply(reply_token, "➕ 追加を押したね")
        else:
            send_reply(reply_token, "リッチメニューを使ってね")

    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)