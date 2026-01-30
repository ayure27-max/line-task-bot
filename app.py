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
                user_message = event["message"]["text"].strip()

                # 予定追加
                if user_message.startswith("予定"):
                    task = user_message[2:].strip()
                    if task:
                        tasks.append(task)
                        reply_text = f"予定「{task}」を追加しました！"
                    else:
                        reply_text = "予定の内容も一緒に送ってね！"

                # やること追加
                elif user_message.startswith("やること"):
                    task = user_message.replace("やること", "").strip()
                    if task:
                        tasks.append(task)
                        reply_text = f"やること「{task}」を追加しました！"
                    else:
                        reply_text = "やることの内容も送ってね！"

                # 一覧表示 ← 🆕追加部分
                elif user_message == "一覧":
                    if tasks:
                        task_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])
                        reply_text = f"現在の予定一覧です\n{task_list}"
                    else:
                        reply_text = "今は予定は入っていません！"

                else:
                    reply_text = "予定を追加する時は\n「予定 ○○」または「やること ○○」\n一覧を見る時は「一覧」と送ってね！"

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