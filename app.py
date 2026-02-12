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
    data.setdefault("settings", {})

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
    tasks = load_tasks()
    ui = get_check_ui_flags(tasks, user_id)

    del_state = "ON" if ui.get("show_delete") else "OFF"
    reo_state = "ON" if ui.get("show_reorder") else "OFF"

    flex = {
        "type": "flex",
        "altText": "追加メニュー",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": "➕ 追加/モード",
                        "weight": "bold",
                        "size": "lg"
                    },

                    # ---- 追加系 ----
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "個人予定を追加",
                            "data": "#add_personal"
                        }
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "全体予定を追加",
                            "data": "#add_global"
                        }
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "チェックリスト作成",
                            "data": "#add_check"
                        }
                    },

                    # ---- 区切り ----
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "text",
                        "text": "🛠 操作モード（普段は隠す）",
                        "weight": "bold",
                        "margin": "lg",
                        "size": "sm",
                        "color": "#666666"
                    },

                    # ---- モード切替 ----
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": f"🗑 削除モード：{del_state}",
                            "data": "#toggle_delete_mode"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": f"↕ 並び替えモード：{reo_state}",
                            "data": "#toggle_reorder_mode"
                        }
                    }
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
    
def handle_toggle_check(reply_token, user_id, data):
    tasks = load_tasks()

    _, _, c_idx, i_idx = data.split("_")
    c_idx = int(c_idx)
    i_idx = int(i_idx)

    checklist = tasks["checklists"][user_id][c_idx]
    item = checklist["items"][i_idx]

    # 状態反転
    item["done"] = not item["done"]

    save_tasks(tasks)

    # 再表示
    handle_list_check(reply_token, user_id)
    
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

def handle_list_check(reply_token, user_id, opened=-1):
    tasks = load_tasks()
    checklists = tasks.get("checklists", {}).get(user_id, [])

    try:
        opened = int(opened)
    except:
        opened = -1

    bubbles = []

    if not checklists:
        bubbles.append({
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [{"type": "text", "text": "チェックリストがありません", "weight": "bold"}]
            }
        })
    else:
        for c_idx, checklist in enumerate(checklists):
            is_open = (opened == c_idx)
            arrow = "▲" if is_open else "▼"

            items = checklist.get("items", [])
            total = len(items)
            done_count = sum(1 for i in items if i.get("done"))

            contents = []

            # タイトル行（開閉 + ゴミ箱）
            contents.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "button",
                        "flex": 4,
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": f"{arrow} {checklist.get('title','(no title)')}",
                            "data": f"#toggle_list_{c_idx}_{opened}"
                        }
                    },
                    {
                        "type": "button",
                        "flex": 1,
                        "style": "secondary",
                        "action": {
                            "type": "postback",
                            "label": "🗑",
                            "data": f"#delete_check_{c_idx}_{opened}"
                        }
                    }
                ]
            })

            # 進捗
            contents.append({
                "type": "text",
                "text": f"進捗: {done_count}/{total}",
                "size": "sm",
                "color": "#888888",
                "margin": "sm"
            })

            if is_open:
                if not items:
                    contents.append({
                        "type": "text",
                        "text": "項目がありません（追加してね）",
                        "size": "sm",
                        "color": "#999999",
                        "margin": "md"
                    })
                else:
                    for i_idx, item in enumerate(items):
                        mark = "☑" if item.get("done") else "⬜"
                        text = item.get("text", "")

                        # 1行：チェック切替 + 削除 + 並び替え（↑↓）
                        contents.append({
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "sm",
                            "contents": [
                                {
                                    "type": "button",
                                    "flex": 5,
                                    "style": "secondary",
                                    "action": {
                                        "type": "postback",
                                        "label": f"{mark} {text}",
                                        "data": f"#toggle_check_{c_idx}_{i_idx}_{opened}"
                                    }
                                },
                                {
                                    "type": "button",
                                    "flex": 1,
                                    "style": "secondary",
                                    "action": {
                                        "type": "postback",
                                        "label": "🗑",
                                        "data": f"#delete_item_{c_idx}_{i_idx}_{opened}"
                                    }
                                }
                            ]
                        })

                        # 並び替えボタン（上下）
                        contents.append({
                            "type": "box",
                            "layout": "horizontal",
                            "spacing": "sm",
                            "margin": "xs",
                            "contents": [
                                {
                                    "type": "button",
                                    "flex": 1,
                                    "style": "secondary",
                                    "height": "sm",
                                    "action": {
                                        "type": "postback",
                                        "label": "↑",
                                        "data": f"#move_item_{c_idx}_{i_idx}_up_{opened}"
                                    }
                                },
                                {
                                    "type": "button",
                                    "flex": 1,
                                    "style": "secondary",
                                    "height": "sm",
                                    "action": {
                                        "type": "postback",
                                        "label": "↓",
                                        "data": f"#move_item_{c_idx}_{i_idx}_down_{opened}"
                                    }
                                }
                            ]
                        })

                # リスト丸ごと削除（下にも置く）
                contents.append({
                    "type": "button",
                    "style": "secondary",
                    "margin": "lg",
                    "action": {
                        "type": "postback",
                        "label": "🗑 このリストを削除",
                        "data": f"#delete_check_{c_idx}_{opened}"
                    }
                })
            else:
                contents.append({
                    "type": "text",
                    "text": "タップで開く",
                    "size": "sm",
                    "color": "#999999",
                    "margin": "md"
                })

            bubbles.append({
                "type": "bubble",
                "body": {"type": "box", "layout": "vertical", "contents": contents}
            })

    flex = {
        "type": "flex",
        "altText": "チェックリスト",
        "contents": {
            "type": "carousel",
            "contents": bubbles[:10]
        }
    }
    send_flex(reply_token, flex)


def handle_toggle_list(reply_token, user_id, data):
    # data: #toggle_list_{c_idx}_{opened}
    _, _, c_idx, opened = data.split("_")
    c_idx = int(c_idx)
    opened = int(opened)

    next_opened = -1 if opened == c_idx else c_idx
    handle_list_check(reply_token, user_id, next_opened)


def handle_toggle_check(reply_token, user_id, data):
    # data: #toggle_check_{c_idx}_{i_idx}_{opened}
    tasks = load_tasks()
    _, _, c_idx, i_idx, opened = data.split("_")
    c_idx = int(c_idx)
    i_idx = int(i_idx)
    opened = int(opened)

    checklists = tasks.get("checklists", {}).get(user_id, [])
    if 0 <= c_idx < len(checklists):
        items = checklists[c_idx].get("items", [])
        if 0 <= i_idx < len(items):
            items[i_idx]["done"] = not items[i_idx].get("done", False)
            save_tasks(tasks)

    # 開いたまま再表示
    handle_list_check(reply_token, user_id, c_idx)


def handle_delete_item(reply_token, user_id, data):
    # data: #delete_item_{c_idx}_{i_idx}_{opened}
    tasks = load_tasks()
    _, _, c_idx, i_idx, opened = data.split("_")
    c_idx = int(c_idx)
    i_idx = int(i_idx)
    opened = int(opened)

    checklists = tasks.get("checklists", {}).get(user_id, [])
    if 0 <= c_idx < len(checklists):
        items = checklists[c_idx].get("items", [])
        if 0 <= i_idx < len(items):
            items.pop(i_idx)
            save_tasks(tasks)

    handle_list_check(reply_token, user_id, c_idx)


def handle_delete_check(reply_token, user_id, data):
    # data: #delete_check_{c_idx}_{opened}
    tasks = load_tasks()
    _, _, c_idx, opened = data.split("_")
    c_idx = int(c_idx)
    opened = int(opened)

    checklists = tasks.get("checklists", {}).get(user_id, [])
    if 0 <= c_idx < len(checklists):
        checklists.pop(c_idx)
        save_tasks(tasks)

    # 削除後に open index を補正
    if opened == c_idx:
        opened = -1
    elif opened > c_idx:
        opened = opened - 1

    handle_list_check(reply_token, user_id, opened)


def handle_move_item(reply_token, user_id, data):
    # data: #move_item_{c_idx}_{i_idx}_{dir}_{opened}
    tasks = load_tasks()
    _, _, c_idx, i_idx, direction, opened = data.split("_")
    c_idx = int(c_idx)
    i_idx = int(i_idx)
    opened = int(opened)

    checklists = tasks.get("checklists", {}).get(user_id, [])
    if not (0 <= c_idx < len(checklists)):
        handle_list_check(reply_token, user_id, opened)
        return

    items = checklists[c_idx].get("items", [])
    if not (0 <= i_idx < len(items)):
        handle_list_check(reply_token, user_id, opened)
        return

    if direction == "up" and i_idx > 0:
        items[i_idx - 1], items[i_idx] = items[i_idx], items[i_idx - 1]
        save_tasks(tasks)
    elif direction == "down" and i_idx < len(items) - 1:
        items[i_idx + 1], items[i_idx] = items[i_idx], items[i_idx + 1]
        save_tasks(tasks)

    # 並び替え後もそのリストを開いて表示
    handle_list_check(reply_token, user_id, c_idx)
    
def get_check_ui_flags(tasks, user_id):
    tasks.setdefault("settings", {})
    tasks["settings"].setdefault(user_id, {})
    tasks["settings"][user_id].setdefault("check_ui", {})
    ui = tasks["settings"][user_id]["check_ui"]

    ui.setdefault("show_delete", False)
    ui.setdefault("show_reorder", False)
    return ui

def toggle_check_ui_flag(tasks, user_id, flag_key):
    ui = get_check_ui_flags(tasks, user_id)
    ui[flag_key] = not ui.get(flag_key, False)
    return ui[flag_key]

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
            
            # --- リッチメニュー：予定表 ---
            if data == "scope=menu&action=list":
                tasks = load_tasks()
                personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
                
                group_tasks = []
                if source_type == "group":
                    tasks.setdefault("groups", {})
                    tasks["groups"].setdefault(group_id, [])
                    group_tasks = [
                        t for t in tasks["groups"][group_id]
                        if user_id not in t.get("done_by", [])
                    ]
                
                send_schedule(reply_token, personal, group_tasks)
            
            # --- リッチメニュー：チェックリスト一覧 ---
            elif data == "scope=menu&action=check":
                handle_list_check(reply_token, user_id, -1)
                
            elif data.startswith("#toggle_list_"):
                handle_toggle_list(reply_token, user_id, data)
                
            elif data.startswith("#toggle_check_"):
                handle_toggle_check(reply_token, user_id, data)
                
            elif data.startswith("#delete_item_"):
                handle_delete_item(reply_token, user_id, data)
                
            elif data.startswith("#delete_check_"):
                handle_delete_check(reply_token, user_id, data)
            
            elif data.startswith("#move_item_"):
                handle_move_item(reply_token, user_id, data)
        
            # --- リッチメニュー：追加（グループで個人予定をpushする特例）---
            elif data == "scope=menu&action=add" and source_type == "group":
                push_message = {"type": "text", "text": "📅 個人予定を追加するよ。予定を書いてね。"}
                user_states[user_id] = "add_personal"
                send_push(user_id, push_message)
                print("POSTBACK:", data)
            
            # --- 通常：追加メニューを表示 ---
            elif data == "scope=menu&action=add":
                handle_menu_add(reply_token, user_id)
            
            # ====== 予定（schedule）系 ======
            elif data.startswith("#list_done_"):
                handle_done(reply_token, user_id, data, source_type, group_id)
            
            elif data.startswith("#list_undo_"):
                # もし handle_undo の引数が (reply_token, user_id, data, group_id=None) なら
                # 下の1行を handle_undo(reply_token, user_id, data, group_id) に変えてOK
                handle_undo(reply_token, user_id, data, source_type, group_id)
        
            elif data.startswith("#list_delete_"):
                handle_delete(reply_token, user_id, data, source_type, group_id)
            
            elif data == "#show_done":
                handle_show_done(reply_token, user_id, source_type, group_id)
            
            elif data == "#add_personal":
                user_states[user_id] = "add_personal"
                send_reply(reply_token, "追加する予定を送ってね")
            
            elif data == "#add_global":
                if source_type == "group":
                    user_states[user_id] = f"add_global_{group_id}"
                    send_reply(reply_token, "🌍 全体予定を書いてね")
                else:
                    send_reply(reply_token, "🌍 全体予定はグループでのみ使えます")
                
            # ====== チェックリスト系（ここが統一ポイント） ======
            elif data == "#add_check":
                 user_states[user_id] = "add_check_title"
                 send_reply(reply_token, "📝 チェックリストのタイトルを送ってね")
                
            elif data == "#toggle_delete_mode":
                tasks = load_tasks()
                new_state = toggle_check_ui_flag(tasks, user_id, "show_delete")
                save_tasks(tasks)
                # 状態が変わったので、追加メニューを描き直してラベル更新
                handle_menu_add(reply_token, user_id)
                
            elif data == "#toggle_reorder_mode":
                tasks = load_tasks()
                new_state = toggle_check_ui_flag(tasks, user_id, "show_reorder")
                save_tasks(tasks)
                handle_menu_add(reply_token, user_id)
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