from flask import Flask, request
import os
import requests
import json
from datetime import datetime

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
    res = requests.post(url, headers=headers, json=data)
    print("LINE status:", res.status_code, res.text)


def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("global", [])
            data.setdefault("states", {})
            data.setdefault("maps", {})   # ← 番号対応表はここ
            return data
    except:
        return {"users": {}, "global": [], "states": {}, "maps": {}}


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


@app.route("/")
def home():
    return "Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])
    tasks = load_tasks()

    for event in events:
        if "message" not in event or event["message"]["type"] != "text":
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]
        user_message = event["message"]["text"].strip()
        clean_message = user_message.replace("　", "").replace(" ", "")

        tasks["users"].setdefault(user_id, [])
        state = tasks["states"].get(user_id)

        # ================= 一覧 =================
        if clean_message == "一覧":
            reply_lines = []
            personal_map = []
            global_map = []

            personal_tasks = [t for t in tasks["users"][user_id] if t["status"] != "done"]
            if personal_tasks:
                reply_lines.append("🗓 あなたの予定")
                for i, t in enumerate(personal_tasks):
                    display_index = i + 1
                    personal_map.append(tasks["users"][user_id].index(t))
                    deadline = t.get("deadline")
                    if deadline:
                        reply_lines.append(f"{display_index}. ⬜ {t['text']}（⏰{deadline}）")
                    else:
                        reply_lines.append(f"{display_index}. ⬜ {t['text']}")

            global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]
            if global_tasks:
                reply_lines.append("\n🌍 全体予定")
                for i, t in enumerate(global_tasks):
                    display_index = i + 1
                    global_map.append(tasks["global"].index(t))
                    deadline = t.get("deadline")
                    if deadline:
                        reply_lines.append(f"G{display_index}. ⬜ {t['text']}（⏰{deadline}）")
                    else:
                        reply_lines.append(f"G{display_index}. ⬜ {t['text']}")

            if not reply_lines:
                reply_lines.append("予定はまだありません！")

            tasks["maps"][user_id] = {
                "personal_map": personal_map,
                "global_map": global_map
            }

            save_tasks(tasks)
            send_reply(reply_token, "\n".join(reply_lines), QUICK_MENU)
            continue

        # ================= モード開始 =================
        if clean_message == "予定追加モード":
            tasks["states"][user_id] = "add_personal"
            save_tasks(tasks)
            send_reply(reply_token, "予定を送ってね\n例: 2026-02-10 歯医者", None)
            continue

        if clean_message == "全体追加モード":
            tasks["states"][user_id] = "add_global"
            save_tasks(tasks)
            send_reply(reply_token, "全体予定を送ってね", None)
            continue

        if clean_message == "完了モード":
            tasks["states"][user_id] = "complete_wait"
            save_tasks(tasks)
            send_reply(reply_token, "完了する番号を送ってね（例: 1 G2）", None)
            continue

        if clean_message == "削除モード":
            tasks["states"][user_id] = "delete_wait"
            save_tasks(tasks)
            send_reply(reply_token, "削除する番号を送ってね（例: 1 G2）", None)
            continue

        # ================= 予定追加 =================
        if state in ["add_personal", "add_global"]:
            parts = user_message.split(" ", 1)
            deadline = None
            text = user_message

            try:
                possible_date = parts[0]
                datetime.strptime(possible_date, "%Y-%m-%d")
                if len(parts) == 2:
                    deadline = possible_date
                    text = parts[1]
            except:
                pass

            task = {"text": text, "deadline": deadline, "status": "pending"}

            if state == "add_personal":
                tasks["users"][user_id].append(task)
                reply = f"📝予定追加『{text}』"
            else:
                task["done_by"] = []
                tasks["global"].append(task)
                reply = f"🌍全体予定追加『{text}』"

            if deadline:
                reply += f"\n⏰締切: {deadline}"

            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, reply, QUICK_MENU)
            continue

        # ================= 完了処理 =================
        if state == "complete_wait":
            maps = tasks.get("maps", {}).get(user_id, {})
            nums = user_message.split()

            for n in nums:
                if n.startswith("G") and n[1:].isdigit():
                    idx = int(n[1:]) - 1
                    if 0 <= idx < len(maps.get("global_map", [])):
                        real_index = maps["global_map"][idx]
                        tasks["global"][real_index].setdefault("done_by", []).append(user_id)

                elif n.isdigit():
                    idx = int(n) - 1
                    if 0 <= idx < len(maps.get("personal_map", [])):
                        real_index = maps["personal_map"][idx]
                        tasks["users"][user_id][real_index]["status"] = "done"

            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, "✅ 完了にしたよ！", QUICK_MENU)
            continue

        # ================= 削除処理 =================
        if state == "delete_wait":
            maps = tasks.get("maps", {}).get(user_id, {})
            nums = sorted(user_message.split(), reverse=True)

            for n in nums:
                if n.startswith("G") and n[1:].isdigit() and user_id in ADMIN_USERS:
                    idx = int(n[1:]) - 1
                    if 0 <= idx < len(maps.get("global_map", [])):
                        real_index = maps["global_map"][idx]
                        tasks["global"].pop(real_index)

                elif n.isdigit():
                    idx = int(n) - 1
                    if 0 <= idx < len(maps.get("personal_map", [])):
                        real_index = maps["personal_map"][idx]
                        tasks["users"][user_id].pop(real_index)

            tasks["states"][user_id] = None
            save_tasks(tasks)
            send_reply(reply_token, "🗑 削除したよ！", QUICK_MENU)
            continue

        send_reply(reply_token, "下のメニューから操作してね👇", QUICK_MENU)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)