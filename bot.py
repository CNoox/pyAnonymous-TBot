from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, ConversationHandler
from telegram import Update
from telegram import ReplyKeyboardMarkup
import sqlite3
import os

DB_FILE = "users.db"
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS replies_map (
            admin_message_id INTEGER PRIMARY KEY,
            user_chat_id INTEGER NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


def add_user(chat_id, first_name, last_name, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (chat_id, first_name, last_name, username) VALUES (?, ?, ?, ?)",
              (chat_id, first_name, last_name, username))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users


WAITING_FOR_MESSAGE = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.first_name or "", user.last_name or "", user.username or "")
    welcome_text = (
        "👋 Hello and welcome!\n\n"
        "This is an anonymous chat bot.\n"
        "You can send messages, photos, GIFs, or stickers, and they will be delivered **completely anonymously**.\n\n"
        "⚡ Important:\n"
        "- Your identity will not be revealed.\n"
        "- Messages you send are forwarded to the admin anonymously.\n"
        "- You can interact freely without worrying about your privacy.\n\n"
        "Use the buttons below or type a command to get started. ✅"
    )
    keyboard = [["Send To All"], ["Get All Users"]] if update.message.chat_id == ADMIN_ID else [["/help", "/home"]]

    keyboard_reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await context.bot.sendMessage(
        chat_id=update.message.chat_id,
        text=welcome_text,
        reply_to_message_id=update.message.message_id,
        reply_markup=keyboard_reply
    )


async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID == update.message.chat_id:
        if update.message.reply_to_message:
            admin_msg_id = update.message.reply_to_message.message_id
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT user_chat_id FROM replies_map WHERE admin_message_id=?", (admin_msg_id,))
            row = c.fetchone()
            conn.close()

            if row:
                target_id = row[0]
                try:
                    await context.bot.send_message(chat_id=target_id, text=update.message.text)
                    await update.message.reply_text("✅ Reply sent successfully.")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Error sending message: {e}")
            else:
                await update.message.reply_text("❌ Unable to find the user's ID.")
        else:
            await update.message.reply_text("❌ You need to reply to a user's message to send a reply.")


async def send_to_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ You are not authorized to perform this action.")

    keyboard = [['/cancel']]
    keyboard_reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Please send the message text to be broadcasted to all users 📩",
        reply_markup=keyboard_reply
    )
    return WAITING_FOR_MESSAGE


async def send_to_all_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    text = update.message.text
    if text != "Send To All" and text != "Get All Users":
        users = [i for i in get_all_users() if i != ADMIN_ID]
        sent, failed = 0, 0
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                sent += 1
            except:
                failed += 1

        keyboard = [['Send To All', 'Get All Users']]
        keyboard_reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(f"✅ Sent to {sent} users | ❌ Failed: {failed}", reply_markup=keyboard_reply)
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id == ADMIN_ID:
        keyboard = [['Send To All', 'Get All Users']]
        keyboard_reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("❌ Canceled.", reply_markup=keyboard_reply)
        return ConversationHandler.END


async def get_all_users_fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="Received!",
            reply_to_message_id=update.message.message_id
        )
        return

    if update.message.chat_id == ADMIN_ID:
        users = get_all_users()
        text = "📋 User List:\n\n"

        for i in users:
            try:
                chat = await context.bot.get_chat(i)
                name = chat.first_name or ""
                lname = chat.last_name or ""
                uname = f"@{chat.username}" if chat.username else ""
                fullname = f"{name} {lname}".strip()

                text += f"👤 {fullname} {uname} — {i}\n"

            except Exception as e:
                text += f"⚠️ {i} (Error fetching user info)\n"

        await update.message.reply_text(text)


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **Bot Help & Instructions**\n\n"
        "Welcome! This bot is designed to help you with various tasks quickly and easily.\n\n"
        "**How to use:**\n"
        "- Simply type a message or use one of the commands above.\n"
        "- You can also send photos, GIFs, stickers, or forward messages.\n"
        "- The bot will reply automatically and forward messages to the admin if needed.\n\n"
        "If you have any questions or feedback, feel free to ask here! ✅"
    )
    await context.bot.send_message(chat_id=update.message.chat_id,
                                   text=help_text,
                                   reply_to_message_id=update.message.message_id)


async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    home_text = (
        "👋 Hello and welcome!\n\n"
        "This is an anonymous chat bot.\n"
        "You can send messages, photos, GIFs, or stickers, and they will be delivered **completely anonymously**.\n\n"
        "⚡ Important:\n"
        "- Your identity will not be revealed.\n"
        "- Messages you send are forwarded to the admin anonymously.\n"
        "- You can interact freely without worrying about your privacy.\n\n"
        "Use the buttons below or type a command to get started. ✅"
    )
    keyboard = [
        ['/help', '/home']
    ]
    keyboard_reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text=home_text,
                                    reply_markup=keyboard_reply)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.first_name, user.last_name, user.username)
    if user.id != ADMIN_ID:
        username = f'@{user.username} ' if user.username else f"{user.first_name} {user.last_name or ''}"

        text = update.message.text
        sticker = update.message.sticker
        video = update.message.video
        photo = update.message.photo
        audio = update.message.audio
        voice = update.message.voice
        gif = update.message.animation

        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text="Received!",
                                       reply_to_message_id=update.message.message_id)

        if text:
            print(f"{username}: {text}")
        if sticker:
            print(f"{username}: Sticker")
        if video:
            print(f"{username}: video")
        if photo:
            print(f"{username}: photo")
        if audio:
            print(f"{username}: audio")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f'{username} :')
        if voice:
            print(f"{username}: voice")
        if gif:
            print(f"{username}: gif")
        forwarded_msg = await context.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS replies_map
                     (admin_message_id INTEGER PRIMARY KEY, user_chat_id INTEGER)''')
        c.execute("INSERT OR REPLACE INTO replies_map (admin_message_id, user_chat_id) VALUES (?, ?)",
                  (forwarded_msg.message_id, user.id))
        conn.commit()
        conn.close()

    if user.id == ADMIN_ID:
        if update.message.reply_to_message:
            admin_msg_id = update.message.reply_to_message.message_id
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT user_chat_id FROM replies_map WHERE admin_message_id=?", (admin_msg_id,))
            row = c.fetchone()
            conn.close()
            if row:
                target_id = row[0]
                try:
                    if update.message.photo:
                        photo = update.message.photo[-1]
                        await context.bot.send_photo(chat_id=target_id, photo=photo.file_id)
                        await update.message.reply_text("✅ Reply sent successfully.")
                    elif update.message.sticker:
                        await context.bot.send_sticker(chat_id=target_id, sticker=update.message.sticker.file_id)
                        await update.message.reply_text("✅ Reply sent successfully.")
                    elif update.message.video:
                        await context.bot.send_video(chat_id=target_id, video=update.message.video.file_id)
                        await update.message.reply_text("✅ Reply sent successfully.")
                    elif update.message.animation:
                        await context.bot.send_animation(chat_id=target_id, animation=update.message.animation.file_id)
                        await update.message.reply_text("✅ Reply sent successfully.")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Error sending message: {e}")
            else:
                await update.message.reply_text("❌ Unable to find the user's ID.")
        else:
            await context.bot.send_message(chat_id=update.message.chat_id,
                                           text="❌ You need to reply to a user's message to send a reply.",
                                           reply_to_message_id=update.message.message_id)


def main():
    conv1 = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Send To All$"), send_to_all_start)],
        states={
            WAITING_FOR_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_to_all_finish)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help))
    app.add_handler(CommandHandler('home', home))
    app.add_handler(conv1)
    app.add_handler(MessageHandler(filters.Regex("^Get All Users$"), get_all_users_fun))
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT, reply_to_user))
    app.add_handler(MessageHandler(filters.ALL, message_handler))
    app.run_polling()


if __name__ == "__main__":
    main()
