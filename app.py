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

                # 一覧表示
    clean_message = user_message.replace("　", "").replace(" ", "").strip()

elif "一覧" in clean_message:
                    if tasks:
                        task_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])
                        reply_text = f"現在の予定一覧です\n{task_list}"
                    else:
                        reply_text = "今は予定は入っていません！"

                # 🆕 タスク完了
                elif user_message.startswith("完了"):
                    number = user_message.replace("完了", "").strip()
                    if number.isdigit():
                        index = int(number) - 1
                        if 0 <= index < len(tasks):
                            done_task = tasks.pop(index)
                            reply_text = f"「{done_task}」を完了にしました！"
                        else:
                            reply_text = "その番号の予定はありません！"
                    else:
                        reply_text = "「完了 1」みたいに番号で教えてね！"

                else:
                    reply_text = (
                        "予定を追加：『予定 ○○』『やること ○○』\n"
                        "一覧を見る：『一覧』\n"
                        "完了する：『完了 番号』"
                    )

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