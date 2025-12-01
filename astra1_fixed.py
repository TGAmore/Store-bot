# ==========================
# الجزء الأول — النسخة الكاملة المصححة
# ==========================

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import os
import time
from supabase import create_client, Client

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Supabase — تم الإبقاء عليها كما هي
SUPABASE_URL = "https://rjhtgcorsuxvctablycl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqaHRnY29yc3V4dmN0YWJseWNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDE1MjU4OSwiZXhwIjoyMDc5NzI4NTg5fQ.os0P5e6Tfr5eri_CCs5xt39P_tYTRhoQxwG_Z2nyLCU"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------ BOT CONFIG ------------------
API_TOKEN = '7652837258:AAG92NVO9S5aUDG73_RiJf7PV32JP8QRaFg'
bot = telebot.TeleBot(API_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ADMIN_ID = 5584938116

# --------------------------------------------------
#                SETTINGS MANAGEMENT
# --------------------------------------------------

def get_setting(key):
    try:
        res = supabase.table("settings").select("value").eq("key", key).single().execute()
        return res.data.get("value") if res.data else None
    except Exception as e:
        logger.error(f"Error reading setting {key}: {e}")
        return None

def set_setting(key, value):
    try:
        res = supabase.table("settings").select("value").eq("key", key).execute()
        if res.data:
            supabase.table("settings").update({"value": value}).eq("key", key).execute()
        else:
            supabase.table("settings").insert({"key": key, "value": value}).execute()
    except Exception as e:
        logger.error(f"Error saving setting {key}: {e}")

# --------------------------------------------------
#               USER MANAGEMENT
# --------------------------------------------------

def update_user(user_id, username):
    try:
        user_id = int(user_id)
    except:
        return

    try:
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if res.data:
            supabase.table("users").update({"username": username}).eq("user_id", user_id).execute()
        else:
            supabase.table("users").insert({"user_id": user_id, "username": username, "balance": 0}).execute()
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")

def is_user_banned(user_id):
    try:
        user_id = int(user_id)
    except:
        return False

    try:
        res = supabase.table("banned_users").select("user_id").eq("user_id", user_id).execute()
        return bool(res.data)
    except:
        return False

# --------------------------------------------------
#               BALANCE MANAGEMENT
# --------------------------------------------------

def get_user_balance(user_id):
    try:
        user_id = int(user_id)
    except:
        return 0

    try:
        res = supabase.table("users").select("balance").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("users").insert({"user_id": user_id, "balance": 0}).execute()
            return 0
        return res.data[0].get("balance", 0)
    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        return 0

def update_balance(user_id, amount):
    try:
        user_id = int(user_id)
    except:
        return

    try:
        current = get_user_balance(user_id)
        new_balance = current + amount
        supabase.table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Error updating balance: {e}")

# --------------------------------------------------
#                 OFFERS MANAGEMENT
# --------------------------------------------------

def fetch_offer_tuple(offer_id):
    try:
        offer_id = int(offer_id)
    except:
        return None

    try:
        res = supabase.table("offers").select("*").eq("id", offer_id).single().execute()
        if not res.data:
            return None
        d = res.data
        return (
            d.get("id"),
            d.get("name"),
            d.get("price"),
            d.get("quantity"),
            d.get("image"),
            d.get("details"),
            d.get("category")
        )
    except Exception as e:
        logger.error(f"Error fetching offer: {e}")
        return None

# --------------------------------------------------
#                     START COMMAND
# --------------------------------------------------

@bot.message_handler(commands=['start'])
def start(message):
    if is_user_banned(message.from_user.id):
        return bot.send_message(message.chat.id, "🚫 لقد تم حظرك من استخدام هذا البوت.")

    user_id = message.chat.id
    username = message.chat.username or "غير متوفر"
    update_user(user_id, username)

    buttons = [
        [
            {"text": "🛍️ العروض", "callback_data": "show_offers"},
            {"text": "💳 شحن رصيد", "callback_data": "recharge_balance"}
        ],
        [{"text": "ℹ️ معلومات الحساب", "callback_data": "account_info"}],
        [{"text": "📩 التواصل مع الإدارة", "callback_data": f"reply_to_admin_{user_id}"}]
    ]

    markup = InlineKeyboardMarkup()
    for row in buttons:
        markup.add(*[InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row])

    bot.send_message(
        user_id,
        f"🎉 مرحباً {message.from_user.first_name}!
اختر من القائمة أدناه:",
        reply_markup=markup
    )

# --------------------------------------------------
#       SHOW OFFERS — CATEGORY SYSTEM
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "show_offers")
def show_offers(call):
    res = supabase.table("offers").select("category").execute()
    categories = {d.get("category") for d in res.data if d.get("category")}

    if not categories:
        return bot.answer_callback_query(call.id, "❌ لا توجد عروض.", show_alert=True)

    markup = InlineKeyboardMarkup(row_width=2)
    for c in sorted(categories):
        markup.add(InlineKeyboardButton(c, callback_data=f"category_{c}"))

    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))

    bot.edit_message_text(
        "📂 اختر قسم العروض:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ============================
# انتهى الجزء الأول
# اكتب:  "أرسل الجزء الثاني"
# ============================

# ==========================
# الجزء الثاني — النسخة الكاملة المصححة
# ==========================

# --------------------------------------------------
#            عرض العروض حسب القسم
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
def show_offers_by_category(call):
    category = call.data.replace("category_", "")
    try:
        res = supabase.table("offers").select("id", "name").eq("category", category).execute()
        offers = [(d.get("id"), d.get("name")) for d in res.data]
    except Exception as e:
        logger.error(f"Error loading offers by category: {e}")
        offers = []

    if not offers:
        return bot.answer_callback_query(call.id, "❌ لا توجد عروض في هذا القسم.", show_alert=True)

    markup = InlineKeyboardMarkup(row_width=2)
    for offer_id, name in offers:
        markup.add(InlineKeyboardButton(name, callback_data=f"offer_{offer_id}"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="show_offers"))

    bot.edit_message_text(
        f"📂 العروض في قسم: {category}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#              تفاصيل العرض — شراء/تعديل
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("offer_"))
def display_offer_details(call):
    if is_user_banned(call.from_user.id):
        return bot.answer_callback_query(call.id, "🚫 لقد تم حظرك.", show_alert=True)

    offer_id = int(call.data.split("_")[1])
    offer = fetch_offer_tuple(offer_id)

    if not offer:
        return bot.send_message(call.message.chat.id, "⚠️ لم يتم العثور على العرض.")

    text = (
        f"📌 اسم العرض: {offer[1]}
"
        f"📝 التفاصيل: {offer[5]}
"
        f"💲 السعر: {offer[2]}
"
        f"📦 الكمية المتاحة: {offer[3]}"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🛒 شراء العرض", callback_data=f"buy_{offer_id}"))

    if call.from_user.id == ADMIN_ID:
        markup.add(InlineKeyboardButton("✏️ تعديل العرض", callback_data=f"edit_{offer_id}"))
        markup.add(InlineKeyboardButton("🗑️ حذف العرض", callback_data=f"delete_{offer_id}"))

    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="show_offers"))

    if offer[4]:  # صورة
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_photo(call.message.chat.id, offer[4], caption=text, reply_markup=markup)
    else:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# --------------------------------------------------
#                حذف عرض (ADMIN)
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_offer(call):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "⚠️ هذا الأمر للأدمن فقط.")

    offer_id = int(call.data.split("_")[1])

    try:
        supabase.table("offers").delete().eq("id", offer_id).execute()
        bot.answer_callback_query(call.id, "🗑️ تم حذف العرض.")
        bot.edit_message_text("تم حذف العرض.", call.message.chat.id, call.message.message_id)
    except:
        bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء الحذف.")

# --------------------------------------------------
#                   تعديل عرض (ADMIN)
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def edit_offer(call):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "⚠️ الأدمن فقط")

    offer_id = int(call.data.split("_")[1])
    msg = bot.send_message(call.message.chat.id, "✏️ أدخل الاسم الجديد:")
    bot.register_next_step_handler(msg, get_new_name, offer_id)

def get_new_name(message, offer_id):
    new_name = message.text.strip()
    msg = bot.send_message(message.chat.id, "✏️ أدخل التفاصيل الجديدة:")
    bot.register_next_step_handler(msg, get_new_details, offer_id, new_name)

def get_new_details(message, offer_id, new_name):
    new_details = message.text.strip()
    msg = bot.send_message(message.chat.id, "✏️ أدخل السعر الجديد:")
    bot.register_next_step_handler(msg, get_new_price, offer_id, new_name, new_details)

def get_new_price(message, offer_id, new_name, new_details):
    try:
        new_price = float(message.text.strip())
        msg = bot.send_message(message.chat.id, "✏️ أدخل الكمية الجديدة:")
        bot.register_next_step_handler(msg, update_offer, offer_id, new_name, new_details, new_price)
    except:
        bot.send_message(message.chat.id, "⚠️ أدخل سعراً صحيحاً.")

def update_offer(message, offer_id, new_name, new_details, new_price):
    try:
        new_quantity = int(message.text.strip())
        supabase.table("offers").update({
            "name": new_name,
            "details": new_details,
            "price": new_price,
            "quantity": new_quantity
        }).eq("id", offer_id).execute()

        bot.send_message(message.chat.id, "✅ تم تحديث العرض بنجاح.")
    except:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء التحديث.")

# --------------------------------------------------
#              نظام الشراء — طلب كمية
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_purchase(call):
    if is_user_banned(call.from_user.id):
        return bot.answer_callback_query(call.id, "🚫 محظور.", show_alert=True)

    offer_id = int(call.data.split("_")[1])
    offer = fetch_offer_tuple(offer_id)

    if not offer:
        return bot.answer_callback_query(call.id, "❌ العرض غير موجود.")

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    msg = bot.send_message(call.message.chat.id, "✏️ أدخل الكمية المطلوبة:")
    bot.register_next_step_handler(msg, process_quantity, offer_id, call.from_user.id)

# --------------------------------------------------
#      تابع الجزء التالي: "أرسل الجزء الثالث"
# --------------------------------------------------


# ==========================
# الجزء الثالث — النسخة الكاملة المصححة
# ==========================

# --------------------------------------------------
#        معالجة الكمية وإتمام عملية الشراء
# --------------------------------------------------

def process_quantity(message, offer_id, user_id):
    try:
        quantity = int(message.text)
    except:
        return bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")

    offer = fetch_offer_tuple(offer_id)

    if not offer:
        return bot.send_message(message.chat.id, "❌ العرض غير موجود.")

    if quantity <= 0:
        return bot.send_message(message.chat.id, "⚠️ الكمية يجب أن تكون أكبر من صفر.")

    if quantity > offer[3]:
        return bot.send_message(message.chat.id, f"⚠️ الكمية المطلوبة غير متوفرة. المتاح: {offer[3]}")

    total_price = quantity * offer[2]
    balance = get_user_balance(user_id)

    if balance < total_price:
        return bot.send_message(message.chat.id, "❌ رصيدك غير كافٍ لإتمام العملية.")

    # تحديث الرصيد
    update_balance(user_id, -total_price)

    # تحديث الكمية في قاعدة البيانات
    supabase.table("offers").update({"quantity": offer[3] - quantity}).eq("id", offer_id).execute()

    # تسجيل العملية
    supabase.table("transactions").insert({
        "user_id": user_id,
        "offer_id": offer_id,
        "amount": total_price
    }).execute()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data="main_menu"))

    bot.send_message(
        message.chat.id,
        f"✅ تمت عملية الشراء بنجاح!
💵 المبلغ المخصوم: {total_price}
📦 الكمية: {quantity}",
        reply_markup=markup
    )

    # إشعار الأدمن
    notify_admin_for_delivery(user_id, fetch_offer_tuple(offer_id), quantity)

# --------------------------------------------------
#          إشعار الأدمن لتسليم الطلب
# --------------------------------------------------

def notify_admin_for_delivery(user_id, offer, quantity):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("إرسال الطلب", callback_data=f"send_request_{user_id}"))
    markup.add(InlineKeyboardButton("إلغاء الطلب", callback_data=f"cancel_request_{user_id}"))

    bot.send_message(
        ADMIN_ID,
        f"📩 طلب جديد من المستخدم {user_id}
"
        f"اسم العرض: {offer[1]}
"
        f"السعر: {offer[2]}
"
        f"الكمية المطلوبة: {quantity}
"
        f"الكمية المتبقية: {offer[3]}",
        reply_markup=markup
    )

# --------------------------------------------------
#            تسليم الطلب للمستخدم
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_request_"))
def request_delivery_message(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "📨 أرسل رسالة أو صورة لتسليم الطلب للمستخدم.")
    bot.register_next_step_handler(msg, deliver_to_user, user_id)

def deliver_to_user(message, user_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📩 رد على الإدارة", callback_data=f"reply_to_admin_{message.chat.id}"))

    try:
        if message.photo:
            bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption or "📦 تم تسليم الطلب.", reply_markup=markup)
        elif message.document:
            bot.send_document(user_id, message.document.file_id, caption=message.caption or "📦 تم تسليم الطلب.", reply_markup=markup)
        else:
            bot.send_message(user_id, message.text, reply_markup=markup)

        bot.send_message(message.chat.id, "✅ تم تسليم الطلب للمستخدم.")

    except Exception as e:
        logger.error(e)
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء التسليم.")

# --------------------------------------------------
#     نظام الرسائل بين المستخدم والإدارة (Reply)
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("reply_to_admin_"))
def handle_user_reply(call):
    admin_id = ADMIN_ID

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚫 إلغاء", callback_data="cancel"))

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

    user_info = (
        f"📩 رسالة جديدة من المستخدم:
"
        f"👤 الاسم: {message.from_user.first_name}
"
        f"@{message.from_user.username}
"
        f"ID: {user_id}
"
        f"الرسالة:
"
    )

    try:
        if message.photo:
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=user_info + (message.caption or ""), reply_markup=markup)
        elif message.document:
            bot.send_document(admin_id, message.document.file_id, caption=user_info + (message.caption or ""), reply_markup=markup)
        else:
            bot.send_message(admin_id, user_info + message.text, reply_markup=markup)

        bot.send_message(message.chat.id, "✅ تم إرسال رسالتك للإدارة.")

    except Exception as e:
        logger.error(e)
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء الإرسال.")

# --------------------------------------------------
#      تابع الجزء التالي: "أرسل الجزء الرابع"
# --------------------------------------------------


# ==========================
# الجزء الرابع — النسخة الكاملة المصححة
# ==========================

# --------------------------------------------------
#               إلغاء الطلب من الأدمن
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_request_"))
def request_cancellation_reason(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "✏️ أدخل سبب الإلغاء:")
    bot.register_next_step_handler(msg, cancel_order, user_id)

def cancel_order(message, user_id):
    reason = message.text

    # جلب آخر معاملة
    try:
        res = supabase.table("transactions").select("amount").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
        transaction = res.data[0] if res.data else None
    except Exception as e:
        logger.error(e)
        transaction = None

    if transaction:
        amount_to_refund = transaction.get("amount", 0)
        update_balance(user_id, amount_to_refund)

        bot.send_message(user_id, f"❎ تم إلغاء طلبك.
📌 السبب: {reason}
💰 تم إرجاع {amount_to_refund} USD لرصيدك.")
        bot.send_message(message.chat.id, f"✔️ تم الإلغاء.
💵 تم إرجاع {amount_to_refund} USD للمستخدم.")
    else:
        bot.send_message(message.chat.id, "⚠️ لا توجد معاملة لإلغائها.")

# --------------------------------------------------
#                    القائمة الرئيسية
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def show_main_menu(call):
    if is_user_banned(call.from_user.id):
        return bot.answer_callback_query(call.id, "🚫 محظور.", show_alert=True)

    user_id = call.message.chat.id
    username = call.message.chat.username or "غير متوفر"

    buttons = [
        [
            {"text": "🛍️ العروض", "callback_data": "show_offers"},
            {"text": "💳 شحن رصيد", "callback_data": "recharge_balance"}
        ],
        [{"text": "ℹ️ معلومات الحساب", "callback_data": "account_info"}],
        [{"text": "📩 التواصل مع الإدارة", "callback_data": f"reply_to_admin_{user_id}"}]
    ]

    markup = InlineKeyboardMarkup()
    for row in buttons:
        markup.add(*[InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row])

    try:
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=(
                f"🎉 مرحباً {call.message.chat.first_name}!
"
                "🛒 اختر من القائمة التالية:
"
                "💳 شحن — عروض — دعم"
            ),
            reply_markup=markup
        )
    except:
        pass

# --------------------------------------------------
#        معلومات الحساب — رصيد المستخدم
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "account_info")
def account_info(call):
    balance = get_user_balance(call.message.chat.id)
    username = call.message.chat.username or "غير متوفر"

    text = (
        f"ℹ️ معلومات الحساب:
"
        f"👤 المستخدم: @{username}
"
        f"🆔 ID: {call.message.chat.id}
"
        f"💰 الرصيد: {balance} USD"
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#     نظام شحن الرصيد — اختيار وسيلة الدفع
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "recharge_balance")
def recharge_balance(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💵 USDT", callback_data="usdt"),
        InlineKeyboardButton("💰 Syriatel Cash", callback_data="syriatelcash"),
        InlineKeyboardButton("💰 Sham Cash", callback_data="shamcash")
    )
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))

    bot.edit_message_text(
        "💳 اختر وسيلة الدفع:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#                 USDT Networks
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "usdt")
def usdt_network(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💵 شبكة TRON", callback_data="network_tron"),
        InlineKeyboardButton("💰 شبكة Ethereum", callback_data="network_ethereum")
    )
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="recharge_balance"))

    bot.edit_message_text(
        "👇 اختر شبكة الإيداع:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#     تابع الجزء التالي: "أرسل الجزء الخامس"
# --------------------------------------------------


# ==========================
# الجزء الخامس — النسخة الكاملة المصححة
# ==========================

# --------------------------------------------------
#       USDT — عرض العنوان حسب الشبكة المختارة
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("network_"))
def usdt_address(call):
    network = call.data.replace("network_", "").upper()

    address = get_setting(f"usdt_{network}")
    if not address:
        return bot.answer_callback_query(call.id, "⚠️ لم يتم إعداد عنوان الإيداع بعد.", show_alert=True)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 إرسال صورة التحويل", callback_data="upload_transfer_proof"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="usdt"))

    bot.edit_message_text(
        f"💰 إيداع USDT عبر شبكة {network}:
🏦 العنوان:
`{address}`",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# --------------------------------------------------
#     Syriatel Cash — خيار العملة (دولار / سوري)
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "syriatelcash")
def syriatel_cash_menu(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💵 دولار", callback_data="syriatel_dollar"),
        InlineKeyboardButton("💰 سوري", callback_data="syriatel_syrian")
    )
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="recharge_balance"))

    bot.edit_message_text(
        "👇 اختر نوع العملة:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#     Sham Cash — اختيار العملة
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "shamcash")
def sham_cash_menu(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💵 دولار", callback_data="sham_dollar"),
        InlineKeyboardButton("💰 سوري", callback_data="sham_syrian")
    )
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="recharge_balance"))

    bot.edit_message_text(
        "👇 اختر عملة التحويل المناسبة:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# --------------------------------------------------
#     إرسال معلومات الشحن بعد اختيار نوع الشبكة
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data in [
    "syriatel_dollar", "syriatel_syrian", "sham_dollar", "sham_syrian"
])
def show_cash_payment_details(call):
    data = call.data

    network_name = {
        "syriatel_dollar": "Syriatel Cash Dollar",
        "syriatel_syrian": "Syriatel Cash Syrian",
        "sham_dollar": "Sham Cash Dollar",
        "sham_syrian": "Sham Cash Syrian"
    }.get(data)

    number = get_setting(data)
    if not number:
        return bot.answer_callback_query(call.id, "⚠️ لم يتم إعداد رقم الاستلام بعد.", show_alert=True)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 إرسال صورة التحويل", callback_data="upload_transfer_proof"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="recharge_balance"))

    bot.edit_message_text(
        f"💳 الإيداع عبر: {network_name}
📱 الرقم:
`{number}`",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# --------------------------------------------------
#        استقبال صورة التحويل (كإثبات دفع)
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data == "upload_transfer_proof")
def ask_for_transfer_proof(call):
    msg = bot.send_message(call.message.chat.id, "📤 أرسل الآن صورة التحويل.")
    bot.register_next_step_handler(msg, receive_transfer_proof)

def receive_transfer_proof(message):
    if not message.photo and not message.document:
        return bot.send_message(message.chat.id, "⚠️ الرجاء إرسال صورة فقط.")

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id

    bot.send_message(message.chat.id, "⏳ تم إرسال الطلب للإدارة، سيتم التحقق وإضافة الرصيد.")

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💰 إضافة رصيد", callback_data=f"confirm_recharge_{message.chat.id}"))

    bot.send_photo(
        ADMIN_ID,
        file_id,
        caption=f"📩 طلب شحن رصيد من المستخدم: {message.chat.id}",
        reply_markup=markup
    )

# --------------------------------------------------
#     تابع الجزء التالي: "أرسل الجزء السادس"
# --------------------------------------------------



# ==========================
# الجزء السادس — النسخة الكاملة المصححة
# ==========================

# --------------------------------------------------
#      تأكيد عملية الشحن من الأدمن وإضافة الرصيد
# --------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_recharge_"))
def confirm_recharge(call):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "⚠️ هذا الخيار للأدمن فقط", show_alert=True)

    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, f"💰 أدخل قيمة الرصيد المطلوب إضافتها للمستخدم {user_id}:")
    bot.register_next_step_handler(msg, process_recharge_amount, user_id)

def process_recharge_amount(message, user_id):
    try:
        amount = float(message.text.strip())
    except:
        return bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")

    update_balance(user_id, amount)

    bot.send_message(message.chat.id, f"✅ تم إضافة {amount} USD لرصيد المستخدم.")
    bot.send_message(user_id, f"💳 تم شحن رصيدك بمبلغ {amount} USD بنجاح.")

# --------------------------------------------------
#       أوامر الأدمن — إضافة عرض جديد
# --------------------------------------------------

@bot.message_handler(commands=["addoffer"])
def add_offer(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⚠️ هذا الأمر للأدمن فقط.")

    msg = bot.reply_to(message, "🛍️ أدخل اسم العرض:")
    bot.register_next_step_handler(msg, get_offer_name)

def get_offer_name(message):
    name = message.text.strip()
    msg = bot.reply_to(message, "✏️ أدخل تفاصيل العرض:")
    bot.register_next_step_handler(msg, get_offer_details, name)

def get_offer_details(message, name):
    details = message.text.strip()
    msg = bot.reply_to(message, "💲 أدخل السعر:")
    bot.register_next_step_handler(msg, get_offer_price, name, details)

def get_offer_price(message, name, details):
    try:
        price = float(message.text.strip())
    except:
        return bot.reply_to(message, "⚠️ أدخل سعراً صحيحاً.")

    msg = bot.reply_to(message, "📦 أدخل الكمية المتاحة:")
    bot.register_next_step_handler(msg, get_offer_quantity, name, details, price)

def get_offer_quantity(message, name, details, price):
    try:
        quantity = int(message.text.strip())
    except:
        return bot.reply_to(message, "⚠️ أدخل رقماً صحيحاً.")

    msg = bot.reply_to(message, "📂 أدخل اسم القسم:")
    bot.register_next_step_handler(msg, get_offer_category, name, details, price, quantity)

def get_offer_category(message, name, details, price, quantity):
    category = message.text.strip()
    msg = bot.reply_to(message, "📸 أرسل صورة العرض.")
    bot.register_next_step_handler(msg, save_offer_image, name, details, price, quantity, category)

def save_offer_image(message, name, details, price, quantity, category):
    if not message.photo:
        return bot.reply_to(message, "⚠️ يجب إرسال صورة.")

    image_id = message.photo[-1].file_id

    try:
        supabase.table("offers").insert({
            "name": name,
            "details": details,
            "price": price,
            "quantity": quantity,
            "category": category,
            "image": image_id
        }).execute()

        bot.reply_to(message, "✅ تم إضافة العرض بنجاح.")
    except Exception as e:
        logger.error(e)
        bot.reply_to(message, "⚠️ حدث خطأ أثناء إضافة العرض.")

# --------------------------------------------------
#           أمر الأدمن — حظر مستخدم
# --------------------------------------------------

@bot.message_handler(commands=["ban"])
def ban_user(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        return bot.reply_to(message, "⚠️ استخدم الصيغة: /ban USER_ID")

    supabase.table("banned_users").insert({"user_id": user_id}).execute()
    bot.reply_to(message, f"🚫 تم حظر المستخدم {user_id}")

# --------------------------------------------------
#           أمر الأدمن — إلغاء الحظر
# --------------------------------------------------

@bot.message_handler(commands=["unban"])
def unban_user(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        return bot.reply_to(message, "⚠️ استخدم الصيغة: /unban USER_ID")

    supabase.table("banned_users").delete().eq("user_id", user_id).execute()
    bot.reply_to(message, f"✅ تم إلغاء حظر المستخدم {user_id}")

# --------------------------------------------------
#                تشغيل البوت
# --------------------------------------------------

print("🤖 Bot Started Successfully...")

bot.polling(none_stop=True)

# ==========================
# انتهى الجزء السادس — نهاية الكود الكامل
# ==========================
