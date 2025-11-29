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

API_TOKEN = '7652837258:AAFsCZKdyfobBMz4KP1KGD6J3uUotHm-u7s'
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
        # use single().execute() — if no row, handle gracefully
        res = supabase.table("offers").select("*").eq("id", offer_id).execute()
        # res.data may be a list or dict depending on SDK; handle both
        if not res or res.data is None:
            return None
        # if list, take first
        row = res.data[0] if isinstance(res.data, list) and len(res.data) > 0 else res.data
        if row:
            return _offer_row_from_dict(row)
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

# ------------------ FIXED: update_user (prevent PGRST116 by avoiding .single()) ------------------

def update_user(user_id, username):
    """
    Ensure user exists in users table; if exists update username, else insert.
    This version avoids using .single() which raises error when no rows exist.
    """
    try:
        user_id = int(user_id)
    except Exception:
        logger.error(f"Invalid user_id in update_user: {user_id}")
        return

    try:
        # Check if user exists using execute() which returns a list in res.data
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        exists = bool(res.data)
        if exists:
            # update username (allow None)
            supabase.table("users").update({"username": username}).eq("user_id", user_id).execute()
        else:
            # insert new user with zero balance
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username,
                "balance": 0
            }).execute()
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")

# ------------------ FIXED: get_user_balance (robust if user missing) ------------------

def get_user_balance(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        logger.error(f"Invalid user_id in get_user_balance: {user_id}")
        return 0
    try:
        res = supabase.table("users").select("balance").eq("user_id", user_id).execute()
        if res and res.data:
            # res.data may be list of rows
            row = res.data[0] if isinstance(res.data, list) and len(res.data) > 0 else res.data
            if row and "balance" in row:
                return row.get("balance") or 0
        # if user not found, create user with balance 0
        try:
            supabase.table("users").insert({"user_id": user_id, "balance": 0, "username": None}).execute()
        except Exception as insert_err:
            logger.error(f"Error inserting missing user in get_user_balance: {insert_err}")
        return 0
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
    except Exception:
        logger.debug(f"add_recharge_request: couldn't cast user_id {user_id} to int")
    try:
        res = supabase.table("recharge_requests").insert({
            "user_id": user_id,
            "deposit_amount": deposit_amount,
            "transaction_id": transaction_id,
            "status": "Pending"
        }).execute()
        if res and res.data and len(res.data) > 0:
            inserted = res.data[0]
            # try different possible id names
            return inserted.get("request_id") or inserted.get("id")
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
            f"✅ تمت عملية الشراء بنجاح!\n💵 تم خصم {total_price} من رصيدك.\n📦 الكمية: {quantity}\nسيتم التواصل معك من الإدارة.",
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
# ------------------ ADMIN NOTIFY ------------------

def notify_admin_for_delivery(user_id, offer, quantity):
    try:
        if offer is None:
            return
        name = offer[1]
        details = offer[5]
        price = offer[2]
        msg = (
            f"📦 **طلب جديد للتسليم**\n\n"
            f"👤 المستخدم: `{user_id}`\n"
            f"🎁 العرض: {name}\n"
            f"ℹ️ التفاصيل: {details}\n"
            f"🔢 الكمية: {quantity}\n"
            f"💵 السعر الإجمالي: {price * quantity}"
        )
        bot.send_message(ADMIN_ID, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

# ------------------ MAIN MENU ------------------

def send_main_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎁 العروض", callback_data="offers"),
        InlineKeyboardButton("💰 رصيدي", callback_data="balance")
    )
    markup.add(
        InlineKeyboardButton("➕ شحن رصيد", callback_data="recharge")
    )
    bot.send_message(chat_id, "👋 أهلاً بك! اختر من القائمة:", reply_markup=markup)

# ------------------ START ------------------

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    update_user(user_id, username)
    send_main_menu(message.chat.id)

# ------------------ CALLBACK HANDLERS ------------------

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data

        if data == "main_menu":
            send_main_menu(call.message.chat.id)

        elif data == "offers":
            offers = get_all_offers()
            if not offers:
                bot.answer_callback_query(call.id, "لا توجد عروض حالياً ❌")
                return
            markup = create_offer_buttons(offers)
            markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
            bot.edit_message_text("🎁 قائمة العروض:", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif data.startswith("offer_"):
            offer_id = data.split("_")[1]
            offer = fetch_offer_tuple(offer_id)
            if not offer:
                bot.answer_callback_query(call.id, "العرض غير موجود ❌")
                return
            
            name = offer[1]
            details = offer[5]
            price = offer[2]
            quantity = offer[3]

            txt = (
                f"🎁 **{name}**\n"
                f"ℹ️ {details}\n"
                f"💵 السعر: {price}\n"
                f"📦 الكمية المتاحة: {quantity}"
            )

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🛒 شراء", callback_data=f"buy_{offer_id}"))
            markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="offers"))

            bot.edit_message_text(
                txt, call.message.chat.id, call.message.message_id,
                reply_markup=markup, parse_mode="Markdown"
            )

        elif data.startswith("buy_"):
            offer_id = data.split("_")[1]
            msg = bot.send_message(call.message.chat.id, "🔢 أدخل الكمية التي تريد شراءها:")
            bot.register_next_step_handler(msg, process_quantity, offer_id, call.from_user.id)

        elif data == "balance":
            bal = get_user_balance(call.from_user.id)
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                f"💰 رصيدك الحالي: {bal}",
                call.message.chat.id, call.message.message_id,
                reply_markup=create_buttons([
                    [{"text": "🔙 رجوع", "callback_data": "main_menu"}]
                ])
            )

        elif data == "recharge":
            msg = bot.send_message(call.message.chat.id, "💵 أدخل مبلغ الشحن:")
            bot.register_next_step_handler(msg, process_recharge_amount)

    except Exception as e:
        logger.error(f"Callback error: {e}")

# ------------------ RECHARGE ------------------

def process_recharge_amount(message):
    try:
        amount = float(message.text)
        if amount <= 0:
            bot.send_message(message.chat.id, "⚠️ المبلغ يجب أن يكون أكبر من 0.")
            return

        msg = bot.send_message(message.chat.id, "🧾 أدخل رقم عملية الدفع (Transaction ID):")
        bot.register_next_step_handler(msg, process_recharge_transaction, amount)

    except:
        bot.send_message(message.chat.id, "⚠️ الرجاء إدخال مبلغ صحيح.")

def process_recharge_transaction(message, amount):
    transaction_id = message.text
    user_id = message.from_user.id

    req_id = add_recharge_request(user_id, amount, transaction_id)
    if req_id:
        bot.send_message(message.chat.id, "⏳ تم إرسال طلب الشحن للإدارة.\nسيتم الرد قريباً.")
        bot.send_message(ADMIN_ID, f"📥 طلب شحن جديد:\n\n👤 المستخدم: {user_id}\n💵 المبلغ: {amount}\n🔖 رقم العملية: {transaction_id}\n🆔 رقم الطلب: {req_id}")
    else:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء إرسال طلب الشحن.")

# ------------------ RUN ------------------

def run_bot():
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_bot()
