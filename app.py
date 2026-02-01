from datetime import datetime
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

# 📱 クイックメニュー
QUICK_MENU = [
    {"type": "action", "action": {"type": "message", "label": "📋 一覧", "text": "一覧"}},
    {"type": "action", "action": {"type": "message", "label": "➕ 予定追加", "text": "予定追加モード"}},
    {"type": "action", "action": {"type": "message", "label": "🌍 全体予定追加", "text": "全体追加モード"}},
    {"type": "action", "action": {"type": "message", "label": "✅ 完了", "text": "完了モード"}},
    {"type": "action", "action": {"type": "message", "label": "❌ 削除", "text": "削除モード"}}
]


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


def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "users" not in data: data["users"] = {}
            if "global" not in data: data["global"] = []
            if "states" not in data: data["states"] = {}
            return data
    except:
        return {"users": {}, "global": [], "states": {}}


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


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

        if user_id not in tasks["users"]:
            tasks["users"][user_id] = []

        if message_type != "text":
            continue

        user_message = event["message"]["text"]
        clean_message = user_message.replace("　", "").replace(" ", "").strip()

        state = tasks["states"].get(user_id)

        # ===== モード処理 =====
        if state == "add_task":
            tasks["users"][user_id].append({"text": user_message, "status": "pending"})
            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, f"予定『{user_message}』を追加したよ！", QUICK_MENU)
            continue

        if state == "add_global":
            tasks["global"].append({"text": user_message, "creator": user_id, "done_by": []})
            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, f"🌍全体予定『{user_message}』を追加！", QUICK_MENU)
            continue

        if state == "complete_mode":
            numbers = user_message.split()
            for num in numbers:
                if num.startswith("G") and num[1:].isdigit():
                    idx = int(num[1:]) - 1
                    if 0 <= idx < len(tasks["global"]):
                        if user_id not in tasks["global"][idx]["done_by"]:
                            tasks["global"][idx]["done_by"].append(user_id)
                elif num.isdigit():
                    idx = int(num) - 1
                    if 0 <= idx < len(tasks["users"][user_id]):
                        tasks["users"][user_id][idx]["status"] = "done"

            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, "まとめて完了にしたよ！", QUICK_MENU)
            continue

        if state == "delete_mode":
            numbers = sorted(user_message.split(), reverse=True)
            for num in numbers:
                if num.startswith("G") and num[1:].isdigit() and user_id in ADMIN_USERS:
                    idx = int(num[1:]) - 1
                    if 0 <= idx < len(tasks["global"]):
                        tasks["global"].pop(idx)
                elif num.isdigit():
                    idx = int(num) - 1
                    if 0 <= idx < len(tasks["users"][user_id]):
                        tasks["users"][user_id].pop(idx)

            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, "まとめて削除したよ！", QUICK_MENU)
            continue

        # ===== モード開始コマンド =====
        if clean_message == "予定追加モード":
            state == "add_task":
            parts = user_message.split(" ", 1)
            
            if len(parts) == 2:
                date_str, text = parts
                try:
                deadline = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
                tasks["users"][user_id].append({
                "text": text,
                "status": "pending",
                "deadline": deadline
                })
                reply = f"予定『{text}』を追加！📅締切: {deadline}"
                except:
                reply = "日付は YYYY-MM-DD 形式で送ってね！例: 2026-02-10 会議"
            else:
                reply = "『日付 内容』の順で送ってね！例: 2026-02-10 会議"
                
            tasks["states"][user_id] = None              
            save_tasks(tasks)
            send_reply(reply_token, "追加したい予定を送ってね！", QUICK_MENU)

        elif clean_message == "全体追加モード":
            tasks["states"][user_id] = "add_global"
            save_tasks(tasks)
            send_reply(reply_token, "追加する全体予定を送ってね！", QUICK_MENU)

        elif clean_message == "完了モード":
            tasks["states"][user_id] = "complete_mode"
            save_tasks(tasks)
            send_reply(reply_token, "完了する番号をスペース区切りで送ってね（例: 1 3 G2）", QUICK_MENU)

        elif clean_message == "削除モード":
            tasks["states"][user_id] = "delete_mode"
            save_tasks(tasks)
            send_reply(reply_token, "削除する番号をスペース区切りで送ってね", QUICK_MENU)

        # ===== 一覧 =====
        elif clean_message == "一覧":
            user_tasks = tasks["users"].get(user_id, [])
            global_tasks = tasks.get("global", [])
            reply_lines = []

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
            send_reply(reply_token, reply_text, QUICK_MENU)

        else:
            send_reply(reply_token, "下のメニューから操作してね👇", QUICK_MENU)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)