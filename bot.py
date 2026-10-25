import os, sqlite3, random, logging, datetime, asyncio
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
TZ = ZoneInfo(os.environ.get("TZNAME", "UTC"))
VERSE_HOUR = int(os.environ.get("VERSE_HOUR", "7"))

# ---------- Database ----------
db = sqlite3.connect(os.environ.get("DB_PATH", "mission_bot.db"), check_same_thread=False)
db.executescript("""
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, keyword TEXT, file_id TEXT, name TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, name TEXT, username TEXT,
    lang TEXT DEFAULT 'en', verse_on INTEGER DEFAULT 1, uses INTEGER DEFAULT 0,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, user_id INTEGER, query TEXT, admin_msg_id INTEGER);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS verses(id INTEGER PRIMARY KEY, ref TEXT, en TEXT, am TEXT);
""")
if not db.execute("SELECT 1 FROM verses").fetchone():
    db.executemany("INSERT INTO verses(ref,en,am) VALUES(?,?,NULL)", [
        ("Matthew 28:19", "Go ye therefore, and teach all nations, baptizing them in the name of the Father, and of the Son, and of the Holy Ghost:"),
        ("Mark 16:15", "And he said unto them, Go ye into all the world, and preach the gospel to every creature."),
        ("Isaiah 6:8", "Also I heard the voice of the Lord, saying, Whom shall I send, and who will go for us? Then said I, Here am I; send me."),
        ("Acts 1:8", "But ye shall receive power, after that the Holy Ghost is come upon you: and ye shall be my witnesses unto me both in Jerusalem, and in all Judaea, and in Samaria, and unto the uttermost part of the earth."),
        ("Psalm 96:3", "Declare his glory among the heathen, his wonders among all people."),
    ])
db.commit()

def q(sql, *a):
    cur = db.execute(sql, a); db.commit(); return cur

# ---------- Texts (English + Amharic) ----------
T = {
 "en": {
  "welcome": "🌟 Welcome!\n\nI help you find files and learn about our mission. Type a word to search, or use the buttons below.",
  "find": "🔎 Find files", "mission": "🎯 Our mission", "verse": "📖 Today's verse",
  "settings": "⚙️ Settings", "help": "❓ Help", "back": "⬅️ Back",
  "ask_kw": "🔎 Type a keyword or file name to search.",
  "found": "✅ Found these for you. Tap one:",
  "not_found": "😔 Sorry, I couldn't find that file. Should I ask the owner to add it?",
  "ask_owner": "📨 Ask the owner",
  "req_sent": "✅ Request sent! The owner will reply here when it's ready.",
  "req_done": "🎉 The owner answered your request. Enjoy!",
  "no_req": "Please search for something first.",
  "no_mission": "The mission has not been added yet.",
  "mission_title": "🎯 Our mission", "no_verse": "No verses added yet.",
  "settings_title": "⚙️ Settings\n\nChoose your language or turn the daily verse on/off.",
  "daily": "🔔 Daily verse", "lang_changed": "✅ Language updated",
  "help_text": "❓ Help\n\n🔎 Type a word or file name to find a file.\n📨 If a file is missing, you can ask the owner.\n📖 You can receive a mission verse every day.\n⚙️ Change language in Settings.",
  "thanks": ["🙏 Thank you for using this bot!", "🌟 Great choice! God bless you!",
             "💛 We're glad to serve you!", "✨ Thanks for being here!"],
 },
 "am": {
  "welcome": "🌟 እንኳን ደህና መጡ!\n\nፋይሎችን እንዲያገኙ እና ስለ ተልዕኳችን እንዲያውቁ እረዳዎታለሁ። ለመፈለግ ቃል ይጻፉ ወይም ከታች ያሉትን አዝራሮች ይጠቀሙ።",
  "find": "🔎 ፋይል ፈልግ", "mission": "🎯 ተልዕኳችን", "verse": "📖 የዛሬ ጥቅስ",
  "settings": "⚙️ ቅንብሮች", "help": "❓ እገዛ", "back": "⬅️ ተመለስ",
  "ask_kw": "🔎 ለመፈለግ ቃል ወይም የፋይል ስም ይጻፉ።",
  "found": "✅ እነዚህ ተገኝተዋል። አንዱን ይምረጡ፦",
  "not_found": "😔 ይቅርታ፣ ፋይሉ አልተገኘም። ባለቤቱ እንዲጨምረው ልጠይቅ?",
  "ask_owner": "📨 ባለቤቱን ጠይቅ",
  "req_sent": "✅ ጥያቄዎ ተልኳል! ዝግጁ ሲሆን ባለቤቱ እዚህ ይመልሳል።",
  "req_done": "🎉 ባለቤቱ ጥያቄዎን መልሷል። ይጠቀሙ!",
  "no_req": "መጀመሪያ ፋይል ይፈልጉ።",
  "no_mission": "ተልዕኮው ገና አልተጨመረም።",
  "mission_title": "🎯 ተልዕኳችን", "no_verse": "ጥቅስ ገና አልተጨመረም።",
  "settings_title": "⚙️ ቅንብሮች\n\nቋንቋ ይምረጡ ወይም ዕለታዊ ጥቅስ ያብሩ/ያጥፉ።",
  "daily": "🔔 ዕለታዊ ጥቅስ", "lang_changed": "✅ ቋንቋ ተቀይሯል",
  "help_text": "❓ እገዛ\n\n🔎 ፋይል ለማግኘት ቃል ወይም የፋይል ስም ይጻፉ።\n📨 ፋይሉ ከሌለ ባለቤቱን መጠየቅ ይችላሉ።\n📖 በየቀኑ የተልዕኮ ጥቅስ ሊደርስዎ ይችላል።\n⚙️ በቅንብሮች ውስጥ ቋንቋ ይቀይሩ።",
  "thanks": ["🙏 ስለተጠቀሙን እናመሰግናለን!", "🌟 እግዚአብሔር ይባርክዎ!",
             "💛 እርስዎን ማገልገል ደስ ያሰኘናል!", "✨ ስለመጡ እናመሰግናለን!"],
 },
}

# ---------- Helpers ----------
def log_user(u):
    q("""INSERT INTO users(user_id,name,username,uses) VALUES(?,?,?,1)
         ON CONFLICT(user_id) DO UPDATE SET uses=uses+1, name=excluded.name, username=excluded.username""",
      u.id, u.full_name, u.username)

def lang(uid):
    r = q("SELECT lang FROM users WHERE user_id=?", uid).fetchone()
    return r[0] if r else "en"

def main_menu(l):
    t = T[l]
    return Markup([[Btn(t["find"], callback_data="find"), Btn(t["mission"], callback_data="mission")],
                   [Btn(t["verse"], callback_data="verse"), Btn(t["settings"], callback_data="settings")],
                   [Btn(t["help"], callback_data="help")]])

def back_btn(l):
    return Markup([[Btn(T[l]["back"], callback_data="home")]])

def settings_menu(uid):
    l = lang(uid); t = T[l]
    on = q("SELECT verse_on FROM users WHERE user_id=?", uid).fetchone()[0]
    return Markup([[Btn("English", callback_data="lang:en"), Btn("አማርኛ", callback_data="lang:am")],
                   [Btn(f"{t['daily']}: {'✅' if on else '❌'}", callback_data="toggle")],
                   [Btn(t["back"], callback_data="home")]])

def verse_text(l):
    rows = q("SELECT ref,en,am FROM verses ORDER BY id").fetchall()
    if not rows: return None
    ref, en, am = rows[datetime.date.today().toordinal() % len(rows)]
    body = am if (l == "am" and am) else en
    return f"📖 {ref}\n\n“{body}”"

SENDERS = {"document": "send_document", "photo": "send_photo",
           "video": "send_video", "audio": "send_audio"}
async def send_stored(bot, chat_id, file_id, kind):
    await getattr(bot, SENDERS[kind])(chat_id, file_id)

# ---------- User commands ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log_user(update.effective_user)
    l = lang(update.effective_user.id)
    await update.message.reply_text(T[l]["welcome"], reply_markup=main_menu(l))

async def search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.message; u = m.from_user
    # Owner replying to a file request -> forward answer to that user
    if u.id == ADMIN_ID and m.reply_to_message:
        r = q("SELECT user_id FROM requests WHERE admin_msg_id=?", m.reply_to_message.message_id).fetchone()
        if r:
            await ctx.bot.send_message(r[0], "💬 " + m.text)
            await m.reply_text("✅ Sent to the user.")
            return
    log_user(u); l = lang(u.id); t = T[l]
    text = m.text.strip().lower(); like = f"%{text}%"
    rows = q("SELECT id,name FROM files WHERE keyword LIKE ? OR lower(name) LIKE ? LIMIT 10", like, like).fetchall()
    if not rows:
        ctx.user_data["last_q"] = m.text.strip()
        kb = Markup([[Btn(t["ask_owner"], callback_data="ask")], [Btn(t["back"], callback_data="home")]])
        await m.reply_text(t["not_found"], reply_markup=kb)
        return
    kb = [[Btn("📄 " + (n or "file"), callback_data=f"get:{i}")] for i, n in rows]
    kb.append([Btn(t["back"], callback_data="home")])
    await m.reply_text(t["found"], reply_markup=Markup(kb))

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query; u = cq.from_user
    log_user(u); l = lang(u.id); t = T[l]; d = cq.data

    if d == "home":
        await cq.answer(); await cq.edit_message_text(t["welcome"], reply_markup=main_menu(l))
    elif d == "find":
        await cq.answer(); await cq.edit_message_text(t["ask_kw"], reply_markup=back_btn(l))
    elif d == "help":
        await cq.answer(); await cq.edit_message_text(t["help_text"], reply_markup=back_btn(l))
    elif d == "mission":
        r = q("SELECT v FROM kv WHERE k=?", f"mission_{l}").fetchone() or q("SELECT v FROM kv WHERE k='mission_en'").fetchone()
        body = r[0] if r else t["no_mission"]
        await cq.answer(); await cq.edit_message_text(f"{t['mission_title']}\n\n{body}", reply_markup=back_btn(l))
    elif d == "verse":
        await cq.answer()
        await cq.edit_message_text(verse_text(l) or t["no_verse"], reply_markup=back_btn(l))
    elif d == "settings":
        await cq.answer(); await cq.edit_message_text(t["settings_title"], reply_markup=settings_menu(u.id))
    elif d.startswith("lang:"):
        q("UPDATE users SET lang=? WHERE user_id=?", d.split(":")[1], u.id)
        l = lang(u.id); t = T[l]
        await cq.answer(t["lang_changed"])
        await cq.edit_message_text(t["settings_title"], reply_markup=settings_menu(u.id))
    elif d == "toggle":
        q("UPDATE users SET verse_on = 1 - verse_on WHERE user_id=?", u.id)
        await cq.answer("✅")
        await cq.edit_message_text(t["settings_title"], reply_markup=settings_menu(u.id))
    elif d.startswith("get:"):
        row = q("SELECT file_id,kind FROM files WHERE id=?", int(d.split(":")[1])).fetchone()
        if not row:
            await cq.answer("File not found", show_alert=True); return
        await cq.answer(random.choice(t["thanks"]), show_alert=True)   # pop-up appreciation
        await send_stored(ctx.bot, cq.message.chat_id, row[0], row[1])
    elif d == "ask":
        query = ctx.user_data.get("last_q")
        if not query:
            await cq.answer(t["no_req"], show_alert=True); return
        rid = q("INSERT INTO requests(user_id,query) VALUES(?,?)", u.id, query).lastrowid
        sent = await ctx.bot.send_message(
            ADMIN_ID,
            f"📨 File request #{rid}\nFrom: {u.full_name} (@{u.username}) id {u.id}\n"
            f"Looking for: {query}\n\nReply to THIS message with a file or text to answer.")
        q("UPDATE requests SET admin_msg_id=? WHERE id=?", sent.message_id, rid)
        ctx.user_data.pop("last_q", None)
        await cq.answer(random.choice(t["thanks"]), show_alert=True)
        await cq.edit_message_text(t["req_sent"], reply_markup=back_btn(l))

# ---------- Owner: add files ----------
async def on_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.message
    if m.from_user.id != ADMIN_ID: return
    if m.document: fid, kind, name = m.document.file_id, "document", m.document.file_name
    elif m.photo: fid, kind, name = m.photo[-1].file_id, "photo", "photo"
    elif m.video: fid, kind, name = m.video.file_id, "video", m.video.file_name or "video"
    elif m.audio: fid, kind, name = m.audio.file_id, "audio", m.audio.file_name or "audio"
    else: return
    req = None
    if m.reply_to_message:
        req = q("SELECT user_id,query FROM requests WHERE admin_msg_id=?", m.reply_to_message.message_id).fetchone()
    if req:   # answering a user's request: send it and save it for next time
        q("INSERT INTO files(keyword,file_id,name,kind) VALUES(?,?,?,?)", req[1].lower(), fid, name, kind)
        await send_stored(ctx.bot, req[0], fid, kind)
        await ctx.bot.send_message(req[0], T[lang(req[0])]["req_done"])
        await m.reply_text(f"✅ Sent to the user and saved under '{req[1].lower()}'.")
        return
    kw = (m.caption or "").strip().lower()
    if not kw:
        await m.reply_text("Add a keyword as the caption, then send again."); return
    q("INSERT INTO files(keyword,file_id,name,kind) VALUES(?,?,?,?)", kw, fid, name, kind)
    await m.reply_text(f"✅ Saved '{name}' under '{kw}'.")

# ---------- Owner commands ----------
def admin_only(fn):
    async def wrapper(update, ctx):
        if update.effective_user.id == ADMIN_ID:
            await fn(update, ctx)
    return wrapper

@admin_only
async def users_cmd(update, ctx):
    total = q("SELECT COUNT(*) FROM users").fetchone()[0]
    nf = q("SELECT COUNT(*) FROM files").fetchone()[0]
    rows = q("SELECT name,username,uses,lang FROM users ORDER BY uses DESC LIMIT 40").fetchall()
    text = f"👥 Users: {total}   📁 Files: {nf}\n\n" + "\n".join(
        f"{n} (@{u}) – {c} uses [{l}]" for n, u, c, l in rows)
    await update.message.reply_text(text[:4000])

@admin_only
async def setmission(update, ctx):   # /setmission en Your text   or   /setmission am ጽሑፍ
    parts = update.message.text.split(None, 2)
    if len(parts) < 3 or parts[1] not in ("en", "am"):
        await update.message.reply_text("Use: /setmission en Your mission text\nor: /setmission am የተልዕኮ ጽሑፍ"); return
    q("INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)", f"mission_{parts[1]}", parts[2])
    await update.message.reply_text("✅ Mission saved.")

@admin_only
async def addverse(update, ctx):   # /addverse Reference | English text | Amharic text (optional)
    body = update.message.text.partition(" ")[2]
    p = [x.strip() for x in body.split("|")]
    if len(p) < 2:
        await update.message.reply_text("Use: /addverse John 3:16 | English text | Amharic text (optional)"); return
    q("INSERT INTO verses(ref,en,am) VALUES(?,?,?)", p[0], p[1], p[2] if len(p) > 2 else None)
    await update.message.reply_text("✅ Verse added.")

@admin_only
async def files_cmd(update, ctx):
    rows = q("SELECT id,keyword,name FROM files ORDER BY id DESC LIMIT 50").fetchall()
    await update.message.reply_text("\n".join(f"{i}. [{k}] {n}" for i, k, n in rows) or "No files yet.")

@admin_only
async def delfile(update, ctx):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Use: /delfile 3  (see numbers with /files)"); return
    q("DELETE FROM files WHERE id=?", int(ctx.args[0]))
    await update.message.reply_text("🗑 Deleted.")

async def verse_cmd(update, ctx):
    l = lang(update.effective_user.id)
    await update.message.reply_text(verse_text(l) or T[l]["no_verse"])

# ---------- Daily verse ----------
async def daily(ctx: ContextTypes.DEFAULT_TYPE):
    for (uid, l) in q("SELECT user_id,lang FROM users WHERE verse_on=1").fetchall():
        txt = verse_text(l)
        if not txt: return
        try:
            await ctx.bot.send_message(uid, "🌅 " + txt)
        except Exception:
            pass
        await asyncio.sleep(0.05)

# ---------- Run ----------
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("verse", verse_cmd))
app.add_handler(CommandHandler("users", users_cmd))
app.add_handler(CommandHandler("setmission", setmission))
app.add_handler(CommandHandler("addverse", addverse))
app.add_handler(CommandHandler("files", files_cmd))
app.add_handler(CommandHandler("delfile", delfile))
app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, on_file))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
app.add_handler(CallbackQueryHandler(on_button))
app.job_queue.run_daily(daily, time=datetime.time(VERSE_HOUR, 0, tzinfo=TZ))
app.run_polling()