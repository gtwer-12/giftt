import telebot
from telebot import types
import sqlite3
import datetime

TOKEN = "7822795168:AAE36aTWxXqR2FCj9WpiQWA9gjQBQXFV30A"
ADMIN_ID = 5119685180

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

bot.set_my_commands(
   commands=[
      telebot.types.BotCommand('/start', 'Botni ishga tushrish uchun'),
      telebot.types.BotCommand('/help', 'help'),
   ]
)

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE,
    tg_username TEXT,
    tg_url TEXT,
    coins INTEGER DEFAULT 0,
    invites INTEGER DEFAULT 0,
    blocked INTEGER DEFAULT 0,
    invited_by INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS shop(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    price INTEGER
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    item_name TEXT,
    price INTEGER,
    date TEXT
)""")
conn.commit()

def get_url_by_tg_id(tg_id):
    cursor.execute("SELECT tg_url FROM users WHERE tg_id=?", (tg_id,))
    data = cursor.fetchone()
    return data[0] if data else None

def get_user(tg_id):
    cursor.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    return cursor.fetchone()


def add_user(tg_id, username, url, invited_by=None):
    cursor.execute(
        "INSERT INTO users (tg_id, tg_username, tg_url, coins, invites, blocked, invited_by) VALUES (?, ?, ?, 0, 0, 0, ?)",
        (tg_id, username, url, invited_by)
    )
    conn.commit()

def update_coins(tg_id, amount):
    cursor.execute("UPDATE users SET coins = coins + ? WHERE tg_id=?", (amount, tg_id))
    conn.commit()

def block_user(tg_id):
    cursor.execute("UPDATE users SET blocked=1 WHERE tg_id=?", (tg_id,))
    conn.commit()

def get_username_by_tg_id(tg_id):
    cursor.execute("SELECT tg_username FROM users WHERE tg_id=?", (tg_id,))
    data = cursor.fetchone()
    return data[0] if data else None

@bot.message_handler(commands=['start'])
def start(msg):
    tg_id = msg.from_user.id
    args = msg.text.split()

    if tg_id == ADMIN_ID:
        return admin_panel(msg)

    u = get_user(tg_id)
    if u and u[6] == 1:
        bot.send_message(tg_id, "🚫 Siz bloklangansiz!")
        return

    invited_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        invited_by = int(args[1].split("_")[1])

    if get_user(tg_id) is None:
        markup = types.ForceReply()
        bot.send_message(tg_id, "Salom! Iltimos Telegram nickingizni yozing:", reply_markup=markup)
        bot.register_next_step_handler(msg, save_username, invited_by)
    else:
        user_panel(msg)

def save_username(msg, invited_by):
    tg_username = msg.text
    markup = types.ForceReply()
    bot.send_message(msg.chat.id, "Endi Telegram URL'ingizni yuboring:", reply_markup=markup)
    bot.register_next_step_handler(msg, save_url, tg_username, invited_by)

def save_url(msg, tg_username, invited_by):
    tg_url = msg.text
    
    add_user(msg.from_user.id, tg_username, tg_url, invited_by)

    if invited_by:
        update_coins(invited_by, 5)
        update_coins(msg.from_user.id, 5)
        cursor.execute("UPDATE users SET invites = invites + 1 WHERE tg_id=?", (invited_by,))
        conn.commit()
        bot.send_message(invited_by, "🎉 Sizning do'stingiz kirdi! Sizga +5 coin qo'shildi.")

    bot.send_message(msg.chat.id, "✅ Siz ro'yxatdan o'tdingiz!")
    user_panel(msg)

def user_panel(msg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Do'st qo'shish", "🛒 Shop")
    markup.add("👤 Mening profilim", "🏆 Reyting")
    bot.send_message(msg.chat.id, "Asosiy menyu:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Do'st qo'shish")
def add_friend(msg):
    ref_link = f"https://t.me/GiftStartCoinBot?start=ref_{msg.from_user.id}"
    bot.send_message(
        msg.chat.id,
        f"🔗 Sizning referal linkingiz:\n{ref_link}\n\nDo'st kirsa sizga va unga 5 coin beriladi!"
    )


@bot.message_handler(func=lambda m: m.text == "🛒 Shop")
def shop_menu(msg):
    markup = types.InlineKeyboardMarkup()
    
    products = [
        ("🩷", 30),
        ("🐻", 35),
        ("🌹", 50),
        ("🎂", 70),
        ("🚀", 80),
        ("💎", 300),
    ]
    for i, (name, price) in enumerate(products, 1):
        markup.add(types.InlineKeyboardButton(f"{name}", callback_data=f"item_{i}_{price}"))
    bot.send_message(msg.chat.id, "🛒 Shopdagi mahsulotlar:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("item_"))
def show_item(call):
    _, item_id, price = call.data.split("_")
    price = int(price)
    user = get_user(call.from_user.id)

    if not user:
        bot.answer_callback_query(call.id, "❌ Avval ro‘yxatdan o‘ting!")
        return

    if user[4] >= price: 
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pay", callback_data=f"pay_{item_id}_{price}"))
        bot.send_message(call.message.chat.id, f"🛍 Siz tanladingiz!\nNarxi: {price} coin", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, f"❌ Sizda {price} coin yetarli emas.\n💰 Sizda {user[4]} coin bor.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def pay_item(call):
    _, item_id, price = call.data.split("_")
    price = int(price)
    user = get_user(call.from_user.id)

    if user[4] < price:
        bot.answer_callback_query(call.id, "❌ Coin yetarli emas!")
        return

    # Mahsulotlar (shop menyusidagi bilan bir xil)
    products = [
        ("🩷", 30),
        ("🐻", 35),
        ("🌹", 50),
        ("🎂", 70),
        ("🚀", 80),
        ("💎", 300),
    ]
    item_name, _ = products[int(item_id) - 1]

    # Coinni kamaytirish
    update_coins(call.from_user.id, -price)

    # Buyurtmani bazaga yozish
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO orders (user_id, item_name, price, date) VALUES (?, ?, ?, ?)",
        (call.from_user.id, item_name, price, date)
    )
    conn.commit()

    bot.send_message(
        call.message.chat.id,
        f"✅ To‘lov muvaffaqiyatli!\nSiz {item_name} uchun {price} coin sarfladingiz."
    )

@bot.message_handler(func=lambda m: m.text == "👤 Mening profilim")
def my_profile(msg):
    user = get_user(msg.from_user.id)
    if user:
        bot.send_message(msg.chat.id, f"👤 Profil:\n💰 Coinlar: {user[4]}\n👥 Taklif qilgan do'stlar: {user[5]}")
    else:
        bot.send_message(msg.chat.id, "❌ Siz ro'yxatdan o'tmagansiz.")

@bot.message_handler(func=lambda m: m.text == "🏆 Reyting")
def rating(msg):
    cursor.execute("SELECT tg_username, coins FROM users ORDER BY coins DESC LIMIT 10")
    rows = cursor.fetchall()
    text = "🏆 Reyting:\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} - {row[1]} coin\n"
    bot.send_message(msg.chat.id, text)

def admin_panel(msg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Coin berish", "📊 Reyting ko'rish")
    markup.add("🚫 Blocklash", "📦 Buyurtmalar")
    markup.add("📢 Xabar yuborish", "👥 Foydalanuvchilar soni")
    bot.send_message(msg.chat.id, "🔑 Admin panel:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Coin berish" and m.from_user.id == ADMIN_ID)
def admin_give_coins(msg):
    bot.send_message(msg.chat.id, "Foydalanuvchi nikini yozing:")
    bot.register_next_step_handler(msg, admin_coin_user)

def admin_coin_user(msg):
    tg_username = msg.text
    cursor.execute("SELECT tg_id FROM users WHERE tg_username=?", (tg_username,))
    user = cursor.fetchone()
    if user:
        bot.send_message(msg.chat.id, "Nechta coin berishni yozing:")
        bot.register_next_step_handler(msg, admin_coin_amount, user[0])
    else:
        bot.send_message(msg.chat.id, "❌ Bunday foydalanuvchi topilmadi.")

def admin_coin_amount(msg, tg_id):
    try:
        amount = int(msg.text)
        update_coins(tg_id, amount)
        bot.send_message(msg.chat.id, f"✅ {amount} coin berildi.")
        bot.send_message(tg_id, f"💰 Sizga admin tomonidan {amount} coin qo'shildi!")
    except:
        bot.send_message(msg.chat.id, "❌ Xatolik!")

@bot.message_handler(func=lambda m: m.text == "📊 Reyting ko'rish" and m.from_user.id == ADMIN_ID)
def admin_rating(msg):
    cursor.execute("SELECT tg_username, coins FROM users ORDER BY coins DESC LIMIT 20")
    rows = cursor.fetchall()
    text = "📊 To'liq reyting:\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} - {row[1]} coin\n"
    bot.send_message(msg.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🚫 Blocklash" and m.from_user.id == ADMIN_ID)
def admin_block(msg):
    bot.send_message(msg.chat.id, "Block qilinadigan foydalanuvchi nikini yozing:")
    bot.register_next_step_handler(msg, admin_block_user)


def admin_block_user(msg):
    tg_username = msg.text
    cursor.execute("SELECT tg_id FROM users WHERE tg_username=?", (tg_username,))
    user = cursor.fetchone()
    if user:
        block_user(user[0])
        bot.send_message(msg.chat.id, f"🚫 {tg_username} blocklandi.")
    else:
        bot.send_message(msg.chat.id, "❌ Foydalanuvchi topilmadi.")

@bot.message_handler(func=lambda m: m.text == "📦 Buyurtmalar" and m.from_user.id == ADMIN_ID)
def admin_orders(msg):
    cursor.execute("SELECT user_id, item_name, price, date FROM orders ORDER BY date DESC LIMIT 20")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(msg.chat.id, "📦 Buyurtmalar yo'q.")
        return

    text = "📦 So‘nggi buyurtmalar:\n\n"
    for row in rows:
        user_id, item_name, price, date = row
        cursor.execute("SELECT tg_username, tg_url FROM users WHERE tg_id=?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            tg_username, tg_url = user_data
            text += f"👤 {tg_username} ({tg_url})\n🛍 {item_name} - {price} coin\n🕒 {date}\n\n"
        else:
            text += f"👤 {user_id}\n🛍 {item_name} - {price} coin\n🕒 {date}\n\n"

    bot.send_message(msg.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish" and m.from_user.id == ADMIN_ID)
def admin_broadcast(msg):
    bot.send_message(msg.chat.id, "Rasm yoki matn yuboring:")
    bot.register_next_step_handler(msg, admin_send_broadcast)

def admin_send_broadcast(msg):
    cursor.execute("SELECT tg_id FROM users WHERE blocked=0")
    users = cursor.fetchall()
    for u in users:
        try:
            if msg.photo:
                bot.send_photo(u[0], msg.photo[-1].file_id, caption=msg.caption or "")
            else:
                bot.send_message(u[0], msg.text)
        except:
            continue
    bot.send_message(msg.chat.id, "✅ Xabar yuborildi.")
    
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar soni" and m.from_user.id == ADMIN_ID)
def admin_user_count(msg):
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    bot.send_message(msg.chat.id, f"👥 Botdan foydalanuvchilar soni: {count} ta")    

print("Bot ishlamoqda...")
bot.infinity_polling()