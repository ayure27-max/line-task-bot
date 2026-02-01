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
    {"type": "action", "action": {"type": "message", "label": "❌ 削除", "text": "削除モード"}}
]


def reply_flex(reply_token, alt_text, bubble):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    data = {
        "replyToken": reply_token,
        "messages": [{
            "type": "flex",
            "altText": alt_text,
            "contents": bubble
        }]
    }
    requests.post(url, headers=headers, json=data)


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
            data.setdefault("users", {})
            data.setdefault("global", [])
            data.setdefault("states", {})
            data.setdefault("maps", {})
            return data
    except:
        return {"users": {}, "global": [], "states": {}, "maps": {}}


def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def task_bubble(title, tasks, is_global=False):
    contents = []

    for t in tasks:
        deadline = f"⏰ {t['deadline']}" if t.get("deadline") else ""

        row = {
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "contents": [
                {"type": "text", "text": t["text"], "size": "md", "wrap": True},
            ]
        }

        if deadline:
            row["contents"].append({
                "type": "text",
                "text": deadline,
                "size": "sm",
                "color": "#888888"
            })

        # ダミーボタン（STEP2で本物にする）
        row["contents"].append({
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {"type": "button", "style": "primary", "height": "sm",
                 "action": {"type": "message", "label": "完了", "text": "完了モード"}},
                {"type": "button", "style": "secondary", "height": "sm",
                 "action": {"type": "message", "label": "削除", "text": "削除モード"}}
            ]
        })

        contents.append(row)

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg"}
            ] + contents
        }
    }

    return bubble


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

        # ================= 一覧（Flex版） =================
        if clean_message == "一覧":
            personal_tasks = [t for t in tasks["users"][user_id] if t["status"] != "done"]
            global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]

            if not personal_tasks and not global_tasks:
                send_reply(reply_token, "予定はまだありません！", QUICK_MENU)
                continue

            bubbles = []
            if personal_tasks:
                bubbles.append(task_bubble("🗓 あなたの予定", personal_tasks))
            if global_tasks:
                bubbles.append(task_bubble("🌍 全体予定", global_tasks, True))

            carousel = {"type": "carousel", "contents": bubbles}
            reply_flex(reply_token, "タスク一覧", carousel)
            continue

        # ===== ここから下は既存ロジックそのまま =====

        if clean_message == "予定追加モード":
            tasks["states"][user_id] = "add_personal"
            save_tasks(tasks)
            send_reply(reply_token, "予定を送ってね\n例: 2026-02-10 歯医者")
            continue

        if clean_message == "全体追加モード":
            tasks["states"][user_id] = "add_global"
            save_tasks(tasks)
            send_reply(reply_token, "全体予定を送ってね")
            continue

        if clean_message == "完了モード":
            tasks["states"][user_id] = "complete_wait"
            save_tasks(tasks)
            send_reply(reply_token, "完了する番号を送ってね（例: 1 G2）")
            continue

        if clean_message == "削除モード":
            tasks["states"][user_id] = "delete_wait"
            save_tasks(tasks)
            send_reply(reply_token, "削除する番号を送ってね（例: 1 G2）")
            continue

        # （以下、追加・完了・削除の既存処理はあなたのコードそのままなので省略せず続けてOK）