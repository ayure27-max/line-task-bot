from flask import Flask, request
import os
import requests
import json
import shutil

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
TASK_FILE = "tasks.json"


def send_reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=data)


def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False)


tasks = load_tasks()


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if "message" not in event:
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]
        message_type = event["message"]["type"]

        if user_id not in tasks:
            tasks[user_id] = []

        # ---------------- 画像メッセージ ----------------
        if message_type == "image":
            message_id = event["message"]["id"]

            headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
            image_url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
            response = requests.get(image_url, headers=headers, stream=True)

            if response.status_code == 200:
                file_path = f"image_{message_id}.jpg"
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)
                reply_text = "画像を保存しました！"
            else:
                reply_text = "画像の取得に失敗しました…"

            send_reply(reply_token, reply_text)
            continue

        # ---------------- テキストメッセージ ----------------
        if message_type == "text":
            user_message = event["message"]["text"]
            clean_message = user_message.replace("　", "").replace(" ", "").strip()

            if clean_message.startswith("予定"):
                task = user_message.replace("予定", "").strip()
                if task:
                    tasks[user_id].append(task)
                    save_tasks(tasks)
                    reply_text = f"予定『{task}』を追加しました！"
                else:
                    reply_text = "予定の内容も送ってね！"

            elif "一覧" in clean_message:
                user_tasks = tasks.get(user_id, [])
                if user_tasks:
                    task_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(user_tasks))
                    reply_text = f"あなたの予定一覧です\n{task_list}"
                else:
                    reply_text = "あなたの予定はまだありません！"

            elif clean_message.startswith("完了"):
                number = clean_message.replace("完了", "").strip()
                user_tasks = tasks.get(user_id, [])

                if number.isdigit():
                    index = int(number) - 1
                    if 0 <= index < len(user_tasks):
                        done_task = user_tasks.pop(index)
                        save_tasks(tasks)
                        reply_text = f"『{done_task}』を完了にしました！"
                    else:
                        reply_text = "その番号の予定はありません！"
                else:
                    reply_text = "『完了 1』みたいに番号で教えてね！"

            else:
                reply_text = "『予定 ○○』『一覧』『完了 1』などと送ってね"

            send_reply(reply_token, reply_text)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)