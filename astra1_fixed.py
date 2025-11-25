from flask import Flask
import threading
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import logging
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'user_data.db')
conn = sqlite3.connect(db_path, check_same_thread=False)
import time

API_TOKEN = '7652837258:AAFsCZKdyfobBMz4KP1KGD6J3uUotHm-u7s'
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
ADMIN_ID = 5584938116
def get_connection():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn, conn.cursor()

def record_transaction(user_id, offer_id, amount):
    """سجل المعاملة في جدول transactions (ينشئ الجدول إذا لم يكن موجودًا)."""
    conn, cur = get_connection()
    try:
        cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            offer_id INTEGER,
            amount REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('INSERT INTO transactions (user_id, offer_id, amount) VALUES (?, ?, ?)',
                    (user_id, offer_id, amount))
        conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(f"Error recording transaction: {e}")
    finally:
        conn.close()
conn = sqlite3.connect('user_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0
        )
        ''')
conn.commit()
cursor.execute('''
CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY
)
''')
conn.commit()
def init_db():
    conn, cur = get_connection()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            details TEXT,
            price REAL,
            quantity INTEGER
        )
    ''')
    conn.commit()

cursor.execute('''
        CREATE TABLE IF NOT EXISTS recharge_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            deposit_amount REAL,
            transaction_id TEXT,
            status TEXT DEFAULT 'Pending'
        )
        ''')
conn.commit()
try:
    cursor.execute("ALTER TABLE offers ADD COLUMN category TEXT;")
    conn.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        pass  # العمود موجود مسبقًا
    else:
        raise

def create_offer_buttons(offers, row_width=2):
    markup = InlineKeyboardMarkup(row_width=row_width)
    for i in range(0, len(offers), row_width):
        row = offers[i:i + row_width]
        buttons = [InlineKeyboardButton(offer[1], callback_data=f"offer_{offer[0]}") for offer in row]
        markup.row(*buttons)
    return markup
def is_user_banned(user_id):
    conn, cur = get_connection()
    cur.execute('SELECT 1 FROM banned_users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None
def update_user(user_id, username):
    try:
        conn, cur = get_connection()
        cur.execute('''
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
        ''', (user_id, username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(e)
def get_user_balance(user_id):
            try:
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else 0
            except sqlite3.Error as e:
                logger.error(f"Error fetching balance: {e}")
                return 0
def update_balance(user_id, amount):
            try:
                cursor.execute('''
                UPDATE users
                SET balance = balance + ?
                WHERE user_id = ?
                ''', (amount, user_id))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error updating balance: {e}")
                bot.send_message(user_id, "⚠️ حدث خطأ أثناء تحديث رصيدك. يرجى المحاولة لاحقًا.")
def add_recharge_request(user_id, deposit_amount, transaction_id):
            try:
                cursor.execute('''
                INSERT INTO recharge_requests (user_id, deposit_amount, transaction_id)
                VALUES (?, ?, ?)
                ''', (user_id, deposit_amount, transaction_id))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Error adding recharge request: {e}")
                return None
def update_request_status(request_id, status):
            try:
                cursor.execute('''
                UPDATE recharge_requests
                SET status = ?
                WHERE request_id = ?
                ''', (status, request_id))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error updating request status: {e}")
def update_offer_in_db(offer_id, name, details, price, quantity, image):
    cursor.execute("UPDATE offers SET name = ?, details = ?, price = ?, quantity = ?, image = ? WHERE id = ?",
                   (name, details, price, quantity, image, offer_id))
    conn.commit()
def delete_offer_from_db(offer_id):
    cursor.execute("DELETE FROM offers WHERE id = ?", (offer_id,))
    conn.commit()
def check_offers_in_db():
    try:
        cursor.execute('SELECT * FROM offers')
        offers = cursor.fetchall()
        if offers:
            print(f"عدد العروض الموجودة في قاعدة البيانات: {len(offers)}")
            for offer in offers:
                print(offer)
        else:
            print("لا توجد عروض في قاعدة البيانات.")
    except sqlite3.Error as e:
        print(f"حدث خطأ أثناء فحص العروض: {e}")
check_offers_in_db()
def process_quantity(message, offer_index, user_id):
    try:
        quantity = int(message.text)

        # جلب العرض
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cur = conn.cursor()

        cur.execute('SELECT id, name, price, quantity FROM offers WHERE id = ?', (offer_index,))
        offer = cur.fetchone()

        if offer is None:
            bot.send_message(message.chat.id, "🚫 لم يتم العثور على العرض.")
            conn.close()
            return

        if quantity <= 0:
            bot.send_message(message.chat.id, "⚠️ الكمية يجب أن تكون أكبر من صفر.")
            conn.close()
            return

        if quantity > offer[3]:
            bot.send_message(message.chat.id, f"⚠️ عذراً، الكمية المطلوبة أكبر من المتاحة. المتاح: {offer[3]} 📦")
            conn.close()
            return

        total_price = offer[2] * quantity
        balance = get_user_balance(user_id)

        if balance < total_price:
            bot.send_message(message.chat.id, "⚠️ رصيدك غير كافٍ لإتمام العملية!")
            conn.close()
            return

        # خصم الرصيد
        update_balance(user_id, -total_price)

        # تحديث الكمية
        cur.execute('UPDATE offers SET quantity = quantity - ? WHERE id = ?', (quantity, offer_index))
        conn.commit()

        # حفظ العملية
        record_transaction(user_id, offer_index, total_price)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data="main_menu"))

        bot.send_message(
            message.chat.id,
            f"✅ تمت عملية الشراء بنجاح!\n💵 تم خصم {total_price} من رصيدك.\n📦 الكمية: {quantity}\nسيتم التواصل معك من الإدارة.",
            reply_markup=markup
        )

        notify_admin_for_delivery(user_id, offer, quantity)
        conn.close()

    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح للكمية.")
def get_all_offers():
    cursor.execute("SELECT * FROM offers")
    return cursor.fetchall()
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
def create_buttons(buttons_by_row):
    markup = InlineKeyboardMarkup()
    for row in buttons_by_row:
        buttons = [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) for btn in row]
        markup.add(*buttons)
    return markup
def create_offer_buttons(offers, row_width=2):
    markup = InlineKeyboardMarkup(row_width=row_width)
    for i in range(0, len(offers), row_width):
        row = offers[i:i + row_width]
        buttons = [InlineKeyboardButton(offer[1], callback_data=f"offer_{offer[0]}") for offer in row]
        markup.add(*buttons)
    return markup
@bot.message_handler(commands=['start'])
def start(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.")
        return
    user_id = message.chat.id
    username = message.chat.username or "⛔ غير متوفر"
    update_user(user_id, username)
    buttons_structure = [
        [{"text": "🛍️ العروض", "callback_data": "show_offers"}, {"text": "💳 شحن رصيد", "callback_data": "recharge_balance"}],  
        [{"text": "ℹ️ معلومات الحساب", "callback_data": "account_info"}],
        [{"text": "📩 التواصل مع الإدارة ", "callback_data": f"reply_to_admin_{message.chat.id}"}]
    ]
    markup = create_buttons(buttons_structure)
    bot.send_message(message.chat.id, f"🎉 مرحباً بك يا {message.from_user.first_name or 'ضيفنا العزيز'}\n في Astra Store!\n\n"
        "🛒 اكتشف العروض المميزة.\n"
        "💳 اشحن رصيدك بسهولة.\n"
        "📩 تواصل معنا لأي استفسار.\n\n"
        "🔽 اختر أحد الخيارات من القائمة أدناه للبدء:", reply_markup=markup)
@bot.callback_query_handler(func=lambda call: call.data == "show_offers")
def show_offers(call):
    cursor.execute("SELECT DISTINCT category FROM offers WHERE category IS NOT NULL")
    categories = cursor.fetchall()
    if not categories:
        bot.answer_callback_query(
            call.id,
            "🚫 لا توجد عروض متاحة حالياً.",
            show_alert=True
        )
        return

    markup = InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(InlineKeyboardButton(cat[0], callback_data=f"category_{cat[0]}"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))

    try:
        bot.edit_message_text("📂 اختر القسم لعرض العروض:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "📂 اختر القسم لعرض العروض:", reply_markup=markup)
@bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
def show_offers_by_category(call):
    category = call.data.split("category_")[1]
    cursor.execute("SELECT id, name FROM offers WHERE category = ?", (category,))
    offers = cursor.fetchall()

    if not offers:
        bot.answer_callback_query(call.id, "❌ لا توجد عروض في هذا القسم.", show_alert=True)
        return

    markup = InlineKeyboardMarkup(row_width=2)
    for offer in offers:
        markup.add(InlineKeyboardButton(offer[1], callback_data=f"offer_{offer[0]}"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="show_offers"))

    try:
        bot.edit_message_text(f"📂 العروض في قسم: {category}", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(call.message.chat.id, f"📂 العروض في قسم: {category}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("offer_"))
def display_offer_details(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return
    try:
        offer_id = int(call.data.split("_")[1])
        cursor.execute('SELECT name, details, price, quantity, image FROM offers WHERE id = ?', (offer_id,))
        offer = cursor.fetchone()
        if not offer:
            bot.send_message(call.message.chat.id, "⚠️ لم يتم العثور على العرض.")
            return
        text = (f"📌 اسم العرض: {offer[0]}\n"
                f"📝 التفاصيل: {offer[1]}\n"
                f"💲 السعر: {offer[2]}\n"
                f"📦 الكمية المتاحة: {offer[3]}")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 شراء العرض", callback_data=f"buy_{offer_id}"))
        if call.from_user.id == ADMIN_ID:
            markup.add(InlineKeyboardButton("✏️ تعديل العرض", callback_data=f"edit_{offer_id}"))
            markup.add(InlineKeyboardButton("🗑️ حذف العرض", callback_data=f"delete_{offer_id}"))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="show_offers"))
        if offer[4]:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_photo(call.message.chat.id, offer[4], caption=text, reply_markup=markup)
        else:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except sqlite3.Error as e:
        bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء عرض تفاصيل العرض.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_offer(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ هذا الأمر مخصص للأدمن فقط!")
        return
    offer_id = int(call.data.split("_")[1])
    try:
        cursor.execute('DELETE FROM offers WHERE id = ?', (offer_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تم حذف العرض بنجاح.")
        bot.edit_message_text("✅ تم حذف العرض.", call.message.chat.id, call.message.message_id)
    except sqlite3.Error as e:
        bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء حذف العرض. يرجى المحاولة لاحقًا.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def edit_offer(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ هذا الأمر مخصص للأدمن فقط!")
        return
    offer_id = int(call.data.split("_")[1])
    msg = bot.send_message(call.message.chat.id, "✏️ أدخل الاسم الجديد للعرض:")
    bot.register_next_step_handler(msg, get_new_name, offer_id)
def get_new_name(message, offer_id):
    new_name = message.text.strip()
    msg = bot.send_message(message.chat.id, "✏️ أدخل التفاصيل الجديدة للعرض:")
    bot.register_next_step_handler(msg, get_new_details, offer_id, new_name)
def get_new_details(message, offer_id, new_name):
    new_details = message.text.strip()
    msg = bot.send_message(message.chat.id, "✏️ أدخل السعر الجديد للعرض:")
    bot.register_next_step_handler(msg, get_new_price, offer_id, new_name, new_details)
def get_new_price(message, offer_id, new_name, new_details):
    try:
        new_price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "✏️ أدخل الكمية الجديدة للعرض:")
        bot.register_next_step_handler(msg, update_offer, offer_id, new_name, new_details, new_price)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ أدخل سعرًا صالحًا.")
        return
def update_offer(message, offer_id, new_name, new_details, new_price):
    try:
        new_quantity = int(message.text.strip())
        cursor.execute('''
        UPDATE offers
        SET name = ?, details = ?, price = ?, quantity = ?
        WHERE id = ?
        ''', (new_name, new_details, new_price, new_quantity, offer_id))
        conn.commit()
        bot.send_message(message.chat.id, "✅ تم تعديل العرض بنجاح.")
    except ValueError:
        bot.answer_callback_query(
            call.id,
            "⚠️ ادخل كمية صالحة.",
            show_alert=True
        )
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء تعديل العرض. يرجى المحاولة لاحقًا.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_purchase(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return

    user_id = call.from_user.id
    offer_index = int(call.data.split("_")[1])

    cursor.execute('SELECT id, name, price, quantity FROM offers WHERE id = ?', (offer_index,))
    offer = cursor.fetchone()

    if offer is None:
        bot.answer_callback_query(call.id, "⚠️ العرض غير موجود.", show_alert=True)
        return

    balance = get_user_balance(user_id)

    if balance < offer[2]:
        bot.answer_callback_query(call.id, "⚠️ رصيدك غير كافٍ لإتمام العملية!", show_alert=True)
        return

    bot.delete_message(call.message.chat.id, call.message.message_id)

    msg = bot.send_message(call.message.chat.id, "✏️ أدخل الكمية المطلوبة:")
    bot.register_next_step_handler(msg, process_quantity, offer_index, user_id)
def notify_admin_for_delivery(user_id, offer, quantity):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("إرسال طلب", callback_data=f"send_request_{user_id}"))
    markup.add(InlineKeyboardButton("إلغاء الطلب", callback_data=f"cancel_request_{user_id}"))
    bot.send_message(ADMIN_ID,  
                         f"طلب جديد من المستخدم: {user_id}\n"
                         f"اسم العرض: {offer[1]}\n"
                         f"السعر: {offer[2]}\n"
                         f"الكمية المطلوبة: {quantity}\n"
                         f"الكمية المتبقية: {offer[3]}",
                         reply_markup=markup
                     )
@bot.callback_query_handler(func=lambda call: call.data.startswith("send_request_"))
def request_delivery_message(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "أرسل رسالة أو ملف أو وسائط لتسليمها للمستخدم.")
    bot.register_next_step_handler(msg, deliver_to_user, user_id)
def deliver_to_user(message, user_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📩 رد على الإدارة", callback_data=f"reply_to_admin_{message.chat.id}"))
    if message.photo:
        bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption or "✅ تم تسليم الطلب.", reply_markup=markup)
    elif message.document:
        bot.send_document(user_id, message.document.file_id, caption=message.caption or "✅ تم تسليم الطلب.", reply_markup=markup)
    elif message.text:
        bot.send_message(user_id, message.text, reply_markup=markup)
    bot.send_message(message.chat.id, "✅ تم تسليم الطلب للمستخدم.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_to_admin_"))
def handle_user_reply(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return
    admin_id = ADMIN_ID
    markup = types.InlineKeyboardMarkup()
    cancel_button = types.InlineKeyboardButton("🚫 إلغاء", callback_data="cancel")
    markup.add(cancel_button)
    msg = bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="✏️ اكتب رسالتك للإدارة:",
        reply_markup=markup
    ) 
    bot.register_next_step_handler(msg, send_reply_to_admin, call.message.chat.id, admin_id)
def send_reply_to_admin(message, user_id, admin_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("رد على المستخدم", callback_data=f"send_request_{user_id}"))
    user_info = f"اسم المستخدم: {message.from_user.first_name or 'غير معروف'}\n"
    user_info += f"المعرف: @{message.from_user.username or 'غير متوفر'}\n"
    user_info += f"ID: {user_id}\n"
    user_info += f"الرسالة:\n"
    if message.photo:
        bot.send_photo(admin_id, message.photo[-1].file_id, caption=user_info + (message.caption or "تم استلام رسالة من المستخدم."), reply_markup=markup)
    elif message.document:
        bot.send_document(admin_id, message.document.file_id, caption=user_info + (message.caption or "تم استلام رسالة من المستخدم."), reply_markup=markup)
    elif message.text:
        bot.send_message(admin_id, user_info + message.text, reply_markup=markup)

    bot.send_message(message.chat.id, "✅ تم إرسال رسالتك للإدارة.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_request_"))
def request_cancellation_reason(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "✏️ أدخل سبب الإلغاء:")
    bot.register_next_step_handler(msg, cancel_order, user_id)


def cancel_order(message, user_id):
    reason = message.text

    # اتصال مستقل (مهم جداً)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()

    # جلب آخر معاملة
    cur.execute('SELECT amount FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1', (user_id,))
    transaction = cur.fetchone()

    print(f"Transaction fetched for user {user_id}: {transaction}")

    if transaction:
        amount_to_refund = transaction[0]  # لأن SELECT amount يرجع عنصر واحد فقط

        update_balance(user_id, amount_to_refund)

        bot.send_message(
            user_id,
            f"❎ تم إلغاء طلبك.\n📌 السبب: {reason}\n💰 تم إرجاع {amount_to_refund} USD إلى رصيدك."
        )

        bot.send_message(
            message.chat.id,
            f"✔️ تم إلغاء الطلب.\n💵 تم إرجاع {amount_to_refund} USD للمستخدم."
        )
    else:
        bot.send_message(user_id, "⚠️ لم يتم العثور على أي معاملة مرتبطة بهذا الطلب.")

    conn.close()
@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def show_main_menu(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return
    user_id = call.message.chat.id
    username = call.message.chat.username or "غير متوفر"
    buttons_structure = [
        [{"text": "🛍️ العروض", "callback_data": "show_offers"}, {"text": "💳 شحن رصيد", "callback_data": "recharge_balance"}],
        [{"text": "ℹ️ معلومات الحساب", "callback_data": "account_info"}],
        [{"text": "📩 التواصل مع الإدارة", "callback_data": f"reply_to_admin_{call.message.chat.id}"}]
    ]
    markup = create_buttons(buttons_structure)
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                f"🎉 مرحباً بك يا {call.message.chat.first_name or 'ضيفنا العزيز'}\n في Astra Store!\n\n"
                "🛒 اكتشف العروض المميزة.\n"
                "💳 اشحن رصيدك بسهولة.\n"
                "📩 تواصل معنا لأي استفسار.\n\n"
                "🔽 اختر أحد الخيارات من القائمة أدناه للبدء:"
            ),
            reply_markup=markup
        )
    except telebot.apihelper.ApiTelegramException as e:
        bot.answer_callback_query(call.id, "⚠️ حدث خطأ أثناء تعديل الرسالة.", show_alert=True)
        print(f"Error editing message: {e}")
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return
    user_id = call.message.chat.id
    if call.data == 'account_info':
        username = call.message.chat.username or "غير متوفر"
        balance = get_user_balance(user_id)
        account_info = (
            f"ℹ️ معلومات الحساب:\n"
            f"👤 اسم المستخدم: @{username}\n"
            f"🆔 معرف المستخدم: {user_id}\n"
            f"💰 رصيد الحساب: {balance} USD\n"
            "🔄 اشحن رصيدك للاستمتاع بخدماتنا المميزة."
        )
        back_button = types.InlineKeyboardMarkup(row_width=1)
        back_button.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_menu'))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=account_info, reply_markup=back_button)
    elif call.data == 'recharge_balance':
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("💵 USDT", callback_data='usdt'),
            types.InlineKeyboardButton("💰 Payeer", callback_data='payeer'),
            types.InlineKeyboardButton("💰 Syriatel Cash", callback_data='syriatelcash'),
            types.InlineKeyboardButton("💰 Sham Cash", callback_data='shamcash'),
        )
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='main_menu'))
        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, 
                              text="💳 اختر وسيلة الدفع التي ترغب في استخدامها لشحن رصيدك 👇:", reply_markup=keyboard)
    elif call.data == 'usdt':
        if is_user_banned(call.from_user.id):
            bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
            return
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("💵 شبكة TRON", callback_data='network_tron'),
            types.InlineKeyboardButton("💰 شبكة Ethereum", callback_data='network_ethereum')
        )
        keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='recharge_balance'))
        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, 
                              text="👇 اختر شبكة الايداع 🌐 المناسبة 👇:", reply_markup=keyboard)
    elif call.data == 'network_tron' or call.data == 'network_ethereum':
        network = "TRON" if call.data == 'network_tron' else "Ethereum"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("الغاء", callback_data='cancel'))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                              text=f"✅ تم اختيار شبكة {network} 🌐.\n"
                                    "\n"
                                    "📥 عنوان الايداع:\n"
                                    "\n"
                                    "TRGQMLpJru9ReRts5UjySEYFaguRccnmFd\n"
                                    "\n"
                                    "⚠️ الحد الادنى للايداع 10💲.\n"
                                    "\n"
                                    "⚠️ يرجى عدم الايداع قيمة أقل من الحد الادنى\n"
                                    "\n"
                                    "\n"
                                    "✏️ يرجى إدخال قيمة الإيداع (بالأرقام) 🔢:",
                              reply_markup=keyboard)
        bot.register_next_step_handler(call.message, handle_deposit, network)
    elif call.data == 'cancel':
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="✅ تم إلغاء العملية.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data='main_menu')
            )
        )
        bot.clear_step_handler(call.message)
    elif call.data.startswith('accept_'):
        request_id = int(call.data.split('_')[1])
        cursor.execute('SELECT user_id, deposit_amount FROM recharge_requests WHERE request_id = ?', (request_id,))
        result = cursor.fetchone()
        if result:
            user_id, deposit_amount = result
            update_balance(user_id, deposit_amount)
            update_request_status(request_id, 'Accepted')
            bot.send_message(user_id, f"✅ تم قبول الإيداع! تم إضافة {deposit_amount} USD إلى رصيدك.")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                  text="✅ تمت معالجة الطلب بالموافقة.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ حدث خطأ: الطلب غير موجود.")
    elif call.data.startswith('reject_'):
        request_id = int(call.data.split('_')[1])
        cursor.execute('SELECT user_id FROM recharge_requests WHERE request_id = ?', (request_id,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            update_request_status(request_id, 'Rejected')
            bot.send_message(user_id, "❎ تم رفض الإيداع. يرجى المحاولة مرة أخرى.")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                                  text="❎ تمت معالجة الطلب بالرفض.")
        else:
            bot.send_message(call.message.chat.id, "⚠️ حدث خطأ: الطلب غير موجود.")
def handle_deposit(message, network):
    try:
        deposit_amount = float(message.text)
        bot.send_message(message.chat.id, "من فضلك أرسل رقم المعاملة (TxId) 🆔 او لقطة شاشة لمعاملة الايداع 🖼️:")
        bot.register_next_step_handler(message, handle_transaction, deposit_amount, network)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")
        bot.register_next_step_handler(message, handle_deposit, network)
def handle_transaction(message, deposit_amount, network):
    transaction_id = message.text
    request_id = add_recharge_request(message.chat.id, deposit_amount, transaction_id)
    if request_id:
        back_button = types.InlineKeyboardMarkup(row_width=1)
        back_button.add(types.InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data='main_menu'))
        bot.send_message(message.chat.id, f"✅ تم إرسال طلبك لشحن رصيد {deposit_amount} USD عبر شبكة {network} 🌐.",
                         reply_markup=back_button)
        send_to_admin(request_id, message.chat.id, deposit_amount, transaction_id, network, message)
    else:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقًا.")
def send_to_admin(request_id, user_id, deposit_amount, transaction_id, network, message):
    try:
        user = bot.get_chat(user_id)
        admin_message = (
            f"طلب شحن جديد:\n"
            f"المستخدم: @{user.username}\n"
            f"المعرف: {user_id}\n"
            f"المبلغ: {deposit_amount} USD\n"
            f"رقم المعاملة: {transaction_id}\n"
            f"الشبكة: {network}\n"
        )
        if message.photo:
            bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_message)
        else:
            bot.send_message(ADMIN_ID, admin_message)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("قبول", callback_data=f'accept_{request_id}'),
            types.InlineKeyboardButton("رفض", callback_data=f'reject_{request_id}')
        )
        bot.send_message(ADMIN_ID, "اختر ما إذا كنت ترغب في قبول أو رفض الطلب.", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error sending to admin: {e}")
@bot.message_handler(commands=['add_offer'])
def add_offer(message):
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "هذا الأمر مخصص للأدمن فقط!")
            return
        msg = bot.send_message(message.chat.id, "✏️ أدخل اسم العرض:")
        bot.register_next_step_handler(msg, get_offer_name)
def get_offer_name(message):
        name = message.text.strip()
        if not name:
            bot.send_message(message.chat.id, "⚠️ اسم العرض لا يمكن أن يكون فارغًا.")
            return
        msg = bot.send_message(message.chat.id, "✏️ أدخل تفاصيل العرض:")
        bot.register_next_step_handler(msg, get_offer_details, name)
def get_offer_details(message, name):
        details = message.text.strip()
        if not details:
            bot.send_message(message.chat.id, "⚠️ تفاصيل العرض لا يمكن أن تكون فارغة.")
            return
        msg = bot.send_message(message.chat.id, "✏️ أدخل سعر العرض:")
        bot.register_next_step_handler(msg, get_offer_price, name, details)
def get_offer_price(message, name, details):
        try:
            price = float(message.text.strip())
            if price <= 0:
                bot.send_message(message.chat.id, "⚠️ يجب أن يكون السعر أكبر من صفر.")
                return
            msg = bot.send_message(message.chat.id, "✏️ أدخل الكمية المتاحة:")
            bot.register_next_step_handler(msg, get_offer_quantity, name, details, price)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ أدخل رقمًا صحيحًا للسعر.")
def get_offer_quantity(message, name, details, price):
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            bot.send_message(message.chat.id, "⚠️ الكمية يجب أن تكون أكبر من صفر.")
            return
        msg = bot.send_message(message.chat.id, "📂 أدخل قسم العرض (مثال: شحن ألعاب، تطبيقات، بطاقات):")
        bot.register_next_step_handler(msg, get_offer_category, name, details, price, quantity)
    except ValueError:
        bot.send_message(message.chat.id, "✏️ أدخل رقمًا صحيحًا للكمية.")
def get_offer_category(message, name, details, price, quantity):
    category = message.text.strip()
    if not category:
        bot.send_message(message.chat.id, "⚠️ لا يمكن ترك القسم فارغًا.")
        return
    msg = bot.send_message(message.chat.id, "🖼️ أرسل صورة العرض (اختياري):")
    bot.register_next_step_handler(msg, get_offer_image, name, details, price, quantity, category)

def get_offer_image(message, name, details, price, quantity, category):
    image = message.photo[-1].file_id if message.photo else None
    try:
        cursor.execute('''
        INSERT INTO offers (name, details, price, quantity, category, image)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, details, price, quantity, category, image))
        conn.commit()
        bot.send_message(message.chat.id, "✅ تم إضافة العرض بنجاح مع القسم.")
    except sqlite3.Error as e:
        logger.error(f"Error adding offer: {e}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء إضافة العرض. يرجى المحاولة لاحقًا.")

@bot.message_handler(commands=['show_users'])
def show_users(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    try:
        cursor.execute('SELECT user_id, username, balance FROM users')
        users = cursor.fetchall()
        if not users:
            bot.send_message(message.chat.id, "❌ لا يوجد مستخدمون في قاعدة البيانات.")
            return
        user_count = len(users)
        response = f"عدد المستخدمين: {user_count}\n\n"
        for user in users:
            user_id, username, balance = user
            response += (f"معرف المستخدم: {user_id}\n"
                         f"اسم المستخدم: {username if username else 'غير متوفر'}\n"
                         f"الرصيد: {balance:.2f}\n"
                         "--------------------------\n")
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                bot.send_message(message.chat.id, response[i:i+4096])
        else:
            bot.send_message(message.chat.id, response)
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء استرداد بيانات المستخدمين.")
        logger.error(f"Error fetching users: {e}")
@bot.message_handler(commands=['update_balance'])
def update_user_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "✏️ أدخل معرف المستخدم والمبلغ (استخدام التنسيق: user_id amount).\n"
                                            "مثال: 123456789 50 لإضافة 50، أو 123456789 -30 لخصم 30.")
    bot.register_next_step_handler(msg, process_balance_update)

def process_balance_update(message):
    try:
        user_input = message.text.split()
        if len(user_input) != 2:
            bot.send_message(message.chat.id, "⚠️ صيغة الإدخال غير صحيحة. يرجى المحاولة مجددًا.")
            return
        user_id = int(user_input[0])
        amount = float(user_input[1])
        # تحديث الرصيد
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            bot.send_message(message.chat.id, f"❎ المستخدم بمعرف {user_id} غير موجود.")
            return
        new_balance = user[0] + amount
        if new_balance < 0:
            bot.send_message(message.chat.id, f"❌ لا يمكن خصم {abs(amount):.2f} لأن الرصيد الحالي ({user[0]:.2f}) لا يكفي.")
            return
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم تحديث الرصيد بنجاح.\nالرصيد الجديد للمستخدم {user_id}: {new_balance:.2f}")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ يرجى التأكد من إدخال المعرف والمبلغ بشكل صحيح.")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء تحديث الرصيد. يرجى المحاولة لاحقًا.")
        logger.error(f"Error updating balance: {e}")
@bot.message_handler(commands=['send_message'])
def send_message_to_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "✏️ أدخل معرف المستخدم والرسالة (استخدام التنسيق: user_id message).\n"
                                            "مثال: 123456789 مرحبًا، هذا اختبار.")
    bot.register_next_step_handler(msg, process_message_to_user)
def process_message_to_user(message):
    try:
        user_input = message.text.split(maxsplit=1)
        if len(user_input) != 2:
            bot.send_message(message.chat.id, "⚠️ صيغة الإدخال غير صحيحة. يرجى المحاولة مجددًا.")
            return
        user_id = int(user_input[0])
        user_message = user_input[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("رد على الإدارة 📩", callback_data=f"reply_to_admin_{message.chat.id}"))
        bot.send_message(user_id, user_message, reply_markup=markup)
        bot.send_message(message.chat.id, f"✅ تم إرسال الرسالة إلى المستخدم {user_id}.")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ يرجى التأكد من إدخال المعرف والرسالة بشكل صحيح.")
    except telebot.apihelper.ApiTelegramException as e:
        bot.send_message(message.chat.id, f"⚠️ حدث خطأ أثناء إرسال الرسالة: {e}")
@bot.message_handler(commands=['ban_user' ])
def ban_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "أدخل معرف المستخدم الذي تريد حظره:")
    bot.register_next_step_handler(msg, process_ban_user)
def process_ban_user(message):
    try:
        user_id = int(message.text)
        cursor.execute('INSERT INTO banned_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"تم حظر المستخدم {user_id}." )
    except ValueError:
        bot.send_message(message.chat.id, "يرجى إدخال معرف مستخدم صحيح.")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, "حدث خطأ �ثناء حظر المستخدم." )
        logger.error(f"Error banning user: {e}")
@bot.message_handler(commands=['unban_user'])
def unban_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "أدخل معرف المستخدم الذي تريد إلغاء حظره:")
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    try:
        user_id = int(message.text)
        cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم إلغاء حظر المستخدم {user_id}. يمكنه الآن استخدام البوت.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إدخال معرف مستخدم صحيح.")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء إلغاء حظر المستخدم.")
        logger.error(f"Error unbanning user: {e}")
@bot.message_handler(commands=['get_banned_users'])
def get_banned_users(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "هذا الأمر مخصص للأدمن فقط!")
        return
    cursor.execute('SELECT user_id FROM banned_users')
    banned_users = cursor.fetchall()
    if banned_users:
        banned_users_list = "\n".join([f"معرف المستخدم: {user_id}" for (user_id,) in banned_users])
        bot.send_message(message.chat.id, f"قائمة المستخدمين المحظورين:\n{banned_users_list}" )
    else:
        bot.send_message(message.chat.id, "لا يوجد مستخدمين محظورين حتى الآن." )
        
@app.route('/')
def home():
    return "بوت شغال!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# ------------------- تشغيل البوت -------------------
bot.infinity_polling()
