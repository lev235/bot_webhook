#!/usr/bin/env python3
"""
Telegram anti-spam + reputation bot (Render/Webhook edition)

• Удаляет мат (ловит е б л а н / е-б-л-а-н / е_б_л_а_н и т.д.)
• Удаляет ссылки/рекламу
• Начисляет репутацию за позитив
• /rep и /top
• Работает через webhook (aiohttp), совместим с Render Free
"""

import json, os, re, logging
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler,
    Defaults, filters
)

TOKEN = os.getenv("BOT_TOKEN")                # обязательно
PUBLIC_URL = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))          # Render проксирует на этот порт
if not (TOKEN and PUBLIC_URL):
    raise SystemExit("Set BOT_TOKEN and APP_URL/RENDER_EXTERNAL_URL")

# ─────────────── фильтры мата/спама ─────────────── #
BASE_MAT = [
    "бля","бляд","хуй","пизд","еба","еби","ебу","ебат","сука","мудак",
    "пидор","гандон","шлюха","еблан","залуп","мудок","нахуй","соси",
    "хуесос","долбаёб","пидар","мразь",
]
def variants(w:str)->list[str]:
    ch=list(w); return [w," ".join(ch),"-".join(ch),"_".join(ch)]
def flex(w:str)->str: return r"\s*[\W_]*".join(map(re.escape,w))
MAT_PATTERNS=[flex(v) for b in BASE_MAT for v in variants(b)]
MAT_REGEX=re.compile(r"(?i)(%s)"%"|".join(MAT_PATTERNS))

SPAM_REGEX=re.compile(r"(https?://\S+|t\.me/|joinchat|скидк|деш[её]в|подпис)",re.I)
POSITIVE={"спасибо","круто","полезно","супер","great","awesome","thanks"}

# ─────────────── репутация ─────────────── #
STORE=Path("reputation.json")
load=lambda: json.loads(STORE.read_text("utf-8")) if STORE.exists() else {}
def inc(user:int,d=1):
    rep=load(); rep[str(user)]=rep.get(str(user),0)+d
    STORE.write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    return rep[str(user)]

# ─────────────── хэндлеры ─────────────── #
async def on_text(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    msg=update.effective_message
    if not msg or not msg.text: return
    t=msg.text.lower()

    if MAT_REGEX.search(t) or SPAM_REGEX.search(t):
        await msg.delete(); return

    if any(w in t for w in POSITIVE):
        await msg.reply_text(f"👍 Репутация +1 (итого {inc(msg.from_user.id)})")

async def cmd_rep(update:Update, _):
    await update.message.reply_text(
        f"👤 Ваша репутация: <b>{load().get(str(update.effective_user.id),0)}</b>"
    )

async def cmd_top(update:Update, _):
    rep=load()
    if not rep:
        await update.message.reply_text("Пока пусто."); return
    top=sorted(rep.items(),key=lambda kv:kv[1],reverse=True)[:10]
    lines=["<b>🏆 ТОП-10</b>"]+[
        f"{i+1}. <a href=\"tg://user?id={uid}\">user_{uid}</a> — {s}"
        for i,(uid,s) in enumerate(top)
    ]
    await update.message.reply_text("\n".join(lines))

# ─────────────── запуск ─────────────── #
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s: %(message)s")

app=(
    ApplicationBuilder()
    .token(TOKEN)
    .defaults(Defaults(parse_mode=ParseMode.HTML))
    .build()
)
app.add_handler(CommandHandler("rep",cmd_rep))
app.add_handler(CommandHandler("top",cmd_top))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,on_text))

if __name__=="__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=f"{TOKEN}",
        webhook_url=f"{PUBLIC_URL}/{TOKEN}",
        drop_pending_updates=True,
    )