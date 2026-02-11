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
        return {"users": {}, "groups": {}, "checklists": {}}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 安全補完
    data.setdefault("users", {})
    data.setdefault("groups", {})
    data.setdefault("checklists", {})

    return data

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

def send_push(user_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "to": user_id,
        "messages": [message]
    }

    res = requests.post(url, headers=headers, json=data)
    print("PUSH status:", res.status_code)
    print("PUSH body:", res.text)

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

def build_schedule_flex(personal_tasks, global_tasks, show_done=False):
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
            if show_done:
                body.append(task_row(task["text"], f"#list_undo_p_{i}", label="復帰"))
            else:
                body.append(
                    task_row(
                        task["text"],
                        f"#list_done_p_{i}",
                        f"#list_delete_p_{i}",
                        label="完了"
                    )
                )
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
            body.append(
                task_row(
                    task["text"],
                    f"#list_done_g_{i}",
                    f"#list_delete_g_{i}",
                )
            )
    else:
        body.append(empty_row())
        
    body.append({
        "type": "button",
        "style": "primary",
        "margin": "lg",
        "action": {
            "type": "postback",
            "label": "完了済みを見る",
            "data": "#show_done"
        }
    })

    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body
        }
    }

def task_row(text, done_data, delete_data=None, label="完了"):
    buttons = [
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": label,
                "data": done_data
            }
        }
    ]

    if delete_data:
        buttons.append({
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "削除",
                "data": delete_data
            }
        })

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
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": buttons,
                "flex": 2
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
    
def send_schedule(reply_token, personal_tasks, global_tasks, show_done=False):
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
                "contents": build_schedule_flex(personal_tasks, global_tasks, show_done)
            }
        ]
    }

    requests.post(url, headers=headers, json=data)
    
def send_done_schedule(reply_token, personal_done, group_done):
    body = []

    body.append({
        "type": "text",
        "text": "✅ 完了済み予定",
        "weight": "bold",
        "size": "lg"
    })

    if personal_done:
        body.append({
            "type": "text",
            "text": "【個人】",
            "margin": "md",
            "weight": "bold"
        })

        for t in personal_done:
            body.append({
                "type": "text",
                "text": "✔ " + t["text"],
                "wrap": True
            })

    elif group_done:
        body.append({
            "type": "text",
            "text": "【グループ】",
            "margin": "md",
            "weight": "bold"
        })

        for t in group_done:
            body.append({
                "type": "text",
                "text": "✔ " + t["text"],
                "wrap": True
            })

    if not personal_done and not group_done:
        body.append({
            "type": "text",
            "text": "完了済み予定はありません"
        })

    flex = {
        "type": "flex",
        "altText": "完了済み予定",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body
            }
        }
    }

    send_flex(reply_token, flex)
    
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
                    },
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "チェックリストを見る",
                            "data": "#list_check"
                ]
            }
        }
    }

    send_flex(reply_token, flex)
    
def handle_message(reply_token, user_id, text, source_type=None, group_id=None):
    state = user_states.get(user_id)
    
    # チェックリストタイトル入力
    if state == "add_check_title":
        tasks = load_tasks()
        
        tasks.setdefault("checklists", {})
        tasks["checklists"].setdefault(user_id, [])
        
        tasks["checklists"][user_id].append({
            "title": text,
            "items": []
        })
        
        save_tasks(tasks)
        
        user_states[user_id] = "add_check_items"
        send_reply(reply_token, "項目を1つずつ送ってね。終わったら「完了」と送ってください。")
        return
    
    # チェックリスト項目追加
    if state == "add_check_items":
        tasks = load_tasks()
        
        if text == "完了":
            user_states.pop(user_id)
            save_tasks(tasks)
            send_reply(reply_token, "✅ チェックリスト作成完了")
            return
            
        tasks["checklists"][user_id][-1]["items"].append({
            "text": text,
            "done": False
        })
        
        save_tasks(tasks)
        send_reply(reply_token, "追加しました。続けて入力してください。")
        return

    # ===== 個人予定追加 =====
    if state == "add_personal":
        tasks = load_tasks()

        tasks["users"].setdefault(user_id, []).append({
            "text": text,
            "status": "todo"
        })

        save_tasks(tasks)
        user_states.pop(user_id)

        personal = [
            t for t in tasks["users"].get(user_id, [])
            if t.get("status") != "done"
        ]

        group_tasks = []
        if source_type == "group" and group_id:
            tasks.setdefault("groups", {})
            tasks["groups"].setdefault(group_id, [])
            group_tasks = [
                t for t in tasks["groups"][group_id]
                if user_id not in t.get("done_by", [])
            ]

        send_schedule(reply_token, personal, group_tasks)

    # ===== 全体予定追加 =====
    elif state and state.startswith("add_global_"):
        group_id = state.replace("add_global_", "")
        tasks = load_tasks()

        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])

        tasks["groups"][group_id].append({
            "text": text,
            "done_by": []
        })

        save_tasks(tasks)
        user_states.pop(user_id)

        send_reply(reply_token, "🌍 全体予定を追加したよ")

    # ===== それ以外 =====
    else:
        send_reply(reply_token, "メニューから操作してね")
        
def handle_done(reply_token, user_id, data, source_type, group_id=None):
    tasks = load_tasks()

    _, _, scope, idx = data.split("_")
    idx = int(idx)

    if scope == "p":
        tasks["users"][user_id][idx]["status"] = "done"

    elif scope == "g" and group_id:
        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])
        
        tasks["groups"][group_id][idx].setdefault("done_by", []).append(user_id)

    save_tasks(tasks)

    # 更新後の予定を再表示
    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
    
    group_tasks = []
    if source_type == "group" and group_id:
        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])
        
        group_tasks = [
            t for t in tasks["groups"][group_id]
            if user_id not in t.get("done_by", [])
        ]
    
    send_schedule(reply_token, personal, group_tasks)
    
def handle_show_done(reply_token, user_id, source_type, group_id=None):
    tasks = load_tasks()

    # 完了済み個人予定
    personal_done = [
        t for t in tasks["users"].get(user_id, [])
        if t.get("status") == "done"
    ]

    # 完了済みグループ予定
    group_done = []
    if source_type == "group" and group_id:
        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])
        
        group_done = [
            t for t in tasks["groups"][group_id]
            if user_id in t.get("done_by", [])
            ]

    send_done_schedule(reply_token, personal_done, group_done)

def handle_undo(reply_token, user_id, data, group_id=None):
    tasks = load_tasks()

    _, _, scope, idx = data.split("_")
    idx = int(idx)

    if scope == "p":
        tasks["users"][user_id][idx]["status"] = "todo"

    elif scope == "g" and group_id:
        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])
        
        if user_id in tasks["groups"][group_id][idx].get("done_by", []):
            tasks["groups"][group_id][idx]["done_by"].remove(user_id)

    save_tasks(tasks)

    send_reply(reply_token, "復帰したよ")

def handle_list_check(reply_token, user_id):
    tasks = load_tasks()

    checklists = tasks.get("checklists", {}).get(user_id, [])

    if not checklists:
        send_reply(reply_token, "📭 チェックリストはまだありません")
        return

    message = "📝 あなたのチェックリスト\n\n"

    for i, cl in enumerate(checklists):
        message += f"{i+1}. {cl['title']}\n"

        for item in cl["items"]:
            mark = "☑" if item["done"] else "⬜"
            message += f"   {mark} {item['text']}\n"

        message += "\n"

    send_reply(reply_token, message)

def handle_delete(reply_token, user_id, data, source_type, group_id=None):
    tasks = load_tasks()

    _, _, scope, idx = data.split("_")
    idx = int(idx)

    if scope == "p":
        if user_id in tasks["users"] and idx < len(tasks["users"][user_id]):
            tasks["users"][user_id].pop(idx)

    elif scope == "g" and group_id:
        tasks.setdefault("groups", {})
        tasks["groups"].setdefault(group_id, [])

        if idx < len(tasks["groups"][group_id]):
            tasks["groups"][group_id].pop(idx)

    save_tasks(tasks)

    # 削除後に再描画
    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]

    group_tasks = []
    if source_type == "group" and group_id:
        group_tasks = [
            t for t in tasks["groups"][group_id]
            if user_id not in t.get("done_by", [])
        ]

    send_schedule(reply_token, personal, group_tasks)

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    print("=== HIT ===")
    print(body)

    for event in body.get("events", []):
        source = event["source"]
        source_type = source["type"]
        user_id = source["userId"]

        group_id = None
        if source_type == "group":
            group_id = source["groupId"]

        # ===== POSTBACK =====
        if event["type"] == "postback":
            data = event["postback"]["data"]
            reply_token = event["replyToken"]
            
            # グループ内で個人追加が押された場合
            if data == "scope=menu&action=add" and source_type == "group":
                
                push_message = {
                "type": "text",
                    "text": "📅 個人予定を追加するよ。予定を書いてね。"
                    }
                
                user_states[user_id] = "add_personal"
                
                send_push(user_id, push_message)
                
                # グループには何も返さない
                print("POSTBACK:", data)

            # 予定表
            elif data == "scope=menu&action=list":
                tasks = load_tasks()

                personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
                
                 # グループ予定
                group_tasks = []
                
                if source_type == "group":
                    tasks.setdefault("groups", {})
                    tasks["groups"].setdefault(group_id, [])
                    
                    group_tasks = [
                        t for t in tasks["groups"][group_id]
                        if user_id not in t.get("done_by", [])
                        ]
                    
                send_schedule(reply_token, personal, group_tasks)

            # 完了処理
            elif data.startswith("#list_done_"):
                handle_done(reply_token, user_id, data, source_type, group_id)
            
            elif data.startswith("#list_undo_"):
                handle_undo(reply_token, user_id, data, source_type, group_id)

            # 追加
            elif data == "scope=menu&action=add":
                handle_menu_add(reply_token, user_id)
                
            elif data == "#add_personal":
                user_states[user_id] = "add_personal"
                send_reply(reply_token, "追加する予定を送ってね")
            
            elif data == "#add_global":
                if source_type == "group":
                    user_states[user_id] = f"add_global_{group_id}"
                    send_reply(reply_token, "🌍 全体予定を書いてね")
                    
                else:
                    send_reply(reply_token, "🌍 全体予定はグループでのみ使えます")
                
            elif data.startswith("#list_delete_"):
                handle_delete(reply_token, user_id, data, source_type, group_id)
                
            elif data == "#show_done":
                handle_show_done(reply_token, user_id, source_type, group_id)
                
            elif data == "#add_check":
                user_states[user_id] = "add_check_title"
                send_reply(reply_token, "📝 チェックリストのタイトルを送ってね")
            
            elif data == "#list_check":
                handle_list_check(reply_token, user_id)

            # その他
            else:
                send_reply(reply_token, "未定義メニュー")

        # ===== MESSAGE =====
        elif event["type"] == "message":
            reply_token = event["replyToken"]
            text = event["message"]["text"]
            handle_message(reply_token, user_id, text, source_type, group_id)

    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)