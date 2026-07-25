# -*- coding: utf-8 -*-
"""
=====================================================================
World War Bot v2 — بازی استراتژیک متنی برای تلگرام (نسخه گسترش‌یافته)
همه‌چیز توی همین یک فایله.

راه‌اندازی:
۱) خط  TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")  رو پیدا کن.
   بهترین کار اینه که BOT_TOKEN رو به عنوان متغیر محیطی (Environment Variable /
   Secret) روی سروری که ران می‌کنی ست کنی، نه اینکه مستقیم توی کد بنویسی.
۲) pip install -r requirements.txt   (یا: pip install python-telegram-bot==21.4)
۳) python bot.py

دیتابیس SQLite خودکار ساخته میشه (worldwar.db) کنار همین فایل.
=====================================================================
"""

import os
import sqlite3
import random
import time
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ------------------------------------------------------------------
# تنظیمات کلی
# ------------------------------------------------------------------
TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
DB_PATH = os.path.join(os.path.dirname(__file__), "worldwar.db")

STARTING_GOLD = 1000
ATTACK_COOLDOWN_SEC = 60 * 10
SANCTION_COOLDOWN_SEC = 60 * 30
RECON_COOLDOWN_SEC = 60 * 5
INCOME_TICK_SEC = 60          # هر ۶۰ ثانیه درآمد منفعل واریز میشه
XP_PER_LEVEL = 1000

# کد هدیه مخفی — در هیچ منو یا /help نمایش داده نمیشه
GIFT_CODES = {
    "BOB": {"gold": 999999999},
}

# ------------------------------------------------------------------
# مناطق جهان
# ------------------------------------------------------------------
REGIONS = {
    "middle_east":   {"name": "خاورمیانه",        "emoji": "🛢",  "resources": {"oil": 2.3, "uranium": 1.4}},
    "africa":        {"name": "آفریقا",            "emoji": "⚪️", "resources": {"gold": 1.8, "iron": 1.6}},
    "south_america": {"name": "آمریکای جنوبی",     "emoji": "🌎", "resources": {"opium": 1.8, "gold": 1.6}},
    "central_asia":  {"name": "آسیای مرکزی",       "emoji": "⚛️", "resources": {"uranium": 2.1, "oil": 1.2}},
    "east_asia":     {"name": "شرق آسیا",          "emoji": "🏭", "resources": {"iron": 1.8, "gold": 1.0}},
    "europe":        {"name": "اروپا",              "emoji": "⚖️", "resources": {"oil": 1.0, "gold": 1.0}},
    "north_america": {"name": "آمریکای شمالی",     "emoji": "💎", "resources": {"uranium": 1.4, "oil": 1.3}},
}

# تنگه‌های استراتژیک — هرکدوم به یه منطقه وصله و بونوس میده به مالکش
STRAITS = {
    "hormuz":   {"name": "تنگه هرمز",       "region": "middle_east",   "bonus_desc": "+۲۵٪ درآمد نفت"},
    "malacca":  {"name": "تنگه مالاکا",     "region": "east_asia",     "bonus_desc": "+۲۵٪ درآمد طلا"},
    "gibraltar":{"name": "تنگه جبل‌الطارق", "region": "europe",        "bonus_desc": "+۲۵٪ درآمد کلی تجارت"},
}
# مالک فعلی هر تنگه (user_id) — در حافظه؛ برای سادگی روی دیتابیس هم میشه بردش
strait_owners = {k: None for k in STRAITS}

# ------------------------------------------------------------------
# کشورها — هرکدوم یه بونوس واقعی‌محور و ۲ آیتم امضادار دارن
# (اسم تجهیزات صرفاً برای فضاسازیه؛ آمار بازی کاملاً ساختگی و برای تعادل بازیه)
# ------------------------------------------------------------------
COUNTRIES = {
    "iran":     {"name": "ایران 🇮🇷",        "bonus": "uranium_mult", "value": 1.5, "desc": "درآمد اورانیوم +۵۰٪",
                 "signature": ["drone_shahed", "missile_fattah"], "faction": "سپاه پاسداران (واحد ویژه)"},
    "usa":      {"name": "آمریکا 🇺🇸",        "bonus": "air_discount", "value": 0.8, "desc": "تجهیزات هوایی ۲۰٪ ارزان‌تر",
                 "signature": ["fighter_f22", "carrier_nimitz"], "faction": None},
    "russia":   {"name": "روسیه 🇷🇺",         "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                 "signature": ["tank_t14", "missile_iskander"], "faction": None},
    "china":    {"name": "چین 🇨🇳",           "bonus": "gold_mult", "value": 1.4, "desc": "درآمد طلا +۴۰٪",
                 "signature": ["fighter_j20", "destroyer_type055"], "faction": None},
    "germany":  {"name": "آلمان 🇩🇪",         "bonus": "iron_mult", "value": 1.4, "desc": "درآمد آهن +۴۰٪",
                 "signature": ["tank_leopard2", "sub_u212"], "faction": None},
    "uk":       {"name": "بریتانیا 🇬🇧",      "bonus": "sea_discount", "value": 0.8, "desc": "تجهیزات دریایی ۲۰٪ ارزان‌تر",
                 "signature": ["fighter_typhoon", "carrier_queenelizabeth"], "faction": None},
    "france":   {"name": "فرانسه 🇫🇷",        "bonus": "oil_mult", "value": 1.3, "desc": "درآمد نفت +۳۰٪",
                 "signature": ["fighter_rafale", "sub_barracuda"], "faction": None},
    "israel":   {"name": "اسرائیل 🇮🇱",       "bonus": "air_discount", "value": 0.75, "desc": "تجهیزات هوایی ۲۵٪ ارزان‌تر",
                 "signature": ["defense_ironbeam", "drone_hermes"], "faction": "موساد (واحد جاسوسی ویژه)"},
    "turkey":   {"name": "ترکیه 🇹🇷",         "bonus": "drone_discount", "value": 0.7, "desc": "پهبادها ۳۰٪ ارزان‌تر",
                 "signature": ["drone_bayraktar", "tank_altay"], "faction": None},
    "india":    {"name": "هند 🇮🇳",           "bonus": "land_discount", "value": 0.85, "desc": "تجهیزات زمینی ۱۵٪ ارزان‌تر",
                 "signature": ["missile_agni", "tank_arjun"], "faction": None},
    "japan":    {"name": "ژاپن 🇯🇵",          "bonus": "sea_discount", "value": 0.75, "desc": "تجهیزات دریایی ۲۵٪ ارزان‌تر",
                 "signature": ["destroyer_kongo", "fighter_f35j"], "faction": None},
    "brazil":   {"name": "برزیل 🇧🇷",         "bonus": "gold_mult", "value": 1.3, "desc": "درآمد طلا +۳۰٪",
                 "signature": ["fighter_gripen", "apc_guarani"], "faction": None},
    "saudi":    {"name": "عربستان سعودی 🇸🇦", "bonus": "oil_mult", "value": 1.6, "desc": "درآمد نفت +۶۰٪",
                 "signature": ["defense_patriot", "fighter_typhoon_ksa"], "faction": None},
    "south_korea": {"name": "کره جنوبی 🇰🇷",  "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                 "signature": ["tank_k2", "defense_kfx"], "faction": None},
}

# ------------------------------------------------------------------
# فروشگاه — دسته‌بندی شده به زیرشاخه، با نیازِ لول
# ------------------------------------------------------------------
SHOP = {
    "air_defense": {"title": "پدافند هوایی 🛡", "parent": "air", "items": [
        {"id": "defense_basic",    "name": "سامانه پدافند پایه",            "price": 1500,  "power": 40,  "level": 1},
        {"id": "defense_patriot",  "name": "سامانه پدافند پاتریوت",         "price": 5000,  "power": 140, "level": 3},
        {"id": "defense_ironbeam", "name": "سامانه پدافند لیزری آیرون‌بیم", "price": 8000,  "power": 200, "level": 5},
    ]},
    "air_drone": {"title": "پهباد 🛸", "parent": "air", "items": [
        {"id": "drone_basic",   "name": "پهباد شناسایی رعد",   "price": 300,  "power": 15,  "level": 1},
        {"id": "drone_shahed",  "name": "پهباد انتحاری شاهد",  "price": 900,  "power": 55,  "level": 2},
        {"id": "drone_bayraktar","name":"پهباد جنگی بایراکتار","price": 1600, "power": 90,  "level": 3},
        {"id": "drone_hermes",  "name": "پهباد شناسایی هرمس",  "price": 1200, "power": 70,  "level": 2},
    ]},
    "air_fighter": {"title": "جنگنده ✈️", "parent": "air", "items": [
        {"id": "fighter_gripen",  "name": "جنگنده گریپن",         "price": 3500,  "power": 130, "level": 3},
        {"id": "fighter_rafale",  "name": "جنگنده رافائل",        "price": 5500,  "power": 190, "level": 4},
        {"id": "fighter_typhoon", "name": "جنگنده تایفون",        "price": 6000,  "power": 210, "level": 4},
        {"id": "fighter_j20",     "name": "جنگنده جی-۲۰",         "price": 7500,  "power": 250, "level": 5},
        {"id": "fighter_f35j",    "name": "جنگنده اف-۳۵",         "price": 9000,  "power": 290, "level": 6},
        {"id": "fighter_f22",     "name": "جنگنده اف-۲۲ رپتور",   "price": 12000, "power": 350, "level": 7},
    ]},
    "air_bomber": {"title": "بمب‌افکن 💣", "parent": "air", "items": [
        {"id": "bomber_basic", "name": "بمب‌افکن راهبردی سیمرغ", "price": 9000,  "power": 300, "level": 5},
        {"id": "bomber_heavy", "name": "بمب‌افکن سنگین دوربرد",   "price": 14000, "power": 420, "level": 7},
    ]},
    "air_missile": {"title": "موشک ☄️", "parent": "air", "items": [
        {"id": "missile_short",   "name": "موشک بالستیک کوتاه‌برد ذوالفقار", "price": 2500, "power": 120, "level": 2},
        {"id": "missile_fattah",  "name": "موشک بالستیک فتاح",              "price": 6000, "power": 260, "level": 4},
        {"id": "missile_iskander","name": "موشک بالستیک اسکندر",           "price": 7000, "power": 280, "level": 5},
        {"id": "missile_agni",    "name": "موشک بالستیک قاره‌پیمای آگنی",   "price": 10000,"power": 340, "level": 6},
    ]},
    "land_infantry": {"title": "پیاده‌نظام 🪖", "parent": "land", "items": [
        {"id": "soldier",  "name": "گروهان پیاده‌نظام",  "price": 100,  "power": 5,  "level": 1},
        {"id": "special_force", "name": "نیروی ویژه",    "price": 600,  "power": 30, "level": 2},
    ]},
    "land_tank": {"title": "تانک 🚜", "parent": "land", "items": [
        {"id": "tank_basic",   "name": "تانک زره‌پوش کاویر",  "price": 1200,  "power": 60,  "level": 2},
        {"id": "tank_altay",   "name": "تانک آلتای",          "price": 3000,  "power": 130, "level": 3},
        {"id": "tank_arjun",   "name": "تانک آرجون",          "price": 3500,  "power": 145, "level": 4},
        {"id": "tank_leopard2","name": "تانک لئوپارد ۲",      "price": 4500,  "power": 180, "level": 5},
        {"id": "tank_k2",      "name": "تانک کی-۲ بلک‌پنتر",  "price": 5500,  "power": 210, "level": 5},
        {"id": "tank_t14",     "name": "تانک تی-۱۴ آرماتا",   "price": 7000,  "power": 260, "level": 6},
    ]},
    "land_support": {"title": "توپخانه و نفربر 🎯", "parent": "land", "items": [
        {"id": "artillery","name": "توپخانه خودکششی رعد", "price": 2200, "power": 100, "level": 3},
        {"id": "apc_basic","name": "نفربر زرهی صاعقه",    "price": 800,  "power": 35,  "level": 1},
        {"id": "apc_guarani","name":"نفربر زرهی گوارانی", "price": 1400, "power": 55,  "level": 2},
    ]},
    "sea_patrol": {"title": "ناوچه گشتی 🚤", "parent": "sea", "items": [
        {"id": "patrol", "name": "ناوچه گشتی", "price": 1500, "power": 50, "level": 1},
    ]},
    "sea_destroyer": {"title": "ناوشکن 🚢", "parent": "sea", "items": [
        {"id": "destroyer_basic",   "name": "ناوشکن دماوند",    "price": 5000, "power": 220, "level": 3},
        {"id": "destroyer_kongo",   "name": "ناوشکن کونگو",     "price": 6500, "power": 260, "level": 4},
        {"id": "destroyer_type055", "name": "ناوشکن تایپ ۰۵۵",  "price": 8000, "power": 310, "level": 5},
    ]},
    "sea_sub": {"title": "زیردریایی 🌊", "parent": "sea", "items": [
        {"id": "sub_basic",   "name": "زیردریایی غدیر",   "price": 6000,  "power": 260, "level": 4},
        {"id": "sub_u212",    "name": "زیردریایی یو-۲۱۲", "price": 8500,  "power": 320, "level": 5},
        {"id": "sub_barracuda","name": "زیردریایی باراکودا","price": 11000,"power": 380, "level": 6},
    ]},
    "sea_carrier": {"title": "ناو هواپیمابر 🛳", "parent": "sea", "items": [
        {"id": "carrier_basic",             "name": "ناو هواپیمابر سبک", "price": 15000, "power": 500, "level": 6},
        {"id": "carrier_queenelizabeth",     "name": "ناو هواپیمابر کوئین الیزابت", "price": 20000, "power": 600, "level": 7},
        {"id": "carrier_nimitz",            "name": "ناو هواپیمابر نیمیتز", "price": 26000, "power": 700, "level": 8},
    ]},
}

AIR_CATEGORY_KEYS = ["air_defense", "air_drone", "air_fighter", "air_bomber", "air_missile"]
LAND_CATEGORY_KEYS = ["land_infantry", "land_tank", "land_support"]
SEA_CATEGORY_KEYS = ["sea_patrol", "sea_destroyer", "sea_sub", "sea_carrier"]

BUILDINGS = {
    "oil_rig":            {"name": "دکل نفت 🛢",                  "price": 2000, "resource": "oil",     "rate": 2},
    "iron_mine":          {"name": "معدن آهن ⛏",                  "price": 1800, "resource": "iron",    "rate": 2},
    "gold_mine":          {"name": "معدن طلا 🏆",                  "price": 2500, "resource": "gold",    "rate": 3},
    "uranium_facility":   {"name": "تأسیسات استخراج اورانیوم ☢️",  "price": 5000, "resource": "uranium", "rate": 1},
}

RESOURCE_NAMES = {
    "gold": "طلا 🏆", "oil": "نفت 🛢", "iron": "آهن ⛏",
    "uranium": "اورانیوم ☢️", "opium": "تریاک 🌿",
}
EXCHANGE_RATES = {"oil": 6, "iron": 8, "uranium": 30, "opium": 12}  # پایین‌تر از سود منفعل، عمداً

def item_lookup(item_id):
    for cat in SHOP.values():
        for it in cat["items"]:
            if it["id"] == item_id:
                return it
    return None

def category_of(item_id):
    for key, cat in SHOP.items():
        for it in cat["items"]:
            if it["id"] == item_id:
                return cat["parent"]
    return None

# ------------------------------------------------------------------
# دیتابیس
# ------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            country TEXT,
            region TEXT,
            gold INTEGER DEFAULT 1000,
            oil INTEGER DEFAULT 0,
            iron INTEGER DEFAULT 0,
            uranium INTEGER DEFAULT 0,
            opium INTEGER DEFAULT 0,
            enriched_30 INTEGER DEFAULT 0,
            enriched_60 INTEGER DEFAULT 0,
            enriched_90 INTEGER DEFAULT 0,
            army TEXT DEFAULT '{}',
            buildings TEXT DEFAULT '{}',
            recon_targets TEXT DEFAULT '[]',
            xp INTEGER DEFAULT 0,
            alliance TEXT DEFAULT NULL,
            last_attack INTEGER DEFAULT 0,
            last_sanction INTEGER DEFAULT 0,
            last_recon INTEGER DEFAULT 0,
            sanctioned_until INTEGER DEFAULT 0,
            sabotaged_until INTEGER DEFAULT 0,
            redeemed_codes TEXT DEFAULT '[]',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row

def get_user_by_username(username):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row

def all_users():
    conn = db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return rows

def create_user(user_id, username, region, country_key):
    conn = db()
    conn.execute(
        "INSERT INTO users (user_id, username, country, region, gold, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, country_key, region, STARTING_GOLD, datetime.now().strftime("%H:%M:%S %d-%m-%Y"))
    )
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = db()
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    for k, v in strait_owners.items():
        if v == user_id:
            strait_owners[k] = None

def update_field(user_id, field, value):
    conn = db()
    conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))
    conn.commit()
    conn.close()

def add_resource(user_id, field, amount):
    conn = db()
    conn.execute(f"UPDATE users SET {field} = {field} + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_json_field(row, field):
    try:
        return json.loads(row[field] or ("{}" if field != "recon_targets" and field != "redeemed_codes" else "[]"))
    except Exception:
        return {} if field not in ("recon_targets", "redeemed_codes") else []

def set_json_field(user_id, field, value):
    update_field(user_id, field, json.dumps(value))

def army_power(army_dict, oil_available=True):
    total = 0
    for item_id, count in army_dict.items():
        it = item_lookup(item_id)
        if not it:
            continue
        cat = category_of(item_id)
        if cat == "air" and not oil_available:
            continue  # بدون نفت، تجهیزات هوایی پرواز نمی‌کنن
        total += count * it["power"]
    return total

def user_level(row):
    return max(1, row["xp"] // XP_PER_LEVEL + 1)

def region_ruler(region_key):
    rows = [r for r in all_users() if r["region"] == region_key]
    if not rows:
        return "NPC"
    best = max(rows, key=lambda r: army_power(get_json_field(r, "army")) + r["gold"])
    power = army_power(get_json_field(best, "army"))
    if power == 0 and best["gold"] <= STARTING_GOLD:
        return "NPC"
    return COUNTRIES.get(best["country"], {}).get("name", best["username"] or "ناشناس")

# ------------------------------------------------------------------
# کیبورد اصلی
# ------------------------------------------------------------------
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["خزانه 🏦", "فروشگاه 🛒"],
        ["تبادلات 📈", "بیانیه 📢"],
        ["اتحاد 🤝", "پشتیبانی 🛠"],
        ["دعوت از دوستان 👥", "وضعیت جهانی 🌍"],
        ["منطقه من 🗺", "نقشه جهان 🗺"],
        ["حذف اکانت ❌"],
    ],
    resize_keyboard=True
)

def country_keyboard():
    conn = db()
    taken = {r["country"] for r in conn.execute("SELECT country FROM users").fetchall()}
    conn.close()
    rows = []
    for key, c in COUNTRIES.items():
        label = c["name"] + (" (گرفته‌شده)" if key in taken else "")
        rows.append([InlineKeyboardButton(label, callback_data=f"pickcountry:{key}")])
    return InlineKeyboardMarkup(rows)

REGION_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"pickregion:{k}")]
    for k, v in REGIONS.items()
])

# ------------------------------------------------------------------
# /start و ثبت‌نام
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    if row:
        await update.message.reply_text(
            f"خوش برگشتی فرمانده {COUNTRIES.get(row['country'],{}).get('name','')}!",
            reply_markup=MAIN_MENU
        )
        return
    await update.message.reply_text(
        "🌍 به «جنگ جهانی» خوش اومدی، فرمانده!\n\nاول یه کشور واقعی انتخاب کن (هر کشور فقط برای یک نفره):",
        reply_markup=country_keyboard()
    )

async def pick_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    country_key = query.data.split(":")[1]
    conn = db()
    taken = conn.execute("SELECT 1 FROM users WHERE country=?", (country_key,)).fetchone()
    conn.close()
    if taken:
        await query.answer("این کشور قبلاً توسط یه بازیکن دیگه گرفته شده!", show_alert=True)
        return
    await query.answer()
    context.user_data["pending_country"] = country_key
    await query.edit_message_text(
        f"کشور {COUNTRIES[country_key]['name']} انتخاب شد ({COUNTRIES[country_key]['desc']}).\n\n"
        "حالا منطقه‌ی جغرافیایی شروعت رو انتخاب کن:",
        reply_markup=REGION_KEYBOARD
    )

async def pick_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_key = query.data.split(":")[1]
    user = update.effective_user
    country_key = context.user_data.pop("pending_country", None)
    if not country_key:
        await query.edit_message_text("یه مشکلی پیش اومد، دوباره /start بزن.")
        return
    conn = db()
    taken = conn.execute("SELECT 1 FROM users WHERE country=?", (country_key,)).fetchone()
    conn.close()
    if taken:
        await query.edit_message_text("این کشور همین الان توسط یکی دیگه گرفته شد. دوباره /start بزن و یکی دیگه انتخاب کن.")
        return
    create_user(user.id, user.username or user.first_name, region_key, country_key)
    await query.edit_message_text(
        f"✅ حکومت {COUNTRIES[country_key]['name']} در منطقه {REGIONS[region_key]['name']} تأسیس شد!\n"
        f"💰 {STARTING_GOLD} طلا برای شروع دریافت کردی.\n"
        f"🎖 بونوس کشورت: {COUNTRIES[country_key]['desc']}"
    )
    await context.bot.send_message(user.id, "از منوی پایین شروع کن:", reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# روتر پیام‌های متنی (دکمه‌های منو + مراحل چندقسمتی)
# ------------------------------------------------------------------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    row = get_user(user.id)
    if not row:
        await update.message.reply_text("اول دستور /start رو بزن تا ثبت‌نام کنی.")
        return

    handlers = {
        "خزانه 🏦": treasury,
        "فروشگاه 🛒": shop_menu,
        "تبادلات 📈": trade_menu,
        "بیانیه 📢": statement,
        "اتحاد 🤝": alliance_menu,
        "پشتیبانی 🛠": support,
        "دعوت از دوستان 👥": invite_friends,
        "وضعیت جهانی 🌍": world_status,
        "منطقه من 🗺": my_region,
        "نقشه جهان 🗺": world_status,
        "حذف اکانت ❌": delete_account_start,
    }
    fn = handlers.get(text)
    if fn:
        await fn(update, context)

# ------------------------------------------------------------------
# خزانه
# ------------------------------------------------------------------
async def treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    army = get_json_field(row, "army")
    buildings = get_json_field(row, "buildings")
    b_lines = "\n".join(f"  {BUILDINGS[b]['name']} × {c}" for b, c in buildings.items() if c) or "  چیزی نداری"
    text = (
        f"🏦 خزانه‌ی «{COUNTRIES.get(row['country'],{}).get('name','')}»\n"
        f"منطقه: {REGIONS[row['region']]['name']}\n"
        f"لول: {user_level(row)} (تجربه: {row['xp']})\n\n"
        f"طلا: {row['gold']} 🏆\n"
        f"نفت: {row['oil']} 🛢\n"
        f"آهن: {row['iron']} ⛏\n"
        f"تریاک: {row['opium']} 🌿\n"
        f"اورانیوم خام: {row['uranium']} ☢️\n"
        f"اورانیوم غنی‌شده ۳۰٪: {row['enriched_30']} گرم\n"
        f"اورانیوم غنی‌شده ۶۰٪: {row['enriched_60']} گرم\n"
        f"اورانیوم غنی‌شده ۹۰٪: {row['enriched_90']} گرم\n\n"
        f"🏗 ساختمان‌ها:\n{b_lines}\n\n"
        f"قدرت نظامی کل: {army_power(army, row['oil']>0)} ⚔️"
        + (" (⚠️ نفت صفره، هواپیماهات پرواز نمی‌کنن!)" if row['oil'] <= 0 else "") +
        f"\nتاریخ ثبت‌نام: {row['created_at']}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# فروشگاه (تجهیزات + ساختمان‌ها)
# ------------------------------------------------------------------
SHOP_ROOT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("تجهیزات هوایی ✈️", callback_data="shopgroup:air")],
    [InlineKeyboardButton("تجهیزات زمینی 🪖", callback_data="shopgroup:land")],
    [InlineKeyboardButton("تجهیزات دریایی 🚢", callback_data="shopgroup:sea")],
    [InlineKeyboardButton("منابع و ساختمان‌ها ⛏", callback_data="shopgroup:resources")],
])

GROUP_KEYS = {"air": AIR_CATEGORY_KEYS, "land": LAND_CATEGORY_KEYS, "sea": SEA_CATEGORY_KEYS}

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 به فروشگاه خوش اومدی. یه گروه انتخاب کن:", reply_markup=SHOP_ROOT_KEYBOARD)

async def shop_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    group = query.data.split(":")[1]
    if group == "resources":
        kb = [[InlineKeyboardButton(f"{b['name']} — {b['price']}💰 (+{b['rate']}/دقیقه)", callback_data=f"buybuild:{key}")]
              for key, b in BUILDINGS.items()]
        await query.edit_message_text("⛏ ساختمان‌های تولید منابع (درآمد خودکار هر دقیقه):", reply_markup=InlineKeyboardMarkup(kb))
        return
    cats = GROUP_KEYS[group]
    kb = [[InlineKeyboardButton(SHOP[c]["title"], callback_data=f"shopcat:{c}")] for c in cats]
    kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="shopgroup:root")])
    await query.edit_message_text("یه زیرشاخه انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))

async def shop_root_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_ROOT_KEYBOARD)

def effective_price(row, item, parent_group):
    country = COUNTRIES.get(row["country"], {})
    price = item["price"]
    bonus = country.get("bonus")
    if bonus == f"{parent_group}_discount":
        price = int(price * country["value"])
    if bonus == "drone_discount" and item["id"].startswith("drone"):
        price = int(price * country["value"])
    if item["id"] in country.get("signature", []):
        price = int(price * 0.8)  # آیتم امضادار کشور ۲۰٪ ارزون‌تر
    return price

async def shop_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_key = query.data.split(":")[1]
    cat = SHOP[cat_key]
    row = get_user(update.effective_user.id)
    lvl = user_level(row)
    kb = []
    for it in cat["items"]:
        price = effective_price(row, it, cat["parent"])
        lock = "" if lvl >= it["level"] else f" 🔒لول {it['level']}"
        kb.append([InlineKeyboardButton(f"{it['name']} — {price}💰 قدرت{it['power']}{lock}", callback_data=f"buy:{cat_key}:{it['id']}")])
    await query.edit_message_text(f"{cat['title']}\nروی هرکدوم بزن تا بخری:", reply_markup=InlineKeyboardMarkup(kb))

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, cat_key, item_id = query.data.split(":")
    cat = SHOP[cat_key]
    item = next(it for it in cat["items"] if it["id"] == item_id)
    user_id = update.effective_user.id
    row = get_user(user_id)
    if user_level(row) < item["level"]:
        await query.answer(f"باید حداقل لول {item['level']} باشی!", show_alert=True)
        return
    price = effective_price(row, item, cat["parent"])
    if row["gold"] < price:
        await query.answer("طلای کافی نداری!", show_alert=True)
        return
    update_field(user_id, "gold", row["gold"] - price)
    army = get_json_field(row, "army")
    army[item_id] = army.get(item_id, 0) + 1
    set_json_field(user_id, "army", army)
    await query.answer(f"✅ {item['name']} خریداری شد!", show_alert=True)

async def buy_building_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    b = BUILDINGS[key]
    user_id = update.effective_user.id
    row = get_user(user_id)
    if row["gold"] < b["price"]:
        await query.answer("طلای کافی نداری!", show_alert=True)
        return
    update_field(user_id, "gold", row["gold"] - b["price"])
    buildings = get_json_field(row, "buildings")
    buildings[key] = buildings.get(key, 0) + 1
    set_json_field(user_id, "buildings", buildings)
    await query.answer(f"✅ {b['name']} ساخته شد! از الان درآمد خودکار داری.", show_alert=True)

# ------------------------------------------------------------------
# درآمد خودکار (Job Queue) — هر INCOME_TICK_SEC یک‌بار
# ------------------------------------------------------------------
async def income_job(context: ContextTypes.DEFAULT_TYPE):
    now = int(time.time())
    for row in all_users():
        buildings = get_json_field(row, "buildings")
        if not buildings:
            continue
        sabotage_active = row["sabotaged_until"] > now
        multiplier = 0.3 if sabotage_active else 1.0
        country = COUNTRIES.get(row["country"], {})
        for key, count in buildings.items():
            if not count:
                continue
            b = BUILDINGS[key]
            amount = b["rate"] * count * multiplier
            if country.get("bonus") == f"{b['resource']}_mult":
                amount *= country["value"]
            if amount > 0:
                add_resource(row["user_id"], b["resource"], int(amount))

# ------------------------------------------------------------------
# تبادلات
# ------------------------------------------------------------------
async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["📈 مرکز تبادلات جهانی — نرخ فروش منابع به طلا (پایین‌تر از ارزش تولید، برای تشویق به سرمایه‌گذاری روی ساختمان):\n"]
    for res, rate in EXCHANGE_RATES.items():
        lines.append(f"{RESOURCE_NAMES[res]}: هر واحد = {rate} طلا")
    lines.append("\n/sell <منبع> <تعداد> — مثال: /sell oil 10")
    lines.append("/send <username> <gold|oil|iron|uranium|opium> <تعداد> — انتقال به بازیکن دیگه")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    if len(context.args) != 2 or context.args[0] not in EXCHANGE_RATES:
        await update.message.reply_text("فرمت درست: /sell oil 10\nمنابع: oil, iron, uranium, opium")
        return
    res, amount_str = context.args
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text("تعداد باید عدد باشه.")
        return
    if amount <= 0 or row[res] < amount:
        await update.message.reply_text("موجودی کافی نیست.")
        return
    gold_gain = amount * EXCHANGE_RATES[res]
    add_resource(user_id, res, -amount)
    add_resource(user_id, "gold", gold_gain)
    await update.message.reply_text(f"✅ {amount} واحد {RESOURCE_NAMES[res]} فروخته شد. +{gold_gain} طلا 🏆")

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    if len(context.args) != 3:
        await update.message.reply_text("فرمت درست: /send username gold 100")
        return
    target_username, field, amount_str = context.args
    target_username = target_username.lstrip("@")
    if field not in ("gold", "oil", "iron", "uranium", "opium"):
        await update.message.reply_text("فقط gold, oil, iron, uranium, opium قابل انتقاله.")
        return
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text("تعداد باید عدد باشه.")
        return
    target = get_user_by_username(target_username)
    if not target:
        await update.message.reply_text("این بازیکن پیدا نشد.")
        return
    if amount <= 0 or row[field] < amount:
        await update.message.reply_text("موجودی کافی نیست.")
        return
    add_resource(user_id, field, -amount)
    add_resource(target["user_id"], field, amount)
    await update.message.reply_text(f"✅ {amount} واحد {RESOURCE_NAMES.get(field,'طلا')} به {target_username} فرستاده شد.")
    try:
        await context.bot.send_message(target["user_id"], f"📥 {amount} واحد {RESOURCE_NAMES.get(field,'طلا')} از طرف {row['username']} دریافت کردی.")
    except Exception:
        pass

# ------------------------------------------------------------------
# سیستم حمله گسترده: موشک / جاسوسی / خرابکاری / ترور
# ------------------------------------------------------------------
def targets_keyboard(exclude_id):
    rows = [r for r in all_users() if r["user_id"] != exclude_id]
    rows = rows[:15]
    kb = [[InlineKeyboardButton(f"{COUNTRIES.get(r['country'],{}).get('name', r['username'])}", callback_data=f"targetpick:{r['user_id']}")] for r in rows]
    return InlineKeyboardMarkup(kb) if kb else None

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    if context.args:
        target_username = context.args[0].lstrip("@")
        target = get_user_by_username(target_username)
        if not target:
            await update.message.reply_text("این بازیکن پیدا نشد.")
            return
        await show_attack_type_menu(update, context, target["user_id"])
        return
    kb = targets_keyboard(update.effective_user.id)
    if not kb:
        await update.message.reply_text("هنوز بازیکن دیگه‌ای ثبت‌نام نکرده که بهش حمله کنی.")
        return
    await update.message.reply_text("یه هدف انتخاب کن (یا مستقیم بنویس: /attack username):", reply_markup=kb)

async def target_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    await show_attack_type_menu(update, context, target_id, edit=True)

async def show_attack_type_menu(update, context, target_id, edit=False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("☄️ حمله موشکی", callback_data=f"atktype:missile:{target_id}")],
        [InlineKeyboardButton("🕵️ جاسوسی/شناسایی", callback_data=f"atktype:recon:{target_id}")],
        [InlineKeyboardButton("🧨 خرابکاری زیرساخت", callback_data=f"atktype:sabotage:{target_id}")],
        [InlineKeyboardButton("🎯 ترور (نیاز به شناسایی قبلی)", callback_data=f"atktype:assassinate:{target_id}")],
    ])
    text = "نوع عملیات رو انتخاب کن:"
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def attack_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, atype, target_id_str = query.data.split(":")
    target_id = int(target_id_str)
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not target:
        await query.answer("این بازیکن دیگه وجود نداره.", show_alert=True)
        return
    if target_id == attacker_id:
        await query.answer("نمی‌تونی به خودت حمله کنی!", show_alert=True)
        return

    now = int(time.time())

    if atype == "missile":
        army = get_json_field(attacker, "army")
        missile_owned = [it for it in army if category_of(it) == "air" and "missile" in it]
        if not missile_owned:
            await query.answer("هیچ موشکی نداری! اول از فروشگاه بخر.", show_alert=True)
            return
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(item_lookup(mid)["name"], callback_data=f"firemissile:{mid}:{target_id}")]
            for mid in missile_owned
        ])
        await query.edit_message_text("کدوم موشک رو شلیک می‌کنی؟", reply_markup=kb)
        return

    if atype == "recon":
        if now - attacker["last_recon"] < RECON_COOLDOWN_SEC:
            wait = (RECON_COOLDOWN_SEC - (now - attacker["last_recon"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        update_field(attacker_id, "last_recon", now)
        recon_list = get_json_field(attacker, "recon_targets")
        if target_id not in recon_list:
            recon_list.append(target_id)
        set_json_field(attacker_id, "recon_targets", recon_list)
        t_power = army_power(get_json_field(target, "army"), target["oil"] > 0)
        await query.edit_message_text(
            f"🕵️ شناسایی موفق!\nقدرت نظامی هدف: {t_power}\nطلا: {target['gold']}\n"
            f"حالا امکان ترور برات باز شده."
        )
        return

    if atype == "sabotage":
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        a_power = army_power(get_json_field(attacker, "army"), attacker["oil"] > 0)
        d_power = army_power(get_json_field(target, "army"), target["oil"] > 0)
        update_field(attacker_id, "last_attack", now)
        if a_power + random.randint(0, 40) > d_power:
            update_field(target_id, "sabotaged_until", now + 60 * 15)
            await query.edit_message_text("🧨 خرابکاری موفق! درآمد ساختمان‌های هدف تا ۱۵ دقیقه ۷۰٪ کاهش پیدا کرد.")
            await notify_defender(context, target_id, attacker, "خرابکاری زیرساخت", "زیرساخت‌های اقتصادی‌ت خراب شد!")
        else:
            await query.edit_message_text("💥 عملیات خرابکاری شکست خورد.")
        return

    if atype == "assassinate":
        recon_list = get_json_field(attacker, "recon_targets")
        if target_id not in recon_list:
            await query.answer("اول باید این هدف رو شناسایی (جاسوسی) کنی!", show_alert=True)
            return
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        update_field(attacker_id, "last_attack", now)
        success = random.random() < 0.55  # شانس بالاتر چون از قبل شناسایی شده
        if success:
            loot = min(target["gold"], random.randint(300, 800))
            add_resource(target_id, "gold", -loot)
            add_resource(attacker_id, "gold", loot)
            add_resource(attacker_id, "xp" if False else "gold", 0)  # (xp افزوده میشه پایین‌تر با update_field جدا)
            update_field(attacker_id, "xp", attacker["xp"] + 150)
            await query.edit_message_text(f"🎯 ترور موفق! غنیمت: {loot} طلا 🏆 + تجربه.")
            await notify_defender(context, target_id, attacker, "ترور", f"یه عملیات ترور موفق علیه رهبری‌ت انجام شد! {loot} طلا از دست دادی.")
        else:
            await query.edit_message_text("💥 عملیات ترور شکست خورد و لو رفت.")
            await notify_defender(context, target_id, attacker, "تلاش ترور ناموفق", "یه تلاش ترور ناموفق علیه‌ت کشف شد!")
        return

async def fire_missile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, missile_id, target_id_str = query.data.split(":")
    target_id = int(target_id_str)
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not target:
        await query.answer("این بازیکن دیگه وجود نداره.", show_alert=True)
        return

    now = int(time.time())
    update_field(attacker_id, "last_attack", now)

    missile = item_lookup(missile_id)
    a_power = army_power(get_json_field(attacker, "army"), attacker["oil"] > 0) + missile["power"] // 2 + random.randint(0, 50)
    d_power = army_power(get_json_field(target, "army"), target["oil"] > 0) + random.randint(0, 50)

    if a_power > d_power:
        loot = min(target["gold"], random.randint(80, 350))
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        update_field(attacker_id, "xp", attacker["xp"] + 100)
        await query.edit_message_text(
            f"☄️ شلیک {missile['name']} موفق بود!\nقدرت تو: {a_power} vs قدرت هدف: {d_power}\n🏆 غنیمت: {loot} طلا"
        )
        await notify_defender(context, target_id, attacker, f"حمله موشکی ({missile['name']})", f"{loot} طلا از دست دادی!")
    else:
        await query.edit_message_text(f"💥 حمله دفع شد. قدرت هدف ({d_power}) بیشتر از تو ({a_power}) بود.")

async def notify_defender(context, target_id, attacker_row, attack_name, extra_text):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ انتقام بگیر", callback_data=f"targetpick:{attacker_row['user_id']}")]])
    attacker_name = COUNTRIES.get(attacker_row["country"], {}).get("name", attacker_row["username"])
    try:
        await context.bot.send_message(
            target_id,
            f"🚨 حمله دریافت شد!\nنوع عملیات: {attack_name}\nمهاجم: {attacker_name}\n{extra_text}",
            reply_markup=kb
        )
    except Exception:
        pass

# ------------------------------------------------------------------
# تحریم
# ------------------------------------------------------------------
async def sanction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    now = int(time.time())
    if now - row["last_sanction"] < SANCTION_COOLDOWN_SEC:
        wait = (SANCTION_COOLDOWN_SEC - (now - row["last_sanction"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    if not context.args:
        await update.message.reply_text("فرمت درست: /sanction username")
        return
    target = get_user_by_username(context.args[0].lstrip("@"))
    if not target:
        await update.message.reply_text("این بازیکن پیدا نشد.")
        return
    until = now + 60 * 20
    update_field(target["user_id"], "sanctioned_until", until)
    update_field(user_id, "last_sanction", now)
    await update.message.reply_text(f"🚫 «{COUNTRIES.get(target['country'],{}).get('name','')}» به مدت ۲۰ دقیقه تحریم شد.")

# ------------------------------------------------------------------
# جدول برترین‌ها
# ------------------------------------------------------------------
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = all_users()
    ranked = sorted(rows, key=lambda r: army_power(get_json_field(r, "army")) + r["gold"], reverse=True)[:10]
    lines = ["🏆 جدول برترین فرماندهان:\n"]
    for i, r in enumerate(ranked, 1):
        score = army_power(get_json_field(r, "army")) + r["gold"]
        name = COUNTRIES.get(r["country"], {}).get("name", r["username"])
        lines.append(f"{i}. {name} — امتیاز {score} (لول {user_level(r)})")
    if not ranked:
        lines.append("هنوز کسی ثبت‌نام نکرده.")
    await update.message.reply_text("\n".join(lines))

# ------------------------------------------------------------------
# وضعیت جهانی / نقشه جهان (شامل تنگه‌ها)
# ------------------------------------------------------------------
async def world_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🗺 نقشه‌ی جهان — وضعیت مناطق\n"]
    for key, r in REGIONS.items():
        res_str = ", ".join(f"{res}({mult}x)" for res, mult in r["resources"].items())
        ruler = region_ruler(key)
        lines.append(f"{r['emoji']} {r['name']}\nمنابع برتر: {res_str}\nمسلط: 👑 {ruler}\n")
    lines.append("🌊 تنگه‌های استراتژیک:\n")
    for key, s in STRAITS.items():
        owner_id = strait_owners.get(key)
        owner_row = get_user(owner_id) if owner_id else None
        owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک"
        lines.append(f"⚓ {s['name']} ({REGIONS[s['region']]['name']}) — {s['bonus_desc']} — مالک: {owner_name}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

async def my_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    r = REGIONS[row["region"]]
    ruler = region_ruler(row["region"])
    text = (
        f"{r['emoji']} منطقه‌ی تو: {r['name']}\n"
        f"منابع برتر این منطقه: {', '.join(f'{k}({v}x)' for k,v in r['resources'].items())}\n"
        f"حاکم فعلی منطقه: 👑 {ruler}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# اتحاد
# ------------------------------------------------------------------
async def alliance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if row["alliance"]:
        await update.message.reply_text(f"🤝 عضو اتحاد «{row['alliance']}» هستی.\nبرای خروج: /leave_alliance")
        return
    await update.message.reply_text("🤝 /create_alliance <اسم>\n/join_alliance <اسم>")

async def create_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /create_alliance <اسم اتحاد>")
        return
    name = " ".join(context.args)[:30]
    update_field(update.effective_user.id, "alliance", name)
    await update.message.reply_text(f"✅ اتحاد «{name}» ساخته شد.")

async def join_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /join_alliance <اسم اتحاد>")
        return
    name = " ".join(context.args)[:30]
    update_field(update.effective_user.id, "alliance", name)
    await update.message.reply_text(f"✅ به اتحاد «{name}» پیوستی.")

async def leave_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_field(update.effective_user.id, "alliance", None)
    await update.message.reply_text("از اتحادت خارج شدی.")

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not row["alliance"]:
        await update.message.reply_text("برای بیانیه باید عضو اتحاد باشی.")
        return
    if not context.args:
        await update.message.reply_text("/announce <متن>")
        return
    text = " ".join(context.args)
    conn = db()
    members = conn.execute("SELECT user_id FROM users WHERE alliance=?", (row["alliance"],)).fetchall()
    conn.close()
    sent = 0
    for m in members:
        if m["user_id"] == update.effective_user.id:
            continue
        try:
            await context.bot.send_message(m["user_id"], f"📢 بیانیه از {row['username']} ({row['alliance']}):\n{text}")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"بیانیه برای {sent} عضو ارسال شد.")

async def statement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 برای صدور بیانیه: /announce <متن پیام>")

# ------------------------------------------------------------------
# حذف اکانت
# ------------------------------------------------------------------
async def delete_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data="delacct:yes")],
        [InlineKeyboardButton("❌ نه، بیخیال", callback_data="delacct:no")],
    ])
    await update.message.reply_text("⚠️ مطمئنی می‌خوای اکانتت رو کامل حذف کنی؟ همه‌چیز از بین میره و برگشت‌پذیر نیست!", reply_markup=kb)

async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    if choice == "yes":
        delete_user(update.effective_user.id)
        await query.edit_message_text("اکانتت کامل حذف شد. هر وقت خواستی دوباره با /start شروع کن.")
    else:
        await query.edit_message_text("لغو شد. اکانتت دست‌نخورده موند.")

# ------------------------------------------------------------------
# کد هدیه (مخفی، در /help نمایش داده نمیشه)
# ------------------------------------------------------------------
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    if not context.args:
        return
    code = context.args[0].strip()
    redeemed = get_json_field(row, "redeemed_codes")
    if code not in GIFT_CODES:
        await update.message.reply_text("کد نامعتبره.")
        return
    if code in redeemed:
        await update.message.reply_text("این کد رو قبلاً استفاده کردی.")
        return
    reward = GIFT_CODES[code]
    for field, amount in reward.items():
        add_resource(user_id, field, amount)
    redeemed.append(code)
    set_json_field(user_id, "redeemed_codes", redeemed)
    await update.message.reply_text("✅ کد با موفقیت فعال شد!")

# ------------------------------------------------------------------
# پشتیبانی / دعوت / راهنما
# ------------------------------------------------------------------
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛠 برای پشتیبانی با ادمین در تماس باش: @your_admin_username")

async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    await update.message.reply_text(f"👥 دوستاتو با این لینک دعوت کن:\n{link}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 قوانین و آموزش:\n\n"
        "/start — ثبت‌نام و انتخاب کشور/منطقه\n"
        "/attack [username] — منوی عملیات حمله (موشک/جاسوسی/خرابکاری/ترور)\n"
        "/sell <resource> <amount> — فروش منابع\n"
        "/send <username> <resource> <amount> — انتقال منابع به بازیکن دیگه\n"
        "/sanction <username> — تحریم یک بازیکن\n"
        "/leaderboard — جدول برترین‌ها\n"
        "/create_alliance, /join_alliance, /leave_alliance, /announce\n\n"
        "نکته: بدون نفت، تجهیزات هوایی‌ت توی حمله شرکت نمی‌کنن!\n"
        "از منوی پایین هم به خزانه، فروشگاه، نقشه جهان و بقیه بخش‌ها دسترسی داری."
    )

# ------------------------------------------------------------------
# اجرای ربات
# ------------------------------------------------------------------
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("sanction", sanction_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("create_alliance", create_alliance_command))
    app.add_handler(CommandHandler("join_alliance", join_alliance_command))
    app.add_handler(CommandHandler("leave_alliance", leave_alliance_command))
    app.add_handler(CommandHandler("announce", announce_command))
    app.add_handler(CommandHandler("redeem", redeem_command))  # مخفی، در /help نیست

    app.add_handler(CallbackQueryHandler(pick_country_callback, pattern="^pickcountry:"))
    app.add_handler(CallbackQueryHandler(pick_region_callback, pattern="^pickregion:"))
    app.add_handler(CallbackQueryHandler(shop_root_callback, pattern="^shopgroup:root$"))
    app.add_handler(CallbackQueryHandler(shop_group_callback, pattern="^shopgroup:"))
    app.add_handler(CallbackQueryHandler(shop_category_callback, pattern="^shopcat:"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy:"))
    app.add_handler(CallbackQueryHandler(buy_building_callback, pattern="^buybuild:"))
    app.add_handler(CallbackQueryHandler(target_pick_callback, pattern="^targetpick:"))
    app.add_handler(CallbackQueryHandler(attack_type_callback, pattern="^atktype:"))
    app.add_handler(CallbackQueryHandler(fire_missile_callback, pattern="^firemissile:"))
    app.add_handler(CallbackQueryHandler(delete_account_callback, pattern="^delacct:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.job_queue.run_repeating(income_job, interval=INCOME_TICK_SEC, first=INCOME_TICK_SEC)

    print("🤖 World War Bot v2 در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
