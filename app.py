from flask import Flask, request
import os
import requests

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

tasks = []

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.json

    if "events" in body:
        for event in body["events"]:
            if event["type"] == "message" and event["message"]["type"] == "text":
                reply_token = event["replyToken"]
                user_message = event["message"]["text"]

                if user_message.startswith("予定"):
                    task = user_message.replace("予定", "").strip()
                    if task:
                        tasks.append(task)
                        reply_text = f"予定を追加したよ！\n・{task}"
                    else:
                        reply_text = "「予定 牛乳を買う」みたいに送ってね！"

                elif user_message.startswith("やること"):
                    task = user_message.replace("やること", "").strip()
                    if task:
                        tasks.append(task)
                        reply_text = f"やることを追加したよ！\n・{task}"
                    else:
                        reply_text = "「やること ゴミ出し」みたいに送ってね！"

                else:
                    reply_text = "予定を追加する時は\n「予定 ○○」または「やること ○○」と送ってね！"

                reply_message(reply_token, reply_text)

    return "OK", 200


def reply_message(reply_token, text):
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
