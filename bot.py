#!/usr/bin/env python3
"""
Telegram anti-spam & reputation bot
• На старте обрабатывает последние 25 сообщений (мат/репутация)
• Дальше работает в реальном времени
"""

import os, re, json, logging
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    MessageHandler, CommandHandler,
    Defaults, filters
)

# ──────────── настройка окружения ──────────── #
TOKEN      = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
PORT       = int(os.getenv("PORT", "10000"))
if not (TOKEN and PUBLIC_URL):
    raise SystemExit("Set BOT_TOKEN and APP_URL/RENDER_EXTERNAL_URL")

# ─────────────── фильтры ─────────────── #
BASE = ["бля","бляд","хуй","пизд","еба","еби","ебу","ебат","сука","мудак",
        "пидор","гандон","шлюха","еблан","залуп","мудок","нахуй",
        "соси","хуесос","долбаёб","пидар","мразь"]

def variants(w:str)->list[str]:
    ch=list(w); return [w, " ".join(ch), "-".join(ch), "_".join(ch)]

def flex(w:str)->str:        # eблан -> е\W*б\W*л...
    return r"\s*[\W_]*".join(map(re.escape, w))

MAT_REGEX  = re.compile("|".join(flex(v) for b in BASE for v in variants(b)), re.I)
SPAM_REGEX = re.compile(r"(https?://\S+|t\.me/|joinchat|скидк|деш[её]в|подпис)", re.I)
POSITIVE   = {"спасибо","круто","полезно","супер","great","awesome","thanks"}

# ───────────── persistent state ───────────── #
STORE = Path("state.json")
state = {"rep": {}, "seen_rep": {}, "seen_del": {}}
if STORE.exists():
    state.update(json.loads(STORE.read_text("utf-8")))

def save():
    STORE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def inc_rep(uid:int, delta:int=1) -> int:
    uid=str(uid)
    state["rep"][uid] = state["rep"].get(uid,0) + delta
    save()
    return state["rep"][uid]

# ─────────── backlog-сканер (25 сообщений) ─────────── #
BACKLOG_LIMIT = 25
backlog_counter = 0        # глобальный счётчик обработанных апдейтов на старте
backlog_done    = False

def in_backlog_phase() -> bool:
    return not backlog_done

def mark_backlog_processed():
    global backlog_done
    backlog_done = True

# ──────────── handlers ──────────── #
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global backlog_counter
    msg = update.effective_message
    if not msg or not msg.text:
        return

    chat_id = str(msg.chat.id)
    mid     = msg.message_id
    txt     = msg.text.lower()

    # ── 1. Первые 25 апдейтов после запуска ── #
    if in_backlog_phase():
        backlog_counter += 1
        if backlog_counter >= BACKLOG_LIMIT:
            mark_backlog_processed()

    # ── 2. Мат / спам ── #
    if MAT_REGEX.search(txt) or SPAM_REGEX.search(txt):
        if mid in state["seen_del"].get(chat_id, {}):
            return            # уже удаляли это сообщение
        await msg.delete()
        state.setdefault("seen_del", {}).setdefault(chat_id, {})[mid] = 1
        save()
        return

    # ── 3. Позитив – начисляем репутацию (если не делали) ── #
    if any(w in txt for w in POSITIVE):
        if mid in state["seen_rep"].get(chat_id, {}):
            return            # уже начисляли за этот message_id
        total = inc_rep(msg.from_user.id)
        await msg.reply_text(f"👍 Репутация +1 (итого {total})")
        state.setdefault("seen_rep", {}).setdefault(chat_id, {})[mid] = 1
        save()

async def cmd_rep(update: Update, _):
    uid=str(update.effective_user.id)
    await update.message.reply_text(
        f"👤 Ваша репутация: <b>{state['rep'].get(uid,0)}</b>"
    )

async def cmd_top(update: Update, _):
    if not state["rep"]:
        await update.message.reply_text("Пока пусто."); return
    top = sorted(state["rep"].items(), key=lambda kv: kv[1], reverse=True)[:10]
    lines = ["<b>🏆 ТОП-10</b>"] + [
        f"{i+1}. <a href='tg://user?id={u}'>user_{u}</a> — {s}"
        for i, (u,s) in enumerate(top)
    ]
    await update.message.reply_text("\n".join(lines))

# ──────────── запуск приложения ──────────── #
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s: %(message)s")

app = (
    ApplicationBuilder()
    .token(TOKEN)
    .defaults(Defaults(parse_mode=ParseMode.HTML))
    .build()
)
app.add_handler(CommandHandler("rep", cmd_rep))
app.add_handler(CommandHandler("top", cmd_top))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{PUBLIC_URL}/{TOKEN}",
        drop_pending_updates=False   # важно: Telegram пришлёт накопленные апдейты
    )
from aiohttp import web

async def ping_handler(request):
    return web.Response(text="OK")

app.web_app.add_get("/ping", ping_handler)