from flask import Flask, request
import os
import requests
import json
import shutil

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
TASK_FILE = "tasks.json"

# 🔐 管理者ユーザーID
ADMIN_USERS = ["U179b29542e4d9d16aad9ee5b8a8eea18"]

# 🎛 クイックメニュー
QUICK_MENU = [
    {"type": "action", "action": {"type": "message", "label": "📋 一覧", "text": "一覧"}},
    {"type": "action", "action": {"type": "message", "label": "🌍 全体予定追加", "text": "全体予定 "}},
    {"type": "action", "action": {"type": "message", "label": "🧍 予定追加", "text": "予定 "}}
]


# ---------------- LINE返信 ----------------
def send_reply(reply_token, text, quick_reply=None):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    message = {"type": "text", "text": text}

    if quick_reply:
        message["quickReply"] = {"items": quick_reply}

    data = {"replyToken": reply_token, "messages": [message]}
    requests.post(url, headers=headers, json=data)


# ---------------- データ管理 ----------------
def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data or "global" not in data:
                return {"users": {}, "global": []}
            return data
    except:
        return {"users": {}, "global": []}


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


tasks = load_tasks()


# ---------------- Web ----------------
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

        if user_id not in tasks["users"]:
            tasks["users"][user_id] = []

        # 🖼️ 画像保存
        if message_type == "image":
            message_id = event["message"]["id"]
            headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
            image_url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
            response = requests.get(image_url, headers=headers, stream=True)

            if response.status_code == 200:
                with open(f"image_{message_id}.jpg", "wb") as f:
                    shutil.copyfileobj(response.raw, f)
                send_reply(reply_token, "画像を保存しました！")
            else:
                send_reply(reply_token, "画像の取得に失敗しました…")
            continue

        # 💬 テキスト処理
        if message_type == "text":
            user_message = event["message"]["text"]
            clean_message = user_message.replace("　", "").replace(" ", "").strip()

            # 🆔 自分のID
            if clean_message == "自分のID":
                reply_text = f"あなたのuserIdはこちら👇\n{user_id}"

            # 🌍 全体予定追加
            elif clean_message.startswith("全体予定"):
                task_text = user_message.replace("全体予定", "").strip()
                if task_text:
                    tasks["global"].append({"text": task_text, "creator": user_id, "done_by": []})
                    save_tasks(tasks)
                    reply_text = f"🌍全体予定『{task_text}』を追加しました！"
                else:
                    reply_text = "全体予定の内容も送ってね！"

            # 🧍 個人予定追加
            elif clean_message.startswith("予定"):
                task_text = user_message.replace("予定", "").strip()
                if task_text:
                    tasks["users"][user_id].append({"text": task_text, "status": "pending"})
                    save_tasks(tasks)
                    reply_text = f"予定『{task_text}』を追加しました！"
                else:
                    reply_text = "予定の内容も送ってね！"

            # 📋 一覧
            elif clean_message == "一覧":
                reply_lines = []

                user_tasks = tasks["users"].get(user_id, [])
                global_tasks = tasks.get("global", [])

                if user_tasks:
                    reply_lines.append("🗓 あなたの予定")
                    for i, t in enumerate(user_tasks):
                        if t["status"] != "done":
                            reply_lines.append(f"{i+1}. ⬜ {t['text']}")

                if global_tasks:
                    reply_lines.append("\n🌍 全体予定")
                    for i, t in enumerate(global_tasks):
                        if user_id not in t.get("done_by", []):
                            reply_lines.append(f"G{i+1}. ⬜ {t['text']}")

                reply_text = "\n".join(reply_lines) if reply_lines else "予定はまだありません！"

            # ✅ 完了
            elif clean_message.startswith("完了"):
                number = clean_message.replace("完了", "").strip()

                if number.startswith("G") and number[1:].isdigit():
                    index = int(number[1:]) - 1
                    if 0 <= index < len(tasks["global"]):
                        if user_id not in tasks["global"][index]["done_by"]:
                            tasks["global"][index]["done_by"].append(user_id)
                            save_tasks(tasks)
                        reply_text = "この全体予定を完了にしました！"
                    else:
                        reply_text = "その番号の全体予定はありません！"

                elif number.isdigit():
                    index = int(number) - 1
                    if 0 <= index < len(tasks["users"][user_id]):
                        tasks["users"][user_id][index]["status"] = "done"
                        save_tasks(tasks)
                        reply_text = "あなたの予定を完了にしました！"
                    else:
                        reply_text = "その番号の予定はありません！"
                else:
                    reply_text = "『完了 1』や『完了 G1』みたいに送ってね！"

            # 🛠 管理者：完了者確認
            elif clean_message.startswith("確認"):
                if user_id not in ADMIN_USERS:
                    reply_text = "このコマンドは管理者のみ使えます🔒"
                else:
                    number = clean_message.replace("確認", "").strip()
                    if number.startswith("G") and number[1:].isdigit():
                        index = int(number[1:]) - 1
                        if 0 <= index < len(tasks["global"]):
                            done_users = tasks["global"][index].get("done_by", [])
                            reply_text = "完了者一覧:\n" + "\n".join(done_users) if done_users else "まだ誰も完了していません"
                        else:
                            reply_text = "その番号の全体予定はありません！"
                    else:
                        reply_text = "『確認 G1』みたいに送ってね！"

            # ❌ 削除
            elif clean_message.startswith("削除"):
                number = clean_message.replace("削除", "").strip()

                if number.startswith("G") and number[1:].isdigit():
                    if user_id not in ADMIN_USERS:
                        reply_text = "全体予定の削除は管理者のみです🔒"
                    else:
                        index = int(number[1:]) - 1
                        if 0 <= index < len(tasks["global"]):
                            deleted = tasks["global"].pop(index)
                            save_tasks(tasks)
                            reply_text = f"🌍全体予定『{deleted['text']}』を削除しました！"
                        else:
                            reply_text = "その番号の全体予定はありません！"

                elif number.isdigit():
                    index = int(number) - 1
                    if 0 <= index < len(tasks["users"][user_id]):
                        deleted = tasks["users"][user_id].pop(index)
                        save_tasks(tasks)
                        reply_text = f"予定『{deleted['text']}』を削除しました！"
                    else:
                        reply_text = "その番号の予定はありません！"
                else:
                    reply_text = "『削除 1』や『削除 G1』みたいに送ってね！"

            else:
                reply_text = "メニューから操作してね！"

            send_reply(reply_token, reply_text, QUICK_MENU)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
