# -*- coding: utf-8 -*-
"""
=====================================================================
World War Bot v3 — بازی استراتژیک متنی برای تلگرام (نسخه گسترش‌یافته)
همه‌چیز توی همین یک فایله.

راه‌اندازی:
۱) BOT_TOKEN رو به عنوان متغیر محیطی (Environment Variable) ست کن.
۲) pip install -r requirements.txt   (باید شامل python-telegram-bot[job-queue]==21.4 باشه)
۳) python bot.py
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
STRAIT_ACTION_COOLDOWN_SEC = 60 * 15
INCOME_TICK_SEC = 60
XP_PER_LEVEL = 1000

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

# ------------------------------------------------------------------
# تنگه‌های استراتژیک — قابل تصرف و باز/بسته شدن
# ------------------------------------------------------------------
STRAITS = {
    "hormuz":    {"name": "تنگه هرمز",       "region": "middle_east", "affects": "oil",  "close_mult": 3.0},
    "malacca":   {"name": "تنگه مالاکا",     "region": "east_asia",   "affects": "gold", "close_mult": 2.0},
    "gibraltar": {"name": "تنگه جبل‌الطارق", "region": "europe",      "affects": "oil",  "close_mult": 1.7},
    "bab_el_mandeb": {"name": "تنگه باب‌المندب", "region": "africa",  "affects": "gold", "close_mult": 1.8},
}

# ------------------------------------------------------------------
# کشورها (هرکدوم با منطقه‌ی خودشون، برای انتخاب قاره→کشور)
# ------------------------------------------------------------------
COUNTRIES = {
    "iran":        {"name": "ایران 🇮🇷",        "region": "middle_east",  "bonus": "uranium_mult", "value": 1.5, "desc": "درآمد اورانیوم +۵۰٪",
                     "signature": ["missile_zolfaghar", "missile_fattah2", "drone_shahed"], "faction": "سپاه پاسداران"},
    "saudi":       {"name": "عربستان سعودی 🇸🇦", "region": "middle_east", "bonus": "oil_mult", "value": 1.6, "desc": "درآمد نفت +۶۰٪",
                     "signature": ["defense_patriot", "fighter_typhoon"], "faction": None},
    "israel":      {"name": "اسرائیل 🇮🇱",       "region": "middle_east", "bonus": "air_discount", "value": 0.75, "desc": "تجهیزات هوایی ۲۵٪ ارزان‌تر",
                     "signature": ["defense_ironbeam", "drone_hermes"], "faction": "موساد"},
    "turkey":      {"name": "ترکیه 🇹🇷",         "region": "middle_east", "bonus": "drone_discount", "value": 0.7, "desc": "پهبادها ۳۰٪ ارزان‌تر",
                     "signature": ["drone_bayraktar", "tank_altay"], "faction": None},
    "egypt":       {"name": "مصر 🇪🇬",           "region": "africa",      "bonus": "gold_mult", "value": 1.3, "desc": "درآمد طلا +۳۰٪",
                     "signature": ["tank_abrams_eg", "fighter_rafale_eg"], "faction": None},
    "germany":     {"name": "آلمان 🇩🇪",         "region": "europe",      "bonus": "iron_mult", "value": 1.4, "desc": "درآمد آهن +۴۰٪",
                     "signature": ["tank_leopard2", "sub_u212"], "faction": None},
    "uk":          {"name": "بریتانیا 🇬🇧",      "region": "europe",      "bonus": "sea_discount", "value": 0.8, "desc": "تجهیزات دریایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_typhoon", "carrier_queenelizabeth"], "faction": None},
    "france":      {"name": "فرانسه 🇫🇷",        "region": "europe",      "bonus": "oil_mult", "value": 1.3, "desc": "درآمد نفت +۳۰٪",
                     "signature": ["fighter_rafale", "sub_barracuda"], "faction": None},
    "russia":      {"name": "روسیه 🇷🇺",         "region": "central_asia","bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                     "signature": ["tank_t14", "missile_iskander"], "faction": None},
    "china":       {"name": "چین 🇨🇳",           "region": "east_asia",   "bonus": "gold_mult", "value": 1.4, "desc": "درآمد طلا +۴۰٪",
                     "signature": ["fighter_j20", "destroyer_type055"], "faction": None},
    "japan":       {"name": "ژاپن 🇯🇵",          "region": "east_asia",   "bonus": "sea_discount", "value": 0.75, "desc": "تجهیزات دریایی ۲۵٪ ارزان‌تر",
                     "signature": ["destroyer_kongo", "fighter_f35"], "faction": None},
    "south_korea": {"name": "کره جنوبی 🇰🇷",    "region": "east_asia",   "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                     "signature": ["tank_k2"], "faction": None},
    "india":       {"name": "هند 🇮🇳",           "region": "central_asia","bonus": "land_discount", "value": 0.85, "desc": "تجهیزات زمینی ۱۵٪ ارزان‌تر",
                     "signature": ["missile_agni", "tank_arjun"], "faction": None},
    "pakistan":    {"name": "پاکستان 🇵🇰",       "region": "central_asia","bonus": "uranium_mult", "value": 1.3, "desc": "درآمد اورانیوم +۳۰٪",
                     "signature": ["missile_shaheen"], "faction": None},
    "usa":         {"name": "آمریکا 🇺🇸",        "region": "north_america","bonus": "air_discount", "value": 0.8, "desc": "تجهیزات هوایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_f22", "carrier_nimitz"], "faction": None},
    "brazil":      {"name": "برزیل 🇧🇷",         "region": "south_america","bonus": "gold_mult", "value": 1.3, "desc": "درآمد طلا +۳۰٪",
                     "signature": ["fighter_gripen"], "faction": None},
}

# ------------------------------------------------------------------
# فروشگاه — دسته‌بندی شده، با تنوع بالا و آیتم‌های امضادار کشوری
# آمار (قیمت/قدرت) کاملاً برای تعادل بازی طراحی شده، نه اطلاعات فنی واقعی
# ------------------------------------------------------------------
SHOP = {
    "air_defense": {"title": "پدافند هوایی 🛡", "parent": "air", "items": [
        {"id": "defense_basic",    "name": "سامانه پدافند پایه",       "price": 1500,  "power": 40,  "level": 1},
        {"id": "defense_hawk",     "name": "سامانه پدافند هاوک",       "price": 3200,  "power": 90,  "level": 2},
        {"id": "defense_patriot",  "name": "سامانه پدافند پاتریوت",    "price": 5000,  "power": 140, "level": 3},
        {"id": "defense_s400",     "name": "سامانه پدافند اس-۴۰۰",     "price": 7000,  "power": 190, "level": 4},
        {"id": "defense_ironbeam", "name": "سامانه پدافند لیزری آیرون‌بیم", "price": 8000, "power": 210, "level": 5},
        {"id": "defense_bavar373", "name": "سامانه پدافند باور-۳۷۳",   "price": 6500,  "power": 180, "level": 4},
    ]},
    "air_drone": {"title": "پهباد 🛸", "parent": "air", "items": [
        {"id": "drone_basic",     "name": "پهباد شناسایی رعد",   "price": 300,  "power": 15,  "level": 1},
        {"id": "drone_shahed",    "name": "پهباد انتحاری شاهد",  "price": 900,  "power": 55,  "level": 2},
        {"id": "drone_mohajer",   "name": "پهباد مهاجر-۶",       "price": 1300, "power": 75,  "level": 3},
        {"id": "drone_bayraktar", "name": "پهباد جنگی بایراکتار","price": 1600, "power": 90,  "level": 3},
        {"id": "drone_hermes",    "name": "پهباد شناسایی هرمس",  "price": 1200, "power": 70,  "level": 2},
        {"id": "drone_reaper",    "name": "پهباد جنگی ریپر",     "price": 2200, "power": 120, "level": 4},
    ]},
    "air_fighter": {"title": "جنگنده ✈️", "parent": "air", "items": [
        {"id": "fighter_f14",     "name": "جنگنده اف-۱۴ تامکت",   "price": 3000,  "power": 110, "level": 2},
        {"id": "fighter_gripen",  "name": "جنگنده گریپن",         "price": 3500,  "power": 130, "level": 3},
        {"id": "fighter_f18",     "name": "جنگنده اف/ای-۱۸",      "price": 4200,  "power": 150, "level": 3},
        {"id": "fighter_rafale",  "name": "جنگنده رافائل",        "price": 5500,  "power": 190, "level": 4},
        {"id": "fighter_typhoon", "name": "جنگنده تایفون",        "price": 6000,  "power": 210, "level": 4},
        {"id": "fighter_su35",    "name": "جنگنده سوخو-۳۵",       "price": 6500,  "power": 225, "level": 5},
        {"id": "fighter_f15ex",   "name": "جنگنده اف-۱۵ ایکس",    "price": 7000,  "power": 240, "level": 5},
        {"id": "fighter_j20",     "name": "جنگنده جی-۲۰",         "price": 7500,  "power": 250, "level": 5},
        {"id": "fighter_j35",     "name": "جنگنده جی-۳۵",         "price": 8000,  "power": 260, "level": 6},
        {"id": "fighter_su57",    "name": "جنگنده سوخو-۵۷",       "price": 8500,  "power": 270, "level": 6},
        {"id": "fighter_f35",     "name": "جنگنده اف-۳۵",         "price": 9500,  "power": 300, "level": 6},
        {"id": "fighter_f22",     "name": "جنگنده اف-۲۲ رپتور",   "price": 12000, "power": 350, "level": 7},
    ]},
    "air_bomber": {"title": "بمب‌افکن 💣", "parent": "air", "items": [
        {"id": "bomber_basic", "name": "بمب‌افکن راهبردی سیمرغ",   "price": 9000,  "power": 300, "level": 5},
        {"id": "bomber_b2",    "name": "بمب‌افکن رادارگریز بی-۲",  "price": 16000, "power": 460, "level": 7},
        {"id": "bomber_tu160", "name": "بمب‌افکن تی‌یو-۱۶۰",      "price": 14000, "power": 420, "level": 6},
    ]},
    "air_missile": {"title": "موشک ☄️ (مصرفی)", "parent": "air", "items": [
        {"id": "missile_scud",       "name": "موشک اسکاد",              "price": 1800,  "power": 90,  "level": 2},
        {"id": "missile_zolfaghar",  "name": "موشک ذوالفقار",           "price": 2500,  "power": 120, "level": 2},
        {"id": "missile_hoveizeh",   "name": "موشک کروز هویزه",         "price": 3200,  "power": 150, "level": 3},
        {"id": "missile_emad",       "name": "موشک عماد",               "price": 4000,  "power": 180, "level": 3},
        {"id": "missile_kheibar",    "name": "موشک خیبرشکن",            "price": 5000,  "power": 210, "level": 4},
        {"id": "missile_fattah2",    "name": "موشک فتاح-۲",             "price": 6500,  "power": 260, "level": 4},
        {"id": "missile_iskander",   "name": "موشک اسکندر",             "price": 7000,  "power": 280, "level": 5},
        {"id": "missile_sejjil",     "name": "موشک سجیل",               "price": 8000,  "power": 300, "level": 5},
        {"id": "missile_agni",       "name": "موشک قاره‌پیمای آگنی",    "price": 10000, "power": 340, "level": 6},
        {"id": "missile_shaheen",    "name": "موشک شاهین",              "price": 9000,  "power": 320, "level": 5},
        {"id": "missile_df17",       "name": "موشک دی‌اف-۱۷",           "price": 11000, "power": 360, "level": 6},
        {"id": "missile_css4",       "name": "موشک قاره‌پیمای سی‌اس‌اس-۴", "price": 15000, "power": 420, "level": 7},
        {"id": "missile_nuclear",    "name": "☢️ موشک هسته‌ای (نمادین)", "price": 50000, "power": 1000, "level": 10},
    ]},
    "land_infantry": {"title": "پیاده‌نظام 🪖", "parent": "land", "items": [
        {"id": "soldier",       "name": "گروهان پیاده‌نظام",  "price": 100,  "power": 5,  "level": 1},
        {"id": "special_force", "name": "نیروی ویژه",         "price": 600,  "power": 30, "level": 2},
        {"id": "commando",      "name": "تکاور دریایی",       "price": 1000, "power": 45, "level": 3},
    ]},
    "land_tank": {"title": "تانک 🚜", "parent": "land", "items": [
        {"id": "tank_basic",    "name": "تانک زره‌پوش کاویر",  "price": 1200,  "power": 60,  "level": 2},
        {"id": "tank_altay",    "name": "تانک آلتای",          "price": 3000,  "power": 130, "level": 3},
        {"id": "tank_arjun",    "name": "تانک آرجون",          "price": 3500,  "power": 145, "level": 4},
        {"id": "tank_k2",       "name": "تانک کی-۲ بلک‌پنتر",  "price": 5500,  "power": 210, "level": 5},
        {"id": "tank_leopard2", "name": "تانک لئوپارد ۲",      "price": 4500,  "power": 180, "level": 5},
        {"id": "tank_abrams",   "name": "تانک ام۱ ابرامز",     "price": 6000,  "power": 230, "level": 6},
        {"id": "tank_t14",      "name": "تانک تی-۱۴ آرماتا",   "price": 7000,  "power": 260, "level": 6},
    ]},
    "land_support": {"title": "توپخانه و نفربر 🎯", "parent": "land", "items": [
        {"id": "artillery",   "name": "توپخانه خودکششی رعد", "price": 2200, "power": 100, "level": 3},
        {"id": "apc_basic",   "name": "نفربر زرهی صاعقه",    "price": 800,  "power": 35,  "level": 1},
        {"id": "apc_guarani", "name": "نفربر زرهی گوارانی",  "price": 1400, "power": 55,  "level": 2},
        {"id": "mlrs",        "name": "راکت‌انداز چندلوله",  "price": 3000, "power": 140, "level": 4},
    ]},
    "sea_patrol": {"title": "ناوچه گشتی 🚤", "parent": "sea", "items": [
        {"id": "patrol", "name": "ناوچه گشتی", "price": 1500, "power": 50, "level": 1},
    ]},
    "sea_destroyer": {"title": "ناوشکن 🚢", "parent": "sea", "items": [
        {"id": "destroyer_basic",   "name": "ناوشکن دماوند",    "price": 5000, "power": 220, "level": 3},
        {"id": "destroyer_kongo",   "name": "ناوشکن کونگو",     "price": 6500, "power": 260, "level": 4},
        {"id": "destroyer_arleigh", "name": "ناوشکن آرلی برک",  "price": 7500, "power": 290, "level": 5},
        {"id": "destroyer_type055", "name": "ناوشکن تایپ ۰۵۵",  "price": 8000, "power": 310, "level": 5},
    ]},
    "sea_sub": {"title": "زیردریایی 🌊", "parent": "sea", "items": [
        {"id": "sub_basic",    "name": "زیردریایی غدیر",   "price": 6000,  "power": 260, "level": 4},
        {"id": "sub_u212",     "name": "زیردریایی یو-۲۱۲", "price": 8500,  "power": 320, "level": 5},
        {"id": "sub_barracuda","name": "زیردریایی باراکودا","price": 11000,"power": 380, "level": 6},
    ]},
    "sea_carrier": {"title": "ناو هواپیمابر 🛳", "parent": "sea", "items": [
        {"id": "carrier_basic",         "name": "ناو هواپیمابر سبک",           "price": 15000, "power": 500, "level": 6},
        {"id": "carrier_queenelizabeth","name": "ناو هواپیمابر کوئین الیزابت", "price": 20000, "power": 600, "level": 7},
        {"id": "carrier_nimitz",        "name": "ناو هواپیمابر نیمیتز",       "price": 26000, "power": 700, "level": 8},
    ]},
}

AIR_CATEGORY_KEYS = ["air_defense", "air_drone", "air_fighter", "air_bomber", "air_missile"]
LAND_CATEGORY_KEYS = ["land_infantry", "land_tank", "land_support"]
SEA_CATEGORY_KEYS = ["sea_patrol", "sea_destroyer", "sea_sub", "sea_carrier"]

# آیتم‌هایی که موقع شلیک/استفاده مصرف میشن (کم میشن از انبار)
CONSUMABLE_CATEGORY = "air_missile"

BUILDINGS = {
    "oil_rig":          {"name": "دکل نفت 🛢",                 "price": 2000, "resource": "oil",     "rate": 2},
    "iron_mine":        {"name": "معدن آهن ⛏",                 "price": 1800, "resource": "iron",    "rate": 2},
    "gold_mine":        {"name": "معدن طلا 🏆",                 "price": 2500, "resource": "gold",    "rate": 3},
    "uranium_facility": {"name": "تأسیسات استخراج اورانیوم ☢️", "price": 5000, "resource": "uranium", "rate": 1},
}

RESOURCE_NAMES = {
    "gold": "طلا 🏆", "oil": "نفت 🛢", "iron": "آهن ⛏",
    "uranium": "اورانیوم ☢️", "opium": "تریاک 🌿",
}
BASE_EXCHANGE_RATES = {"oil": 6, "iron": 8, "uranium": 30, "opium": 12}

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

def shop_category_key_of(item_id):
    for key, cat in SHOP.items():
        for it in cat["items"]:
            if it["id"] == item_id:
                return key
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
            casualties INTEGER DEFAULT 0,
            alliance TEXT DEFAULT NULL,
            last_attack INTEGER DEFAULT 0,
            last_sanction INTEGER DEFAULT 0,
            last_recon INTEGER DEFAULT 0,
            last_strait_action INTEGER DEFAULT 0,
            sanctioned_until INTEGER DEFAULT 0,
            sabotaged_until INTEGER DEFAULT 0,
            redeemed_codes TEXT DEFAULT '[]',
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS straits (
            strait_key TEXT PRIMARY KEY,
            owner_id INTEGER,
            is_open INTEGER DEFAULT 1
        )
    """)
    for key in STRAITS:
        conn.execute("INSERT OR IGNORE INTO straits (strait_key, owner_id, is_open) VALUES (?, NULL, 1)", (key,))
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
    conn.execute("UPDATE straits SET owner_id=NULL WHERE owner_id=?", (user_id,))
    conn.commit()
    conn.close()

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
    default = "[]" if field in ("recon_targets", "redeemed_codes") else "{}"
    try:
        return json.loads(row[field] or default)
    except Exception:
        return [] if field in ("recon_targets", "redeemed_codes") else {}

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
            continue
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

# --- تنگه‌ها ---
def get_strait(key):
    conn = db()
    row = conn.execute("SELECT * FROM straits WHERE strait_key=?", (key,)).fetchone()
    conn.close()
    return row

def all_straits():
    conn = db()
    rows = conn.execute("SELECT * FROM straits").fetchall()
    conn.close()
    return rows

def set_strait(key, owner_id=None, is_open=None):
    conn = db()
    if owner_id is not None:
        conn.execute("UPDATE straits SET owner_id=? WHERE strait_key=?", (owner_id, key))
    if is_open is not None:
        conn.execute("UPDATE straits SET is_open=? WHERE strait_key=?", (1 if is_open else 0, key))
    conn.commit()
    conn.close()

def current_exchange_rates():
    """نرخ تبادلات با در نظر گرفتن تنگه‌های بسته"""
    rates = dict(BASE_EXCHANGE_RATES)
    for key, s in STRAITS.items():
        srow = get_strait(key)
        if srow and srow["is_open"] == 0:
            rates[s["affects"]] = rates.get(s["affects"], 1) * s["close_mult"]
    return rates

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
        ["تنگه‌ها ⚓", "حذف اکانت ❌"],
    ],
    resize_keyboard=True
)

REGION_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"pickregion:{k}")]
    for k, v in REGIONS.items()
])

def countries_in_region_keyboard(region_key, taken):
    rows = []
    for key, c in COUNTRIES.items():
        if c["region"] != region_key:
            continue
        label = c["name"] + (" (گرفته‌شده)" if key in taken else "")
        rows.append([InlineKeyboardButton(label, callback_data=f"pickcountry:{key}")])
    rows.append([InlineKeyboardButton("⬅️ قاره‌ی دیگه", callback_data="backtoregion")])
    return InlineKeyboardMarkup(rows)

# ------------------------------------------------------------------
# /start و ثبت‌نام (اول قاره/منطقه، بعد کشور همون منطقه)
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
        "🌍 به «جنگ جهانی» خوش اومدی، فرمانده!\n\nاول یه قاره/منطقه انتخاب کن:",
        reply_markup=REGION_KEYBOARD
    )

async def pick_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_key = query.data.split(":")[1]
    conn = db()
    taken = {r["country"] for r in conn.execute("SELECT country FROM users").fetchall()}
    conn.close()
    await query.edit_message_text(
        f"منطقه {REGIONS[region_key]['emoji']} {REGIONS[region_key]['name']} انتخاب شد.\nحالا یه کشور از این منطقه انتخاب کن:",
        reply_markup=countries_in_region_keyboard(region_key, taken)
    )

async def back_to_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("یه قاره/منطقه انتخاب کن:", reply_markup=REGION_KEYBOARD)

async def pick_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    country_key = query.data.split(":")[1]
    conn = db()
    taken = conn.execute("SELECT 1 FROM users WHERE country=?", (country_key,)).fetchone()
    conn.close()
    if taken:
        await query.answer("این کشور قبلاً گرفته شده!", show_alert=True)
        return
    await query.answer()
    user = update.effective_user
    country = COUNTRIES[country_key]
    create_user(user.id, user.username or user.first_name, country["region"], country_key)
    await query.edit_message_text(
        f"✅ حکومت {country['name']} تأسیس شد!\n"
        f"💰 {STARTING_GOLD} طلا برای شروع دریافت کردی.\n"
        f"🎖 بونوس کشورت: {country['desc']}"
    )
    await context.bot.send_message(user.id, "از منوی پایین شروع کن:", reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# روتر پیام‌های متنی
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
        "تنگه‌ها ⚓": straits_menu,
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
    a_lines = "\n".join(f"  {item_lookup(i)['name']} × {c}" for i, c in army.items() if c) or "  چیزی نداری"
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
        f"⚔️ تجهیزات نظامی:\n{a_lines}\n\n"
        f"قدرت نظامی کل: {army_power(army, row['oil']>0)}"
        + (" (⚠️ نفت صفره، هواپیماهات پرواز نمی‌کنن!)" if row['oil'] <= 0 else "") +
        f"\n💀 تلفات کل: {row['casualties']}\n"
        f"تاریخ ثبت‌نام: {row['created_at']}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# فروشگاه
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
        kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="shopgroup:root")])
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
        price = int(price * 0.8)
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
        lock = "" if lvl >= it["level"] else f" 🔒لول{it['level']}"
        kb.append([InlineKeyboardButton(f"{it['name']} — {price}💰 ق{it['power']}{lock}", callback_data=f"buy:{cat_key}:{it['id']}")])
    kb.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"shopgroup:{cat['parent']}")])
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
    await query.answer(f"✅ {b['name']} ساخته شد!", show_alert=True)

# ------------------------------------------------------------------
# درآمد خودکار
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
    rates = current_exchange_rates()
    lines = ["📈 مرکز تبادلات جهانی — نرخ فروش منابع به طلا:\n"]
    for res, rate in rates.items():
        extra = " ⚠️ (قیمت بالا رفته، یه تنگه بسته‌ست!)" if rate > BASE_EXCHANGE_RATES[res] else ""
        lines.append(f"{RESOURCE_NAMES[res]}: هر واحد = {int(rate)} طلا{extra}")
    lines.append("\n/sell <منبع> <تعداد>\n/send <username> <resource> <تعداد>")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    rates = current_exchange_rates()
    if len(context.args) != 2 or context.args[0] not in rates:
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
    gold_gain = int(amount * rates[res])
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
    await update.message.reply_text(f"✅ {amount} واحد {RESOURCE_NAMES.get(field,'طلا')} فرستاده شد.")
    try:
        await context.bot.send_message(target["user_id"], f"📥 {amount} واحد {RESOURCE_NAMES.get(field,'طلا')} از {row['username']} دریافت کردی.")
    except Exception:
        pass

# ------------------------------------------------------------------
# تنگه‌ها — تصرف، باز/بسته کردن، تاثیر روی قیمت‌ها + پیام همگانی
# ------------------------------------------------------------------
async def straits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        owner_row = get_user(srow["owner_id"]) if srow["owner_id"] else None
        owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک"
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb.append([InlineKeyboardButton(f"{s['name']} | مالک: {owner_name} | {status}", callback_data=f"straitinfo:{key}")])
    await update.message.reply_text("⚓ تنگه‌های استراتژیک جهان:", reply_markup=InlineKeyboardMarkup(kb))

async def strait_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    s = STRAITS[key]
    srow = get_strait(key)
    user_id = update.effective_user.id
    owner_row = get_user(srow["owner_id"]) if srow["owner_id"] else None
    owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک (NPC)"
    status = "باز 🟢" if srow["is_open"] else "بسته 🔴"

    kb_rows = []
    if srow["owner_id"] == user_id:
        if srow["is_open"]:
            kb_rows.append([InlineKeyboardButton("🔴 بستن تنگه", callback_data=f"straitclose:{key}")])
        else:
            kb_rows.append([InlineKeyboardButton("🟢 باز کردن تنگه", callback_data=f"straitopen:{key}")])
    else:
        kb_rows.append([InlineKeyboardButton("⚔️ تلاش برای تصرف", callback_data=f"straitcapture:{key}")])
    kb_rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="straitback")])

    await query.edit_message_text(
        f"⚓ {s['name']}\nمنطقه: {REGIONS[s['region']]['name']}\nمالک فعلی: {owner_name}\nوضعیت: {status}\n"
        f"اثر بسته شدن: قیمت {RESOURCE_NAMES[s['affects']]} تا {s['close_mult']}× بالا میره.",
        reply_markup=InlineKeyboardMarkup(kb_rows)
    )

async def strait_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        owner_row = get_user(srow["owner_id"]) if srow["owner_id"] else None
        owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک"
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb.append([InlineKeyboardButton(f"{s['name']} | مالک: {owner_name} | {status}", callback_data=f"straitinfo:{key}")])
    await query.edit_message_text("⚓ تنگه‌های استراتژیک جهان:", reply_markup=InlineKeyboardMarkup(kb))

async def strait_capture_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    user_id = update.effective_user.id
    row = get_user(user_id)
    now = int(time.time())
    if now - row["last_strait_action"] < STRAIT_ACTION_COOLDOWN_SEC:
        wait = (STRAIT_ACTION_COOLDOWN_SEC - (now - row["last_strait_action"])) // 60
        await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
        return
    update_field(user_id, "last_strait_action", now)
    srow = get_strait(key)
    my_power = army_power(get_json_field(row, "army"), row["oil"] > 0)
    if srow["owner_id"]:
        owner_row = get_user(srow["owner_id"])
        owner_power = army_power(get_json_field(owner_row, "army"), owner_row["oil"] > 0)
    else:
        owner_power = 100  # مقاومت پیش‌فرض NPC
    success = my_power + random.randint(0, 60) > owner_power
    if success:
        set_strait(key, owner_id=user_id, is_open=True)
        await query.answer("✅ تنگه رو تصرف کردی!", show_alert=True)
        await broadcast_to_all(context, f"⚓ {STRAITS[key]['name']} توسط {COUNTRIES.get(row['country'],{}).get('name')} تصرف شد!")
    else:
        await query.answer("💥 تلاش برای تصرف شکست خورد.", show_alert=True)
    await strait_info_callback(update, context)

async def strait_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    srow = get_strait(key)
    if srow["owner_id"] != update.effective_user.id:
        await query.answer("این تنگه مال تو نیست!", show_alert=True)
        return
    set_strait(key, is_open=False)
    await query.answer("تنگه بسته شد.", show_alert=True)
    s = STRAITS[key]
    await broadcast_to_all(context, f"🚨 {s['name']} بسته شد! قیمت {RESOURCE_NAMES[s['affects']]} به‌شدت افزایش یافت.")
    await strait_info_callback(update, context)

async def strait_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    srow = get_strait(key)
    if srow["owner_id"] != update.effective_user.id:
        await query.answer("این تنگه مال تو نیست!", show_alert=True)
        return
    set_strait(key, is_open=True)
    await query.answer("تنگه باز شد.", show_alert=True)
    s = STRAITS[key]
    await broadcast_to_all(context, f"✅ {s['name']} دوباره باز شد. قیمت {RESOURCE_NAMES[s['affects']]} به حالت عادی برگشت.")
    await strait_info_callback(update, context)

async def broadcast_to_all(context, text):
    for row in all_users():
        try:
            await context.bot.send_message(row["user_id"], text)
        except Exception:
            pass

# ------------------------------------------------------------------
# سیستم حمله گسترده
# ------------------------------------------------------------------
def targets_keyboard(exclude_id):
    rows = [r for r in all_users() if r["user_id"] != exclude_id][:15]
    kb = [[InlineKeyboardButton(f"{COUNTRIES.get(r['country'],{}).get('name', r['username'])}", callback_data=f"targetpick:{r['user_id']}")] for r in rows]
    return InlineKeyboardMarkup(kb) if kb else None

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not row:
        await update.message.reply_text("اول /start بزن.")
        return
    if context.args:
        target = get_user_by_username(context.args[0].lstrip("@"))
        if not target:
            await update.message.reply_text("این بازیکن پیدا نشد.")
            return
        await show_attack_type_menu(update, context, target["user_id"])
        return
    kb = targets_keyboard(update.effective_user.id)
    if not kb:
        await update.message.reply_text("هنوز بازیکن دیگه‌ای ثبت‌نام نکرده.")
        return
    await update.message.reply_text("یه هدف انتخاب کن:", reply_markup=kb)

async def target_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    await show_attack_type_menu(update, context, target_id, edit=True)

async def show_attack_type_menu(update, context, target_id, edit=False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("☄️ حمله موشکی", callback_data=f"atktype:missile:{target_id}")],
        [InlineKeyboardButton("✈️ حمله هوایی ترکیبی", callback_data=f"atktype:airstrike:{target_id}")],
        [InlineKeyboardButton("🚜 حمله زمینی", callback_data=f"atktype:landstrike:{target_id}")],
        [InlineKeyboardButton("🚢 حمله دریایی", callback_data=f"atktype:seastrike:{target_id}")],
        [InlineKeyboardButton("🕵️ جاسوسی/شناسایی", callback_data=f"atktype:recon:{target_id}")],
        [InlineKeyboardButton("🧨 خرابکاری زیرساخت", callback_data=f"atktype:sabotage:{target_id}")],
        [InlineKeyboardButton("🎯 ترور (نیاز به شناسایی)", callback_data=f"atktype:assassinate:{target_id}")],
    ])
    text = "نوع عملیات رو انتخاب کن:"
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

def sub_power(army_dict, oil_ok, categories):
    total = 0
    for item_id, count in army_dict.items():
        it = item_lookup(item_id)
        if not it:
            continue
        cat = category_of(item_id)
        if cat == "air" and not oil_ok:
            continue
        if cat in categories:
            total += count * it["power"]
    return total

def record_casualties(user_id, army_dict, loss_ratio=0.15):
    """موقع شکست، بخشی از تجهیزات به عنوان تلفات از بین میره"""
    lost_power = 0
    changed = False
    for item_id in list(army_dict.keys()):
        count = army_dict[item_id]
        if count <= 0:
            continue
        lose = int(count * loss_ratio)
        if lose > 0:
            army_dict[item_id] = count - lose
            it = item_lookup(item_id)
            lost_power += lose * (it["power"] if it else 0)
            changed = True
    if changed:
        set_json_field(user_id, "army", army_dict)
        update_field(user_id, "casualties", get_user(user_id)["casualties"] + lost_power)
    return lost_power

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
        missile_owned = [it for it in army if shop_category_key_of(it) == "air_missile" and army[it] > 0]
        if not missile_owned:
            await query.answer("هیچ موشکی نداری! اول از فروشگاه بخر.", show_alert=True)
            return
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{item_lookup(mid)['name']} ({army[mid]} عدد)", callback_data=f"firemissile:{mid}:{target_id}")]
            for mid in missile_owned
        ])
        await query.edit_message_text("کدوم موشک رو شلیک می‌کنی؟ (بعد از شلیک از انبارت کم میشه)", reply_markup=kb)
        return

    if atype in ("airstrike", "landstrike", "seastrike"):
        cat_map = {"airstrike": "air", "landstrike": "land", "seastrike": "sea"}
        parent = cat_map[atype]
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        update_field(attacker_id, "last_attack", now)
        a_army = get_json_field(attacker, "army")
        d_army = get_json_field(target, "army")
        a_power = sub_power(a_army, attacker["oil"] > 0, [parent]) + random.randint(0, 40)
        d_power = sub_power(d_army, target["oil"] > 0, [parent]) + random.randint(0, 40)
        name_fa = {"air": "هوایی", "land": "زمینی", "sea": "دریایی"}[parent]
        if a_power > d_power and a_power > 0:
            loot = min(target["gold"], random.randint(100, 400))
            add_resource(target_id, "gold", -loot)
            add_resource(attacker_id, "gold", loot)
            update_field(attacker_id, "xp", attacker["xp"] + 120)
            lost = record_casualties(target_id, d_army)
            await query.edit_message_text(f"⚔️ حمله {name_fa} موفق بود! ({a_power} vs {d_power})\n🏆 غنیمت: {loot}\n💀 تلفات هدف: {lost}")
            await notify_defender(context, target_id, attacker, f"حمله {name_fa}", f"{loot} طلا از دست دادی و {lost} قدرت نظامی تلفات دادی!")
        else:
            await query.edit_message_text(f"💥 حمله {name_fa} دفع شد. ({a_power} vs {d_power})")
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
        await query.edit_message_text(f"🕵️ شناسایی موفق!\nقدرت هدف: {t_power}\nطلا: {target['gold']}\nحالا امکان ترور باز شده.")
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
            await query.edit_message_text("🧨 خرابکاری موفق! درآمد ساختمان‌های هدف تا ۱۵ دقیقه ۷۰٪ کاهش یافت.")
            await notify_defender(context, target_id, attacker, "خرابکاری زیرساخت", "زیرساخت‌های اقتصادی‌ت خراب شد!")
        else:
            await query.edit_message_text("💥 خرابکاری شکست خورد.")
        return

    if atype == "assassinate":
        recon_list = get_json_field(attacker, "recon_targets")
        if target_id not in recon_list:
            await query.answer("اول باید این هدف رو شناسایی کنی!", show_alert=True)
            return
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await query.answer(f"⏳ {wait} دقیقه دیگه صبر کن.", show_alert=True)
            return
        update_field(attacker_id, "last_attack", now)
        success = random.random() < 0.55
        if success:
            loot = min(target["gold"], random.randint(300, 800))
            add_resource(target_id, "gold", -loot)
            add_resource(attacker_id, "gold", loot)
            update_field(attacker_id, "xp", attacker["xp"] + 150)
            await query.edit_message_text(f"🎯 ترور موفق! غنیمت: {loot} طلا 🏆")
            await notify_defender(context, target_id, attacker, "ترور", f"عملیات ترور موفق! {loot} طلا از دست دادی.")
        else:
            await query.edit_message_text("💥 ترور شکست خورد و لو رفت.")
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

    a_army = get_json_field(attacker, "army")
    if a_army.get(missile_id, 0) <= 0:
        await query.answer("این موشک رو دیگه نداری!", show_alert=True)
        return

    now = int(time.time())
    update_field(attacker_id, "last_attack", now)

    # مصرف موشک از انبار
    a_army[missile_id] -= 1
    if a_army[missile_id] <= 0:
        del a_army[missile_id]
    set_json_field(attacker_id, "army", a_army)

    missile = item_lookup(missile_id)
    d_army = get_json_field(target, "army")
    a_power = army_power(a_army, attacker["oil"] > 0) + missile["power"] + random.randint(0, 50)
    d_power = army_power(d_army, target["oil"] > 0) + random.randint(0, 50)

    if a_power > d_power:
        loot = min(target["gold"], random.randint(80, 350))
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        update_field(attacker_id, "xp", attacker["xp"] + 100)
        lost = record_casualties(target_id, d_army)
        await query.edit_message_text(
            f"☄️ شلیک {missile['name']} موفق بود!\nقدرت تو: {a_power} vs هدف: {d_power}\n🏆 غنیمت: {loot}\n💀 تلفات هدف: {lost}\n(۱ عدد {missile['name']} مصرف شد)"
        )
        await notify_defender(context, target_id, attacker, f"حمله موشکی ({missile['name']})", f"{loot} طلا و {lost} قدرت نظامی از دست دادی!")
    else:
        await query.edit_message_text(f"💥 حمله دفع شد. قدرت هدف ({d_power}) بیشتر از تو ({a_power}) بود.\n(۱ عدد {missile['name']} مصرف شد)")

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
# وضعیت جهانی / نقشه جهان
# ------------------------------------------------------------------
async def world_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🗺 نقشه‌ی جهان — وضعیت مناطق\n"]
    for key, r in REGIONS.items():
        res_str = ", ".join(f"{res}({mult}x)" for res, mult in r["resources"].items())
        ruler = region_ruler(key)
        lines.append(f"{r['emoji']} {r['name']}\nمنابع برتر: {res_str}\nمسلط: 👑 {ruler}\n")
    lines.append("⚓ تنگه‌های استراتژیک: (برای جزئیات، از منو «تنگه‌ها» رو بزن)\n")
    for key, s in STRAITS.items():
        srow = get_strait(key)
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        lines.append(f"  {s['name']}: {status}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

async def my_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    r = REGIONS[row["region"]]
    ruler = region_ruler(row["region"])
    text = (
        f"{r['emoji']} منطقه‌ی تو: {r['name']}\n"
        f"منابع برتر: {', '.join(f'{k}({v}x)' for k,v in r['resources'].items())}\n"
        f"حاکم فعلی: 👑 {ruler}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# اتحاد
# ------------------------------------------------------------------
async def alliance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if row["alliance"]:
        await update.message.reply_text(f"🤝 عضو اتحاد «{row['alliance']}» هستی.\n/leave_alliance برای خروج")
        return
    await update.message.reply_text("🤝 /create_alliance <اسم>\n/join_alliance <اسم>")

async def create_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /create_alliance <اسم>")
        return
    name = " ".join(context.args)[:30]
    update_field(update.effective_user.id, "alliance", name)
    await update.message.reply_text(f"✅ اتحاد «{name}» ساخته شد.")

async def join_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /join_alliance <اسم>")
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
    await update.message.reply_text("📢 برای بیانیه: /announce <متن پیام>")

# ------------------------------------------------------------------
# حذف اکانت
# ------------------------------------------------------------------
async def delete_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data="delacct:yes")],
        [InlineKeyboardButton("❌ نه، بیخیال", callback_data="delacct:no")],
    ])
    await update.message.reply_text("⚠️ مطمئنی می‌خوای اکانتت رو کامل حذف کنی؟ برگشت‌پذیر نیست!", reply_markup=kb)

async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    if choice == "yes":
        delete_user(update.effective_user.id)
        await query.edit_message_text("اکانتت حذف شد. هر وقت خواستی دوباره /start بزن.")
    else:
        await query.edit_message_text("لغو شد.")

# ------------------------------------------------------------------
# کد هدیه مخفی
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
    await update.message.reply_text("✅ کد فعال شد!")

# ------------------------------------------------------------------
# پشتیبانی / دعوت / راهنما
# ------------------------------------------------------------------
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛠 پشتیبانی: @your_admin_username")

async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    await update.message.reply_text(f"👥 لینک دعوت:\n{link}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 راهنما:\n\n"
        "/start — ثبت‌نام (قاره → کشور)\n"
        "/attack [username] — منوی حمله (موشک/هوایی/زمینی/دریایی/جاسوسی/خرابکاری/ترور)\n"
        "/sell <resource> <amount>\n"
        "/send <username> <resource> <amount>\n"
        "/sanction <username>\n"
        "/leaderboard\n"
        "/create_alliance, /join_alliance, /leave_alliance, /announce\n\n"
        "نکته: موشک‌ها موقع شلیک مصرف میشن. بدون نفت، هواپیماها کار نمی‌کنن.\n"
        "از منو «تنگه‌ها» می‌تونی تنگه‌های استراتژیک رو تصرف و باز/بسته کنی."
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
    app.add_handler(CommandHandler("redeem", redeem_command))

    app.add_handler(CallbackQueryHandler(pick_region_callback, pattern="^pickregion:"))
    app.add_handler(CallbackQueryHandler(back_to_region_callback, pattern="^backtoregion$"))
    app.add_handler(CallbackQueryHandler(pick_country_callback, pattern="^pickcountry:"))
    app.add_handler(CallbackQueryHandler(shop_root_callback, pattern="^shopgroup:root$"))
    app.add_handler(CallbackQueryHandler(shop_group_callback, pattern="^shopgroup:"))
    app.add_handler(CallbackQueryHandler(shop_category_callback, pattern="^shopcat:"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy:"))
    app.add_handler(CallbackQueryHandler(buy_building_callback, pattern="^buybuild:"))
    app.add_handler(CallbackQueryHandler(target_pick_callback, pattern="^targetpick:"))
    app.add_handler(CallbackQueryHandler(attack_type_callback, pattern="^atktype:"))
    app.add_handler(CallbackQueryHandler(fire_missile_callback, pattern="^firemissile:"))
    app.add_handler(CallbackQueryHandler(delete_account_callback, pattern="^delacct:"))
    app.add_handler(CallbackQueryHandler(strait_info_callback, pattern="^straitinfo:"))
    app.add_handler(CallbackQueryHandler(strait_back_callback, pattern="^straitback$"))
    app.add_handler(CallbackQueryHandler(strait_capture_callback, pattern="^straitcapture:"))
    app.add_handler(CallbackQueryHandler(strait_close_callback, pattern="^straitclose:"))
    app.add_handler(CallbackQueryHandler(strait_open_callback, pattern="^straitopen:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.job_queue.run_repeating(income_job, interval=INCOME_TICK_SEC, first=INCOME_TICK_SEC)

    print("🤖 World War Bot v3 در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
