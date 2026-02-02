from flask import Flask, request
import os
import requests
import json
from datetime import datetime

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
TASK_FILE = "tasks.json"

ADMIN_USERS = ["U179b29542e4d9d16aad9ee5b8a8eea18"]

QUICK_MENU = [
    {"type": "action", "action": {"type": "message", "label": "📋 一覧", "text": "一覧"}},
    {"type": "action", "action": {"type": "message", "label": "➕ 予定追加", "text": "予定追加モード"}},
    {"type": "action", "action": {"type": "message", "label": "🌍 全体予定追加", "text": "全体追加モード"}},
    {"type": "action", "action": {"type": "message", "label": "✅ 完了", "text": "完了モード"}},
    {"type": "action", "action": {"type": "message", "label": "❌ 削除", "text": "削除モード"}},
    {"type": "action", "action": {"type": "message", "label": "🧩 チェック作成", "text": "チェック作成モード"}},
    {"type": "action", "action": {"type": "message", "label": "📚 テンプレ", "text": "templates"}}
]

# ================= 送信 =================

def send_reply(reply_token, text, quick_reply=None):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    message = {"type": "text", "text": text}
    if quick_reply:
        message["quickReply"] = {"items": quick_reply}
    requests.post(url, headers=headers, json={"replyToken": reply_token, "messages": [message]})


def reply_flex(reply_token, alt_text, contents):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    data = {"replyToken": reply_token,
            "messages": [{"type": "flex", "altText": alt_text, "contents": contents}]}
    r = requests.post(url, headers=headers, json=data)
    print("Flex:", r.status_code, r.text)

# ================= データ =================

def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    data.setdefault("users", {})
    data.setdefault("global", [])
    data.setdefault("states", {})
    data.setdefault("maps", {})
    data.setdefault("checklists", {})
    return data


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

# ================= Flex一覧 =================

def build_unified_task_bubble(personal_tasks, global_tasks, user_id, tasks):
    body = [{"type": "text", "text": "📋 タスク一覧", "weight": "bold", "size": "lg"}]
    personal_map, global_map = [], []

    if personal_tasks:
        body.append({"type": "text", "text": "🗓 あなたの予定", "margin": "lg", "weight": "bold"})
        for i, t in enumerate(personal_tasks, 1):
            personal_map.append(tasks["users"][user_id].index(t))
            body.append({
                "type": "box","layout": "horizontal","margin": "sm",
                "contents": [
                    {"type": "button","style": "secondary","height": "sm",
                     "action": {"type": "message", "label": str(i), "text": str(i)}},
                    {"type": "text","text": t["text"],"wrap": True,"flex": 5,"margin": "md"}
                ]
            })

    if global_tasks:
        body.append({"type": "text", "text": "🌍 全体予定", "margin": "lg", "weight": "bold"})
        for i, t in enumerate(global_tasks, 1):
            global_map.append(tasks["global"].index(t))
            body.append({
                "type": "box","layout": "horizontal","margin": "sm",
                "contents": [
                    {"type": "button","style": "secondary","height": "sm",
                     "action": {"type": "message", "label": f"G{i}", "text": f"G{i}"}},
                    {"type": "text","text": t["text"],"wrap": True,"flex": 5,"margin": "md"}
                ]
            })

    tasks["maps"][user_id] = {"personal_map": personal_map, "global_map": global_map}
    save_tasks(tasks)

    return {"type": "bubble",
            "body": {"type": "box", "layout": "vertical", "contents": body}}

# ================= Webhook =================

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    tasks = load_tasks()

    for event in body.get("events", []):
        if event.get("message", {}).get("type") != "text":
            continue

        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = event["message"]["text"].strip()
        state = tasks["states"].get(user_id)

        tasks["users"].setdefault(user_id, [])
        tasks["checklists"].setdefault(user_id,
            {"templates": [], "editing": None, "active": None})

        checklists = tasks["checklists"][user_id]
        editing = checklists.get("editing")
        active = checklists.get("active")

        # ===== 一覧 =====
        if text == "一覧":
            personal = [t for t in tasks["users"][user_id] if t["status"] != "done"]
            global_t = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]
            if not personal and not global_t:
                send_reply(reply_token, "予定はまだありません！", QUICK_MENU)
            else:
                bubble = build_unified_task_bubble(personal, global_t, user_id, tasks)
                reply_flex(reply_token, "タスク一覧", bubble)
            continue

        # ===== チェックテンプレ作成 =====
        if text == "チェック作成モード":
            checklists["editing"] = {"name": None, "items": []}
            save_tasks(tasks)
            send_reply(reply_token, "テンプレ名を送ってね")
            continue

        if editing:
            if editing["name"] is None:
                editing["name"] = text
                save_tasks(tasks)
                send_reply(reply_token, "項目を1行ずつ送信。終わったら『保存』")
                continue

            if text == "保存":
                checklists["templates"].append(editing)
                checklists["editing"] = None
                save_tasks(tasks)
                send_reply(reply_token, f"テンプレ『{editing['name']}』保存完了！", QUICK_MENU)
                continue

            editing["items"].append(text)
            save_tasks(tasks)
            send_reply(reply_token, f"追加: {text}")
            continue

        # ===== テンプレ一覧 =====
        if text == "templates":
            temps = checklists["templates"]
            if not temps:
                send_reply(reply_token, "テンプレはまだ無いよ", QUICK_MENU)
            else:
                lines = "\n".join(f"{i+1}. {t['name']}" for i, t in enumerate(temps))
                send_reply(reply_token, f"テンプレ一覧\n{lines}", QUICK_MENU)
            continue

        # ===== チェック開始 =====
        if text.startswith("start "):
            idx = int(text.split()[1]) - 1
            template = checklists["templates"][idx]
            checklists["active"] = {
                "name": template["name"],
                "items": [{"text": i, "done": False} for i in template["items"]]
            }
            save_tasks(tasks)
            send_reply(reply_token, f"チェック『{template['name']}』開始！\nlistで表示")
            continue

        # ===== チェック表示 =====
        if text == "list" and active:
            lines = [f"{i+1}. {'✅' if x['done'] else '⬜'} {x['text']}"
                     for i, x in enumerate(active["items"])]
            send_reply(reply_token, f"🧾 {active['name']}\n" + "\n".join(lines))
            continue

        # ===== チェック完了 =====
        if text.startswith("done ") and active:
            idx = int(text.split()[1]) - 1
            active["items"][idx]["done"] = True
            save_tasks(tasks)
            send_reply(reply_token, "チェック完了！")
            continue

        # ===== チェック終了 =====
        if text == "finish" and active:
            checklists["active"] = None
            save_tasks(tasks)
            send_reply(reply_token, "チェック終了！", QUICK_MENU)
            continue

        send_reply(reply_token, "メニューから選んでね👇", QUICK_MENU)

    return "OK", 200


@app.route("/")
def home():
    return "Bot is running!"