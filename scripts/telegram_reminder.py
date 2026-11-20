#!/usr/bin/env python3
"""
ЎзММА Ижро Мониторинги — Кунлик Telegram эслатма боти (соат 10:00 UZT).
index.html ичидаги RAW_DATA маълумотларини ўқийди, бугунги сана бўйича
қарздорликларни қайта ҳисоблайди ва ҳар бир ижрочига шахсий эслатма юборади.
"""

import datetime
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML_PATH = os.path.join(ROOT_DIR, "index.html")
CHAT_IDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_ids.json")

EXECUTOR_CONTACTS = {
    "С.Умаров (19 та)": {"name": "Умаров Саидаҳмад", "username": "SayidAhmad_1501", "phone": ""},
    "С.Устабабаев (12 та)": {"name": "Устабабаев Санджар", "username": "", "phone": "+998900452414"},
    "Н.Хакимов (9 та)": {"name": "Хакимов Низом", "username": "Nizom_Khakimov", "phone": ""},
    "Ф.Ачилов (8 та)": {"name": "Ачилов Фаёз", "username": "achiiilov", "phone": ""},
    "У.Ахмедов (4 та)": {"name": "Ахмедов Улуғбек", "username": "bek3300204", "phone": ""},
    "Н.Қутбиддинова (3 та)": {"name": "Қутбиддинова Нодира", "username": "yourrnodii", "phone": ""},
    "Ш.Хаитов (2 та)": {"name": "Хаитов Шохруз", "username": "Shahruz9", "phone": ""},
}


def tg_api(token: str, method: str, payload: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_raw_data() -> dict:
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    match = re.search(r"const\s+RAW_DATA\s*=\s*(\{.*?\});", html)
    if not match:
        raise RuntimeError("index.html ичидан RAW_DATA топилмади")
    return json.loads(match.group(1))


def recalculate_tasks(tasks: list[dict], today_uzt: datetime.date) -> None:
    for t in tasks:
        dl = (t.get("deadline") or "").strip()
        parts = dl.split(".")
        if len(parts) == 3:
            try:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                target = datetime.date(y, m, d)
                diff = (target - today_uzt).days
                t["days_diff"] = diff
                t["is_overdue"] = diff < 0
            except ValueError:
                pass


def load_chat_ids() -> dict:
    if os.path.exists(CHAT_IDS_PATH):
        with open(CHAT_IDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_chat_ids(chat_ids: dict) -> None:
    with open(CHAT_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(chat_ids, f, ensure_ascii=False, indent=2)


def discover_chat_ids(token: str, chat_ids: dict) -> dict:
    """Ботга /start босган фойдаланувчиларнинг chat_id рақамларини автоматик аниқлайди."""
    username_to_sheet = {
        info["username"].lower(): sheet
        for sheet, info in EXECUTOR_CONTACTS.items()
        if info["username"]
    }
    try:
        res = tg_api(token, "getUpdates")
        for upd in res.get("result", []):
            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            user = msg.get("from") or {}
            uname = (user.get("username") or "").lower()
            chat_id = chat.get("id")
            if uname and uname in username_to_sheet and chat_id:
                sheet = username_to_sheet[uname]
                chat_ids[sheet] = chat_id
            # Устабабаев Санджар исм ёки телефон юборса ҳам мослаш
            text = (msg.get("text") or "").lower()
            contact = msg.get("contact") or {}
            phone = (contact.get("phone_number") or "").replace("+", "")
            if ("998900452414" in phone or "устабабаев" in text or "ustababaev" in text or "санжар" in text or "санджар" in text) and chat_id:
                chat_ids["С.Устабабаев (12 та)"] = chat_id
    except Exception as e:
        print(f"getUpdates хатоси: {e}")
    return chat_ids


def build_personal_message(sheet: str, info: dict, tasks: list[dict], today_str: str) -> str:
    ex_tasks = [t for t in tasks if t.get("sheet_source") == sheet]
    done = [t for t in ex_tasks if t.get("status") == "Бажарилди"]
    overdue = [t for t in ex_tasks if t.get("is_overdue") and t.get("status") != "Бажарилди"]
    upcoming = [t for t in ex_tasks if not t.get("is_overdue") and t.get("status") != "Бажарилди"]

    total = len(ex_tasks)
    done_pct = f"{(len(done) / total * 100):.1f}" if total else "0.0"
    overdue_pct = f"{(len(overdue) / total * 100):.1f}" if total else "0.0"

    lines = [
        f"📌 <b>ЎзММА Ижро Мониторинги — Кунлик Эслатма</b>",
        f"📅 Сана: <b>{today_str}</b>",
        f"👤 Масъул: <b>{info['name']}</b>",
        f"📊 Жами: {total} та | Бажарилди: {len(done)} та ({done_pct}%) | Қарздорлик: <b>{len(overdue)} та ({overdue_pct}%)</b>",
        "",
    ]

    if overdue:
        lines.append(f"🚨 <b>МУДДАТИ ЎТГАН ҚАРЗДОРЛИКЛАР ({len(overdue)} та):</b>")
        for idx, t in enumerate(overdue[:10], 1):
            doc = (t.get("doc_info") or "").replace("\n", " ")
            days = abs(t.get("days_diff", 0))
            snippet = (t.get("task_text") or "")[:95].replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"{idx}. <b>[{t['id']}]</b> {doc} — <i>{days} кун кечиккан</i>\n   {snippet}...")
        if len(overdue) > 10:
            lines.append(f"...ва яна {len(overdue) - 10} та муддати ўтган топшириқ.")
    else:
        lines.append("✅ Сизда муддати ўтган қарздорликлар йўқ!")

    if upcoming:
        lines.append(f"\n⏳ Муддати яқинлашаётган топшириқлар: <b>{len(upcoming)} та</b>.")

    lines.append("\n🔗 Дешборд: https://ozmmaijrovatahlil.github.io/")
    lines.append("Илтимос, <b>edo.ijro.uz</b> орқали ижро натижасини бугун якунланг.")
    return "\n".join(lines)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN муҳит ўзгарувчиси ўрнатилмаган!")

    uzt_now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
    today_uzt = uzt_now.date()
    today_str = uzt_now.strftime("%d.%m.%Y")

    raw_data = load_raw_data()
    tasks = raw_data.get("tasks", [])
    recalculate_tasks(tasks, today_uzt)

    chat_ids = load_chat_ids()
    # Қўшимча равишда GitHub Secret орқали берилган chat_ids ни ҳам ўқиш
    env_chat_ids = os.environ.get("EXECUTOR_CHAT_IDS", "").strip()
    if env_chat_ids:
        try:
            chat_ids.update(json.loads(env_chat_ids))
        except json.JSONDecodeError:
            pass

    chat_ids = discover_chat_ids(token, chat_ids)
    save_chat_ids(chat_ids)

    sent_report = []
    missing_report = []

    for sheet, info in EXECUTOR_CONTACTS.items():
        cid = chat_ids.get(sheet)
        if not cid:
            missing_report.append(f"{info['name']} (@{info['username'] or info['phone']})")
            continue
        msg_text = build_personal_message(sheet, info, tasks, today_str)
        try:
            tg_api(token, "sendMessage", {
                "chat_id": cid,
                "text": msg_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            sent_report.append(info["name"])
            print(f"Юборилди: {info['name']} (chat_id={cid})")
        except urllib.error.URLError as e:
            print(f"Хатолик ({info['name']}): {e}")

    print("Юборилганлар:", sent_report)
    if missing_report:
        print("Ҳали ботга /start босмаганлар:", missing_report)


if __name__ == "__main__":
    main()
