from flask import Flask, request
import requests
import os
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import traceback
import re

DATABASE_URL = os.getenv("DATABASE_URL")

def db_ping():
    if not DATABASE_URL:
        print("❌ DATABASE_URL is missing")
        return False
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        print("✅ DB connected (SELECT 1 OK)")
        return True
    except Exception as e:
        print("❌ DB connection failed:", e)
        return False
import json

app = Flask(__name__)

DB_READY = False

def ensure_db_ready():
    global DB_READY
    if DB_READY:
        return True
    try:
        init_db()          # テーブル作成
        DB_READY = True
        print("✅ init_db done (once)")
        return True
    except Exception as e:
        print("❌ init_db failed:", e)
        DB_READY = False
        return False

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
print("TOKEN EXISTS:", bool(LINE_CHANNEL_ACCESS_TOKEN))

user_states = {}
DATA_FILE = "tasks.json"

DEFAULT_TASKS = {
    "users": {},
    "groups": {},
    "checklists": {},
    "settings": {},
    "board": {"users": {}, "groups": {}},

    # 集会所（合言葉）
    "spaces": {},           # space_id -> {name, pass, created_by}
    "memberships": {},      # user_id -> [space_id...]
    "active_space": {}      # user_id -> space_id
    "space_tasks": {}   # space_id -> [ {text, done_by: []}, ... ]
}

def db_connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が未設定です（Renderの環境変数に入れてね）")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
def init_db():
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    k TEXT PRIMARY KEY,
                    v JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

def load_tasks():
    if not ensure_db_ready():
        raise RuntimeError("DB_INIT_FAILED")

    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT v FROM kv_store WHERE k = %s;", ("tasks",))
            row = cur.fetchone()

    data = row["v"] if row else DEFAULT_TASKS.copy()
    data.setdefault("users", {})
    data.setdefault("groups", {})
    data.setdefault("checklists", {})
    data.setdefault("settings", {})
    data.setdefault("board", {"users": {}, "groups": {}})
    data["board"].setdefault("users", {})
    data["board"].setdefault("groups", {})
    data.setdefault("spaces", {})
    data.setdefault("memberships", {})
    data.setdefault("active_space", {})
    data.setdefault("space_tasks", {})
    return data

def save_tasks(data):
    if not ensure_db_ready():
        raise RuntimeError("DB_INIT_FAILED")

    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO kv_store (k, v)
                VALUES (%s, %s)
                ON CONFLICT (k)
                DO UPDATE SET v = EXCLUDED.v, updated_at = now();
            """, ("tasks", Jsonb(data)))

def db_ping():
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        print("✅ DB connected (SELECT 1 OK)")
        return True
    except Exception as e:
        print("❌ DB connection failed:", e)
        return False
    
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
                body.append(task_row(task["text"], f"#list_undo_p_{i}", label="↩"))
            else:
                body.append(
                    task_row(
                        task["text"],
                        f"#list_done_p_{i}",
                        f"#list_delete_p_{i}",
                        label="✅"
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
                    f"#space_done_{i}",
                    f"#space_delete_{i}"
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

def task_row(text, done_data, delete_data=None, label="✅"):
    buttons = [
        {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": label,   # ← ✅ とか 復帰 とか
                "data": done_data
            }
        }
    ]

    if delete_data:
        buttons.append({
            "type": "button",
            "style": "secondary",   # 危険なのでsecondaryのまま
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "🗑",
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
    
BOARD_TITLE = "伝言板"

def handle_other_menu(reply_token, user_id, source_type=None, group_id=None):
    tasks = load_tasks()
    ui = get_board_ui_flags(tasks, user_id)
    del_state = "ON" if ui.get("show_delete") else "OFF"
    reo_state = "ON" if ui.get("show_reorder") else "OFF"

    flex = {
        "type": "flex",
        "altText": "その他",
        "contents": {
            "type": "bubble",
            "styles": {"body": {"backgroundColor": "#F8FAFC"}},
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "🧰 その他", "weight": "bold", "size": "lg"},
                    {"type": "separator", "margin": "md"},

                    {"type": "button", "style": "primary",
                     "action": {"type": "postback", "label": f"📌 {BOARD_TITLE} ← 一覧", "data": "#board_list"}},
                    
                    {"type": "button", "style": "secondary",
                     "action": {"type": "postback", "label": "🗝 合言葉で集会所に参加", "data": "#space_join"}},

                    {"type": "button", "style": "secondary",
                     "action": {"type": "postback", "label": f"➕ {BOARD_TITLE}に入れる", "data": "#board_add"}},

                    {"type": "separator", "margin": "md"},

                    {"type": "text", "text": f"🛠 {BOARD_TITLE}の整理（普段は隠す）",
                     "size": "sm", "color": "#64748B"},

                    {"type": "button", "style": "secondary",
                     "action": {"type": "postback", "label": f"🗑 削除モード：{del_state}", "data": "#board_toggle_delete"}},

                    {"type": "button", "style": "secondary",
                     "action": {"type": "postback", "label": f"↕ 並び替えモード：{reo_state}", "data": "#board_toggle_reorder"}},

                    {"type": "separator", "margin": "md"},

                    {"type": "button", "style": "secondary",
                     "action": {"type": "postback", "label": "🌍 全体予定追加", "data": "#other_add_global"}}
                ]
            }
        }
    }
    send_flex(reply_token, flex)

def normalize_pass(s: str) -> str:
    # 合言葉の表記揺れを減らす（空白トリム、連続空白を1つ）
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def get_or_create_space_by_pass(tasks, passphrase: str, created_by: str):
    """
    合言葉に一致する集会所があれば返す。無ければ作って返す。
    ※セキュリティ軽め：passは平文保存
    """
    passphrase = normalize_pass(passphrase)
    if not passphrase:
        return None

    # 既存検索
    for sid, info in tasks.get("spaces", {}).items():
        if info.get("pass") == passphrase:
            return sid

    # 新規作成
    # space_id は単純に連番でOK（衝突しにくい）
    tasks.setdefault("spaces", {})
    sid = f"s{len(tasks['spaces']) + 1}"

    tasks["spaces"][sid] = {
        "name": passphrase,      # 今は名前＝合言葉でOK（後で編集可能にしても良い）
        "pass": passphrase,
        "created_by": created_by
    }
    return sid

def join_space(tasks, user_id: str, space_id: str):
    tasks.setdefault("memberships", {})
    tasks.setdefault("active_space", {})

    tasks["memberships"].setdefault(user_id, [])
    if space_id not in tasks["memberships"][user_id]:
        tasks["memberships"][user_id].append(space_id)

    tasks["active_space"][user_id] = space_id

def get_active_space_id(tasks, user_id: str):
    return tasks.get("active_space", {}).get(user_id)

def get_space_global_tasks(tasks, user_id: str):
    sid = get_active_space_id(tasks, user_id)
    if not sid:
        return [], None  # 未参加
    tasks.setdefault("space_tasks", {})
    tasks["space_tasks"].setdefault(sid, [])
    return tasks["space_tasks"][sid], sid
    
def _get_board_list(tasks, source_type, user_id, group_id):
    if source_type == "group" and group_id:
        return tasks["board"]["groups"].setdefault(group_id, [])
    return tasks["board"]["users"].setdefault(user_id, [])

def handle_board_list(reply_token, user_id, source_type=None, group_id=None):
    tasks = load_tasks()
    ui = get_board_ui_flags(tasks, user_id)
    show_delete = ui.get("show_delete", False)
    show_reorder = ui.get("show_reorder", False)

    items = _get_board_list(tasks, source_type, user_id, group_id)

    body = [
        {"type": "text", "text": f"📌 {BOARD_TITLE}", "weight": "bold", "size": "lg"},
        {"type": "text", "text": "（連絡先もお願い事もここにまとめる）", "size": "sm", "color": "#64748B"},
        {"type": "separator", "margin": "md"},
    ]

    if not items:
        body.append({"type": "text", "text": "まだ何も入ってないよ", "color": "#94A3B8"})
    else:
        for i, it in enumerate(items):
            text = it.get("text", "")
            row = [
                {"type": "text", "text": f"• {text}", "wrap": True, "flex": 8, "size": "sm"}
            ]

            if show_delete:
                row.append({
                    "type": "button", "style": "secondary", "height": "sm", "flex": 1,
                    "action": {"type": "postback", "label": "🗑", "data": f"#board_delete_{i}"}
                })

            body.append({"type": "box", "layout": "horizontal", "spacing": "sm", "contents": row})

            if show_reorder:
                body.append({
                    "type": "box", "layout": "horizontal", "spacing": "sm", "margin": "xs",
                    "contents": [
                        {"type": "button", "style": "secondary", "height": "sm",
                         "action": {"type": "postback", "label": "↑", "data": f"#board_move_{i}_up"}},
                        {"type": "button", "style": "secondary", "height": "sm",
                         "action": {"type": "postback", "label": "↓", "data": f"#board_move_{i}_down"}},
                    ]
                })

    flex = {
        "type": "flex",
        "altText": BOARD_TITLE,
        "contents": {"type": "bubble", "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": body}}
    }
    send_flex(reply_token, flex)
    
def handle_message(reply_token, user_id, text, source_type=None, group_id=None):
    state = user_states.get(user_id)

    # ✅ 集会所 参加（合言葉入力）
    if state == "space_join_wait_pass":
        tasks = load_tasks()
        passphrase = normalize_pass(text)
        if not passphrase:
            send_reply(reply_token, "合言葉が空っぽみたい。もう一度送ってね")
            return

        sid = get_or_create_space_by_pass(tasks, passphrase, user_id)
        if not sid:
            send_reply(reply_token, "合言葉がうまく読めなかった…もう一度送ってね")
            return

        join_space(tasks, user_id, sid)
        save_tasks(tasks)
        user_states.pop(user_id, None)

        space_name = tasks["spaces"][sid].get("name", "集会所")
        send_reply(reply_token, f"✅ 「{space_name}」に参加したよ！\n以後の全体予定はこの集会所が対象になるよ")
        return

    # （以下、既存の add_check_title / add_personal / board_add... など）

    # ✅ 伝言板 追加（ここを最上部に）
    if state and state.startswith("board_add"):
        tasks = load_tasks()

        if state == "board_add_user":
            tasks["board"]["users"].setdefault(user_id, []).append({"text": text})
        else:
            # board_add_group:<gid>
            gid = state.split(":", 1)[1]
            tasks["board"]["groups"].setdefault(gid, []).append({"text": text})

        save_tasks(tasks)
        user_states.pop(user_id, None)
        send_reply(reply_token, f"📌 {BOARD_TITLE}に入れたよ")
        return
        
    if state == "space_add_global":
        tasks = load_tasks()
        
        global_list, sid = get_space_global_tasks(tasks, user_id)
        if not sid:
            send_reply(reply_token, "まだ集会所に参加してないみたい。先に「合言葉で集会所に参加」を押してね")
            return
            
        tasks["space_tasks"][sid].append({"text": text, "done_by": []})
        save_tasks(tasks)
        
        user_states.pop(user_id, None)
        send_reply(reply_token, "🌍 全体予定を追加したよ")
        return
    
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
    
def handle_delete(reply_token, user_id, data, source_type, group_id=None):
    """
    data: #list_delete_p_{idx}  or  #list_delete_g_{idx}
    """
    tasks = load_tasks()

    # data を分解
    # 例: "#list_delete_p_0" -> ["#list", "delete", "p", "0"]
    _, _, scope, idx = data.split("_")
    idx = int(idx)

    if scope == "p":
        # 個人予定
        user_list = tasks.get("users", {}).get(user_id, [])
        if 0 <= idx < len(user_list):
            user_list.pop(idx)
            tasks["users"][user_id] = user_list

    elif scope == "g":
        # 全体予定（グループ）
        if source_type == "group" and group_id:
            group_list = tasks.get("groups", {}).get(group_id, [])
            if 0 <= idx < len(group_list):
                group_list.pop(idx)
                tasks.setdefault("groups", {})[group_id] = group_list

    save_tasks(tasks)

    # 削除後の最新状態で再表示（done は除外）
    personal = [
        t for t in tasks.get("users", {}).get(user_id, [])
        if t.get("status") != "done"
    ]

    global_tasks = []
    if source_type == "group" and group_id:
        global_tasks = [
            t for t in tasks.get("groups", {}).get(group_id, [])
            if user_id not in t.get("done_by", [])
        ]

    send_schedule(reply_token, personal, global_tasks)
    
def handle_space_done(reply_token, user_id, data):
    idx = int(data.split("_")[-1])
    tasks = load_tasks()

    items, sid = get_space_global_tasks(tasks, user_id)
    if not sid:
        send_reply(reply_token, "集会所が未選択だよ")
        return

    if 0 <= idx < len(items):
        items[idx].setdefault("done_by", [])
        if user_id not in items[idx]["done_by"]:
            items[idx]["done_by"].append(user_id)

    save_tasks(tasks)

    # 再表示（個人 + 集会所）
    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
    global_tasks, _ = get_space_global_tasks(tasks, user_id)
    send_schedule(reply_token, personal, global_tasks)

def handle_space_delete(reply_token, user_id, data):
    idx = int(data.split("_")[-1])
    tasks = load_tasks()

    items, sid = get_space_global_tasks(tasks, user_id)
    if not sid:
        send_reply(reply_token, "集会所が未選択だよ")
        return

    if 0 <= idx < len(items):
        items.pop(idx)

    save_tasks(tasks)

    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
    global_tasks, _ = get_space_global_tasks(tasks, user_id)
    send_schedule(reply_token, personal, global_tasks)

def handle_undo(reply_token, user_id, data, group_id):
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

    # ✅ ここでモード（settings）を読む
    ui = get_check_ui_flags(tasks, user_id)
    show_delete = ui.get("show_delete", False)
    show_reorder = ui.get("show_reorder", False)

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

            # =========================
            # タイトル行（開閉 + ゴミ箱）
            # show_delete が OFF の時はゴミ箱を描画しない
            # =========================
            if show_delete:
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
            else:
                # ゴミ箱を出さない代わりに、開閉ボタンを横いっぱいに
                contents.append({
                    "type": "button",
                    "style": "primary",
                    "action": {
                        "type": "postback",
                        "label": f"{arrow} {checklist.get('title','(no title)')}",
                        "data": f"#toggle_list_{c_idx}_{opened}"
                    }
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

                        row_contents = [
                            {
                                "type": "button",
                                "flex": 5 if show_delete else 6,
                                "style": "secondary",
                                "action": {
                                    "type": "postback",
                                    "label": f"{mark} {text}",
                                    "data": f"#toggle_check_{c_idx}_{i_idx}_{opened}"
                                }
                            }
                        ]

                        # ✅ 削除モードONの時だけ、項目削除ボタンを出す
                        if show_delete:
                            row_contents.append({
                                "type": "button",
                                "flex": 1,
                                "style": "secondary",
                                "action": {
                                    "type": "postback",
                                    "label": "🗑",
                                    "data": f"#delete_item_{c_idx}_{i_idx}_{opened}"
                                }
                            })

                        contents.append({
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "sm",
                            "contents": row_contents
                        })

                        # ✅ 並び替えモードONの時だけ、↑↓を出す
                        if show_reorder:
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

                # ✅ リスト丸ごと削除は削除モードONの時だけ
                if show_delete:
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
    
def handle_board_delete(reply_token, user_id, data, source_type=None, group_id=None):
    # data: #board_delete_{i}
    idx = int(data.split("_")[-1])
    tasks = load_tasks()
    items = _get_board_list(tasks, source_type, user_id, group_id)
    if 0 <= idx < len(items):
        items.pop(idx)
        save_tasks(tasks)
    handle_board_list(reply_token, user_id, source_type, group_id)

def handle_board_move(reply_token, user_id, data, source_type=None, group_id=None):
    # data: #board_move_{i}_up/down
    parts = data.split("_")
    idx = int(parts[2])
    direction = parts[3]
    tasks = load_tasks()
    items = _get_board_list(tasks, source_type, user_id, group_id)

    if direction == "up" and idx > 0:
        items[idx-1], items[idx] = items[idx], items[idx-1]
        save_tasks(tasks)
    elif direction == "down" and idx < len(items)-1:
        items[idx+1], items[idx] = items[idx], items[idx+1]
        save_tasks(tasks)

    handle_board_list(reply_token, user_id, source_type, group_id)
    
def get_check_ui_flags(tasks, user_id):
    tasks.setdefault("settings", {})
    tasks["settings"].setdefault(user_id, {})
    tasks["settings"][user_id].setdefault("check_ui", {})
    ui = tasks["settings"][user_id]["check_ui"]

    ui.setdefault("show_delete", False)
    ui.setdefault("show_reorder", False)
    return ui

def get_board_ui_flags(tasks, user_id):
    tasks.setdefault("settings", {})
    tasks["settings"].setdefault(user_id, {})
    tasks["settings"][user_id].setdefault("board_ui", {})
    ui = tasks["settings"][user_id]["board_ui"]
    ui.setdefault("show_delete", False)
    ui.setdefault("show_reorder", False)
    return ui

def toggle_board_ui_flag(tasks, user_id, flag_key):
    ui = get_board_ui_flags(tasks, user_id)
    ui[flag_key] = not ui.get(flag_key, False)
    return ui[flag_key]

def toggle_check_ui_flag(tasks, user_id, flag_key):
    ui = get_check_ui_flags(tasks, user_id)
    ui[flag_key] = not ui.get(flag_key, False)
    return ui[flag_key]

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json(silent=True) or {}
    print("=== HIT ===")

    for event in body.get("events", []):
        reply_token = event.get("replyToken")

        try:
            source = event.get("source", {}) or {}
            source_type = source.get("type")
            user_id = source.get("userId")
            group_id = source.get("groupId") if source_type == "group" else None

            if event.get("type") == "postback":
                data = event.get("postback", {}).get("data", "") or ""

                # --- リッチメニュー：予定表 ---
                if data == "scope=menu&action=list":
                    tasks = load_tasks()
                    personal = [t for t in tasks["users"].get(user_id, []) if t.get("status") != "done"]
                    
                    global_tasks, sid = get_space_global_tasks(tasks, user_id)
                    
                    未参加なら全体予定は空（必要なら案内だけ出す）
                    # if not sid:
                    #     send_reply(reply_token, "🗝 まだ集会所が未選択だよ。「その他」→「合言葉で集会所に参加」から入ってね")
                    send_schedule(reply_token, personal, global_tasks)

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

                # --- 通常：追加メニューを表示 ---
                elif data == "scope=menu&action=add":
                    handle_menu_add(reply_token, user_id)

                # --- その他メニュー ---
                elif data in ("scope=menu&action=other", "other"):
                    handle_other_menu(reply_token, user_id, source_type, group_id)

                # --- 伝言板 ---
                elif data == "#board_list":
                    handle_board_list(reply_token, user_id, source_type, group_id)

                elif data == "#board_add":
                    if source_type == "group" and group_id:
                        user_states[user_id] = f"board_add_group:{group_id}"
                        send_reply(reply_token, f"➕ {BOARD_TITLE}に入れる内容を送ってね（グループ共有）")
                    else:
                        user_states[user_id] = "board_add_user"
                        send_reply(reply_token, f"➕ {BOARD_TITLE}に入れる内容を送ってね（個人用）")

                # --- 集会所参加（合言葉）---
                elif data == "#space_join":
                    user_states[user_id] = "space_join_wait_pass"
                    send_reply(reply_token, "🗝 合言葉（例：現場名 / 職長名）を送ってね")

                elif data == "#board_toggle_delete":
                    tasks = load_tasks()
                    toggle_board_ui_flag(tasks, user_id, "show_delete")
                    save_tasks(tasks)
                    handle_other_menu(reply_token, user_id, source_type, group_id)

                elif data == "#board_toggle_reorder":
                    tasks = load_tasks()
                    toggle_board_ui_flag(tasks, user_id, "show_reorder")
                    save_tasks(tasks)
                    handle_other_menu(reply_token, user_id, source_type, group_id)

                elif data.startswith("#board_delete_"):
                    handle_board_delete(reply_token, user_id, data, source_type, group_id)

                elif data.startswith("#board_move_"):
                    handle_board_move(reply_token, user_id, data, source_type, group_id)

                # ====== 予定（schedule）系 ======
                elif data.startswith("#space_done_"):
                    handle_space_done(reply_token, user_id, data)
                    
                elif data.startswith("#space_delete_"):
                    handle_space_delete(reply_token, user_id, data)
                    
                elif data.startswith("#list_undo_"):
                    handle_undo(reply_token, user_id, data, group_id)

                elif data == "#show_done":
                    handle_show_done(reply_token, user_id, source_type, group_id)

                elif data == "#add_personal":
                    user_states[user_id] = "add_personal"
                    send_reply(reply_token, "追加する予定を送ってね")
                    
                elif data == "#other_add_global":
                    user_states[user_id] = "space_add_global"
                    send_reply(reply_token, "🌍 全体予定（集会所共通）を送ってね")

                # ====== チェックリスト作成 ======
                elif data == "#add_check":
                    user_states[user_id] = "add_check_title"
                    send_reply(reply_token, "📝 チェックリストのタイトルを送ってね")

                # ====== モード切替 ======
                elif data == "#toggle_delete_mode":
                    tasks = load_tasks()
                    toggle_check_ui_flag(tasks, user_id, "show_delete")
                    save_tasks(tasks)
                    handle_menu_add(reply_token, user_id)

                elif data == "#toggle_reorder_mode":
                    tasks = load_tasks()
                    toggle_check_ui_flag(tasks, user_id, "show_reorder")
                    save_tasks(tasks)
                    handle_menu_add(reply_token, user_id)

                else:
                    send_reply(reply_token, "未定義メニュー")

            elif event.get("type") == "message":
                text = event.get("message", {}).get("text", "")
                handle_message(reply_token, user_id, text, source_type, group_id)

        except Exception as e:
            print("❌ webhook handler error:", repr(e))
            print(traceback.format_exc())
            if reply_token:
                send_reply(
                    reply_token,
                    "⚠️ いま保存先（DB）が一時的に不調みたい。\n少し待ってからもう一度操作してね。"
                )

    return "OK", 200
    
@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)