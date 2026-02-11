from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
print("TOKEN EXISTS:", bool(LINE_CHANNEL_ACCESS_TOKEN))

user_states = {}
DATA_FILE = "tasks.json"

def load_tasks():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "global": []}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tasks(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
def send_reply(reply_token, text):
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
    res = requests.post(url, headers=headers, json=data)
    print("LINE reply status:", res.status_code)
    print("LINE reply body:", res.text)

def send_flex(reply_token, flex):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [flex]
    }
    requests.post(url, headers=headers, json=data)

def build_schedule_flex(personal_tasks, global_tasks):
    body = []

    body.append({
        "type": "text",
        "text": "📅 予定表",
        "weight": "bold",
        "size": "lg"
    })

    # 👤 個人予定
    body.append({
        "type": "text",
        "text": "👤 個人の予定",
        "weight": "bold",
        "margin": "lg"
    })

    if personal_tasks:
        for i, task in enumerate(personal_tasks):
            body.append(task_row(task["text"], f"#list_done_p_{i}"))
    else:
        body.append(empty_row())

    # 🌍 全体予定
    body.append({
        "type": "text",
        "text": "🌍 全体の予定",
        "weight": "bold",
        "margin": "lg"
    })

    if global_tasks:
        for i, task in enumerate(global_tasks):
            body.append(task_row(task["text"], f"#list_done_g_{i}"))
    else:
        body.append(empty_row())

    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body
        }
    }

def task_row(text, postback_data):
    return {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {
                "type": "text",
                "text": text,
                "wrap": True,
                "flex": 5
            },
            {
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "postback",
                    "label": "完了",
                    "data": postback_data
                }
            }
        ]
    }
    
def empty_row():
    return {
        "type": "text",
        "text": "（なし）",
        "size": "sm",
        "color": "#999999"
    }
    
def send_schedule(reply_token, personal_tasks, global_tasks):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "flex",
                "altText": "予定表",
                "contents": build_schedule_flex(personal_tasks, global_tasks)
            }
        ]
    }

    requests.post(url, headers=headers, json=data)
    
def handle_menu_add(reply_token, user_id):
    user_states[user_id] = "add_select"

    flex = {
        "type": "flex",
        "altText": "追加メニュー",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "個人予定",
                            "data": "#add_personal"
                        }
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "全体予定",
                            "data": "#add_global"
                        }
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "チェックリスト",
                            "data": "#add_check"
                        }
                    }
                ]
            }
        }
    }

    send_flex(reply_token, flex)
    
def handle_message(reply_token, user_id, text):
    state = user_states.get(user_id)

    if state == "add_personal":
        tasks = load_tasks()
        tasks["users"].setdefault(user_id, []).append({
            "text": text,
            "status": "todo"
        })
        save_tasks(tasks)

        user_states.pop(user_id)
        send_reply(reply_token, "📅 個人予定を追加したよ")

    else:
        send_reply(reply_token, "メニューから操作してね")

def handle_done(reply_token, user_id, data):
    tasks = load_tasks()

    _, _, scope, idx = data.split("_")
    idx = int(idx)

    if scope == "p":
        tasks["users"][user_id][idx]["status"] = "done"

    elif scope == "g":
        tasks["global"][idx].setdefault("done_by", []).append(user_id)

    save_tasks(tasks)

    # 更新後の予定を再表示
    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
    global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]

    send_schedule(reply_token, personal, global_tasks)

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    print("=== HIT ===")
    print(body)

    for event in body.get("events", []):

        reply_token = event["replyToken"]
        user_id = event["source"]["userId"]

        # ===== POSTBACK =====
        if event["type"] == "postback":
            data = event["postback"]["data"]
            print("POSTBACK:", data)

            # 予定表
            if data == "scope=menu&action=list":
                tasks = load_tasks()

                personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
                global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]

                send_schedule(reply_token, personal, global_tasks)

            # 完了処理
            elif data.startswith("#list_done_"):
                handle_done(reply_token, user_id, data)

            # 追加
            elif data == "scope=menu&action=add":
                handle_menu_add(reply_token, user_id)

            # その他
            else:
                send_reply(reply_token, "未定義メニュー")

        # ===== MESSAGE =====
        elif event["type"] == "message":
            text = event["message"]["text"]
            handle_message(reply_token, user_id, text)

    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)