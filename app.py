from flask import Flask, request
import requests
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

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
        reply_token = event.get("replyToken")

        if event["type"] == "postback":
            data = event["postback"]["data"]

            if data == "#menu_list":
                send_reply(reply_token, "📅 予定表")
            elif data == "#menu_add":
                send_reply(reply_token, "➕ 追加")
            elif data == "#menu_check":
                send_reply(reply_token, "✅ チェック")
            elif data == "#menu_other":
                send_reply(reply_token, "⚙️ その他")
            else:
                send_reply(reply_token, "未定義メニュー")

        elif event["type"] == "message":
            send_reply(reply_token, "メニューから操作してね")

    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)