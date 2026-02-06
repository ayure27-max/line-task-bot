from flask import Flask, request
import os
import requests
import json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
TASK_FILE = "tasks.json"

url = "https://api.line.me/v2/bot/richmenu"

headers = {
    "Authorization": f"Bearer {headers = {
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    "Content-Type": "image/png"
}}",
    "Content-Type": "application/json"
}

richmenu = {
    "size": {
        "width": 1040,
        "height": 1040
    },
    "selected": True,
    "name": "main-menu",
    "chatBarText": "メニュー",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 520, "height": 520},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=list"
            }
        },
        {
            "bounds": {"x": 520, "y": 0, "width": 520, "height": 520},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=add"
            }
        },
        {
            "bounds": {"x": 0, "y": 520, "width": 520, "height": 520},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=check"
            }
        },
        {
            "bounds": {"x": 520, "y": 520, "width": 520, "height": 520},
            "action": {
                "type": "postback",
                "data": "scope=menu&action=other"
            }
        }
    ]
}

r = requests.post(url, headers=headers, json=richmenu)
print(r.status_code)
print(r.text)

if r.status_code == 200:
    richmenu_id = r.json()["richMenuId"]
    print("RichMenu ID:", richmenu_id)



ADMIN_USERS = ["U179b29542e4d9d16aad9ee5b8a8eea18"]


# ================= 送信系 =================

def reply_flex(reply_token, alt_text, contents):
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
            "contents": contents
        }]
    }

    r = requests.post(url, headers=headers, json=data)
    print("Flex status:", r.status_code)
    print("Flex response:", r.text)
#=======postback関連========
def parse_postback(data: str) -> dict:
    """
    scope=menu&action=list
    ↓
    {"scope": "menu", "action": "list"}
    """
    result = {}
    for item in data.split("&"):
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
    return result

# ================= データ =================

def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}

    data.setdefault("users", {})
    data.setdefault("global", [])
    data.setdefault("maps", {})
    data.setdefault("checklists", {})

    return data

def save_tasks(tasks):
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ================= Flexバブル =================
# ================= Flex一覧バブル（統合版） =================

def build_unified_task_bubble(personal_tasks, global_tasks, user_id, tasks):
    body = [
        {"type": "text", "text": "📋 タスク一覧", "weight": "bold", "size": "lg"}
    ]

    personal_map = []
    global_map = []

    # ---------- 個人予定 ----------
    if personal_tasks:
        body.append({"type": "text", "text": "🗓 あなたの予定", "margin": "lg", "weight": "bold"})

        for i, t in enumerate(personal_tasks, start=1):
            personal_map.append(tasks["users"][user_id].index(t))

            row = {
                "type": "box",
                "layout": "horizontal",
                "margin": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "message", "label": str(i), "text": str(i)}
                    },
                    {
                        "type": "text",
                        "text": str(t.get("text", "（内容不明）")),
                        "wrap": True,
                        "flex": 5,
                        "margin": "md"
                    }
                ]
            }

            if t.get("deadline"):
                row["contents"].append({
                    "type": "text",
                    "text": str(t["deadline"]),
                    "size": "xs",
                    "color": "#888888",
                    "align": "end"
                })

            body.append(row)

    # ---------- 全体予定 ----------
    if global_tasks:
        body.append({"type": "text", "text": "🌍 全体予定", "margin": "lg", "weight": "bold"})

        for i, t in enumerate(global_tasks, start=1):
            global_map.append(tasks["global"].index(t))

            row = {
                "type": "box",
                "layout": "horizontal",
                "margin": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {"type": "message", "label": f"G{i}", "text": f"G{i}"}
                    },
                    {
                        "type": "text",
                        "text": str(t.get("text", "（内容不明）")),
                        "wrap": True,
                        "flex": 5,
                        "margin": "md"
                    }
                ]
            }

            if t.get("deadline"):
                row["contents"].append({
                    "type": "text",
                    "text": str(t["deadline"]),
                    "size": "xs",
                    "color": "#888888",
                    "align": "end"
                })

            body.append(row)

    # 🔥 マッピング保存（超重要）
    tasks["maps"][user_id] = {
        "personal_map": personal_map,
        "global_map": global_map
    }
    save_tasks(tasks)

    return {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": body},
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [{
                "type": "button",
                "style": "secondary",
                "action": {"type": "message", "label": "操作は次の段階で解放", "text": "noop"}
            }]
        }
    }

def handle_menu_list(reply_token, user_id, tasks):
    personal_tasks = tasks.get("users", {}).get(user_id, [])
    global_tasks = tasks.get("global", [])

    bubble = build_unified_task_bubble(
        personal_tasks,
        global_tasks,
        user_id,
        tasks
    )

    reply_flex(reply_token, "予定一覧", bubble)
    
    #========予定表flex表示========
def build_schedule_bubble(personal_tasks, global_tasks, user_id, tasks):

    contents = []

    contents.append({
        "type": "text",
        "text": "📋 予定一覧",
        "weight": "bold",
        "size": "xl"
    })

    contents.append({
        "type": "text",
        "text": "👤 あなたの予定",
        "weight": "bold",
        "margin": "lg"
    })

    if personal_tasks:
        for i, task in enumerate(personal_tasks):
            contents.append(task_row(task, f"P{i+1}"))
    else:
        contents.append(empty_row())

    contents.append({
        "type": "text",
        "text": "🏢 全体予定",
        "weight": "bold",
        "margin": "lg"
    })

    if global_tasks:
        for i, task in enumerate(global_tasks):
            contents.append(task_row(task, f"G{i+1}"))
    else:
        contents.append(empty_row())

    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": contents
        }
    }
    
def task_row(task, label):
    deadline = f" ⏰{task['deadline']}" if task.get("deadline") else ""

    return {
        "type": "box",
        "layout": "vertical",
        "margin": "md",
        "spacing": "sm",
        "contents": [
            {
                "type": "text",
                "text": "⬜",
                "size": "sm",
                "flex": 1
            },
            {
                "type": "text",
                "text": task["text"] + deadline,
                "wrap": True,
                "size": "sm",
                "flex": 6
            },
            {
                "type": "box",
                "layout": "vertical",
                "flex": 2,
                "contents": [
                    {
                        "type": "text",
                        "text": "完了",
                        "size": "xs",
                        "align": "center",
                        "color": "#ffffff"
                    }
                ],
                "backgroundColor": "#4CAF50",
                "cornerRadius": "md",
                "paddingAll": "4px",
                "action": {
                    "type": "message",
                    "label": "完了",
                    "text": f"done {label}"
                }
            }
        ]
    }
    
def empty_row():
    return {
        "type": "text",
        "text": "予定はまだありません",
        "size": "sm",
        "color": "#999999",
        "margin": "md"
    }
# ================= Webhook =================

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])
    tasks = load_tasks()

    for event in events:
        user_id = event["source"]["userId"]
        reply_token = event["replyToken"]

        # postback 以外は無視
        if event["type"] != "postback":
            continue

        data = parse_postback(event["postback"]["data"])
        scope = data.get("scope")
        action = data.get("action")

        # --- menu ---
        if scope == "menu":
            if action == "list":
                handle_menu_list(reply_token, user_id, tasks)

        save_tasks(tasks)

    return "OK", 200


@app.route("/")
def home():
    return "Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    
