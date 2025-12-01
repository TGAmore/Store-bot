import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import os
import time
from supabase import create_client, Client

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Supabase credentials (placed directly as you requested - NOT recommended for production)
SUPABASE_URL = "https://rjhtgcorsuxvctablycl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqaHRnY29yc3V4dmN0YWJseWNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDE1MjU4OSwiZXhwIjoyMDc5NzI4NTg5fQ.os0P5e6Tfr5eri_CCs5xt39P_tYTRhoQxwG_Z2nyLCU"

# create client (assumes compatible supabase python lib is installed)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

API_TOKEN = '7652837258:AAEAvgJG3XzJH2S_3e0udRe2WvJDzMVDbbs'
bot = telebot.TeleBot(API_TOKEN)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ADMIN_ID = 5584938116

# ------------------ Helper converters / fetchers to keep original tuple-based interfaces ------------------

def _offer_row_from_dict(d):
    """
    Return a tuple like (id, name, price, quantity, image, details, category)
    to preserve original code assumptions about indexing.
    """
    if not d:
        return None
    return (
        d.get("id"),
        d.get("name"),
        d.get("price"),
        d.get("quantity"),
        d.get("image"),
        d.get("details"),
        d.get("category")
    )

def fetch_offer_tuple(offer_id):
    """Fetch single offer and return tuple (id, name, price, quantity, image, details, category) or None"""
    try:
        offer_id = int(offer_id)
    except Exception:
        # fallback: if can't convert, return None
        logger.error(f"Invalid offer_id for fetch_offer_tuple: {offer_id}")
        return None

    try:
        res = supabase.table("offers").select("*").eq("id", offer_id).single().execute()
        if res.data:
            return _offer_row_from_dict(res.data)
        return None
    except Exception as e:
        logger.error(f"Error fetching offer {offer_id}: {e}")
        return None

def _rows_from_list_of_dicts(list_dicts):
    """Convert list of dict rows from Supabase to list of tuples preserving order used in original code:
       (id, name, price, quantity, image, details, category)
    """
    rows = []
    if not list_dicts:
        return rows
    for d in list_dicts:
        rows.append(_offer_row_from_dict(d))
    return rows

# ------------------ DB-like functions (replace sqlite behavior with Supabase) ------------------

def get_connection():
    """
    Kept for compatibility with original code where get_connection returned connection and cursor.
    Here we return supabase client and None for cursor.
    """
    return supabase, None

def record_transaction(user_id, offer_id, amount):
    """سجل المعاملة في جدول transactions."""
    try:
        user_id = int(user_id)
        offer_id = int(offer_id)
    except Exception:
        # if can't convert, still try to insert as-is
        pass
    try:
        supabase.table("transactions").insert({
            "user_id": user_id,
            "offer_id": offer_id,
            "amount": amount
        }).execute()
    except Exception as e:
        logging.getLogger(__name__).error(f"Error recording transaction: {e}")

def is_user_banned(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        # invalid id -> not banned
        return False
    try:
        res = supabase.table("banned_users").select("user_id").eq("user_id", user_id).execute()
        return bool(res.data)
    except Exception as e:
        logger.error(f"Error checking banned status: {e}")
        return False

def update_user(user_id, username):
    try:
        user_id = int(user_id)
    except:
        return

    try:
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()

        if res.data and len(res.data) > 0:
            supabase.table("users").update({"username": username}).eq("user_id", user_id).execute()
        else:
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "balance": 0
            }).execute()

    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")

def get_user_balance(user_id):
    try:
        user_id = int(user_id)
    except:
        return 0

    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()

        # المستخدم غير موجود → إنشاؤه
        if not res.data:
            supabase.table("users").insert({
                "user_id": user_id,
                "balance": 0
            }).execute()
            return 0
        
        return res.data[0].get("balance", 0)

    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        return 0

def update_balance(user_id, amount):
    try:
        user_id = int(user_id)
    except Exception:
        logger.error(f"Invalid user_id in update_balance: {user_id}")
        return
    try:
        # Get current balance
        current = get_user_balance(user_id)
        new_balance = (current or 0) + amount
        supabase.table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Error updating balance for {user_id}: {e}")
        try:
            bot.send_message(user_id, "⚠️ حدث خطأ أثناء تحديث رصيدك. يرجى المحاولة لاحقًا.")
        except Exception:
            # ignore sending errors
            pass

def add_recharge_request(user_id, deposit_amount, transaction_id):
    try:
        user_id = int(user_id)
    except:
        pass

    # أهم تعديل:
    update_user(user_id, None)   # ضمان أن المستخدم موجود قبل الإيداع

    try:
        res = supabase.table("recharge_requests").insert({
            "user_id": user_id,
            "deposit_amount": deposit_amount,
            "transaction_id": transaction_id,
            "status": "Pending"
        }).execute()

        if res.data:
            return res.data[0].get("id") or res.data[0].get("request_id")

        return None

    except Exception as e:
        logger.error(f"Error adding recharge request: {e}")
        return None

def update_request_status(request_id, status):
    try:
        # request_id may be int
        try:
            request_id = int(request_id)
        except Exception:
            pass
        supabase.table("recharge_requests").update({"status": status}).eq("request_id", request_id).execute()
    except Exception as e:
        logger.error(f"Error updating request status: {e}")

def update_offer_in_db(offer_id, name, details, price, quantity, image):
    try:
        offer_id = int(offer_id)
    except Exception:
        logger.error(f"Invalid offer_id in update_offer_in_db: {offer_id}")
        return
    try:
        supabase.table("offers").update({
            "name": name,
            "details": details,
            "price": price,
            "quantity": quantity,
            "image": image
        }).eq("id", offer_id).execute()
    except Exception as e:
        logger.error(f"Error updating offer {offer_id}: {e}")

def delete_offer_from_db(offer_id):
    try:
        offer_id = int(offer_id)
    except Exception:
        logger.error(f"Invalid offer_id in delete_offer_from_db: {offer_id}")
        return
    try:
        supabase.table("offers").delete().eq("id", offer_id).execute()
    except Exception as e:
        logger.error(f"Error deleting offer {offer_id}: {e}")

def check_offers_in_db():
    try:
        res = supabase.table("offers").select("*").execute()
        offers = res.data
        if offers:
            print(f"عدد العروض الموجودة في قاعدة البيانات: {len(offers)}")
            for d in offers:
                print(d)
        else:
            print("لا توجد عروض في قاعدة البيانات.")
    except Exception as e:
        print(f"حدث خطأ أثناء فحص العروض: {e}")

def process_quantity(message, offer_index, user_id):
    try:
        quantity = int(message.text)

        # جلب العرض
        offer = fetch_offer_tuple(offer_index)

        if offer is None:
            bot.send_message(message.chat.id, "🚫 لم يتم العثور على العرض.")
            return

        if quantity <= 0:
            bot.send_message(message.chat.id, "⚠️ الكمية يجب أن تكون أكبر من صفر.")
            return

        if quantity > (offer[3] or 0):
            bot.send_message(message.chat.id, f"⚠️ عذراً، الكمية المطلوبة أكبر من المتاحة. المتاح: {offer[3]} 📦")
            return

        total_price = (offer[2] or 0) * quantity
        balance = get_user_balance(user_id)

        if balance < total_price:
            bot.send_message(message.chat.id, "⚠️ رصيدك غير كافٍ لإتمام العملية!")
            return

        # خصم الرصيد
        update_balance(user_id, -total_price)

        # تحديث الكمية
        try:
            supabase.table("offers").update({"quantity": (offer[3] or 0) - quantity}).eq("id", int(offer_index)).execute()
        except Exception as e:
            logger.error(f"Error updating offer quantity {offer_index}: {e}")

        # حفظ العملية
        record_transaction(user_id, offer_index, total_price)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data="main_menu"))

        bot.send_message(
            message.chat.id,
            f"✅ تمت عملية الشراء بنجاح!
💵 تم خصم {total_price} من رصيدك.
📦 الكمية: {quantity}
سيتم التواصل معك من الإدارة.",
            reply_markup=markup
        )

        # Need to fetch fresh offer dict for admin notification to show remaining quantity
        try:
            fresh = fetch_offer_tuple(offer_index)
            notify_admin_for_delivery(user_id, fresh, quantity)
        except Exception as e:
            logger.error(f"Error notifying admin after purchase: {e}")

    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح للكمية.")
    except Exception as e:
        logger.error(f"Unexpected error in process_quantity: {e}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ داخلي أثناء معالجة الكمية.")

def get_all_offers():
    try:
        res = supabase.table("offers").select("*").execute()
        return _rows_from_list_of_dicts(res.data)
    except Exception as e:
        logger.error(f"Error fetching offers: {e}")
        return []

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

# ------------------ Bot Handlers (kept original logic & names) ------------------

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
    bot.send_message(message.chat.id, f"🎉 مرحباً بك يا {message.from_user.first_name or 'ضيفنا العزيز'}
 في Astra Store!

"
        "🛒 اكتشف العروض المميزة.
"
        "💳 اشحن رصيدك بسهولة.
"
        "📩 تواصل معنا لأي استفسار.

"
        "🔽 اختر أحد الخيارات من القائمة أدناه للبدء:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "show_offers")
def show_offers(call):
    try:
        # older SDKs or different environments may not support advanced .not_ constructs,
        # so fetch all offers and extract categories locally (skip None/empty)
        res = supabase.table("offers").select("category").execute()
        cats = set()
        if res.data:
            for d in res.data:
                c = d.get("category")
                if c:
                    cats.add(c)
        categories = [(c,) for c in list(cats)]
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        categories = []

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
    try:
        res = supabase.table("offers").select("id", "name").eq("category", category).execute()
        offers = []
        if res.data:
            for d in res.data:
                offers.append((d.get("id"), d.get("name")))
    except Exception as e:
        logger.error(f"Error fetching offers by category {category}: {e}")
        offers = []

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
        offer = fetch_offer_tuple(offer_id)  # (id, name, price, quantity, image, details, category)
        if not offer:
            bot.send_message(call.message.chat.id, "⚠️ لم يتم العثور على العرض.")
            return
        text = (f"📌 اسم العرض: {offer[1]}
"
                f"📝 التفاصيل: {offer[5]}
"
                f"💲 السعر: {offer[2]}
"
                f"📦 الكمية المتاحة: {offer[3]}")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 شراء العرض", callback_data=f"buy_{offer_id}"))
        if call.from_user.id == ADMIN_ID:
            markup.add(InlineKeyboardButton("✏️ تعديل العرض", callback_data=f"edit_{offer_id}"))
            markup.add(InlineKeyboardButton("🗑️ حذف العرض", callback_data=f"delete_{offer_id}"))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="show_offers"))
        if offer[4]:
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            bot.send_photo(call.message.chat.id, offer[4], caption=text, reply_markup=markup)
        else:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        logger.error(f"Error displaying offer details: {e}")
        bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء عرض تفاصيل العرض.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_offer(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⚠️ هذا الأمر مخصص للأدمن فقط!")
        return
    offer_id = int(call.data.split("_")[1])
    try:
        delete_offer_from_db(offer_id)
        bot.answer_callback_query(call.id, "✅ تم حذف العرض بنجاح.")
        bot.edit_message_text("✅ تم حذف العرض.", call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error deleting offer via callback: {e}")
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
        update_offer_in_db(offer_id, new_name, new_details, new_price, new_quantity, None)
        bot.send_message(message.chat.id, "✅ تم تعديل العرض بنجاح.")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ ادخل كمية صالحة.")
    except Exception as e:
        logger.error(f"Error updating offer via handler: {e}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء تعديل العرض. يرجى المحاولة لاحقًا.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_purchase(call):
    if is_user_banned(call.from_user.id):
        bot.answer_callback_query(call.id, "🚫 لقد تم حظرك من استخدام هذا البوت بشكل دائم.", show_alert=True)
        return

    user_id = call.from_user.id
    offer_index = int(call.data.split("_")[1])

    offer = fetch_offer_tuple(offer_index)

    if offer is None:
        bot.answer_callback_query(call.id, "⚠️ العرض غير موجود.", show_alert=True)
        return

    balance = get_user_balance(user_id)

    if balance < (offer[2] or 0):
        bot.answer_callback_query(call.id, "⚠️ رصيدك غير كافٍ لإتمام العملية!", show_alert=True)
        return

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    msg = bot.send_message(call.message.chat.id, "✏️ أدخل الكمية المطلوبة:")
    bot.register_next_step_handler(msg, process_quantity, offer_index, user_id)

def notify_admin_for_delivery(user_id, offer, quantity):
    """
    offer is expected to be the tuple (id, name, price, quantity, image, details, category)
    """
    try:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("إرسال طلب", callback_data=f"send_request_{user_id}"))
        markup.add(InlineKeyboardButton("إلغاء الطلب", callback_data=f"cancel_request_{user_id}"))
        bot.send_message(ADMIN_ID,
                         f"طلب جديد من المستخدم: {user_id}
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
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

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
    try:
        if message.photo:
            bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption or "✅ تم تسليم الطلب.", reply_markup=markup)
        elif message.document:
            bot.send_document(user_id, message.document.file_id, caption=message.caption or "✅ تم تسليم الطلب.", reply_markup=markup)
        elif message.text:
            bot.send_message(user_id, message.text, reply_markup=markup)
        bot.send_message(message.chat.id, "✅ تم تسليم الطلب للمستخدم.")
    except Exception as e:
        logger.error(f"Error delivering to user {user_id}: {e}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء تسليم الرسالة للمستخدم.")

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
    user_info = f"اسم المستخدم: {message.from_user.first_name or 'غير معروف'}
"
    user_info += f"المعرف: @{message.from_user.username or 'غير متوفر'}
"
    user_info += f"ID: {user_id}
"
    user_info += f"الرسالة:
"
    try:
        if message.photo:
            bot.send_photo(admin_id, message.photo[-1].file_id, caption=user_info + (message.caption or "تم استلام رسالة من المستخدم."), reply_markup=markup)
        elif message.document:
            bot.send_document(admin_id, message.document.file_id, caption=user_info + (message.caption or "تم استلام رسالة من المستخدم."), reply_markup=markup)
        elif message.text:
            bot.send_message(admin_id, user_info + message.text, reply_markup=markup)

        bot.send_message(message.chat.id, "✅ تم إرسال رسالتك للإدارة.")
    except Exception as e:
        logger.error(f"Error sending reply to admin: {e}")
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء إرسال رسالتك للإدارة.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_request_"))
def request_cancellation_reason(call):
    user_id = int(call.data.split("_")[2])
    msg = bot.send_message(call.message.chat.id, "✏️ أدخل سبب الإلغاء:")
    bot.register_next_step_handler(msg, cancel_order, user_id)

def cancel_order(message, user_id):
    reason = message.text

    # جلب آخر معاملة
    try:
        try:
            uid = int(user_id)
        except Exception:
            uid = user_id
        res = supabase.table("transactions").select("amount").eq("user_id", uid).order("id", desc=True).limit(1).execute()
        transaction = None
        if res.data and len(res.data) > 0:
            transaction = res.data[0]
        logger.debug(f"Transaction fetched for user {user_id}: {transaction}")
    except Exception as e:
        logger.error(f"Error fetching transaction for cancel: {e}")
        transaction = None

    if transaction:
        amount_to_refund = transaction.get("amount", 0)

        update_balance(user_id, amount_to_refund)

        bot.send_message(
            user_id,
            f"❎ تم إلغاء طلبك.
📌 السبب: {reason}
💰 تم إرجاع {amount_to_refund} USD إلى رصيدك."
        )

        bot.send_message(
            message.chat.id,
            f"✔️ تم إلغاء الطلب.
💵 تم إرجاع {amount_to_refund} USD للمستخدم."
        )
    else:
        bot.send_message(user_id, "⚠️ لم يتم العثور على أي معاملة مرتبطة بهذا الطلب.")

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
                f"🎉 مرحباً بك يا {call.message.chat.first_name or 'ضيفنا العزيز'}
 في Astra Store!

"
                "🛒 اكتشف العروض المميزة.
"
                "💳 اشحن رصيدك بسهولة.
"
                "📩 تواصل معنا لأي استفسار.

"
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
    try:
        if call.data == 'account_info':
            username = call.message.chat.username or "غير متوفر"
            balance = get_user_balance(user_id)
            account_info = (
                f"ℹ️ معلومات الحساب:
"
                f"👤 اسم المستخدم: @{username}
"
                f"🆔 معرف المستخدم: {user_id}
"
                f"💰 رصيد الحساب: {balance} USD
"
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
                                  text=f"✅ تم اختيار شبكة {network} 🌐.
"
                                        "
"
                                        "📥 عنوان الايداع:
"
                                        "
"
                                        "TRGQMLpJru9ReRts5UjySEYFaguRccnmFd
"
                                        "
"
                                        "⚠️ الحد الادنى للايداع 10💲.
"
                                        "
"
                                        "⚠️ يرجى عدم الايداع قيمة أقل من الحد الادنى
"
                                        "
"
                                        "
"
                                        "✏️ يرجى إدخال قيمة الإيداع (بالأرقام) 🔢:",
                                  reply_markup=keyboard)
            bot.register_next_step_handler(call.message, handle_deposit, network)
        elif call.data == 'payeer':
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='recharge_balance'))
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                  text=(
                                      "💰 الدفع عبر Payeer

"
                                      "📥 حساب Payeer:
"
                                      "P123456789

"
                                      "⚠️ الحد الأدنى للإيداع: 5$

"
                                      "✏️ أرسل قيمة الإيداع (بالأرقام):"
                                  ), reply_markup=keyboard)
            bot.register_next_step_handler(call.message, handle_deposit_payeer)
        elif call.data == 'syriatelcash':
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='recharge_balance'))
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                  text=(
                                      "📱 الدفع عبر Syriatel Cash

"
                                      "📥 رقم الدفع:
"
                                      "+963 988 000 000

"
                                      "⚠️ الحد الأدنى للإيداع: 10000 SYP

"
                                      "✏️ أرسل قيمة الإيداع (بالأرقام):"
                                  ), reply_markup=keyboard)
            bot.register_next_step_handler(call.message, handle_deposit_syriatel)
        elif call.data == 'shamcash':
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data='recharge_balance'))
            bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id,
                                  text=(
                                      "📱 الدفع عبر Sham Cash

"
                                      "📥 رقم الدفع:
"
                                      "+963 999 000 000

"
                                      "⚠️ الحد الأدنى للإيداع: 10000 SYP

"
                                      "✏️ أرسل قيمة الإيداع (بالأرقام):"
                                  ), reply_markup=keyboard)
            bot.register_next_step_handler(call.message, handle_deposit_sham)
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
            try:
                res = supabase.table("recharge_requests").select("user_id", "deposit_amount").eq("request_id", request_id).single().execute()
                if res.data:
                    user_id_req = res.data.get("user_id")
                    deposit_amount = res.data.get("deposit_amount", 0)
                    update_balance(user_id_req, deposit_amount)
                    update_request_status(request_id, 'Accepted')
                    bot.send_message(user_id_req, f"✅ تم قبول الإيداع! تم إضافة {deposit_amount} USD إلى رصيدك.")
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="✅ تمت معالجة الطلب بالموافقة.")
                else:
                    bot.send_message(call.message.chat.id, "⚠️ حدث خطأ: الطلب غير موجود.")
            except Exception as e:
                logger.error(f"Error accepting recharge request {request_id}: {e}")
                bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء معالجة الطلب.")
        elif call.data.startswith('reject_'):
            request_id = int(call.data.split('_')[1])
            try:
                res = supabase.table("recharge_requests").select("user_id").eq("request_id", request_id).single().execute()
                if res.data:
                    user_id_req = res.data.get("user_id")
                    update_request_status(request_id, 'Rejected')
                    bot.send_message(user_id_req, "❎ تم رفض الإيداع. يرجى المحاولة مرة أخرى.")
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="❎ تمت معالجة الطلب بالرفض.")
                else:
                    bot.send_message(call.message.chat.id, "⚠️ حدث خطأ: الطلب غير موجود.")
            except Exception as e:
                logger.error(f"Error rejecting recharge request {request_id}: {e}")
                bot.send_message(call.message.chat.id, "⚠️ حدث خطأ أثناء معالجة الطلب.")
    except Exception as e:
        logger.error(f"Error in handle_query: {e}")

# Deposit handlers for USDT are already implemented as handle_deposit and handle_transaction

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

# New handlers: Payeer, Syriatel Cash, Sham Cash

def handle_deposit_payeer(message):
    try:
        deposit_amount = float(message.text)
        bot.send_message(message.chat.id, "من فضلك أرسل رقم المعاملة أو لقطة شاشة لمعاملة الدفع عبر Payeer 🖼️:")
        bot.register_next_step_handler(message, handle_transaction_payeer, deposit_amount)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")
        bot.register_next_step_handler(message, handle_deposit_payeer)

def handle_transaction_payeer(message, deposit_amount):
    transaction_id = message.text
    request_id = add_recharge_request(message.chat.id, deposit_amount, transaction_id)
    if request_id:
        back_button = types.InlineKeyboardMarkup(row_width=1)
        back_button.add(types.InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data='main_menu'))
        bot.send_message(message.chat.id, f"✅ تم إرسال طلبك لشحن رصيد {deposit_amount} USD عبر Payeer.",
                         reply_markup=back_button)
        send_to_admin(request_id, message.chat.id, deposit_amount, transaction_id, "Payeer", message)
    else:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقًا.")

def handle_deposit_syriatel(message):
    try:
        deposit_amount = float(message.text)
        bot.send_message(message.chat.id, "من فضلك أرسل رقم أو لقطة شاشة لمعاملة Syriatel Cash 🖼️:")
        bot.register_next_step_handler(message, handle_transaction_syriatel, deposit_amount)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")
        bot.register_next_step_handler(message, handle_deposit_syriatel)

def handle_transaction_syriatel(message, deposit_amount):
    transaction_id = message.text
    request_id = add_recharge_request(message.chat.id, deposit_amount, transaction_id)
    if request_id:
        back_button = types.InlineKeyboardMarkup(row_width=1)
        back_button.add(types.InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data='main_menu'))
        bot.send_message(message.chat.id, f"✅ تم إرسال طلبك لشحن رصيد {deposit_amount} عبر Syriatel Cash.",
                         reply_markup=back_button)
        send_to_admin(request_id, message.chat.id, deposit_amount, transaction_id, "Syriatel Cash", message)
    else:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقًا.")

def handle_deposit_sham(message):
    try:
        deposit_amount = float(message.text)
        bot.send_message(message.chat.id, "من فضلك أرسل رقم أو لقطة شاشة لمعاملة Sham Cash 🖼️:")
        bot.register_next_step_handler(message, handle_transaction_sham, deposit_amount)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال رقم صحيح.")
        bot.register_next_step_handler(message, handle_deposit_sham)

def handle_transaction_sham(message, deposit_amount):
    transaction_id = message.text
    request_id = add_recharge_request(message.chat.id, deposit_amount, transaction_id)
    if request_id:
        back_button = types.InlineKeyboardMarkup(row_width=1)
        back_button.add(types.InlineKeyboardButton("🔙 رجوع إلى الواجهة الرئيسية", callback_data='main_menu'))
        bot.send_message(message.chat.id, f"✅ تم إرسال طلبك لشحن رصيد {deposit_amount} عبر Sham Cash.",
                         reply_markup=back_button)
        send_to_admin(request_id, message.chat.id, deposit_amount, transaction_id, "Sham Cash", message)
    else:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة لاحقًا.")


def send_to_admin(request_id, user_id, deposit_amount, transaction_id, network, message):
    try:
        user = bot.get_chat(user_id)
        admin_message = (
            f"طلب شحن جديد:
"
            f"المستخدم: @{user.username}
"
            f"المعرف: {user_id}
"
            f"المبلغ: {deposit_amount} 
"
            f"رقم المعاملة: {transaction_id}
"
            f"الوسيلة/الشبكة: {network}
"
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

# ... rest of admin and utility handlers remain unchanged (show_users, update_balance, etc.)

@bot.message_handler(commands=['show_users'])
def show_users(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    try:
        res = supabase.table("users").select("user_id", "username", "balance").execute()
        users = res.data or []
        if not users:
            bot.send_message(message.chat.id, "❌ لا يوجد مستخدمون في قاعدة البيانات.")
            return
        user_count = len(users)
        response = f"عدد المستخدمين: {user_count}

"
        for u in users:
            user_id = u.get("user_id")
            username = u.get("username")
            balance = u.get("balance") or 0
            response += (f"معرف المستخدم: {user_id}
"
                         f"اسم المستخدم: {username if username else 'غير متوفر'}
"
                         f"الرصيد: {balance:.2f}
"
                         "--------------------------
")
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                bot.send_message(message.chat.id, response[i:i+4096])
        else:
            bot.send_message(message.chat.id, response)
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ حدث خطأ أثناء استرداد بيانات المستخدمين.")
        logger.error(f"Error fetching users: {e}")

@bot.message_handler(commands=['update_balance'])
def update_user_balance(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "✏️ أدخل معرف المستخدم والمبلغ (استخدام التنسيق: user_id amount).
"
                                            "مثال: 123456789 50 لإضافة 50، أو 123456789 -30 لخصم 30.")
    bot.register_next_step_handler(msg, process_balance_update)

# remaining admin handlers (send_message, ban/unban, get_banned_users) unchanged

@bot.message_handler(commands=['send_message'])
def send_message_to_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🚫 هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "✏️ أدخل معرف المستخدم والرسالة (استخدام التنسيق: user_id message).
"
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

@bot.message_handler(commands=['ban_user'])
def ban_user(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "هذا الأمر مخصص للأدمن فقط!")
        return
    msg = bot.send_message(message.chat.id, "أدخل معرف المستخدم الذي تريد حظره:")
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    try:
        user_id = int(message.text)
        supabase.table("banned_users").insert({"user_id": user_id}).execute()
        bot.send_message(message.chat.id, f"تم حظر المستخدم {user_id}.")
    except ValueError:
        bot.send_message(message.chat.id, "يرجى إدخال معرف مستخدم صحيح.")
    except Exception as e:
        bot.send_message(message.chat.id, "حدث خطأ أثناء حظر المستخدم.")
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
        supabase.table("banned_users").delete().eq("user_id", user_id).execute()
        bot.send_message(message.chat.id, f"✅ تم إلغاء حظر المستخدم {user_id}. يمكنه الآن استخدام البوت.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ يرجى إدخال معرف مستخدم صحيح.")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء إلغاء حظر المستخدم.")
        logger.error(f"Error unbanning user: {e}")

@bot.message_handler(commands=['get_banned_users'])
def get_banned_users(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "هذا الأمر مخصص للأادمن فقط!")
        return
    try:
        res = supabase.table("banned_users").select("user_id").execute()
        banned_users = res.data or []
        if banned_users:
            banned_users_list = "
".join([f"معرف المستخدم: {d.get('user_id')}" for d in banned_users])
            bot.send_message(message.chat.id, f"قائمة المستخدمين المحظورين:
{banned_users_list}")
        else:
            bot.send_message(message.chat.id, "لا يوجد مستخدمين محظورين حتى الآن.")
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
    except Exception as e:
        logger.error(f"Error getting banned users: {e}")
        bot.send_message(message.chat.id, "حدث خطأ أثناء استرجاع قائمة المحظورين.")

# ------------------ Entry point ------------------
if __name__ == '__main__':
    # Optionally print initial state of offers
    try:
        check_offers_in_db()
    except Exception:
        pass

    bot.polling(none_stop=True, interval=0, timeout=20, long_polling_timeout=60)
    time.sleep(15)
