# -*- coding: utf-8 -*-
"""
=====================================================================
World War Bot v6 — بازی استراتژیک متنی برای تلگرام (نسخه‌ی کامل)
همه‌چیز توی همین یک فایله.

راه‌اندازی:
۱) BOT_TOKEN رو به عنوان متغیر محیطی ست کن.
۲) اگه Volume داری، DATABASE_PATH رو بذار روی /data/worldwar.db تا اطلاعات هیچ‌وقت پاک نشه.
۳) pip install -r requirements.txt  (باید python-telegram-bot[job-queue]==21.4 باشه)
۴) python bot.py

نکته: کشورها بر اساس اعضای واقعیِ ناتو و بریکس (تا جولای ۲۰۲۶) انتخاب شدن.
جمعیت/تجهیزات تقریبی و برای فضاسازی بازی‌ان، نه داده‌ی رسمی نظامی.
=====================================================================
"""

import os
import sqlite3
import random
import time
import json
import math
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "worldwar.db"))

ATTACK_COOLDOWN_SEC = 60 * 10
SANCTION_COOLDOWN_SEC = 60 * 30
RECON_COOLDOWN_SEC = 60 * 5
INCOME_TICK_SEC = 60
TAX_TICK_SEC = 60 * 60
MARKET_TICK_SEC = 60 * 120
NEW_PLAYER_SHIELD_SEC = 60 * 30
DAILY_BONUS_COOLDOWN_SEC = 60 * 60 * 24
TAX_RATE = 0.03
XP_PER_LEVEL = 1000
XP_PER_DOLLAR_SPENT = 0.05
DEFENSE_REPAIR_RATE = 25

GIFT_CODES = {"BOB": {"gold": 999999999}}
CUR = "$"

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def card(title, lines):
    body = "\n".join(esc(l) for l in lines)
    return f"<b>{esc(title)}</b>\n<blockquote>{body}</blockquote>"

async def send_card(message_obj, title, lines, reply_markup=None):
    await message_obj.reply_text(card(title, lines), parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def send_card_via_bot(bot, chat_id, title, lines, reply_markup=None):
    try:
        await bot.send_message(chat_id, card(title, lines), parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception:
        pass

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
    "oceania":       {"name": "اقیانوسیه",          "emoji": "🐨", "resources": {"gold": 1.5, "iron": 1.3}},
}

STRAITS = {
    "hormuz":        {"name": "تنگه هرمز",       "region": "middle_east", "affects": "oil",  "close_mult": 3.0, "true_owner_country": "iran"},
    "malacca":       {"name": "تنگه مالاکا",     "region": "east_asia",   "affects": "gold", "close_mult": 2.0, "true_owner_country": "china"},
    "gibraltar":     {"name": "تنگه جبل‌الطارق", "region": "europe",      "affects": "oil",  "close_mult": 1.7, "true_owner_country": "uk"},
    "bab_el_mandeb": {"name": "تنگه باب‌المندب", "region": "africa",      "affects": "gold", "close_mult": 1.8, "true_owner_country": "egypt"},
    "hudson":        {"name": "تنگه هادسون",     "region": "north_america","affects": "uranium", "close_mult": 1.6, "true_owner_country": "usa"},
}

# ------------------------------------------------------------------
# کشورها — فقط اعضای واقعی بریکس و ناتو (تا جولای ۲۰۲۶)، هرکدوم با تگ alliance
# ------------------------------------------------------------------
COUNTRIES = {
    # ---------------- بریکس (۱۱ عضو) ----------------
    "iran":        {"name": "ایران 🇮🇷", "alliance": "brics", "region": "middle_east", "population": "~۸۸ میلیون",
                     "start_gold": 20000, "bonus": "uranium_mult", "value": 1.5, "desc": "درآمد اورانیوم +۵۰٪",
                     "signature": ["missile_zolfaghar", "missile_fattah2", "drone_shahed"], "faction": "سپاه پاسداران",
                     "equipment_info": [("پهباد شاهد", "صدها فروند"), ("موشک بالستیک متنوع", "هزاران فروند (تخمینی)")]},
    "saudi":       {"name": "عربستان سعودی 🇸🇦", "alliance": "brics", "region": "middle_east", "population": "~۳۶ میلیون",
                     "start_gold": 35000, "bonus": "oil_mult", "value": 1.6, "desc": "درآمد نفت +۶۰٪",
                     "signature": ["defense_patriot", "fighter_typhoon"], "faction": None,
                     "equipment_info": [("پدافند پاتریوت", "چندین سامانه")]},
    "egypt":       {"name": "مصر 🇪🇬", "alliance": "brics", "region": "africa", "population": "~۱۱۰ میلیون",
                     "start_gold": 17000, "bonus": "gold_mult", "value": 1.3, "desc": "درآمد دلار +۳۰٪",
                     "signature": ["tank_abrams", "fighter_rafale"], "faction": None,
                     "equipment_info": [("تانک ابرامز", "صدها دستگاه")]},
    "ethiopia":    {"name": "اتیوپی 🇪🇹", "alliance": "brics", "region": "africa", "population": "~۱۲۸ میلیون",
                     "start_gold": 9000, "bonus": "iron_mult", "value": 1.2, "desc": "درآمد آهن +۲۰٪",
                     "signature": [], "faction": None, "equipment_info": [("تجهیزات زمینی سبک", "متوسط")]},
    "south_africa":{"name": "آفریقای جنوبی 🇿🇦", "alliance": "brics", "region": "africa", "population": "~۶۰ میلیون",
                     "start_gold": 15000, "bonus": "iron_mult", "value": 1.3, "desc": "درآمد آهن +۳۰٪",
                     "signature": [], "faction": None, "equipment_info": [("تجهیزات زرهی محلی", "متوسط")]},
    "uae":         {"name": "امارات متحده 🇦🇪", "alliance": "brics", "region": "middle_east", "population": "~۱۰ میلیون",
                     "start_gold": 32000, "bonus": "gold_mult", "value": 1.4, "desc": "درآمد دلار +۴۰٪",
                     "signature": [], "faction": None, "equipment_info": [("جنگنده اف-۱۶", "ده‌ها فروند")]},
    "russia":      {"name": "روسیه 🇷🇺", "alliance": "brics", "region": "central_asia", "population": "~۱۴۴ میلیون",
                     "start_gold": 30000, "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                     "signature": ["tank_t14", "missile_iskander"], "faction": None,
                     "equipment_info": [("تانک تی-۱۴/تی-۹۰", "هزاران دستگاه (تخمینی)")]},
    "china":       {"name": "چین 🇨🇳", "alliance": "brics", "region": "east_asia", "population": "~۱.۴۱ میلیارد",
                     "start_gold": 38000, "bonus": "gold_mult", "value": 1.4, "desc": "درآمد دلار +۴۰٪",
                     "signature": ["fighter_j20", "destroyer_type055"], "faction": None,
                     "equipment_info": [("جنگنده جی-۲۰", "چند صد فروند")]},
    "indonesia":   {"name": "اندونزی 🇮🇩", "alliance": "brics", "region": "east_asia", "population": "~۲۸۰ میلیون",
                     "start_gold": 19000, "bonus": "gold_mult", "value": 1.2, "desc": "درآمد دلار +۲۰٪",
                     "signature": [], "faction": None, "equipment_info": [("ناوچه گشتی", "متعدد")]},
    "india":       {"name": "هند 🇮🇳", "alliance": "brics", "region": "central_asia", "population": "~۱.۴۴ میلیارد",
                     "start_gold": 25000, "bonus": "land_discount", "value": 0.85, "desc": "تجهیزات زمینی ۱۵٪ ارزان‌تر",
                     "signature": ["missile_agni", "tank_arjun"], "faction": None,
                     "equipment_info": [("موشک آگنی", "چند ده فروند")]},
    "brazil":      {"name": "برزیل 🇧🇷", "alliance": "brics", "region": "south_america", "population": "~۲۱۷ میلیون",
                     "start_gold": 20000, "bonus": "gold_mult", "value": 1.3, "desc": "درآمد دلار +۳۰٪",
                     "signature": ["fighter_gripen"], "faction": None, "equipment_info": [("جنگنده گریپن", "چند ده فروند")]},

    # ---------------- ناتو (۳۲ عضو) ----------------
    "turkey":      {"name": "ترکیه 🇹🇷", "alliance": "nato", "region": "middle_east", "population": "~۸۵ میلیون",
                     "start_gold": 22000, "bonus": "drone_discount", "value": 0.7, "desc": "پهبادها ۳۰٪ ارزان‌تر",
                     "signature": ["drone_bayraktar", "tank_altay"], "faction": None,
                     "equipment_info": [("پهباد بایراکتار", "صدها فروند")]},
    "germany":     {"name": "آلمان 🇩🇪", "alliance": "nato", "region": "europe", "population": "~۸۴ میلیون",
                     "start_gold": 33000, "bonus": "iron_mult", "value": 1.4, "desc": "درآمد آهن +۴۰٪",
                     "signature": ["tank_leopard2", "sub_u212"], "faction": None,
                     "equipment_info": [("تانک لئوپارد ۲", "چند صد دستگاه")]},
    "uk":          {"name": "بریتانیا 🇬🇧", "alliance": "nato", "region": "europe", "population": "~۶۸ میلیون",
                     "start_gold": 34000, "bonus": "sea_discount", "value": 0.8, "desc": "تجهیزات دریایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_typhoon", "carrier_queenelizabeth"], "faction": None,
                     "equipment_info": [("ناو هواپیمابر کوئین الیزابت", "۲ فروند")]},
    "france":      {"name": "فرانسه 🇫🇷", "alliance": "nato", "region": "europe", "population": "~۶۸ میلیون",
                     "start_gold": 33000, "bonus": "oil_mult", "value": 1.3, "desc": "درآمد نفت +۳۰٪",
                     "signature": ["fighter_rafale", "sub_barracuda"], "faction": None,
                     "equipment_info": [("جنگنده رافائل", "ده‌ها فروند")]},
    "italy":       {"name": "ایتالیا 🇮🇹", "alliance": "nato", "region": "europe", "population": "~۵۹ میلیون",
                     "start_gold": 28000, "bonus": "sea_discount", "value": 0.85, "desc": "تجهیزات دریایی ۱۵٪ ارزان‌تر",
                     "signature": [], "faction": None, "equipment_info": [("ناوشکن مدرن", "چند فروند")]},
    "spain":       {"name": "اسپانیا 🇪🇸", "alliance": "nato", "region": "europe", "population": "~۴۸ میلیون",
                     "start_gold": 25000, "bonus": "gold_mult", "value": 1.2, "desc": "درآمد دلار +۲۰٪",
                     "signature": [], "faction": None, "equipment_info": [("جنگنده تایفون", "ده‌ها فروند")]},
    "poland":      {"name": "لهستان 🇵🇱", "alliance": "nato", "region": "europe", "population": "~۳۷ میلیون",
                     "start_gold": 22000, "bonus": "land_discount", "value": 0.85, "desc": "تجهیزات زمینی ۱۵٪ ارزان‌تر",
                     "signature": ["tank_k2"], "faction": None, "equipment_info": [("تانک کی-۲", "صدها دستگاه")]},
    "usa":         {"name": "آمریکا 🇺🇸", "alliance": "nato", "region": "north_america", "population": "~۳۴۰ میلیون",
                     "start_gold": 45000, "bonus": "air_discount", "value": 0.8, "desc": "تجهیزات هوایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_f22", "carrier_nimitz"], "faction": None,
                     "equipment_info": [("ناو هواپیمابر نیمیتز", "چند فروند")]},
    "canada":      {"name": "کانادا 🇨🇦", "alliance": "nato", "region": "north_america", "population": "~۳۹ میلیون",
                     "start_gold": 30000, "bonus": "iron_mult", "value": 1.25, "desc": "درآمد آهن +۲۵٪",
                     "signature": [], "faction": None, "equipment_info": [("جنگنده اف-۱۸", "ده‌ها فروند")]},
    "portugal":    {"name": "پرتغال 🇵🇹", "alliance": "nato", "region": "europe", "population": "~۱۰.۵ میلیون",
                     "start_gold": 22000, "bonus": "sea_discount", "value": 0.9, "desc": "تجهیزات دریایی ۱۰٪ ارزان‌تر",
                     "signature": [], "faction": None, "equipment_info": [("ناوچه گشتی", "چند فروند")]},
}

# ------------------------------------------------------------------
# بقیه‌ی اعضای ناتو (تا جولای ۲۰۲۶) — به‌صورت خودکار اضافه میشن
# ------------------------------------------------------------------
_EXTRA_NATO = [
    # key,          name fa,                region,          bonus,          value, desc,                     population
    ("albania",     "آلبانی 🇦🇱",           "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۲.۸ میلیون"),
    ("belgium",     "بلژیک 🇧🇪",            "europe",        "gold_mult",     1.15, "درآمد دلار +۱۵٪",           "~۱۲ میلیون"),
    ("bulgaria",    "بلغارستان 🇧🇬",        "europe",        "iron_mult",     1.15, "درآمد آهن +۱۵٪",            "~۶.۵ میلیون"),
    ("croatia",     "کرواسی 🇭🇷",           "europe",        "sea_discount",  0.9,  "تجهیزات دریایی ۱۰٪ ارزان‌تر", "~۳.۸ میلیون"),
    ("czechia",     "جمهوری چک 🇨🇿",        "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۱۰.۵ میلیون"),
    ("denmark",     "دانمارک 🇩🇰",          "europe",        "sea_discount",  0.85, "تجهیزات دریایی ۱۵٪ ارزان‌تر", "~۵.۹ میلیون"),
    ("estonia",     "استونی 🇪🇪",           "europe",        "land_discount", 0.85, "تجهیزات زمینی ۱۵٪ ارزان‌تر", "~۱.۴ میلیون"),
    ("finland",     "فنلاند 🇫🇮",           "europe",        "land_discount", 0.85, "تجهیزات زمینی ۱۵٪ ارزان‌تر", "~۵.۶ میلیون"),
    ("greece",      "یونان 🇬🇷",            "europe",        "sea_discount",  0.85, "تجهیزات دریایی ۱۵٪ ارزان‌تر", "~۱۰.۴ میلیون"),
    ("hungary",     "مجارستان 🇭🇺",         "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۹.۶ میلیون"),
    ("iceland",     "ایسلند 🇮🇸",           "europe",        "sea_discount",  0.85, "تجهیزات دریایی ۱۵٪ ارزان‌تر", "~۰.۴ میلیون"),
    ("latvia",      "لتونی 🇱🇻",            "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۱.۸ میلیون"),
    ("lithuania",   "لیتوانی 🇱🇹",          "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۲.۷ میلیون"),
    ("luxembourg",  "لوکزامبورگ 🇱🇺",       "europe",        "gold_mult",     1.3,  "درآمد دلار +۳۰٪",           "~۰.۷ میلیون"),
    ("montenegro",  "مونته‌نگرو 🇲🇪",       "europe",        "sea_discount",  0.9,  "تجهیزات دریایی ۱۰٪ ارزان‌تر", "~۰.۶ میلیون"),
    ("netherlands", "هلند 🇳🇱",             "europe",        "gold_mult",     1.25, "درآمد دلار +۲۵٪",           "~۱۸ میلیون"),
    ("north_macedonia","مقدونیه شمالی 🇲🇰", "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۲.۱ میلیون"),
    ("norway",      "نروژ 🇳🇴",             "europe",        "oil_mult",      1.3,  "درآمد نفت +۳۰٪",            "~۵.۵ میلیون"),
    ("romania",     "رومانی 🇷🇴",           "europe",        "iron_mult",     1.2,  "درآمد آهن +۲۰٪",            "~۱۹ میلیون"),
    ("slovakia",    "اسلواکی 🇸🇰",          "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۵.۴ میلیون"),
    ("slovenia",    "اسلوونی 🇸🇮",          "europe",        "land_discount", 0.9,  "تجهیزات زمینی ۱۰٪ ارزان‌تر", "~۲.۱ میلیون"),
    ("sweden",      "سوئد 🇸🇪",             "europe",        "air_discount",  0.85, "تجهیزات هوایی ۱۵٪ ارزان‌تر", "~۱۰.۵ میلیون"),
]

for _key, _name, _region, _bonus, _value, _desc, _pop in _EXTRA_NATO:
    COUNTRIES[_key] = {
        "name": _name, "alliance": "nato", "region": _region, "population": _pop,
        "start_gold": 20000, "bonus": _bonus, "value": _value, "desc": _desc,
        "signature": [], "faction": None,
        "equipment_info": [("تجهیزات استاندارد عضو ناتو", "متوسط تا خوب")],
    }

DEFAULT_START_GOLD = 15000

# ------------------------------------------------------------------
# فروشگاه
# ------------------------------------------------------------------
SHOP = {
    "air_defense": {"title": "پدافند هوایی 🛡", "parent": "air", "items": [
        {"id": "defense_basic",    "name": "سامانه پدافند پایه",       "price": 1500,  "power": 40,  "level": 1, "desc": "سامانه‌ی ورودی و ارزان؛ دفاع پایه در برابر تهدیدات هوایی سبک مثل پهبادهای کوچک. برای شروع کار خوبه ولی جلوی موشک‌های سنگین زیاد دووم نمیاره."},
        {"id": "defense_hawk",     "name": "سامانه پدافند هاوک",       "price": 3200,  "power": 90,  "level": 2, "desc": "سامانه‌ی میان‌برد کلاسیک؛ قدیمی ولی هنوز در برابر جنگنده‌های نسل قدیم و پهبادهای متوسط مؤثره."},
        {"id": "defense_patriot",  "name": "سامانه پدافند پاتریوت",    "price": 5000,  "power": 140, "level": 3, "desc": "یکی از پرکاربردترین سامانه‌های پدافندی جهان؛ توان رهگیری موشک‌های بالستیک کوتاه و میان‌برد رو داره."},
        {"id": "defense_s400",     "name": "سامانه پدافند اس-۴۰۰",     "price": 7000,  "power": 190, "level": 4, "desc": "برد بالا و توان رهگیری چندهدفه به‌صورت هم‌زمان."},
        {"id": "defense_ironbeam", "name": "سامانه پدافند لیزری آیرون‌بیم", "price": 8000, "power": 210, "level": 5, "desc": "فناوری لیزری نسل جدید؛ رهگیری فوق‌سریع."},
        {"id": "defense_bavar373", "name": "سامانه پدافند باور-۳۷۳",   "price": 6500,  "power": 180, "level": 4, "desc": "سامانه‌ی بومی چندلایه با پوشش گسترده."},
    ]},
    "air_drone": {"title": "پهباد 🛸", "parent": "air", "items": [
        {"id": "drone_basic",     "name": "پهباد شناسایی رعد",   "price": 300,  "power": 15,  "level": 1, "recon": True, "desc": "مناسب برای شناسایی سبک و ارزان‌قیمت؛ اولین ابزار جاسوسی هر ارتش نوپا."},
        {"id": "drone_shahed",    "name": "پهباد انتحاری شاهد",  "price": 900,  "power": 55,  "level": 2, "desc": "پهباد کامیکازه با برد بالا و هزینه‌ی پایین عملیاتی."},
        {"id": "drone_mohajer",   "name": "پهباد مهاجر-۶",       "price": 1300, "power": 75,  "level": 3, "desc": "توان حمل مهمات سبک؛ چندمنظوره."},
        {"id": "drone_bayraktar", "name": "پهباد جنگی بایراکتار","price": 1600, "power": 90,  "level": 3, "desc": "شهرت جهانی در عملیات ترکیبی شناسایی-حمله."},
        {"id": "drone_hermes",    "name": "پهباد شناسایی هرمس",  "price": 1200, "power": 70,  "level": 2, "recon": True, "desc": "تخصصی برای شناسایی دقیق و طولانی‌مدت؛ بهترین گزینه برای جاسوسی."},
        {"id": "drone_reaper",    "name": "پهباد جنگی ریپر",     "price": 2200, "power": 120, "level": 4, "desc": "پهباد سنگین با توان حمل مهمات بالا."},
    ]},
    "air_fighter": {"title": "جنگنده ✈️", "parent": "air", "items": [
        {"id": "fighter_f14",     "name": "جنگنده اف-۱۴ تامکت",   "price": 3000,  "power": 110, "level": 2, "desc": "جنگنده کلاسیک؛ با وجود قدمت هنوز قابل اتکاست."},
        {"id": "fighter_gripen",  "name": "جنگنده گریپن",         "price": 3500,  "power": 130, "level": 3, "desc": "سبک، چابک و مقرون‌به‌صرفه."},
        {"id": "fighter_f18",     "name": "جنگنده اف/ای-۱۸",      "price": 4200,  "power": 150, "level": 3, "desc": "چندمنظوره‌ی اثبات‌شده."},
        {"id": "fighter_rafale",  "name": "جنگنده رافائل",        "price": 5500,  "power": 190, "level": 4, "desc": "چابکی بالا و سامانه‌های الکترونیکی پیشرفته."},
        {"id": "fighter_typhoon", "name": "جنگنده تایفون",        "price": 6000,  "power": 210, "level": 4, "desc": "برتری هوایی با سرعت و مانورپذیری بالا."},
        {"id": "fighter_su35",    "name": "جنگنده سوخو-۳۵",       "price": 6500,  "power": 225, "level": 5, "desc": "مانورپذیری فوق‌العاده در نبرد نزدیک."},
        {"id": "fighter_f15ex",   "name": "جنگنده اف-۱۵ ایکس",    "price": 7000,  "power": 240, "level": 5, "desc": "ظرفیت بالای حمل مهمات و برد زیاد."},
        {"id": "fighter_j20",     "name": "جنگنده جی-۲۰",         "price": 7500,  "power": 250, "level": 5, "desc": "رادارگریز نسل پنجم."},
        {"id": "fighter_j35",     "name": "جنگنده جی-۳۵",         "price": 8000,  "power": 260, "level": 6, "desc": "نسل جدید رادارگریز چندمنظوره."},
        {"id": "fighter_su57",    "name": "جنگنده سوخو-۵۷",       "price": 8500,  "power": 270, "level": 6, "desc": "ترکیب رادارگریزی و مانورپذیری بالا."},
        {"id": "fighter_f35",     "name": "جنگنده اف-۳۵",         "price": 9500,  "power": 300, "level": 6, "desc": "رادارگریز چندنقشی با سامانه‌های حسگر پیشرفته."},
        {"id": "fighter_f22",     "name": "جنگنده اف-۲۲ رپتور",   "price": 12000, "power": 350, "level": 7, "desc": "برتری هوایی بلامنازع نسل پنجم."},
    ]},
    "air_bomber": {"title": "بمب‌افکن 💣", "parent": "air", "items": [
        {"id": "bomber_basic", "name": "بمب‌افکن راهبردی سیمرغ",   "price": 9000,  "power": 300, "level": 5, "desc": "بمب‌افکن راهبردی برد بلند."},
        {"id": "bomber_b2",    "name": "بمب‌افکن رادارگریز بی-۲",  "price": 16000, "power": 460, "level": 7, "desc": "رادارگریزی افسانه‌ای در حملات راهبردی."},
        {"id": "bomber_tu160", "name": "بمب‌افکن تی‌یو-۱۶۰",      "price": 14000, "power": 420, "level": 6, "desc": "سریع‌ترین بمب‌افکن ابرصوت جهان."},
    ]},
    "air_missile": {"title": "موشک ☄️ (مصرفی)", "parent": "air", "items": [
        {"id": "missile_scud",      "name": "موشک اسکاد",              "price": 1800,  "power": 90,   "level": 2, "desc": "موشک بالستیک کلاسیک کوتاه‌برد."},
        {"id": "missile_zolfaghar", "name": "موشک ذوالفقار",           "price": 2500,  "power": 120,  "level": 2, "desc": "دقت بالا در برد کوتاه تا میان‌برد."},
        {"id": "missile_hoveizeh",  "name": "موشک کروز هویزه",         "price": 3200,  "power": 150,  "level": 3, "desc": "پرواز کم‌ارتفاع برای عبور از رادار."},
        {"id": "missile_emad",      "name": "موشک عماد",               "price": 4000,  "power": 180,  "level": 3, "desc": "قابلیت هدایت دقیق در فاز پایانی."},
        {"id": "missile_kheibar",   "name": "موشک خیبرشکن",            "price": 5000,  "power": 210,  "level": 4, "desc": "سوخت جامد، آماده‌سازی سریع."},
        {"id": "missile_fattah2",   "name": "موشک فتاح-۲ (Fattah-2)",  "price": 6500,  "power": 260,  "level": 4, "desc": "نسل پیشرفته‌ی کروز سنگین با دقت و توان تخریب بالا."},
        {"id": "missile_iskander",  "name": "موشک اسکندر",             "price": 7000,  "power": 280,  "level": 5, "desc": "مانورپذیری بالا در مسیر پرواز."},
        {"id": "missile_sejjil",    "name": "موشک سجیل",               "price": 8000,  "power": 300,  "level": 5, "desc": "سوخت جامد دوربرد."},
        {"id": "missile_agni",      "name": "موشک قاره‌پیمای آگنی",    "price": 10000, "power": 340,  "level": 6, "desc": "برد قاره‌پیما."},
        {"id": "missile_shaheen",   "name": "موشک شاهین",              "price": 9000,  "power": 320,  "level": 5, "desc": "دوربرد با دقت بالا."},
        {"id": "missile_df17",      "name": "موشک دی‌اف-۱۷",           "price": 11000, "power": 360,  "level": 6, "desc": "کلاهک مانوردار ابرصوت."},
        {"id": "missile_css4",      "name": "موشک قاره‌پیمای سی‌اس‌اس-۴", "price": 15000, "power": 420,  "level": 7, "desc": "برد بین‌قاره‌ای."},
        {"id": "missile_nuclear",   "name": "☢️ موشک هسته‌ای (نمادین)", "price": 60000, "power": 1000, "level": 10, "desc": "صرفاً آیتم نمادین بازی برای بالاترین سطح قدرت، بدون جزئیات فنی واقعی."},
    ]},
    "land_infantry": {"title": "پیاده‌نظام 🪖", "parent": "land", "items": [
        {"id": "soldier",       "name": "گروهان پیاده‌نظام",  "price": 100,  "power": 5,  "level": 1, "desc": "ستون فقرات هر ارتش."},
        {"id": "special_force", "name": "نیروی ویژه",         "price": 600,  "power": 30, "level": 2, "desc": "آموزش‌دیده برای عملیات ویژه."},
        {"id": "commando",      "name": "تکاور دریایی",       "price": 1000, "power": 45, "level": 3, "desc": "توان عملیات ترکیبی زمین و دریا."},
    ]},
    "land_tank": {"title": "تانک 🚜", "parent": "land", "items": [
        {"id": "tank_basic",    "name": "تانک زره‌پوش کاویر",  "price": 1200,  "power": 60,  "level": 2, "desc": "تانک ورودی اقتصادی."},
        {"id": "tank_t90",      "name": "تانک تی-۹۰",          "price": 2600,  "power": 115, "level": 3, "desc": "تعادل خوب بین قیمت و قدرت."},
        {"id": "tank_altay",    "name": "تانک آلتای",          "price": 3000,  "power": 130, "level": 3, "desc": "زره مدرن و سامانه‌ی آتش پیشرفته."},
        {"id": "tank_arjun",    "name": "تانک آرجون",          "price": 3500,  "power": 145, "level": 4, "desc": "طراحی بومی با زره مرکب."},
        {"id": "tank_k2",       "name": "تانک کی-۲ بلک‌پنتر",  "price": 5500,  "power": 210, "level": 5, "desc": "یکی از پیشرفته‌ترین تانک‌های امروزی."},
        {"id": "tank_leopard2", "name": "تانک لئوپارد ۲",      "price": 4500,  "power": 180, "level": 5, "desc": "استاندارد طلایی تانک‌های اروپایی."},
        {"id": "tank_abrams",   "name": "تانک ام۱ ابرامز",     "price": 6000,  "power": 230, "level": 6, "desc": "زره کامپوزیت پیشرفته."},
        {"id": "tank_t14",      "name": "تانک تی-۱۴ آرماتا",   "price": 7000,  "power": 260, "level": 6, "desc": "برج بدون‌سرنشین، نسل جدید."},
    ]},
    "land_support": {"title": "توپخانه و نفربر 🎯", "parent": "land", "items": [
        {"id": "artillery",   "name": "توپخانه خودکششی رعد", "price": 2200, "power": 100, "level": 3, "desc": "پشتیبانی آتش از راه دور."},
        {"id": "apc_basic",   "name": "نفربر زرهی صاعقه",    "price": 800,  "power": 35,  "level": 1, "desc": "انتقال امن نیرو در خط مقدم."},
        {"id": "apc_guarani", "name": "نفربر زرهی گوارانی",  "price": 1400, "power": 55,  "level": 2, "desc": "چرخ‌دار و سریع."},
        {"id": "mlrs",        "name": "راکت‌انداز چندلوله",  "price": 3000, "power": 140, "level": 4, "desc": "آتش گسترده روی مساحت وسیع."},
    ]},
    "sea_patrol": {"title": "ناوچه گشتی 🚤", "parent": "sea", "items": [
        {"id": "patrol", "name": "ناوچه گشتی", "price": 1500, "power": 50, "level": 1, "desc": "گشت‌زنی و دفاع ساحلی."},
    ]},
    "sea_destroyer": {"title": "ناوشکن 🚢", "parent": "sea", "items": [
        {"id": "destroyer_basic",   "name": "ناوشکن دماوند",    "price": 5000, "power": 220, "level": 3, "desc": "ناوشکن چندمنظوره."},
        {"id": "destroyer_kongo",   "name": "ناوشکن کونگو",     "price": 6500, "power": 260, "level": 4, "desc": "سامانه‌ی ایجیس پیشرفته."},
        {"id": "destroyer_arleigh", "name": "ناوشکن آرلی برک",  "price": 7500, "power": 290, "level": 5, "desc": "ستون فقرات ناوگان‌های مدرن."},
        {"id": "destroyer_type055", "name": "ناوشکن تایپ ۰۵۵",  "price": 8000, "power": 310, "level": 5, "desc": "یکی از بزرگ‌ترین ناوشکن‌های جهان."},
    ]},
    "sea_sub": {"title": "زیردریایی 🌊", "parent": "sea", "items": [
        {"id": "sub_basic",    "name": "زیردریایی غدیر",    "price": 6000,  "power": 260, "level": 4, "desc": "زیردریایی ساحلی چابک."},
        {"id": "sub_u212",     "name": "زیردریایی یو-۲۱۲",  "price": 8500,  "power": 320, "level": 5, "desc": "سکوت صوتی بالا."},
        {"id": "sub_barracuda","name": "زیردریایی باراکودا","price": 11000, "power": 380, "level": 6, "desc": "زیردریایی حمله‌ای هسته‌ای‌بر."},
    ]},
    "sea_carrier": {"title": "ناو هواپیمابر 🛳", "parent": "sea", "items": [
        {"id": "carrier_basic",          "name": "ناو هواپیمابر سبک",           "price": 15000, "power": 500, "level": 6, "desc": "استقرار سریع نیروی هوایی در دریا."},
        {"id": "carrier_queenelizabeth", "name": "ناو هواپیمابر کوئین الیزابت", "price": 20000, "power": 600, "level": 7, "desc": "یکی از بزرگ‌ترین ناوهای هواپیمابر جهان."},
        {"id": "carrier_nimitz",         "name": "ناو هواپیمابر نیمیتز",       "price": 26000, "power": 700, "level": 8, "desc": "قدرت پروازی راهبردی."},
    ]},
}
AIR_CATS = ["air_defense", "air_drone", "air_fighter", "air_bomber", "air_missile"]
LAND_CATS = ["land_infantry", "land_tank", "land_support"]
SEA_CATS = ["sea_patrol", "sea_destroyer", "sea_sub", "sea_carrier"]

BUILDINGS = {
    "oil_rig":          {"name": "دکل نفت 🛢",                 "price": 2500, "resource": "oil",     "rate": 3},
    "iron_mine":        {"name": "معدن آهن ⛏",                 "price": 2200, "resource": "iron",    "rate": 3},
    "gold_mine":        {"name": "معدن طلا 🏆",                 "price": 3000, "resource": "gold",    "rate": 4},
    "uranium_facility": {"name": "تأسیسات استخراج اورانیوم ☢️", "price": 6000, "resource": "uranium", "rate": 1},
}
RESOURCE_NAMES = {
    "gold": f"دلار {CUR}", "oil": "نفت 🛢", "iron": "آهن ⛏",
    "uranium": "اورانیوم ☢️", "opium": "تریاک 🌿",
}
BASE_EXCHANGE_RATES = {"oil": 6, "iron": 8, "uranium": 30, "opium": 12}
current_rates = dict(BASE_EXCHANGE_RATES)

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

def missile_travel_seconds(power):
    return min(35, 4 + power // 25)

# ------------------------------------------------------------------
# دیتابیس
# ------------------------------------------------------------------
def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
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
            pending TEXT DEFAULT '{}',
            recon_targets TEXT DEFAULT '[]',
            xp INTEGER DEFAULT 0,
            casualties INTEGER DEFAULT 0,
            tax_paid INTEGER DEFAULT 0,
            defense_health INTEGER DEFAULT 100,
            shield_until INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
            battle_log TEXT DEFAULT '[]',
            alliance TEXT DEFAULT NULL,
            last_attack INTEGER DEFAULT 0,
            last_sanction INTEGER DEFAULT 0,
            last_recon INTEGER DEFAULT 0,
            sanctioned_until INTEGER DEFAULT 0,
            sabotaged_until INTEGER DEFAULT 0,
            blockaded_until INTEGER DEFAULT 0,
            redeemed_codes TEXT DEFAULT '[]',
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS straits (
            strait_key TEXT PRIMARY KEY,
            is_open INTEGER DEFAULT 1
        )
    """)
    for key in STRAITS:
        conn.execute("INSERT OR IGNORE INTO straits (strait_key, is_open) VALUES (?, 1)", (key,))
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
    start_gold = COUNTRIES.get(country_key, {}).get("start_gold", DEFAULT_START_GOLD)
    alliance = COUNTRIES.get(country_key, {}).get("alliance")  # "brics" یا "nato" — خودکار
    shield_until = int(time.time()) + NEW_PLAYER_SHIELD_SEC
    conn = db()
    conn.execute(
        "INSERT INTO users (user_id, username, country, region, gold, alliance, shield_until, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, username, country_key, region, start_gold, alliance, shield_until, datetime.now().strftime("%H:%M:%S %d-%m-%Y"))
    )
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = db()
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
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

def add_xp(user_id, amount):
    row = get_user(user_id)
    if row:
        update_field(user_id, "xp", row["xp"] + int(amount))

def get_json_field(row, field):
    default = "[]" if field in ("recon_targets", "redeemed_codes", "battle_log") else "{}"
    try:
        return json.loads(row[field] or default)
    except Exception:
        return [] if field in ("recon_targets", "redeemed_codes", "battle_log") else {}

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

def defense_power_of(army_dict, health_pct=100):
    total = 0
    for item_id, count in army_dict.items():
        if shop_category_key_of(item_id) == "air_defense":
            it = item_lookup(item_id)
            total += count * it["power"]
    return int(total * (health_pct / 100))

def owns_recon_drone(army_dict):
    for item_id, count in army_dict.items():
        it = item_lookup(item_id)
        if it and it.get("recon") and count > 0:
            return True
    return False

def user_level(row):
    return max(1, row["xp"] // XP_PER_LEVEL + 1)

def is_shielded(row):
    return row["shield_until"] > int(time.time())

def shield_remaining_minutes(row):
    return max(0, (row["shield_until"] - int(time.time())) // 60)

def add_battle_log(user_id, entry):
    row = get_user(user_id)
    if not row:
        return
    log = get_json_field(row, "battle_log")
    log.insert(0, entry)
    log = log[:10]
    set_json_field(user_id, "battle_log", log)

def region_ruler(region_key):
    rows = [r for r in all_users() if r["region"] == region_key]
    if not rows:
        return "NPC"
    best = max(rows, key=lambda r: army_power(get_json_field(r, "army")) + r["gold"])
    power = army_power(get_json_field(best, "army"))
    if power == 0 and best["gold"] <= COUNTRIES.get(best["country"], {}).get("start_gold", DEFAULT_START_GOLD):
        return "NPC"
    return COUNTRIES.get(best["country"], {}).get("name", best["username"] or "ناشناس")

def get_strait(key):
    conn = db()
    row = conn.execute("SELECT * FROM straits WHERE strait_key=?", (key,)).fetchone()
    conn.close()
    return row

def set_strait_open(key, is_open):
    conn = db()
    conn.execute("UPDATE straits SET is_open=? WHERE strait_key=?", (1 if is_open else 0, key))
    conn.commit()
    conn.close()

def strait_owner_row(key):
    owner_country = STRAITS[key]["true_owner_country"]
    for r in all_users():
        if r["country"] == owner_country:
            return r
    return None

def effective_rates():
    rates = dict(current_rates)
    for key, s in STRAITS.items():
        srow = get_strait(key)
        if srow and srow["is_open"] == 0:
            rates[s["affects"]] = rates.get(s["affects"], 1) * s["close_mult"]
    return rates

# ------------------------------------------------------------------
# کیبوردها
# ------------------------------------------------------------------
def kb(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

MAIN_MENU = kb([
    ["خزانه 🏦", "فروشگاه 🛒"],
    ["حمله ⚔️", "کارگاه 🛠"],
    ["تبادلات 📈", "بیانیه 📢"],
    ["اتحاد 🤝", "پشتیبانی 🛠"],
    ["🎁 پاداش روزانه", "📜 تاریخچه جنگ‌ها"],
    ["دعوت از دوستان 👥", "وضعیت جهانی 🌍"],
    ["منطقه من 🗺", "تنگه‌ها ⚓"],
    ["حذف اکانت ❌"],
])
SHOP_MENU = kb([
    ["تجهیزات هوایی ✈️", "تجهیزات زمینی 🪖"],
    ["تجهیزات دریایی 🚢", "منابع و ساختمان‌ها ⛏"],
    ["بازگشت به منو اصلی ⬅️"],
])
AIR_SUB_MENU = kb([["پدافند 🛡", "پهباد 🛸"], ["جنگنده ✈️", "بمب‌افکن 💣"], ["موشک ☄️"], ["بازگشت به فروشگاه ⬅️"]])
LAND_SUB_MENU = kb([["پیاده‌نظام 🪖", "تانک 🚜"], ["توپخانه و نفربر 🎯"], ["بازگشت به فروشگاه ⬅️"]])
SEA_SUB_MENU = kb([["ناوچه گشتی 🚤", "ناوشکن 🚢"], ["زیردریایی 🌊", "ناو هواپیمابر 🛳"], ["بازگشت به فروشگاه ⬅️"]])
SUBMENU_LABEL_TO_CAT = {
    "پدافند 🛡": "air_defense", "پهباد 🛸": "air_drone", "جنگنده ✈️": "air_fighter",
    "بمب‌افکن 💣": "air_bomber", "موشک ☄️": "air_missile",
    "پیاده‌نظام 🪖": "land_infantry", "تانک 🚜": "land_tank", "توپخانه و نفربر 🎯": "land_support",
    "ناوچه گشتی 🚤": "sea_patrol", "ناوشکن 🚢": "sea_destroyer", "زیردریایی 🌊": "sea_sub", "ناو هواپیمابر 🛳": "sea_carrier",
}
PARENT_TO_SUBMENU = {"air": AIR_SUB_MENU, "land": LAND_SUB_MENU, "sea": SEA_SUB_MENU}
PARENT_FA = {"air": "هوایی", "land": "زمینی", "sea": "دریایی"}

ATTACK_TYPE_MENU = kb([
    ["✈️ استفاده از تجهیزات هوایی", "🚜 استفاده از تجهیزات زمینی"],
    ["🚢 استفاده از تجهیزات دریایی"],
    ["🕵️ جاسوسی", "🧨 خرابکاری"],
    ["🌊 محاصره دریایی", "🎯 ترور"],
    ["🔄 هدف دیگه (رندوم)"],
    ["لغو حمله ❌"],
])
LOADOUT_MENU = kb([
    ["➕ افزودن تجهیزات دیگر"],
    ["🚀 شروع حمله با همین تجهیزات"],
    ["لغو حمله ❌"],
])
TRADE_MENU = kb([
    ["فروش نفت 🛢", "فروش آهن ⛏"],
    ["فروش اورانیوم ☢️", "فروش تریاک 🌿"],
    ["بازگشت به منو اصلی ⬅️"],
])
RESOURCE_LABEL_TO_KEY = {"فروش نفت 🛢": "oil", "فروش آهن ⛏": "iron", "فروش اورانیوم ☢️": "uranium", "فروش تریاک 🌿": "opium"}

def item_list_keyboard(cat_key):
    items = SHOP[cat_key]["items"]
    rows = []
    for i in range(0, len(items), 2):
        rows.append([it["name"] for it in items[i:i+2]])
    parent = SHOP[cat_key]["parent"]
    back_label = f"بازگشت به تجهیزات {PARENT_FA[parent]} ⬅️"
    rows.append([back_label])
    return kb(rows), back_label

def owned_item_keyboard(cat_key, army):
    owned_items = [it for it in SHOP[cat_key]["items"] if army.get(it["id"], 0) > 0]
    parent = SHOP[cat_key]["parent"]
    back_label = f"بازگشت به تجهیزات {PARENT_FA[parent]} ⬅️"
    if not owned_items:
        return None, back_label
    rows = [[f"{it['name']} (داری: {army.get(it['id'],0)})"] for it in owned_items]
    rows.append([back_label])
    return kb(rows), back_label

def find_item_by_button_text(cat_key, text):
    for it in SHOP[cat_key]["items"]:
        if text.startswith(it["name"]):
            return it
    return None

BUILDINGS_MENU = kb([[b["name"]] for b in BUILDINGS.values()] + [["بازگشت به فروشگاه ⬅️"]])

ALLIANCE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🌐 بریکس (BRICS)", callback_data="pickalliance:brics")],
    [InlineKeyboardButton("🛡 ناتو (NATO)", callback_data="pickalliance:nato")],
])

def countries_in_alliance_keyboard(alliance_key, taken):
    rows = []
    for key, c in COUNTRIES.items():
        if c["alliance"] != alliance_key:
            continue
        label = c["name"] + (" (گرفته‌شده)" if key in taken else "")
        rows.append([InlineKeyboardButton(label, callback_data=f"pickcountry:{key}")])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="backtoalliance")])
    return InlineKeyboardMarkup(rows)

# ------------------------------------------------------------------
# /start
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    context.user_data.clear()
    if row:
        await update.message.reply_text(f"خوش برگشتی فرمانده {COUNTRIES.get(row['country'],{}).get('name','')}!", reply_markup=MAIN_MENU)
        return
    await update.message.reply_text(
        "🌍 به «جنگ جهانی» خوش اومدی، فرمانده!\n\n"
        "این یه بازی استراتژیک زنده‌ست با کشورهای واقعی عضو بریکس و ناتو. کشورت رو اداره می‌کنی، اقتصادت رو می‌سازی، ارتش تشکیل می‌دی و با بقیه‌ی بازیکن‌ها وارد جنگ، جاسوسی و دیپلماسی میشی.\n\n"
        "اول یکی از این دو اتحادیه رو انتخاب کن:",
        reply_markup=ALLIANCE_KEYBOARD
    )

async def pick_alliance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    alliance_key = query.data.split(":")[1]
    conn = db()
    taken = {r["country"] for r in conn.execute("SELECT country FROM users").fetchall()}
    conn.close()
    alliance_name = "بریکس (BRICS)" if alliance_key == "brics" else "ناتو (NATO)"
    await query.edit_message_text(
        f"اتحادیه‌ی {alliance_name} انتخاب شد.\nحالا کشورت رو انتخاب کن (هر کشور فقط برای یک بازیکنه):",
        reply_markup=countries_in_alliance_keyboard(alliance_key, taken)
    )

async def back_to_alliance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("یکی از این دو اتحادیه رو انتخاب کن:", reply_markup=ALLIANCE_KEYBOARD)

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
        f"✅ حکومت {country['name']} به‌طور رسمی تأسیس شد!\n\n"
        f"💰 سرمایه‌ی اولیه: {country['start_gold']}{CUR}\n"
        f"🎖 بونوس اقتصادی: {country['desc']}\n"
        f"👥 جمعیت: {country['population']}"
    )
    await context.bot.send_message(user.id, "از منوی پایین شروع کن:", reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# روتر مرکزی
# ------------------------------------------------------------------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    row = get_user(user.id)
    if not row:
        await update.message.reply_text("اول دستور /start رو بزن.")
        return

    state = context.user_data.get("state")
    if state == "await_purchase_qty":
        await handle_purchase_qty(update, context, row, text); return
    if state == "await_building_qty":
        await handle_building_qty(update, context, row, text); return
    if state == "await_combat_qty":
        await handle_combat_qty(update, context, row, text); return
    if state == "await_sell_qty":
        await handle_sell_qty(update, context, row, text); return
    if state == "await_pinpoint_choice":
        await handle_pinpoint_choice(update, context, text); return
    if state == "await_loadout_choice":
        await handle_loadout_choice(update, context, text); return
    if state == "await_alliance_chat":
        await handle_alliance_chat(update, context, row, text); return

    if text == "خزانه 🏦":
        await treasury(update, context); return
    if text == "فروشگاه 🛒":
        context.user_data.clear()
        await update.message.reply_text("🛒 به فروشگاه تسلیحات و منابع خوش اومدی. یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text == "حمله ⚔️":
        await start_random_attack(update, context); return
    if text == "کارگاه 🛠":
        await workshop_menu(update, context); return
    if text == "تبادلات 📈":
        context.user_data.clear()
        await trade_menu(update, context); return
    if text == "بیانیه 📢":
        await statement(update, context); return
    if text == "اتحاد 🤝":
        await alliance_menu(update, context); return
    if text == "پشتیبانی 🛠":
        await support(update, context); return
    if text == "دعوت از دوستان 👥":
        await invite_friends(update, context); return
    if text in ("وضعیت جهانی 🌍", "نقشه جهان 🗺"):
        await world_status(update, context); return
    if text == "منطقه من 🗺":
        await my_region(update, context); return
    if text == "تنگه‌ها ⚓":
        await straits_menu(update, context); return
    if text == "حذف اکانت ❌":
        await delete_account_start(update, context); return
    if text == "بازگشت به منو اصلی ⬅️":
        context.user_data.clear()
        await update.message.reply_text("منوی اصلی:", reply_markup=MAIN_MENU); return

    if text == "💰 برداشت سود":
        await withdraw_profit(update, context); return
    if text == "🔧 تعمیر کامل پدافند":
        await repair_defense(update, context); return
    if text in RESOURCE_LABEL_TO_KEY:
        await start_sell_flow(update, context, RESOURCE_LABEL_TO_KEY[text]); return

    if text == "تجهیزات هوایی ✈️":
        await update.message.reply_text("یه زیرشاخه‌ی هوایی انتخاب کن:", reply_markup=AIR_SUB_MENU); return
    if text == "تجهیزات زمینی 🪖":
        await update.message.reply_text("یه زیرشاخه‌ی زمینی انتخاب کن:", reply_markup=LAND_SUB_MENU); return
    if text == "تجهیزات دریایی 🚢":
        await update.message.reply_text("یه زیرشاخه‌ی دریایی انتخاب کن:", reply_markup=SEA_SUB_MENU); return
    if text == "منابع و ساختمان‌ها ⛏":
        await update.message.reply_text("⛏ ساختمان‌های تولید منابع (سود جمع میشه، باید دستی از خزانه برداشتش کنی):", reply_markup=BUILDINGS_MENU); return
    if text == "بازگشت به فروشگاه ⬅️":
        context.user_data["mode"] = None
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text.startswith("بازگشت به تجهیزات"):
        for parent, menu in PARENT_TO_SUBMENU.items():
            if PARENT_FA[parent] in text:
                await update.message.reply_text("یه زیرشاخه انتخاب کن:", reply_markup=menu); return

    if text in SUBMENU_LABEL_TO_CAT:
        cat_key = SUBMENU_LABEL_TO_CAT[text]
        context.user_data["current_cat"] = cat_key
        if context.user_data.get("mode") == "attack":
            listkb, back_label = owned_item_keyboard(cat_key, get_json_field(row, "army"))
            if not listkb:
                await update.message.reply_text(f"چیزی از دسته‌ی «{SHOP[cat_key]['title']}» نداری. اول از فروشگاه بخر.", reply_markup=kb([[back_label]]))
                return
            await update.message.reply_text(f"{SHOP[cat_key]['title']}\nکدوم تجهیزات رو برای این عملیات می‌فرستی؟", reply_markup=listkb)
        else:
            listkb, _ = item_list_keyboard(cat_key)
            await update.message.reply_text(f"{SHOP[cat_key]['title']}\nروی هرکدوم بزن تا اطلاعاتش رو ببینی:", reply_markup=listkb)
        return

    cur_cat = context.user_data.get("current_cat")
    if cur_cat:
        item = find_item_by_button_text(cur_cat, text)
        if item:
            if context.user_data.get("mode") == "attack":
                await show_item_for_combat(update, context, cur_cat, item)
            else:
                await show_item_info(update, context, cur_cat, item)
            return

    b_match = next((k for k, b in BUILDINGS.items() if b["name"] == text), None)
    if b_match:
        await show_building_info(update, context, b_match)
        return

    if text in ("✈️ استفاده از تجهیزات هوایی", "🚜 استفاده از تجهیزات زمینی", "🚢 استفاده از تجهیزات دریایی"):
        parent_map = {"هوایی": "air", "زمینی": "land", "دریایی": "sea"}
        for fa, parent in parent_map.items():
            if fa in text:
                context.user_data["mode"] = "attack"
                context.user_data["current_cat"] = None
                await update.message.reply_text(f"کدوم زیرشاخه‌ی {fa} رو می‌خوای برای حمله استفاده کنی؟", reply_markup=PARENT_TO_SUBMENU[parent])
                return

    if text == "🕵️ جاسوسی":
        await do_recon(update, context); return
    if text == "🧨 خرابکاری":
        await do_sabotage(update, context); return
    if text == "🌊 محاصره دریایی":
        await do_blockade(update, context); return
    if text == "🎯 ترور":
        await do_assassinate(update, context); return
    if text == "🔄 هدف دیگه (رندوم)":
        await start_random_attack(update, context); return
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU); return

    if text == "🎁 پاداش روزانه":
        await daily_bonus(update, context); return
    if text == "📜 تاریخچه جنگ‌ها":
        await war_history(update, context); return
    if text == "💬 چت اتحاد (ارسال به هم‌پیمانان)":
        context.user_data["state"] = "await_alliance_chat"
        await update.message.reply_text("هرچی از الان بفرستی، برای همه‌ی هم‌پیمانان اتحادت ارسال میشه. برای خروج، «خروج از چت» رو بفرست.", reply_markup=kb([["خروج از چت"]]))
        return

# ------------------------------------------------------------------
# خزانه
# ------------------------------------------------------------------
async def treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    country = COUNTRIES.get(row["country"], {})
    army = get_json_field(row, "army")
    buildings = get_json_field(row, "buildings")
    pending = get_json_field(row, "pending")
    b_lines = [f"{BUILDINGS[b]['name']} × {c}" for b, c in buildings.items() if c] or ["چیزی نداری"]
    a_lines = [f"{item_lookup(i)['name']} × {c}" for i, c in army.items() if c] or ["چیزی نداری"]
    pending_lines = [f"{RESOURCE_NAMES[res]}: {amt}" for res, amt in pending.items() if amt] or ["فعلاً سودی جمع نشده"]
    lines = [
        f"🌍 کشور: {country.get('name','')} | 👥 جمعیت: {country.get('population','-')}",
        f"🗺 منطقه: {REGIONS[row['region']]['name']}",
        f"🎖 لول: {user_level(row)} | تجربه: {row['xp']}",
        "",
        f"💵 دلار نقد: {row['gold']}{CUR}",
        f"🛢 نفت: {row['oil']}   ⛏ آهن: {row['iron']}   🌿 تریاک: {row['opium']}",
        f"☢️ اورانیوم خام: {row['uranium']} | غنی ۳۰/۶۰/۹۰٪: {row['enriched_30']}/{row['enriched_60']}/{row['enriched_90']} گرم",
        "",
        "🏗 ساختمان‌ها:", *b_lines,
        "",
        "💰 سود جمع‌شده (منتظر برداشت):", *pending_lines,
        "",
        "⚔️ تجهیزات نظامی:", *a_lines,
        "",
        f"🛡 سلامت پدافند: {row['defense_health']}٪",
        f"💪 قدرت نظامی کل: {army_power(army, row['oil']>0)}" + (" ⚠️ (نفت صفره)" if row['oil']<=0 else ""),
        f"💀 تلفات کل: {row['casualties']}",
        f"🧾 مالیات پرداختی: {row['tax_paid']}{CUR}",
        f"📅 ثبت‌نام: {row['created_at']}",
    ]
    await send_card(update.message, f"🏦 خزانه‌ی {country.get('name','')}", lines, reply_markup=kb([["💰 برداشت سود"], ["بازگشت به منو اصلی ⬅️"]]))

async def withdraw_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    pending = get_json_field(row, "pending")
    if not any(pending.values()):
        await update.message.reply_text("فعلاً سودی برای برداشت نداری.", reply_markup=MAIN_MENU)
        return
    lines = []
    for res, amt in pending.items():
        if amt:
            add_resource(row["user_id"], res, amt)
            lines.append(f"+{amt} {RESOURCE_NAMES[res]}")
    set_json_field(row["user_id"], "pending", {})
    await send_card(update.message, "💰 سود برداشت شد", lines, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# کارگاه
# ------------------------------------------------------------------
async def workshop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    army = get_json_field(row, "army")
    defense_items = [f"{item_lookup(i)['name']} × {c}" for i, c in army.items() if shop_category_key_of(i) == "air_defense" and c > 0]
    if not defense_items:
        defense_items = ["هنوز هیچ سامانه‌ی پدافندی نصب نکردی."]
    health = row["defense_health"]
    lines = ["🛡 سامانه‌های پدافندی نصب‌شده:", *defense_items, "", f"❤️ سلامت فعلی پدافند: {health}٪"]
    if health < 100:
        repair_cost = (100 - health) * DEFENSE_REPAIR_RATE
        lines.append(f"🔧 هزینه‌ی تعمیر کامل: {repair_cost}{CUR}")
        kb_ = kb([["🔧 تعمیر کامل پدافند"], ["بازگشت به منو اصلی ⬅️"]])
    else:
        lines.append("همه‌چیز سالمه ✅")
        kb_ = kb([["بازگشت به منو اصلی ⬅️"]])
    await send_card(update.message, "🛠 کارگاه نظامی", lines, reply_markup=kb_)

async def repair_defense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    health = row["defense_health"]
    if health >= 100:
        await update.message.reply_text("پدافندت از قبل سالمه.", reply_markup=MAIN_MENU)
        return
    cost = (100 - health) * DEFENSE_REPAIR_RATE
    if row["gold"] < cost:
        await update.message.reply_text(f"دلار کافی نداری! هزینه: {cost}{CUR}", reply_markup=MAIN_MENU)
        return
    update_field(row["user_id"], "gold", row["gold"] - cost)
    update_field(row["user_id"], "defense_health", 100)
    await update.message.reply_text(f"✅ پدافندت کاملاً تعمیر شد! ({cost}{CUR} پرداخت شد)", reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# خرید تجهیزات
# ------------------------------------------------------------------
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

async def show_item_info(update, context, cat_key, item):
    row = get_user(update.effective_user.id)
    cat = SHOP[cat_key]
    price = effective_price(row, item, cat["parent"])
    lvl = user_level(row)
    owned = get_json_field(row, "army").get(item["id"], 0)
    lines = [f"💬 {item.get('desc','')}", "", f"💰 قیمت واحد: {price}{CUR}", f"💪 قدرت: {item['power']}", f"📦 تعداد فعلی تو: {owned}"]
    if lvl < item["level"]:
        lines.append(f"🔒 نیاز به لول {item['level']} (لول تو: {lvl})")
    lines.append("")
    lines.append("برای خرید، تعداد رو بفرست (مثلاً: 3)")
    context.user_data["state"] = "await_purchase_qty"
    context.user_data["purchase_item"] = item["id"]
    context.user_data["purchase_cat"] = cat_key
    _, back_label = item_list_keyboard(cat_key)
    await send_card(update.message, f"📦 {item['name']}", lines, reply_markup=kb([[back_label]]))

async def handle_purchase_qty(update, context, row, text):
    if text.startswith("بازگشت"):
        context.user_data["state"] = None
        cat_key = context.user_data.get("purchase_cat") or context.user_data.get("current_cat")
        if cat_key:
            listkb, _ = item_list_keyboard(cat_key)
            await update.message.reply_text(f"{SHOP[cat_key]['title']}:", reply_markup=listkb)
        else:
            await update.message.reply_text("منوی اصلی:", reply_markup=MAIN_MENU)
        return
    try:
        qty = int(text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً فقط یه عدد مثبت بفرست.")
        return
    item_id = context.user_data.get("purchase_item")
    cat_key = context.user_data.get("purchase_cat")
    item = item_lookup(item_id)
    cat = SHOP[cat_key]
    if user_level(row) < item["level"]:
        await update.message.reply_text(f"باید حداقل لول {item['level']} باشی!")
        return
    price = effective_price(row, item, cat["parent"])
    total = price * qty
    if row["gold"] < total:
        await update.message.reply_text(f"دلار کافی نداری! قیمت کل: {total}{CUR}")
        return
    update_field(row["user_id"], "gold", row["gold"] - total)
    army = get_json_field(row, "army")
    army[item_id] = army.get(item_id, 0) + qty
    set_json_field(row["user_id"], "army", army)
    add_xp(row["user_id"], total * XP_PER_DOLLAR_SPENT)
    context.user_data["state"] = None
    listkb, _ = item_list_keyboard(cat_key)
    await update.message.reply_text(f"✅ {qty} عدد {item['name']} خریداری شد! (مجموع {total}{CUR})", reply_markup=listkb)

async def show_building_info(update, context, b_key):
    b = BUILDINGS[b_key]
    row = get_user(update.effective_user.id)
    owned = get_json_field(row, "buildings").get(b_key, 0)
    lines = [f"💰 قیمت واحد: {b['price']}{CUR}", f"📈 نرخ تولید: +{b['rate']} {RESOURCE_NAMES[b['resource']]} در دقیقه به‌ازای هر واحد", f"📦 تعداد فعلی تو: {owned}", "", "برای خرید، تعداد رو بفرست:"]
    context.user_data["state"] = "await_building_qty"
    context.user_data["purchase_building"] = b_key
    await send_card(update.message, f"🏗 {b['name']}", lines, reply_markup=kb([["بازگشت به فروشگاه ⬅️"]]))

async def handle_building_qty(update, context, row, text):
    if text.startswith("بازگشت"):
        context.user_data["state"] = None
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU)
        return
    try:
        qty = int(text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً فقط یه عدد مثبت بفرست.")
        return
    b_key = context.user_data.get("purchase_building")
    b = BUILDINGS[b_key]
    total = b["price"] * qty
    if row["gold"] < total:
        await update.message.reply_text(f"دلار کافی نداری! قیمت کل: {total}{CUR}")
        return
    update_field(row["user_id"], "gold", row["gold"] - total)
    buildings = get_json_field(row, "buildings")
    buildings[b_key] = buildings.get(b_key, 0) + qty
    set_json_field(row["user_id"], "buildings", buildings)
    add_xp(row["user_id"], total * XP_PER_DOLLAR_SPENT)
    context.user_data["state"] = None
    await update.message.reply_text(f"✅ {qty} عدد {b['name']} ساخته شد!", reply_markup=BUILDINGS_MENU)

# ------------------------------------------------------------------
# درآمد + مالیات + بازار
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
        pending = get_json_field(row, "pending")
        changed = False
        for key, count in buildings.items():
            if not count:
                continue
            b = BUILDINGS[key]
            amount = b["rate"] * count * multiplier
            if country.get("bonus") == f"{b['resource']}_mult":
                amount *= country["value"]
            if amount > 0:
                pending[b["resource"]] = pending.get(b["resource"], 0) + int(amount)
                changed = True
        if changed:
            set_json_field(row["user_id"], "pending", pending)

async def tax_job(context: ContextTypes.DEFAULT_TYPE):
    for row in all_users():
        if row["gold"] <= 0:
            continue
        tax = int(row["gold"] * TAX_RATE)
        if tax > 0:
            add_resource(row["user_id"], "gold", -tax)
            update_field(row["user_id"], "tax_paid", row["tax_paid"] + tax)

MARKET_EVENTS = [
    "تنش‌های ژئوپلیتیکی در چند منطقه‌ی کلیدی باعث نوسان شدید در بازارهای جهانی انرژی و فلزات شده است. کارشناسان اقتصادی هشدار داده‌اند که این وضعیت ممکن است تا ساعات آینده ادامه یابد و بازیکنانی که در حال حاضر منابع راهبردی زیادی در اختیار دارند، بیشترین تأثیر رو از این نوسانات خواهند دید.",
    "کاهش ناگهانی عرضه در برخی از بزرگ‌ترین تولیدکنندگان جهان، موجی از نگرانی را در میان معامله‌گران ایجاد کرده و قیمت‌ها را به‌شدت تحت تأثیر قرار داده است. تحلیل‌گران بازار جهانی توصیه می‌کنند سرمایه‌گذاران تصمیمات فروش خودشون رو با احتیاط بیشتری بگیرند.",
    "یک توافق تجاری غیرمنتظره بین چند قدرت اقتصادی بزرگ باعث شده بازارها واکنش سریع نشان دهند و نرخ‌های تبادل در ساعات اخیر دستخوش تغییرات چشمگیری بشن. این توافق می‌تونه در بلندمدت هم روی اقتصاد جهانی بازی اثر بذاره.",
    "اختلال در مسیرهای حمل‌ونقل دریایی و بسته شدن موقت برخی گذرگاه‌های استراتژیک، زنجیره‌ی تأمین جهانی رو تحت فشار قرار داده و قیمت کالاهای اساسی رو به‌شدت جابه‌جا کرده. کشورهایی که وابستگی بالایی به واردات این منابع دارند بیشتر از همه آسیب می‌بینن.",
    "افزایش تقاضا برای منابع استراتژیک به‌دلیل بازسازی ارتش‌ها در چند کشور، بازار جهانی رو وارد یک دوره‌ی نوسان کوتاه‌مدت اما شدید کرده. کارشناسان میگن این روند ممکنه در چرخه‌های بعدی هم تکرار بشه.",
]

async def market_job(context: ContextTypes.DEFAULT_TYPE):
    global current_rates
    changes = []
    for res, base in BASE_EXCHANGE_RATES.items():
        pct = random.uniform(-0.35, 0.35)
        new_rate = max(1, base * (1 + pct))
        old_rate = current_rates.get(res, base)
        current_rates[res] = round(new_rate, 1)
        direction = "📈 افزایش" if new_rate > old_rate else "📉 کاهش"
        changes.append(f"{RESOURCE_NAMES[res]}: {direction} به {current_rates[res]}{CUR} (نرخ قبلی: {round(old_rate,1)}{CUR})")
    event_text = random.choice(MARKET_EVENTS)
    lines = [
        event_text, "",
        "نتیجه‌ی این تحولات روی نرخ تبادلات جهانی به شرح زیر است:", "",
        *changes, "",
        "توصیه می‌شود سرمایه‌گذاران و فرماندهان اقتصادی کشورها با احتیاط بیشتری معاملات خودشون رو در ساعات آینده انجام بدن، چون این نوسانات هر ۱۰ دقیقه یک‌بار ممکنه دوباره تکرار بشه.",
    ]
    text = card("📰 گزارش ویژه‌ی اقتصادی جهانی", lines)
    for row in all_users():
        try:
            await context.bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

# ------------------------------------------------------------------
# تبادلات
# ------------------------------------------------------------------
async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rates = effective_rates()
        lines = ["نرخ لحظه‌ای فروش منابع (هر ۱۰ دقیقه در بازار جهانی نوسان می‌کنه):", ""]
        for res, rate in rates.items():
            extra = " ⚠️ (یه تنگه بسته‌ست، قیمت بالاتره)" if rate > current_rates.get(res, rate) else ""
            lines.append(f"{RESOURCE_NAMES[res]}: {round(rate,1)}{CUR}{extra}")
        lines.append("")
        lines.append("یکی از گزینه‌های پایین رو بزن، یا برای انتقال به بازیکن دیگه: /send یوزرنیم منبع تعداد")
        await send_card(update.message, "📈 مرکز تبادلات جهانی", lines, reply_markup=TRADE_MENU)
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا توی تبادلات: {e}", reply_markup=MAIN_MENU)

async def start_sell_flow(update, context, resource_key):
    row = get_user(update.effective_user.id)
    owned = row[resource_key]
    rates = effective_rates()
    rate = rates.get(resource_key, BASE_EXCHANGE_RATES[resource_key])
    if owned <= 0:
        await update.message.reply_text(f"موجودی {RESOURCE_NAMES[resource_key]} نداری.", reply_markup=TRADE_MENU)
        return
    context.user_data["state"] = "await_sell_qty"
    context.user_data["sell_resource"] = resource_key
    lines = [f"موجودی فعلی: {owned}", f"نرخ فعلی هر واحد: {round(rate,1)}{CUR}", "", "چند واحد می‌خوای بفروشی؟ (یا بنویس «همه»)"]
    await send_card(update.message, f"💱 فروش {RESOURCE_NAMES[resource_key]}", lines, reply_markup=kb([["بازگشت به منو اصلی ⬅️"]]))

async def handle_sell_qty(update, context, row, text):
    if text.startswith("بازگشت"):
        context.user_data["state"] = None
        await update.message.reply_text("منوی اصلی:", reply_markup=MAIN_MENU)
        return
    res = context.user_data.get("sell_resource")
    owned = row[res]
    if text.strip() in ("همه", "all", "All"):
        qty = owned
    else:
        try:
            qty = int(text.strip())
        except ValueError:
            await update.message.reply_text("لطفاً یه عدد بفرست یا بنویس «همه».")
            return
    if qty <= 0 or qty > owned:
        await update.message.reply_text(f"موجودی کافی نیست. موجودی فعلی: {owned}")
        return
    rate = effective_rates().get(res, BASE_EXCHANGE_RATES[res])
    gold_gain = int(qty * rate)
    add_resource(row["user_id"], res, -qty)
    add_resource(row["user_id"], "gold", gold_gain)
    add_xp(row["user_id"], gold_gain * XP_PER_DOLLAR_SPENT)
    context.user_data["state"] = None
    await update.message.reply_text(f"✅ {qty} واحد {RESOURCE_NAMES[res]} فروخته شد. +{gold_gain}{CUR}", reply_markup=MAIN_MENU)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن."); return
    rates = effective_rates()
    if len(context.args) != 2 or context.args[0] not in rates:
        await update.message.reply_text("فرمت درست: /sell oil 10"); return
    res, amount_str = context.args
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text("تعداد باید عدد باشه."); return
    if amount <= 0 or row[res] < amount:
        await update.message.reply_text("موجودی کافی نیست."); return
    gold_gain = int(amount * rates[res])
    add_resource(user_id, res, -amount)
    add_resource(user_id, "gold", gold_gain)
    add_xp(user_id, gold_gain * XP_PER_DOLLAR_SPENT)
    await update.message.reply_text(f"✅ {amount} واحد {RESOURCE_NAMES[res]} فروخته شد. +{gold_gain}{CUR}")

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن."); return
    if len(context.args) != 3:
        await update.message.reply_text("فرمت درست: /send username gold 100"); return
    target_username, field, amount_str = context.args
    target_username = target_username.lstrip("@")
    if field not in ("gold", "oil", "iron", "uranium", "opium"):
        await update.message.reply_text("فقط gold, oil, iron, uranium, opium قابل انتقاله."); return
    try:
        amount = int(amount_str)
    except ValueError:
        await update.message.reply_text("تعداد باید عدد باشه."); return
    target = get_user_by_username(target_username)
    if not target:
        await update.message.reply_text("این بازیکن پیدا نشد."); return
    if amount <= 0 or row[field] < amount:
        await update.message.reply_text("موجودی کافی نیست."); return
    add_resource(user_id, field, -amount)
    add_resource(target["user_id"], field, amount)
    await update.message.reply_text(f"✅ {amount} واحد {RESOURCE_NAMES.get(field, 'دلار')} فرستاده شد.")
    try:
        await context.bot.send_message(target["user_id"], f"📥 {amount} واحد {RESOURCE_NAMES.get(field,'دلار')} از {row['username']} دریافت کردی.")
    except Exception:
        pass

# ------------------------------------------------------------------
# تنگه‌ها
# ------------------------------------------------------------------
async def straits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb_rows = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb_rows.append([InlineKeyboardButton(f"{s['name']} | {status}", callback_data=f"straitinfo:{key}")])
    await update.message.reply_text("⚓ تنگه‌های استراتژیک جهان — هرکدوم همیشه دست کشور واقعی صاحبشه:", reply_markup=InlineKeyboardMarkup(kb_rows))

async def strait_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    s = STRAITS[key]
    srow = get_strait(key)
    user_id = update.effective_user.id
    owner_row = strait_owner_row(key)
    owner_name = COUNTRIES[s['true_owner_country']]['name'] + ("" if owner_row else " (هنوز کسی این کشور رو انتخاب نکرده)")
    status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
    kb_rows = []
    if owner_row and owner_row["user_id"] == user_id:
        if srow["is_open"]:
            kb_rows.append([InlineKeyboardButton("🔴 بستن تنگه", callback_data=f"straitclose:{key}")])
        else:
            kb_rows.append([InlineKeyboardButton("🟢 باز کردن تنگه", callback_data=f"straitopen:{key}")])
    kb_rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data="straitback")])
    text = card(f"⚓ {s['name']}", [
        f"منطقه: {REGIONS[s['region']]['name']}",
        f"مالک ثابت: {owner_name}",
        f"وضعیت: {status}",
        f"اثر بسته شدن: قیمت {RESOURCE_NAMES[s['affects']]} تا {s['close_mult']}× بالا میره (برای همه).",
        "این تنگه قابل تصرف نیست، همیشه دست کشور واقعی صاحبشه.",
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb_rows))

async def strait_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb_rows = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb_rows.append([InlineKeyboardButton(f"{s['name']} | {status}", callback_data=f"straitinfo:{key}")])
    await query.edit_message_text("⚓ تنگه‌های استراتژیک جهان:", reply_markup=InlineKeyboardMarkup(kb_rows))

async def strait_close_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    owner_row = strait_owner_row(key)
    if not owner_row or owner_row["user_id"] != update.effective_user.id:
        await query.answer("این تنگه مال تو نیست!", show_alert=True); return
    set_strait_open(key, False)
    await query.answer("تنگه بسته شد.", show_alert=True)
    s = STRAITS[key]
    owner_country_name = COUNTRIES[s['true_owner_country']]['name']
    lines = [
        f"دولت {owner_country_name} به‌طور رسمی اعلام کرد که به دلیل ملاحظات امنیتی و راهبردی، {s['name']} را تا اطلاع ثانوی مسدود می‌کند.",
        "",
        f"این تنگه یکی از مهم‌ترین مسیرهای عبور محموله‌های {RESOURCE_NAMES[s['affects']]} در سطح جهان محسوب می‌شود و بسته شدن آن می‌تواند اثرات قابل‌توجهی بر بازارهای جهانی داشته باشد.",
        "",
        f"بر اساس گزارش‌های اولیه، انتظار می‌رود قیمت {RESOURCE_NAMES[s['affects']]} در بازارهای جهانی تا {s['close_mult']}× نسبت به نرخ عادی افزایش یابد.",
        "",
        "کارشناسان اقتصادی به تمامی فرماندهان اقتصادی کشورها توصیه می‌کنند در معاملات مرتبط با این منبع در روزهای آینده احتیاط بیشتری به خرج دهند، چرا که این وضعیت ممکن است تا زمان بازگشایی مجدد تنگه ادامه داشته باشد.",
    ]
    text = card(f"🚨 خبر فوری: {s['name']} مسدود شد", lines)
    for row in all_users():
        try:
            await context.bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
        except Exception:
            pass
    await strait_info_callback(update, context)

async def strait_open_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.split(":")[1]
    owner_row = strait_owner_row(key)
    if not owner_row or owner_row["user_id"] != update.effective_user.id:
        await query.answer("این تنگه مال تو نیست!", show_alert=True); return
    set_strait_open(key, True)
    await query.answer("تنگه باز شد.", show_alert=True)
    s = STRAITS[key]
    owner_country_name = COUNTRIES[s['true_owner_country']]['name']
    lines = [
        f"دولت {owner_country_name} اعلام کرد که پس از رفع ملاحظات امنیتی، {s['name']} مجدداً به روی کشتیرانی و تجارت جهانی باز شده است.",
        "",
        f"با این تصمیم، انتظار می‌رود قیمت {RESOURCE_NAMES[s['affects']]} به‌تدریج به نرخ عادی بازار جهانی بازگردد.",
    ]
    text = card(f"✅ خبر فوری: {s['name']} بازگشایی شد", lines)
    for row in all_users():
        try:
            await context.bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
        except Exception:
            pass
    await strait_info_callback(update, context)

# ------------------------------------------------------------------
# حمله — رندوم + چیدمان چندتجهیزاتی (loadout)
# ------------------------------------------------------------------
async def start_random_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    candidates = [r for r in all_users() if r["user_id"] != user.id and not is_shielded(r)]
    if not candidates:
        await update.message.reply_text("هیچ هدف قابل‌حمله‌ای در دسترس نیست (بقیه یا ثبت‌نام نکردن یا هنوز تحت محافظت تازه‌واردن).", reply_markup=MAIN_MENU)
        return
    target = random.choice(candidates)
    context.user_data.clear()
    context.user_data["attack_target_id"] = target["user_id"]
    context.user_data["loadout"] = []
    tc = COUNTRIES.get(target["country"], {})
    t_army = get_json_field(target, "army")
    t_power = army_power(t_army, target["oil"] > 0)
    lines = [
        f"🌍 کشور هدف: {tc.get('name','ناشناس')}",
        f"👥 جمعیت: {tc.get('population','-')}",
        f"💪 قدرت نظامی برآوردی: {t_power}",
        f"🛡 قدرت پدافند برآوردی: {defense_power_of(t_army, target['defense_health'])}",
        "",
        "برای اطلاعات دقیق‌تر، اول عملیات جاسوسی انجام بده. حالا نوع عملیات رو انتخاب کن؛ می‌تونی چند نوع تجهیزات مختلف رو هم با هم برای یک حمله‌ی ترکیبی انتخاب کنی 👇",
    ]
    await send_card(update.message, "🎯 هدف پیدا شد!", lines, reply_markup=ATTACK_TYPE_MENU)

async def show_item_for_combat(update, context, cat_key, item):
    row = get_user(update.effective_user.id)
    owned = get_json_field(row, "army").get(item["id"], 0)
    if owned <= 0:
        await update.message.reply_text(f"چیزی از «{item['name']}» نداری! اول از فروشگاه بخر.")
        return
    is_missile = cat_key == "air_missile"
    lines = [f"💬 {item.get('desc','')}", "", f"💪 قدرت واحد: {item['power']}", f"📦 تعداد موجود: {owned}"]
    if is_missile:
        lines.append(f"⏱ زمان تخمینی رسیدن: تا {missile_travel_seconds(item['power'])} ثانیه")
        lines.append("⚠️ مصرفی؛ بعد از شلیک از انبار کم میشه.")
    else:
        lines.append("ℹ️ این نیروها بعد از عملیات به کشورت برمی‌گردن، ولی جلوی پدافند قوی ممکنه تلفات بدن.")
    lines.append("")
    lines.append("چند واحد از این رو به عملیات اضافه می‌کنی؟ عدد رو بفرست:")
    context.user_data["state"] = "await_combat_qty"
    context.user_data["combat_item"] = item["id"]
    context.user_data["combat_cat"] = cat_key
    _, back_label = item_list_keyboard(cat_key)
    await send_card(update.message, f"⚔️ {item['name']}", lines, reply_markup=kb([[back_label]]))

async def handle_combat_qty(update, context, row, text):
    if text.startswith("بازگشت"):
        context.user_data["state"] = None
        cat_key = context.user_data.get("combat_cat")
        if cat_key:
            listkb, _ = item_list_keyboard(cat_key)
            await update.message.reply_text(f"{SHOP[cat_key]['title']}:", reply_markup=listkb)
        else:
            await update.message.reply_text("منوی اصلی:", reply_markup=MAIN_MENU)
        return
    try:
        qty = int(text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً فقط یه عدد مثبت بفرست.")
        return

    item_id = context.user_data.get("combat_item")
    cat_key = context.user_data.get("combat_cat")
    army = get_json_field(row, "army")
    owned = army.get(item_id, 0)
    # جمع تعداد قبلاً به چیدمان اضافه‌شده از همین آیتم رو هم لحاظ کن
    already = sum(q for iid, cid, q in context.user_data.get("loadout", []) if iid == item_id)
    if qty + already > owned:
        await update.message.reply_text(f"فقط {owned - already} تای دیگه از این داری (بخشیش از قبل تو چیدمان حمله‌ست).")
        return

    loadout = context.user_data.setdefault("loadout", [])
    loadout.append((item_id, cat_key, qty))
    context.user_data["state"] = None

    summary = "\n".join(f"• {item_lookup(iid)['name']} × {q}" for iid, cid, q in loadout)
    await send_card(update.message, "🧰 چیدمان فعلی حمله", [summary, "", "می‌خوای تجهیزات دیگه‌ای هم اضافه کنی، یا همین الان حمله رو شروع کنیم؟"], reply_markup=LOADOUT_MENU)

async def handle_loadout_choice(update, context, text):
    if text == "➕ افزودن تجهیزات دیگر":
        context.user_data["state"] = None
        await update.message.reply_text("کدوم نوع تجهیزات رو اضافه می‌کنی؟", reply_markup=ATTACK_TYPE_MENU)
        return
    if text == "🚀 شروع حمله با همین تجهیزات":
        row = get_user(update.effective_user.id)
        await proceed_to_pinpoint_or_launch(update, context, row)
        return
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU)
        return
    await update.message.reply_text("یکی از گزینه‌های کیبورد رو انتخاب کن.")

async def proceed_to_pinpoint_or_launch(update, context, row):
    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id)
    if not target:
        await update.message.reply_text("این هدف دیگه در دسترس نیست.", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return
    t_buildings = get_json_field(target, "buildings")
    owned_buildings = {k: c for k, c in t_buildings.items() if c > 0}
    if owned_buildings:
        rows = [[BUILDINGS[k]["name"]] for k in owned_buildings]
        rows.append(["🎯 حمله‌ی عمومی (بدون نقطه‌زنی)"])
        context.user_data["state"] = "await_pinpoint_choice"
        await send_card(update.message, "🎯 نقطه‌زنی", ["می‌تونی مشخصاً یکی از ساختمان‌های هدف رو نشونه بگیری. یکی رو انتخاب کن:"], reply_markup=kb(rows))
        return
    await launch_combat(update, context, row)

async def handle_pinpoint_choice(update, context, text):
    pin_target = None
    if text != "🎯 حمله‌ی عمومی (بدون نقطه‌زنی)":
        for key, b in BUILDINGS.items():
            if b["name"] == text:
                pin_target = key
                break
        if not pin_target:
            await update.message.reply_text("یکی از گزینه‌های لیست رو انتخاب کن.")
            return
    context.user_data["pinpoint_building"] = pin_target
    context.user_data["state"] = None
    row = get_user(update.effective_user.id)
    await launch_combat(update, context, row)

async def launch_combat(update, context, row):
    loadout = context.user_data.get("loadout", [])
    target_id = context.user_data.get("attack_target_id")
    pinpoint = context.user_data.get("pinpoint_building")
    if not loadout:
        await update.message.reply_text("چیزی برای حمله انتخاب نکردی.", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return

    now = int(time.time())
    if now - row["last_attack"] < ATTACK_COOLDOWN_SEC:
        wait = (ATTACK_COOLDOWN_SEC - (now - row["last_attack"])) // 60
        await update.message.reply_text(f"⏳ باید {wait} دقیقه‌ی دیگه صبر کنی.")
        return
    update_field(row["user_id"], "last_attack", now)

    army = get_json_field(row, "army")
    has_missile = any(cid == "air_missile" for _, cid, _ in loadout)
    max_travel = 0

    for item_id, cat_key, qty in loadout:
        if cat_key == "air_missile":
            army[item_id] = max(0, army.get(item_id, 0) - qty)
            if army[item_id] <= 0:
                army.pop(item_id, None)
            item = item_lookup(item_id)
            max_travel = max(max_travel, missile_travel_seconds(item["power"]))
    if has_missile:
        set_json_field(row["user_id"], "army", army)

    summary = "\n".join(f"• {item_lookup(iid)['name']} × {q}" for iid, cid, q in loadout)
    context.user_data.clear()

    if has_missile:
        await send_card(update.message, "☄️ حمله‌ی ترکیبی شلیک شد", [summary, "", f"زمان تخمینی رسیدن کل عملیات: تا {max_travel} ثانیه..."], reply_markup=MAIN_MENU)
        context.job_queue.run_once(
            deliver_combat_impact, when=max_travel,
            data={"attacker_id": row["user_id"], "target_id": target_id, "loadout": loadout, "pinpoint": pinpoint}
        )
    else:
        await update.message.reply_text("⚔️ عملیات ترکیبی آغاز شد؛ نتیجه رو براتون می‌فرستم...", reply_markup=MAIN_MENU)
        await resolve_combat(context.bot, row["user_id"], target_id, loadout, pinpoint=pinpoint)

async def deliver_combat_impact(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await resolve_combat(context.bot, data["attacker_id"], data["target_id"], data["loadout"], pinpoint=data.get("pinpoint"))

async def resolve_combat(bot, attacker_id, target_id, loadout, pinpoint=None):
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not attacker or not target:
        return
    a_army = get_json_field(attacker, "army")
    d_army = get_json_field(target, "army")
    d_oil_ok = target["oil"] > 0
    a_oil_ok = attacker["oil"] > 0

    committed_power = 0
    involves_air = False
    for item_id, cat_key, qty in loadout:
        item = item_lookup(item_id)
        parent = category_of(item_id)
        p = qty * item["power"]
        if parent == "air":
            involves_air = True
            if not a_oil_ok:
                p = 0
        committed_power += p
    a_power = committed_power + random.randint(0, 40)

    defense = defense_power_of(d_army, target["defense_health"])
    d_power = army_power(d_army, d_oil_ok) + random.randint(0, 40)
    if involves_air:
        d_power += int(defense * 0.5)

    success = a_power > d_power

    attacker_losses_summary = []
    if defense > 0 and involves_air:
        for item_id, cat_key, qty in loadout:
            parent = category_of(item_id)
            if parent != "air" or cat_key == "air_missile":
                continue
            loss_fraction = min(0.6, defense / (defense + a_power + 1))
            losses = max(1, math.ceil(qty * loss_fraction)) if qty > 0 else 0
            losses = min(losses, qty)
            if losses > 0:
                a_army[item_id] = max(0, a_army.get(item_id, 0) - losses)
                if a_army[item_id] <= 0:
                    a_army.pop(item_id, None)
                attacker_losses_summary.append(f"{item_lookup(item_id)['name']} × {losses}")
        if attacker_losses_summary:
            set_json_field(attacker_id, "army", a_army)
        new_health = max(0, target["defense_health"] - random.randint(3, 10))
        update_field(target_id, "defense_health", new_health)

    weapons_summary = "\n".join(f"• {item_lookup(iid)['name']} × {q}" for iid, cid, q in loadout)
    pin_line = ""
    if pinpoint and success:
        buildings = get_json_field(target, "buildings")
        if buildings.get(pinpoint, 0) > 0:
            buildings[pinpoint] -= 1
            set_json_field(target_id, "buildings", buildings)
            pin_line = f"🎯 نقطه‌زنی موفق: {BUILDINGS[pinpoint]['name']} هدف قرار گرفت و یک واحد از اون نابود شد!"

    lines_attacker = ["سلاح‌های استفاده‌شده در این عملیات ترکیبی:", weapons_summary, ""]
    if success:
        qty_sum = sum(q for _, _, q in loadout)
        loot = min(target["gold"], random.randint(150, 600) + qty_sum * 8)
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        add_xp(attacker_id, 90 + qty_sum * 5)
        lost = record_casualties(target_id, d_army)
        lines_attacker += [
            f"✅ عملیات کاملاً موفقیت‌آمیز بود! (قدرت حمله {a_power} در برابر قدرت دفاع {d_power})",
            f"🏆 غنیمت: {loot}{CUR}",
            f"💀 تلفات نظامی هدف: {lost}",
        ]
        if pin_line:
            lines_attacker.append(pin_line)
        if attacker_losses_summary:
            lines_attacker.append("🛡 پدافند هدف در این حمله باعث تلفات زیر به نیروهات شد:\n" + "\n".join(attacker_losses_summary))
        await send_card_via_bot(bot, attacker_id, "🎉 گزارش عملیات: موفق", lines_attacker)
        await notify_defender(bot, target_id, attacker, "حمله‌ی ترکیبی", f"{loot}{CUR} و {lost} قدرت نظامی از دست دادی!" + (f"\n{pin_line}" if pin_line else ""))
    else:
        lines_attacker.append(f"💥 عملیات ناموفق بود. (قدرت حمله {a_power} در برابر قدرت دفاع {d_power})")
        if attacker_losses_summary:
            lines_attacker.append("🛡 پدافند هدف حتی در دفاع موفق هم این تلفات رو بهت زد:\n" + "\n".join(attacker_losses_summary))
        await send_card_via_bot(bot, attacker_id, "❌ گزارش عملیات: ناموفق", lines_attacker)

    now_ts = int(time.time())
    add_battle_log(attacker_id, {"type": "حمله ترکیبی", "role": "attacker", "other": COUNTRIES.get(target["country"],{}).get("name",""), "success": success, "time": now_ts})
    add_battle_log(target_id, {"type": "حمله ترکیبی", "role": "defender", "other": COUNTRIES.get(attacker["country"],{}).get("name",""), "success": success, "time": now_ts})
    await broadcast_attack_news(bot, attacker, target, "حمله‌ی نظامی ترکیبی", success)

def record_casualties(user_id, army_dict, loss_ratio=0.15):
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

async def notify_defender(bot, target_id, attacker_row, attack_name, extra_text):
    kb_ = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ انتقام بگیر", callback_data=f"revenge:{attacker_row['user_id']}")]])
    attacker_name = COUNTRIES.get(attacker_row["country"], {}).get("name", attacker_row["username"])
    await send_card_via_bot(bot, target_id, "🚨 حمله دریافت شد!", [f"نوع عملیات: {attack_name}", f"مهاجم: {attacker_name}", extra_text], reply_markup=kb_)

WAR_NEWS_INTROS = [
    "منابع خبری بین‌المللی گزارش می‌دهند که وضعیت میدانی در ساعات اخیر به‌شدت پیچیده‌تر شده و ناظران نظامی این تحول را از نزدیک دنبال می‌کنند.",
    "به گزارش خبرگزاری‌های بین‌المللی، شرایط منطقه‌ای بار دیگر دستخوش تنش شده و کارشناسان نسبت به گسترش دامنه‌ی درگیری‌ها هشدار داده‌اند.",
    "بر اساس تحلیل ناظران نظامی مستقل، این رویداد می‌تواند تعادل قدرت در منطقه را برای مدتی تحت تأثیر قرار دهد.",
]
WAR_NEWS_CLOSINGS = [
    "کارشناسان بین‌المللی همچنان این وضعیت را زیر نظر دارند و انتظار می‌رود واکنش‌های بیشتری از سوی سایر بازیگران منطقه‌ای در ساعات آینده ثبت شود.",
    "منابع آگاه معتقدند این تحول می‌تواند پیامدهای گسترده‌تری برای توازن قدرت در سطح جهانی به همراه داشته باشد؛ اخبار تکمیلی به‌محض دریافت اعلام خواهد شد.",
    "همچنان باید دید طرفین درگیر چه واکنشی به این رویداد نشان می‌دهند؛ خبرنگاران ما این وضعیت را تا اطلاع بعدی رصد می‌کنند.",
]

async def broadcast_attack_news(bot, attacker_row, target_row, action_desc, success):
    attacker_country = COUNTRIES.get(attacker_row["country"], {}).get("name", "یک کشور ناشناس")
    target_country = COUNTRIES.get(target_row["country"], {}).get("name", "یک کشور ناشناس")
    result_txt = "با موفقیت کامل به سرانجام رسید" if success else "با شکست و دفع کامل نیروهای مهاجم مواجه شد"
    lines = [
        random.choice(WAR_NEWS_INTROS),
        "",
        f"طبق گزارش‌های تأییدنشده‌ی رسیده از منابع میدانی، نیروهای {attacker_country} در ساعات اخیر یک عملیات از نوع «{action_desc}» را علیه {target_country} آغاز کردند.",
        "",
        f"این عملیات، که بلافاصله واکنش مقامات دفاعی {target_country} را در پی داشت، در نهایت {result_txt}.",
        "",
        f"مقامات {target_country} در نخستین واکنش، این اقدام را نقض آشکار امنیت منطقه‌ای دانسته و تهدید کرده‌اند که پاسخ متقابل را در زمان و مکان مناسب اعلام خواهند کرد. در سوی مقابل، منابع نزدیک به دولت {attacker_country} این عملیات را «دفاع مشروع از منافع ملی» توصیف کرده‌اند.",
        "",
        random.choice(WAR_NEWS_CLOSINGS),
    ]
    text = card(f"📰 خبر فوری: درگیری میان {attacker_country} و {target_country}", lines)
    for row in all_users():
        try:
            await bot.send_message(row["user_id"], text, parse_mode=ParseMode.HTML)
        except Exception:
            pass

async def revenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    target = get_user(target_id)
    if not target:
        await context.bot.send_message(update.effective_user.id, "این بازیکن دیگه در دسترس نیست.", reply_markup=MAIN_MENU)
        return
    context.user_data.clear()
    context.user_data["attack_target_id"] = target_id
    context.user_data["loadout"] = []
    tc = COUNTRIES.get(target["country"], {})
    lines = [f"🌍 کشور: {tc.get('name','ناشناس')}", "نوع عملیات رو انتخاب کن 👇"]
    await send_card_via_bot(context.bot, update.effective_user.id, "🎯 هدف انتخاب شد", lines, reply_markup=ATTACK_TYPE_MENU)

# ------------------------------------------------------------------
# جاسوسی، خرابکاری، ترور
# ------------------------------------------------------------------
async def do_recon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id) if target_id else None
    if not target:
        await update.message.reply_text("اول یه هدف داشته باش (از منوی حمله).")
        return
    a_army = get_json_field(attacker, "army")
    if not owns_recon_drone(a_army):
        await update.message.reply_text("برای جاسوسی به یه پهباد شناسایی نیاز داری (رعد یا هرمس). اول از فروشگاه بخر.")
        return
    now = int(time.time())
    if now - attacker["last_recon"] < RECON_COOLDOWN_SEC:
        wait = (RECON_COOLDOWN_SEC - (now - attacker["last_recon"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    update_field(attacker_id, "last_recon", now)
    recon_list = get_json_field(attacker, "recon_targets")
    if target_id not in recon_list:
        recon_list.append(target_id)
    set_json_field(attacker_id, "recon_targets", recon_list)
    d_army = get_json_field(target, "army")
    d_buildings = get_json_field(target, "buildings")
    b_lines = [f"{BUILDINGS[k]['name']} × {c}" for k, c in d_buildings.items() if c] or ["چیزی نداره"]
    lines = [
        f"💪 قدرت نظامی: {army_power(d_army, target['oil'] > 0)}",
        f"🛡 قدرت پدافند: {defense_power_of(d_army, target['defense_health'])} (سلامت {target['defense_health']}٪)",
        f"💵 دلار نقد: {target['gold']}{CUR}",
        "🏗 ساختمان‌ها:", *b_lines,
        "", "حالا امکان ترور این هدف برات باز شده، و توی حمله می‌تونی نقطه‌زنی روی ساختمان‌هاش رو هم انتخاب کنی.",
    ]
    await send_card(update.message, "🕵️ گزارش شناسایی", lines, reply_markup=ATTACK_TYPE_MENU)

async def do_sabotage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id) if target_id else None
    if not target:
        await update.message.reply_text("اول یه هدف داشته باش (از منوی حمله).")
        return
    now = int(time.time())
    if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
        wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    a_power = army_power(get_json_field(attacker, "army"), attacker["oil"] > 0)
    d_power = army_power(get_json_field(target, "army"), target["oil"] > 0)
    update_field(attacker_id, "last_attack", now)
    success = a_power + random.randint(0, 40) > d_power
    if success:
        update_field(target_id, "sabotaged_until", now + 60 * 15)
        await update.message.reply_text("🧨 خرابکاری موفق! درآمد ساختمان‌های هدف تا ۱۵ دقیقه ۷۰٪ کاهش یافت.", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "خرابکاری زیرساخت", "زیرساخت‌های اقتصادی‌ت خراب شد!")
    else:
        await update.message.reply_text("💥 خرابکاری شکست خورد.", reply_markup=MAIN_MENU)
    add_battle_log(attacker_id, {"type": "خرابکاری", "role": "attacker", "other": COUNTRIES.get(target["country"],{}).get("name",""), "success": success, "time": now})
    add_battle_log(target_id, {"type": "خرابکاری", "role": "defender", "other": COUNTRIES.get(attacker["country"],{}).get("name",""), "success": success, "time": now})
    await broadcast_attack_news(context.bot, attacker, target, "خرابکاری زیرساخت", success)
    context.user_data.clear()

async def do_blockade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id) if target_id else None
    if not target:
        await update.message.reply_text("اول یه هدف داشته باش (از منوی حمله).")
        return
    now = int(time.time())
    if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
        wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    a_sea = sub_power(get_json_field(attacker, "army"), attacker["oil"] > 0, ["sea"])
    d_sea = sub_power(get_json_field(target, "army"), target["oil"] > 0, ["sea"])
    update_field(attacker_id, "last_attack", now)
    success = a_sea + random.randint(0, 40) > d_sea
    if success:
        update_field(target_id, "blockaded_until", now + 60 * 20)
        await update.message.reply_text("🌊 محاصره‌ی دریایی موفق بود! هدف تا ۲۰ دقیقه نمی‌تونه توی تبادلات جهانی منابعش رو بفروشه.", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "محاصره‌ی دریایی", "بنادر و مسیرهای تجاری‌ت محاصره شد؛ تا ۲۰ دقیقه نمی‌تونی بفروشی!")
    else:
        await update.message.reply_text("💥 محاصره‌ی دریایی شکست خورد؛ نیروی دریایی هدف قوی‌تر بود.", reply_markup=MAIN_MENU)
    add_battle_log(attacker_id, {"type": "محاصره دریایی", "role": "attacker", "other": COUNTRIES.get(target["country"],{}).get("name",""), "success": success, "time": now})
    add_battle_log(target_id, {"type": "محاصره دریایی", "role": "defender", "other": COUNTRIES.get(attacker["country"],{}).get("name",""), "success": success, "time": now})
    await broadcast_attack_news(context.bot, attacker, target, "محاصره‌ی دریایی", success)
    context.user_data.clear()

def leader_title_for(country_key, i):
    """عنوان کلی و ساختگی رهبر کشور (بدون اسم واقعی هیچ شخص واقعی)"""
    titles = ["رئیس‌جمهور", "نخست‌وزیر"]
    return titles[i % 2]

async def do_assassinate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id) if target_id else None
    if not target:
        await update.message.reply_text("اول یه هدف داشته باش (از منوی حمله).")
        return
    recon_list = get_json_field(attacker, "recon_targets")
    if target_id not in recon_list:
        await update.message.reply_text("اول باید این هدف رو شناسایی (جاسوسی) کنی!")
        return
    now = int(time.time())
    if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
        wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    update_field(attacker_id, "last_attack", now)
    success = random.random() < 0.55
    target_country = COUNTRIES.get(target["country"], {})
    title = leader_title_for(target["country"], target_id)
    if success:
        loot = min(target["gold"], random.randint(300, 800))
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        add_xp(attacker_id, 150)
        await update.message.reply_text(f"🎯 عملیات ترور علیه {title} {target_country.get('name','')} موفق بود! غنیمت: {loot}{CUR}", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "ترور", f"{title} کشورت هدف ترور قرار گرفت! {loot}{CUR} از دست دادی.")
    else:
        await update.message.reply_text(f"💥 عملیات ترور علیه {title} {target_country.get('name','')} شکست خورد و لو رفت.", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "تلاش ترور ناموفق", f"یه تلاش ترور ناموفق علیه {title} کشورت کشف شد!")
    add_battle_log(attacker_id, {"type": "ترور", "role": "attacker", "other": target_country.get("name",""), "success": success, "time": now})
    add_battle_log(target_id, {"type": "ترور", "role": "defender", "other": COUNTRIES.get(attacker["country"],{}).get("name",""), "success": success, "time": now})
    await broadcast_attack_news(context.bot, attacker, target, f"تلاش ترور {title}", success)
    context.user_data.clear()

# ------------------------------------------------------------------
# تحریم / لیدربورد / وضعیت جهانی / اتحاد / حذف اکانت / کد هدیه
# ------------------------------------------------------------------
async def sanction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن."); return
    now = int(time.time())
    if now - row["last_sanction"] < SANCTION_COOLDOWN_SEC:
        wait = (SANCTION_COOLDOWN_SEC - (now - row["last_sanction"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن."); return
    if not context.args:
        await update.message.reply_text("فرمت درست: /sanction username"); return
    target = get_user_by_username(context.args[0].lstrip("@"))
    if not target:
        await update.message.reply_text("این بازیکن پیدا نشد."); return
    until = now + 60 * 20
    update_field(target["user_id"], "sanctioned_until", until)
    update_field(user_id, "last_sanction", now)
    await update.message.reply_text(f"🚫 «{COUNTRIES.get(target['country'],{}).get('name','')}» به مدت ۲۰ دقیقه تحریم شد.")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = all_users()
    ranked = sorted(rows, key=lambda r: army_power(get_json_field(r, "army")) + r["gold"], reverse=True)[:10]
    lines = []
    for i, r in enumerate(ranked, 1):
        score = army_power(get_json_field(r, "army")) + r["gold"]
        name = COUNTRIES.get(r["country"], {}).get("name", r["username"])
        lines.append(f"{i}. {name} — امتیاز {score} (لول {user_level(r)})")
    if not ranked:
        lines.append("هنوز کسی ثبت‌نام نکرده.")
    await send_card(update.message, "🏆 جدول برترین فرماندهان", lines)

async def world_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = []
    for key, r in REGIONS.items():
        res_str = ", ".join(f"{res}({mult}x)" for res, mult in r["resources"].items())
        ruler = region_ruler(key)
        lines.append(f"{r['emoji']} {r['name']} — منابع: {res_str} — 👑 {ruler}")
    lines.append("")
    lines.append("⚓ تنگه‌ها:")
    for key, s in STRAITS.items():
        srow = get_strait(key)
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        lines.append(f"  {s['name']}: {status}")
    await send_card(update.message, "🗺 نقشه‌ی جهان", lines, reply_markup=MAIN_MENU)

async def my_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    r = REGIONS[row["region"]]
    ruler = region_ruler(row["region"])
    lines = [f"منابع برتر: {', '.join(f'{k}({v}x)' for k,v in r['resources'].items())}", f"حاکم فعلی: 👑 {ruler}"]
    await send_card(update.message, f"{r['emoji']} {r['name']}", lines, reply_markup=MAIN_MENU)

ALLIANCE_DISPLAY = {"brics": "بریکس (BRICS)", "nato": "ناتو (NATO)"}

async def alliance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    alliance = row["alliance"]
    if not alliance:
        await update.message.reply_text("کشورت هنوز به هیچ اتحادیه‌ای وصل نیست.", reply_markup=MAIN_MENU)
        return
    conn = db()
    members_count = conn.execute("SELECT COUNT(*) c FROM users WHERE alliance=?", (alliance,)).fetchone()["c"]
    conn.close()
    lines = [
        f"همه‌ی بازیکن‌هایی که کشور عضو {ALLIANCE_DISPLAY[alliance]} انتخاب کردن، خودکار عضو همین اتحادیه‌ن.",
        f"تعداد اعضای فعلی: {members_count} نفر",
        "",
        "از «چت اتحاد» می‌تونی مستقیم با همه‌ی هم‌پیمانانت پیام رد و بدل کنی، یا از /announce برای یه پیام رسمی استفاده کنی.",
    ]
    await send_card(update.message, f"🤝 اتحادیه‌ی {ALLIANCE_DISPLAY[alliance]}", lines, reply_markup=kb([["💬 چت اتحاد (ارسال به هم‌پیمانان)"], ["بازگشت به منو اصلی ⬅️"]]))

async def handle_alliance_chat(update, context, row, text):
    if text == "خروج از چت":
        context.user_data["state"] = None
        await update.message.reply_text("از چت اتحاد خارج شدی.", reply_markup=MAIN_MENU)
        return
    alliance = row["alliance"]
    if not alliance:
        context.user_data["state"] = None
        await update.message.reply_text("عضو هیچ اتحادیه‌ای نیستی.", reply_markup=MAIN_MENU)
        return
    conn = db()
    members = conn.execute("SELECT user_id FROM users WHERE alliance=?", (alliance,)).fetchall()
    conn.close()
    country_name = COUNTRIES.get(row["country"], {}).get("name", row["username"])
    sent = 0
    for m in members:
        if m["user_id"] == row["user_id"]:
            continue
        try:
            await context.bot.send_message(m["user_id"], f"💬 [{ALLIANCE_DISPLAY[alliance]}] {country_name}:\n{text}")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ به {sent} هم‌پیمان ارسال شد. (بازم می‌تونی بنویسی، یا «خروج از چت» بزنی)")

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not row["alliance"]:
        await update.message.reply_text("عضو هیچ اتحادیه‌ای نیستی."); return
    if not context.args:
        await update.message.reply_text("/announce <متن>"); return
    text = " ".join(context.args)
    conn = db()
    members = conn.execute("SELECT user_id FROM users WHERE alliance=?", (row["alliance"],)).fetchall()
    conn.close()
    sent = 0
    for m in members:
        if m["user_id"] == update.effective_user.id:
            continue
        try:
            await context.bot.send_message(m["user_id"], f"📢 بیانیه‌ی رسمی از {row['username']} ({ALLIANCE_DISPLAY[row['alliance']]}):\n{text}")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"بیانیه برای {sent} عضو ارسال شد.")

async def statement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 برای بیانیه: /announce <متن پیام>", reply_markup=MAIN_MENU)

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    now = int(time.time())
    if now - row["last_daily"] < DAILY_BONUS_COOLDOWN_SEC:
        remaining = DAILY_BONUS_COOLDOWN_SEC - (now - row["last_daily"])
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        await update.message.reply_text(f"⏳ پاداش امروز رو قبلاً گرفتی. {hrs} ساعت و {mins} دقیقه‌ی دیگه دوباره در دسترسه.", reply_markup=MAIN_MENU)
        return
    gold_reward = random.randint(500, 2000)
    resource_key = random.choice(["oil", "iron", "uranium"])
    resource_reward = random.randint(10, 40)
    add_resource(row["user_id"], "gold", gold_reward)
    add_resource(row["user_id"], resource_key, resource_reward)
    add_xp(row["user_id"], 50)
    update_field(row["user_id"], "last_daily", now)
    await send_card(update.message, "🎁 پاداش روزانه دریافت شد", [
        f"+{gold_reward}{CUR}",
        f"+{resource_reward} {RESOURCE_NAMES[resource_key]}",
        "+۵۰ تجربه",
        "", "فردا دوباره سر بزن!",
    ], reply_markup=MAIN_MENU)

async def war_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    log = get_json_field(row, "battle_log")
    if not log:
        await update.message.reply_text("هنوز هیچ درگیری‌ای نداشتی.", reply_markup=MAIN_MENU)
        return
    lines = []
    for entry in log:
        role_fa = "حمله به" if entry["role"] == "attacker" else "حمله از طرف"
        result_fa = "✅ موفق" if entry["success"] else "❌ ناموفق"
        when = datetime.fromtimestamp(entry["time"]).strftime("%H:%M %d-%m")
        lines.append(f"{when} | {entry['type']} | {role_fa} {entry['other']} | {result_fa}")
    await send_card(update.message, "📜 تاریخچه‌ی جنگ‌های اخیر", lines, reply_markup=MAIN_MENU)

async def delete_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb_ = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف کن", callback_data="delacct:yes")],
        [InlineKeyboardButton("❌ نه، بیخیال", callback_data="delacct:no")],
    ])
    await update.message.reply_text("⚠️ مطمئنی می‌خوای اکانتت رو کامل حذف کنی؟ برگشت‌پذیر نیست!", reply_markup=kb_)

async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":")[1]
    if choice == "yes":
        delete_user(update.effective_user.id)
        await query.edit_message_text("اکانتت حذف شد. هر وقت خواستی دوباره /start بزن.")
    else:
        await query.edit_message_text("لغو شد.")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن."); return
    if not context.args:
        return
    code = context.args[0].strip()
    redeemed = get_json_field(row, "redeemed_codes")
    if code not in GIFT_CODES:
        await update.message.reply_text("کد نامعتبره."); return
    if code in redeemed:
        await update.message.reply_text("این کد رو قبلاً استفاده کردی."); return
    reward = GIFT_CODES[code]
    for field, amount in reward.items():
        add_resource(user_id, field, amount)
    redeemed.append(code)
    set_json_field(user_id, "redeemed_codes", redeemed)
    await update.message.reply_text("✅ کد فعال شد!")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛠 پشتیبانی: @your_admin_username", reply_markup=MAIN_MENU)

async def invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    await update.message.reply_text(f"👥 لینک دعوت:\n{link}", reply_markup=MAIN_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 راهنمای کامل بازی:\n\n"
        "/start — ثبت‌نام (قاره → کشور، بیش از ۵۰ کشور واقعی از ناتو و بریکس)\n"
        "«حمله ⚔️» یه هدف رندوم پیدا می‌کنه. می‌تونی چند نوع تجهیزات مختلف رو با هم به یک حمله‌ی ترکیبی اضافه کنی، نقطه‌زنی روی یه ساختمون خاص انجام بدی، و همه‌چیز رو خودت انتخاب کنی.\n"
        "جاسوسی فقط با پهباد شناسایی ممکنه. پدافند هدف هم بهت تلفات می‌زنه و در طول حمله فرسوده میشه؛ از «کارگاه 🛠» تعمیرش کن.\n"
        "درآمد ساختمون‌ها جمع میشه، باید دستی «برداشت سود» بزنی.\n"
        "قیمت‌های بازار هر ۱۰ دقیقه نوسان می‌کنه و خبرش برای همه میره.\n"
        "تنگه‌ها دست کشور واقعی صاحبشونه؛ فقط باز/بسته میشن.\n\n"
        "/sell, /send, /sanction, /leaderboard, /create_alliance, /join_alliance, /leave_alliance, /announce"
    )

# ------------------------------------------------------------------
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sell", sell_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("sanction", sanction_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("announce", announce_command))
    app.add_handler(CommandHandler("redeem", redeem_command))

    app.add_handler(CallbackQueryHandler(pick_alliance_callback, pattern="^pickalliance:"))
    app.add_handler(CallbackQueryHandler(back_to_alliance_callback, pattern="^backtoalliance$"))
    app.add_handler(CallbackQueryHandler(pick_country_callback, pattern="^pickcountry:"))
    app.add_handler(CallbackQueryHandler(delete_account_callback, pattern="^delacct:"))
    app.add_handler(CallbackQueryHandler(strait_info_callback, pattern="^straitinfo:"))
    app.add_handler(CallbackQueryHandler(strait_back_callback, pattern="^straitback$"))
    app.add_handler(CallbackQueryHandler(strait_close_callback, pattern="^straitclose:"))
    app.add_handler(CallbackQueryHandler(strait_open_callback, pattern="^straitopen:"))
    app.add_handler(CallbackQueryHandler(revenge_callback, pattern="^revenge:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.job_queue.run_repeating(income_job, interval=INCOME_TICK_SEC, first=INCOME_TICK_SEC)
    app.job_queue.run_repeating(tax_job, interval=TAX_TICK_SEC, first=TAX_TICK_SEC)
    app.job_queue.run_repeating(market_job, interval=MARKET_TICK_SEC, first=MARKET_TICK_SEC)

    print("🤖 World War Bot v6 در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()