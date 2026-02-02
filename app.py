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

# ================= 送信系 =================

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


# ================= データ =================

def load_tasks():
    try:
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("global", [])
            data.setdefault("states", {})
            data.setdefault("maps", {})
            data.setdefault("checklists", {})
            return data
    except:
        return {"users": {}, "global": [], "states": {}, "maps": {},"checklists": {}}


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


# ================= Webhook =================

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
        clean_message = user_message.strip()

        tasks["users"].setdefault(user_id, [])
        tasks["checklists"].setdefault(user_id, {
            "templates": [],
            "active": {},
            "history": {}
        })
        print(json.dumps(tasks["checklists"][user_id], indent=2, ensure_ascii=False))
        state = tasks["states"].get(user_id)
        
        # ===== 一覧（統合Flex版） =====
        if clean_message == "一覧":
            for g in tasks["global"]:
                g.setdefault("done_by", [])
                
            personal_tasks = [t for t in tasks["users"][user_id] if t.get("status") != "done"]
            global_tasks = [t for t in tasks["global"] if user_id not in t.get("done_by", [])]
            
            if not personal_tasks and not global_tasks:
                send_reply(reply_token, "予定はまだありません！", QUICK_MENU)
                continue
            
            bubble = build_unified_task_bubble(personal_tasks, global_tasks, user_id, tasks)
            reply_flex(reply_token, "タスク一覧", bubble)
            continue
        
            bubbles = []

            if personal_tasks:
                bubbles.append(build_task_bubble("🗓 あなたの予定", personal_tasks))

            if global_tasks:
                bubbles.append(build_task_bubble("🌍 全体予定", global_tasks))

            if not bubbles:
                send_reply(reply_token, "予定の表示に失敗しましたがデータは無事です🙏", QUICK_MENU)
                continue

            carousel = {"type": "carousel", "contents": bubbles[:10]}
            reply_flex(reply_token, "タスク一覧", carousel)
            continue
            
        # ===== チェックリスト作成モード開始 =====
        if clean_message == "チェック作成モード":
            tasks["checklists"].setdefault(user_id, {"templates": [], "editing": None})
            
            tasks["checklists"][user_id]["editing"] = {
                 "name": None,
                 "items": []
            }
            
            save_tasks(tasks)
            send_reply(reply_token,
                 "🧩 チェックリストテンプレ作成開始！\nまずは名前を送ってね",
                 QUICK_MENU
            )
            continue
            
        editing = tasks.get("checklists", {}).get(user_id, {}).get("editing")
        
        if editing and editing["name"] is None:
            editing["name"] = user_message
            save_tasks(tasks)
            send_reply(reply_token,
                f"📋 テンプレ名『{user_message}』登録！\n次はチェック項目を1行ずつ送ってね\n完了したら『保存』",
                QUICK_MENU
            )
            continue
            
        if editing and editing["name"] and clean_message not in ["保存", "削除", "上へ", "下へ"]:
            editing["items"].append(user_message)
            save_tasks(tasks)
            send_reply(reply_token,
                 f"✅ 追加: {user_message}\n現在{len(editing['items'])}項目\n『保存』で完成",
                 QUICK_MENU
            )
            continue
            
        if editing and clean_message == "保存":
            tasks["checklists"][user_id]["templates"].append(editing)
            tasks["checklists"][user_id]["editing"] = None
            save_tasks(tasks)
            
            send_reply(reply_token,
                f"🎉 テンプレ『{editing['name']}』保存完了！",
                QUICK_MENU
            )
            continue
            
        # ===== チェックリスト編集中の操作 =====
        checklists = tasks.setdefault("checklists", {}).setdefault(user_id, {"templates": [], "editing": None})
        editing = checklists.get("editing")
        
        if editing:
            msg = user_message.strip()
            
            # ❌ 削除（例: del 3）
            if msg.startswith("del "):
                try:
                    idx = int(msg.split()[1]) - 1
                    if 0 <= idx < len(editing["items"]):
                        removed = editing["items"].pop(idx)
                        save_tasks(tasks)
                        send_reply(reply_token, f"🗑 削除: {removed}", QUICK_MENU)
                    else:
                         send_reply(reply_token, "番号が不正だよ", QUICK_MENU)
                except:
                    send_reply(reply_token, "使い方: del 3", QUICK_MENU)
                continue
                
            # 🔄 並び替え（例: mv 5 2 → 5番を2番目へ）
            if msg.startswith("mv "):
                try:
                    _, a, b = msg.split()
                    a, b = int(a) - 1, int(b) - 1
                    
                    items = editing["items"]
                    if 0 <= a < len(items) and 0 <= b < len(items):
                        item = items.pop(a)
                        items.insert(b, item)
                        save_tasks(tasks)
                        send_reply(reply_token, "🔄 並び替えたよ", QUICK_MENU)
                    else:
                        send_reply(reply_token, "番号が不正だよ", QUICK_MENU)
                except:
                    send_reply(reply_token, "使い方: mv 5 2", QUICK_MENU)
                continue
                    
            # 📋 編集中リスト表示
            if msg == "list":
                if not editing["items"]:
                    send_reply(reply_token, "まだ項目がないよ", QUICK_MENU)
                else:
                    lines = "\n".join(f"{i+1}. {t}" for i, t in enumerate(editing["items"]))
                    send_reply(reply_token, f"🛠 編集中リスト\n{lines}", QUICK_MENU)
                    continue
                    
            # 💾 テンプレ保存
            if msg.startswith("save "):
                name = msg[5:].strip()
                
                if not name:
                    send_reply(reply_token, "チェックリスト名を入れてね", QUICK_MENU)
                    return "OK"
                    
                    if not editing["items"]:
                        send_reply(reply_token, "項目が空だよ", QUICK_MENU)
                        return "OK"
                        
                    template = {
                        "name": name,
                         "items": editing["items"][:]
                    }
                    
                    checklists["templates"].append(template)
                    checklists["editing"] = None
                    save_tasks(tasks)
                    
                    send_reply(reply_token, f"✅ テンプレ『{name}』を保存したよ", QUICK_MENU)
                    return "OK"
            
        # 📚 テンプレ一覧表示
        if clean_message == "templates":
            checklists = tasks.setdefault("checklists", {}).setdefault(user_id, {"templates": [], "editing": None})
            templates = checklists.get("templates", [])
            
            if not templates:
                send_reply(reply_token, "保存されたテンプレはまだ無いよ", QUICK_MENU)
            else:
                lines = "\n".join(f"{i+1}. {t['name']} ({len(t['items'])}項目)" for i, t in enumerate(templates))
                send_reply(reply_token, f"📚 テンプレ一覧\n{lines}", QUICK_MENU)
                
            return "OK"

        # ===== 以下元のロジック =====
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

        # ===== 予定追加 =====
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

        # ===== 完了 =====
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

        # ===== 削除 =====
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


@app.route("/")
def home():
    return "Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)