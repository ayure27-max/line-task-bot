from flask import Flask, request
import requests
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

user_states = {}

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

　elif data == "#add_personal":
    user_states[user_id] = "add_personal"
    send_reply(reply_token, "追加する予定を送ってね")
    
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

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()

    for event in body.get("events", []):
        reply_token = event.get("replyToken")
        user_id = event["source"]["userId"]

        if event["type"] == "postback":
            data = event["postback"]["data"]
            
            if data == "#menu_list":
                handle_menu_list(reply_token, user_id)

            elif data == "#menu_add":
                handle_menu_add(reply_token, user_id)

            elif data == "#menu_check":
                handle_menu_check(reply_token, user_id)

            elif data == "#menu_other":
                handle_menu_other(reply_token, user_id)

            elif data.startswith("#list_done_"):
                handle_done(reply_token, user_id, data)

        elif event["type"] == "message":
            handle_message(reply_token, user_id, event["message"]["text"])
            
             # ===== 予定表表示 =====
            if data == "#menu_list":
                tasks = load_tasks()
                user_id = event["source"]["userId"]
                
                personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
                global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]
                
                send_schedule(reply_token, personal, global_tasks)
            # ===== 完了 =====
            elif data.startswith("#list_done_"):
                tasks = load_tasks()
                user_id = event["source"]["userId"]
                
                _, _, scope, idx = data.split("_")
                idx = int(idx)
                
                if scope == "p":
                    tasks["users"][user_id][idx]["status"] = "done"
                elif scope == "g":
                    tasks["global"][idx].setdefault("done_by", []).append(user_id)
                    
                save_tasks(tasks)

    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)