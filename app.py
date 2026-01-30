from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

TASK_FILE = "tasks.json"


# ----------------------------
# LINE返信
# ----------------------------
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


# ----------------------------
# タスク保存・読み込み
# ----------------------------
def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False)


tasks = load_tasks()


# ----------------------------
# 動作確認用ページ
# ----------------------------
@app.route("/")
def home():
    return "Bot is running!"


# ----------------------------
# LINE Webhook
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if "message" not in event:
            continue

        reply_token = event["replyToken"]
        message_type = event["message"]["type"]

        # =========================
        # テキストメッセージ処理
        # =========================
        if message_type == "text":
            user_message = event["message"]["text"]
            clean_message = user_message.replace("　", "").replace(" ", "").strip()

            # 予定追加
            if clean_message.startswith("予定"):
                task = user_message.replace("予定", "").strip()
                if task:
                    tasks.append(task)
                    save_tasks(tasks)
                    reply_text = f"予定『{task}』を追加しました！"
                else:
                    reply_text = "予定の内容も一緒に送ってね！"

            # やること追加
            elif clean_message.startswith("やること"):
                task = user_message.replace("やること", "").strip()
                if task:
                    tasks.append(task)
                    save_tasks(tasks)
                    reply_text = f"やること『{task}』を追加しました！"
                else:
                    reply_text = "やることの内容も送ってね！"

            # 一覧表示
            elif "一覧" in clean_message:
                if tasks:
                    task_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(tasks))
                    reply_text = f"現在の予定一覧です\n{task_list}"
                else:
                    reply_text = "今は予定は入っていません！"

            # タスク完了
            elif clean_message.startswith("完了"):
                number = clean_message.replace("完了", "").strip()
                if number.isdigit():
                    index = int(number) - 1
                    if 0 <= index < len(tasks):
                        done_task = tasks.pop(index)
                        save_tasks(tasks)
                        reply_text = f"『{done_task}』を完了にしました！"
                    else:
                        reply_text = "その番号の予定はありません！"
                else:
                    reply_text = "『完了 1』みたいに番号で教えてね！"

            else:
                reply_text = (
                    "予定を追加：『予定 ○○』『やること ○○』\n"
                    "一覧を見る：『一覧』\n"
                    "完了する：『完了 番号』"
                )

        # =========================
        # 画像メッセージ処理
        # =========================
        elif message_type == "image":
            reply_text = "画像を受け取りました！文字を読み取ります📸（次のステップでOCR追加）"

        else:
            reply_text = "未対応のメッセージです"

        send_reply(reply_token, reply_text)

    return "OK", 200


# ----------------------------
# Render用ポート設定
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)