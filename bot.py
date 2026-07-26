# -*- coding: utf-8 -*-
"""
=====================================================================
World War Bot v5 — بازی استراتژیک متنی برای تلگرام
همه‌چیز توی همین یک فایله.

راه‌اندازی:
۱) BOT_TOKEN رو به عنوان متغیر محیطی ست کن.
۲) DATABASE_PATH رو هم بذار روی /data/worldwar.db اگه Volume داری (وگرنه کنار خود فایل ساخته میشه).
۳) pip install -r requirements.txt  (باید python-telegram-bot[job-queue]==21.4 باشه)
۴) python bot.py

نکات:
- اعداد جمعیت/تجهیزات کشورها تقریبی و برای فضاسازی بازی هستن، نه داده‌ی رسمی.
- هر آیتم یه فیلد image_url داره (فعلاً خالی) — اگه بعداً عکس واقعی/مجاز پیدا کردی،
  کافیه لینکش رو توی همون فیلد بذاری تا با عکس ارسال بشه.
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
TAX_RATE = 0.03
XP_PER_LEVEL = 1000
XP_PER_DOLLAR_SPENT = 0.05

GIFT_CODES = {"BOB": {"gold": 999999999}}
CUR = "$"

# ------------------------------------------------------------------
# ابزار فرمت شیک (blockquote)
# ------------------------------------------------------------------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def card(title, lines):
    body = "\n".join(lines)
    return f"<b>{esc(title)}</b>\n<blockquote>{body}</blockquote>"

async def send_card(message_obj, title, lines, reply_markup=None):
    text = card(title, lines)
    await message_obj.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

async def send_card_via_bot(bot, chat_id, title, lines, reply_markup=None):
    text = card(title, lines)
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

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

STRAITS = {
    "hormuz":        {"name": "تنگه هرمز",       "region": "middle_east", "affects": "oil",  "close_mult": 3.0, "true_owner_country": "iran"},
    "malacca":       {"name": "تنگه مالاکا",     "region": "east_asia",   "affects": "gold", "close_mult": 2.0, "true_owner_country": "china"},
    "gibraltar":     {"name": "تنگه جبل‌الطارق", "region": "europe",      "affects": "oil",  "close_mult": 1.7, "true_owner_country": "uk"},
    "bab_el_mandeb": {"name": "تنگه باب‌المندب", "region": "africa",      "affects": "gold", "close_mult": 1.8, "true_owner_country": "egypt"},
}

# ------------------------------------------------------------------
# کشورها
# ------------------------------------------------------------------
COUNTRIES = {
    "iran":        {"name": "ایران 🇮🇷", "region": "middle_east", "population": "~۸۸ میلیون",
                     "start_gold": 8000, "bonus": "uranium_mult", "value": 1.5, "desc": "درآمد اورانیوم +۵۰٪",
                     "signature": ["missile_zolfaghar", "missile_fattah2", "drone_shahed"], "faction": "سپاه پاسداران",
                     "equipment_info": [("پهباد شاهد", "صدها فروند"), ("موشک بالستیک متنوع", "هزاران فروند (تخمینی)"), ("جنگنده قدیمی اف-۱۴", "چند ده فروند")]},
    "saudi":       {"name": "عربستان سعودی 🇸🇦", "region": "middle_east", "population": "~۳۶ میلیون",
                     "start_gold": 15000, "bonus": "oil_mult", "value": 1.6, "desc": "درآمد نفت +۶۰٪",
                     "signature": ["defense_patriot", "fighter_typhoon"], "faction": None,
                     "equipment_info": [("پدافند پاتریوت", "چندین سامانه"), ("جنگنده تایفون/اف-۱۵", "ده‌ها فروند")]},
    "israel":      {"name": "اسرائیل 🇮🇱", "region": "middle_east", "population": "~۹.۵ میلیون",
                     "start_gold": 12000, "bonus": "air_discount", "value": 0.75, "desc": "تجهیزات هوایی ۲۵٪ ارزان‌تر",
                     "signature": ["defense_ironbeam", "drone_hermes"], "faction": "موساد",
                     "equipment_info": [("پدافند آیرون‌دام/آیرون‌بیم", "چندین سامانه"), ("جنگنده اف-۳۵", "چند ده فروند")]},
    "turkey":      {"name": "ترکیه 🇹🇷", "region": "middle_east", "population": "~۸۵ میلیون",
                     "start_gold": 9000, "bonus": "drone_discount", "value": 0.7, "desc": "پهبادها ۳۰٪ ارزان‌تر",
                     "signature": ["drone_bayraktar", "tank_altay"], "faction": None,
                     "equipment_info": [("پهباد بایراکتار", "صدها فروند"), ("تانک آلتای/لئوپارد", "صدها دستگاه")]},
    "egypt":       {"name": "مصر 🇪🇬", "region": "africa", "population": "~۱۱۰ میلیون",
                     "start_gold": 7000, "bonus": "gold_mult", "value": 1.3, "desc": "درآمد دلار +۳۰٪",
                     "signature": ["tank_abrams", "fighter_rafale"], "faction": None,
                     "equipment_info": [("تانک ابرامز", "صدها دستگاه"), ("جنگنده رافائل/اف-۱۶", "ده‌ها فروند")]},
    "germany":     {"name": "آلمان 🇩🇪", "region": "europe", "population": "~۸۴ میلیون",
                     "start_gold": 14000, "bonus": "iron_mult", "value": 1.4, "desc": "درآمد آهن +۴۰٪",
                     "signature": ["tank_leopard2", "sub_u212"], "faction": None,
                     "equipment_info": [("تانک لئوپارد ۲", "چند صد دستگاه"), ("زیردریایی یو-۲۱۲", "چند فروند")]},
    "uk":          {"name": "بریتانیا 🇬🇧", "region": "europe", "population": "~۶۸ میلیون",
                     "start_gold": 15000, "bonus": "sea_discount", "value": 0.8, "desc": "تجهیزات دریایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_typhoon", "carrier_queenelizabeth"], "faction": None,
                     "equipment_info": [("ناو هواپیمابر کوئین الیزابت", "۲ فروند"), ("جنگنده تایفون", "ده‌ها فروند")]},
    "france":      {"name": "فرانسه 🇫🇷", "region": "europe", "population": "~۶۸ میلیون",
                     "start_gold": 14000, "bonus": "oil_mult", "value": 1.3, "desc": "درآمد نفت +۳۰٪",
                     "signature": ["fighter_rafale", "sub_barracuda"], "faction": None,
                     "equipment_info": [("جنگنده رافائل", "ده‌ها فروند"), ("زیردریایی باراکودا", "چند فروند")]},
    "russia":      {"name": "روسیه 🇷🇺", "region": "central_asia", "population": "~۱۴۴ میلیون",
                     "start_gold": 13000, "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                     "signature": ["tank_t14", "missile_iskander"], "faction": None,
                     "equipment_info": [("تانک تی-۱۴/تی-۹۰", "هزاران دستگاه (تخمینی)"), ("موشک اسکندر", "صدها فروند")]},
    "china":       {"name": "چین 🇨🇳", "region": "east_asia", "population": "~۱.۴۱ میلیارد",
                     "start_gold": 16000, "bonus": "gold_mult", "value": 1.4, "desc": "درآمد دلار +۴۰٪",
                     "signature": ["fighter_j20", "destroyer_type055"], "faction": None,
                     "equipment_info": [("جنگنده جی-۲۰", "چند صد فروند"), ("ناوشکن تایپ ۰۵۵", "چند فروند")]},
    "japan":       {"name": "ژاپن 🇯🇵", "region": "east_asia", "population": "~۱۲۳ میلیون",
                     "start_gold": 15000, "bonus": "sea_discount", "value": 0.75, "desc": "تجهیزات دریایی ۲۵٪ ارزان‌تر",
                     "signature": ["destroyer_kongo", "fighter_f35"], "faction": None,
                     "equipment_info": [("ناوشکن کونگو", "چند فروند"), ("جنگنده اف-۳۵", "ده‌ها فروند")]},
    "south_korea": {"name": "کره جنوبی 🇰🇷", "region": "east_asia", "population": "~۵۲ میلیون",
                     "start_gold": 12000, "bonus": "land_discount", "value": 0.8, "desc": "تجهیزات زمینی ۲۰٪ ارزان‌تر",
                     "signature": ["tank_k2"], "faction": None,
                     "equipment_info": [("تانک کی-۲", "صدها دستگاه")]},
    "india":       {"name": "هند 🇮🇳", "region": "central_asia", "population": "~۱.۴۴ میلیارد",
                     "start_gold": 10000, "bonus": "land_discount", "value": 0.85, "desc": "تجهیزات زمینی ۱۵٪ ارزان‌تر",
                     "signature": ["missile_agni", "tank_arjun"], "faction": None,
                     "equipment_info": [("موشک آگنی", "چند ده فروند"), ("تانک آرجون", "صدها دستگاه")]},
    "pakistan":    {"name": "پاکستان 🇵🇰", "region": "central_asia", "population": "~۲۴۰ میلیون",
                     "start_gold": 7000, "bonus": "uranium_mult", "value": 1.3, "desc": "درآمد اورانیوم +۳۰٪",
                     "signature": ["missile_shaheen"], "faction": None,
                     "equipment_info": [("موشک شاهین", "چند ده فروند")]},
    "usa":         {"name": "آمریکا 🇺🇸", "region": "north_america", "population": "~۳۴۰ میلیون",
                     "start_gold": 20000, "bonus": "air_discount", "value": 0.8, "desc": "تجهیزات هوایی ۲۰٪ ارزان‌تر",
                     "signature": ["fighter_f22", "carrier_nimitz"], "faction": None,
                     "equipment_info": [("ناو هواپیمابر نیمیتز", "چند فروند"), ("جنگنده اف-۲۲/اف-۳۵", "چند صد فروند")]},
    "brazil":      {"name": "برزیل 🇧🇷", "region": "south_america", "population": "~۲۱۷ میلیون",
                     "start_gold": 9000, "bonus": "gold_mult", "value": 1.3, "desc": "درآمد دلار +۳۰٪",
                     "signature": ["fighter_gripen"], "faction": None,
                     "equipment_info": [("جنگنده گریپن", "چند ده فروند")]},
}
DEFAULT_START_GOLD = 8000

# ------------------------------------------------------------------
# فروشگاه (image_url فعلاً None — بعداً قابل‌پر‌کردنه)
# ------------------------------------------------------------------
SHOP = {
    "air_defense": {"title": "پدافند هوایی 🛡", "parent": "air", "items": [
        {"id": "defense_basic",    "name": "سامانه پدافند پایه",       "price": 1500,  "power": 40,  "level": 1, "image_url": None, "desc": "سامانه‌ی ورودی، دفاع پایه در برابر تهدیدات هوایی سبک."},
        {"id": "defense_hawk",     "name": "سامانه پدافند هاوک",       "price": 3200,  "power": 90,  "level": 2, "image_url": None, "desc": "سامانه‌ی میان‌برد کلاسیک ولی هنوز مؤثر."},
        {"id": "defense_patriot",  "name": "سامانه پدافند پاتریوت",    "price": 5000,  "power": 140, "level": 3, "image_url": None, "desc": "یکی از پرکاربردترین سامانه‌های پدافندی جهان."},
        {"id": "defense_s400",     "name": "سامانه پدافند اس-۴۰۰",     "price": 7000,  "power": 190, "level": 4, "image_url": None, "desc": "برد بالا، توان رهگیری چندهدفه."},
        {"id": "defense_ironbeam", "name": "سامانه پدافند لیزری آیرون‌بیم", "price": 8000, "power": 210, "level": 5, "image_url": None, "desc": "فناوری لیزری نسل جدید برای رهگیری دقیق."},
        {"id": "defense_bavar373", "name": "سامانه پدافند باور-۳۷۳",   "price": 6500,  "power": 180, "level": 4, "image_url": None, "desc": "سامانه‌ی بومی چندلایه با پوشش گسترده."},
    ]},
    "air_drone": {"title": "پهباد 🛸", "parent": "air", "items": [
        {"id": "drone_basic",     "name": "پهباد شناسایی رعد",   "price": 300,  "power": 15,  "level": 1, "recon": True, "image_url": None, "desc": "مناسب برای شناسایی سبک و ارزان‌قیمت."},
        {"id": "drone_shahed",    "name": "پهباد انتحاری شاهد",  "price": 900,  "power": 55,  "level": 2, "image_url": None, "desc": "پهباد کامیکازه با برد بالا و هزینه‌ی پایین عملیاتی."},
        {"id": "drone_mohajer",   "name": "پهباد مهاجر-۶",       "price": 1300, "power": 75,  "level": 3, "image_url": None, "desc": "توان حمل مهمات سبک، چندمنظوره."},
        {"id": "drone_bayraktar", "name": "پهباد جنگی بایراکتار","price": 1600, "power": 90,  "level": 3, "image_url": None, "desc": "شهرت جهانی در عملیات ترکیبی شناسایی-حمله."},
        {"id": "drone_hermes",    "name": "پهباد شناسایی هرمس",  "price": 1200, "power": 70,  "level": 2, "recon": True, "image_url": None, "desc": "تخصصی برای شناسایی دقیق و طولانی‌مدت."},
        {"id": "drone_reaper",    "name": "پهباد جنگی ریپر",     "price": 2200, "power": 120, "level": 4, "image_url": None, "desc": "پهباد سنگین با توان حمل مهمات بالا."},
    ]},
    "air_fighter": {"title": "جنگنده ✈️", "parent": "air", "items": [
        {"id": "fighter_f14",     "name": "جنگنده اف-۱۴ تامکت",   "price": 3000,  "power": 110, "level": 2, "image_url": None, "desc": "جنگنده کلاسیک ولی همچنان قابل اتکا."},
        {"id": "fighter_gripen",  "name": "جنگنده گریپن",         "price": 3500,  "power": 130, "level": 3, "image_url": None, "desc": "سبک، چابک و مقرون‌به‌صرفه."},
        {"id": "fighter_f18",     "name": "جنگنده اف/ای-۱۸",      "price": 4200,  "power": 150, "level": 3, "image_url": None, "desc": "چندمنظوره‌ی اثبات‌شده در عملیات‌های گوناگون."},
        {"id": "fighter_rafale",  "name": "جنگنده رافائل",        "price": 5500,  "power": 190, "level": 4, "image_url": None, "desc": "چابکی بالا و سامانه‌های الکترونیکی پیشرفته."},
        {"id": "fighter_typhoon", "name": "جنگنده تایفون",        "price": 6000,  "power": 210, "level": 4, "image_url": None, "desc": "برتری هوایی با سرعت و مانورپذیری بالا."},
        {"id": "fighter_su35",    "name": "جنگنده سوخو-۳۵",       "price": 6500,  "power": 225, "level": 5, "image_url": None, "desc": "مانورپذیری فوق‌العاده در نبرد نزدیک."},
        {"id": "fighter_f15ex",   "name": "جنگنده اف-۱۵ ایکس",    "price": 7000,  "power": 240, "level": 5, "image_url": None, "desc": "ظرفیت بالای حمل مهمات و برد زیاد."},
        {"id": "fighter_j20",     "name": "جنگنده جی-۲۰",         "price": 7500,  "power": 250, "level": 5, "image_url": None, "desc": "رادارگریز نسل پنجم."},
        {"id": "fighter_j35",     "name": "جنگنده جی-۳۵",         "price": 8000,  "power": 260, "level": 6, "image_url": None, "desc": "نسل جدید رادارگریز چندمنظوره."},
        {"id": "fighter_su57",    "name": "جنگنده سوخو-۵۷",       "price": 8500,  "power": 270, "level": 6, "image_url": None, "desc": "ترکیب رادارگریزی و مانورپذیری بالا."},
        {"id": "fighter_f35",     "name": "جنگنده اف-۳۵",         "price": 9500,  "power": 300, "level": 6, "image_url": None, "desc": "رادارگریز چندنقشی با سامانه‌های حسگر پیشرفته."},
        {"id": "fighter_f22",     "name": "جنگنده اف-۲۲ رپتور",   "price": 12000, "power": 350, "level": 7, "image_url": None, "desc": "برتری هوایی بلامنازع نسل پنجم."},
    ]},
    "air_bomber": {"title": "بمب‌افکن 💣", "parent": "air", "items": [
        {"id": "bomber_basic", "name": "بمب‌افکن راهبردی سیمرغ",   "price": 9000,  "power": 300, "level": 5, "image_url": None, "desc": "بمب‌افکن راهبردی برد بلند."},
        {"id": "bomber_b2",    "name": "بمب‌افکن رادارگریز بی-۲",  "price": 16000, "power": 460, "level": 7, "image_url": None, "desc": "رادارگریزی افسانه‌ای در حملات راهبردی."},
        {"id": "bomber_tu160", "name": "بمب‌افکن تی‌یو-۱۶۰",      "price": 14000, "power": 420, "level": 6, "image_url": None, "desc": "سریع‌ترین بمب‌افکن ابرصوت جهان."},
    ]},
    "air_missile": {"title": "موشک ☄️ (مصرفی)", "parent": "air", "items": [
        {"id": "missile_scud",      "name": "موشک اسکاد",              "price": 1800,  "power": 90,   "level": 2, "image_url": None, "desc": "موشک بالستیک کلاسیک کوتاه‌برد."},
        {"id": "missile_zolfaghar", "name": "موشک ذوالفقار",           "price": 2500,  "power": 120,  "level": 2, "image_url": None, "desc": "دقت بالا در برد کوتاه تا میان‌برد."},
        {"id": "missile_hoveizeh",  "name": "موشک کروز هویزه",         "price": 3200,  "power": 150,  "level": 3, "image_url": None, "desc": "پرواز کم‌ارتفاع برای عبور از رادار."},
        {"id": "missile_emad",      "name": "موشک عماد",               "price": 4000,  "power": 180,  "level": 3, "image_url": None, "desc": "قابلیت هدایت دقیق در فاز پایانی."},
        {"id": "missile_kheibar",   "name": "موشک خیبرشکن",            "price": 5000,  "power": 210,  "level": 4, "image_url": None, "desc": "سوخت جامد، آماده‌سازی سریع."},
        {"id": "missile_fattah2",   "name": "موشک فتاح-۲ (Fattah-2)",  "price": 6500,  "power": 260,  "level": 4, "image_url": None, "desc": "نسل پیشرفته‌ی کروز سنگین با دقت و توان تخریب بالا؛ مناسب اهداف ساختاری و استراتژیک."},
        {"id": "missile_iskander",  "name": "موشک اسکندر",             "price": 7000,  "power": 280,  "level": 5, "image_url": None, "desc": "مانورپذیری بالا در مسیر پرواز."},
        {"id": "missile_sejjil",    "name": "موشک سجیل",               "price": 8000,  "power": 300,  "level": 5, "image_url": None, "desc": "سوخت جامد دوربرد."},
        {"id": "missile_agni",      "name": "موشک قاره‌پیمای آگنی",    "price": 10000, "power": 340,  "level": 6, "image_url": None, "desc": "برد قاره‌پیما."},
        {"id": "missile_shaheen",   "name": "موشک شاهین",              "price": 9000,  "power": 320,  "level": 5, "image_url": None, "desc": "دوربرد با دقت بالا."},
        {"id": "missile_df17",      "name": "موشک دی‌اف-۱۷",           "price": 11000, "power": 360,  "level": 6, "image_url": None, "desc": "کلاهک مانوردار ابرصوت."},
        {"id": "missile_css4",      "name": "موشک قاره‌پیمای سی‌اس‌اس-۴", "price": 15000, "power": 420,  "level": 7, "image_url": None, "desc": "برد بین‌قاره‌ای."},
        {"id": "missile_nuclear",   "name": "☢️ موشک هسته‌ای (نمادین)", "price": 50000, "power": 1000, "level": 10, "image_url": None, "desc": "صرفاً یه آیتم نمادین بازی برای بالاترین سطح قدرت؛ بدون هیچ جزئیات فنی واقعی."},
    ]},
    "land_infantry": {"title": "پیاده‌نظام 🪖", "parent": "land", "items": [
        {"id": "soldier",       "name": "گروهان پیاده‌نظام",  "price": 100,  "power": 5,  "level": 1, "image_url": None, "desc": "ستون فقرات هر ارتش."},
        {"id": "special_force", "name": "نیروی ویژه",         "price": 600,  "power": 30, "level": 2, "image_url": None, "desc": "آموزش‌دیده برای عملیات ویژه."},
        {"id": "commando",      "name": "تکاور دریایی",       "price": 1000, "power": 45, "level": 3, "image_url": None, "desc": "توان عملیات ترکیبی زمین و دریا."},
    ]},
    "land_tank": {"title": "تانک 🚜", "parent": "land", "items": [
        {"id": "tank_basic",    "name": "تانک زره‌پوش کاویر",  "price": 1200,  "power": 60,  "level": 2, "image_url": None, "desc": "تانک ورودی اقتصادی."},
        {"id": "tank_t90",      "name": "تانک تی-۹۰",          "price": 2600,  "power": 115, "level": 3, "image_url": None, "desc": "تعادل خوب بین قیمت و قدرت."},
        {"id": "tank_altay",    "name": "تانک آلتای",          "price": 3000,  "power": 130, "level": 3, "image_url": None, "desc": "زره مدرن و سامانه‌ی آتش پیشرفته."},
        {"id": "tank_arjun",    "name": "تانک آرجون",          "price": 3500,  "power": 145, "level": 4, "image_url": None, "desc": "طراحی بومی با زره مرکب."},
        {"id": "tank_k2",       "name": "تانک کی-۲ بلک‌پنتر",  "price": 5500,  "power": 210, "level": 5, "image_url": None, "desc": "یکی از پیشرفته‌ترین تانک‌های امروزی."},
        {"id": "tank_leopard2", "name": "تانک لئوپارد ۲",      "price": 4500,  "power": 180, "level": 5, "image_url": None, "desc": "استاندارد طلایی تانک‌های اروپایی."},
        {"id": "tank_abrams",   "name": "تانک ام۱ ابرامز",     "price": 6000,  "power": 230, "level": 6, "image_url": None, "desc": "زره کامپوزیت پیشرفته."},
        {"id": "tank_t14",      "name": "تانک تی-۱۴ آرماتا",   "price": 7000,  "power": 260, "level": 6, "image_url": None, "desc": "برج بدون‌سرنشین، نسل جدید."},
    ]},
    "land_support": {"title": "توپخانه و نفربر 🎯", "parent": "land", "items": [
        {"id": "artillery",   "name": "توپخانه خودکششی رعد", "price": 2200, "power": 100, "level": 3, "image_url": None, "desc": "پشتیبانی آتش از راه دور."},
        {"id": "apc_basic",   "name": "نفربر زرهی صاعقه",    "price": 800,  "power": 35,  "level": 1, "image_url": None, "desc": "انتقال امن نیرو در خط مقدم."},
        {"id": "apc_guarani", "name": "نفربر زرهی گوارانی",  "price": 1400, "power": 55,  "level": 2, "image_url": None, "desc": "چرخ‌دار و سریع."},
        {"id": "mlrs",        "name": "راکت‌انداز چندلوله",  "price": 3000, "power": 140, "level": 4, "image_url": None, "desc": "آتش گسترده روی مساحت وسیع."},
    ]},
    "sea_patrol": {"title": "ناوچه گشتی 🚤", "parent": "sea", "items": [
        {"id": "patrol", "name": "ناوچه گشتی", "price": 1500, "power": 50, "level": 1, "image_url": None, "desc": "گشت‌زنی و دفاع ساحلی."},
    ]},
    "sea_destroyer": {"title": "ناوشکن 🚢", "parent": "sea", "items": [
        {"id": "destroyer_basic",   "name": "ناوشکن دماوند",    "price": 5000, "power": 220, "level": 3, "image_url": None, "desc": "ناوشکن چندمنظوره."},
        {"id": "destroyer_kongo",   "name": "ناوشکن کونگو",     "price": 6500, "power": 260, "level": 4, "image_url": None, "desc": "سامانه‌ی ایجیس پیشرفته."},
        {"id": "destroyer_arleigh", "name": "ناوشکن آرلی برک",  "price": 7500, "power": 290, "level": 5, "image_url": None, "desc": "ستون فقرات ناوگان‌های مدرن."},
        {"id": "destroyer_type055", "name": "ناوشکن تایپ ۰۵۵",  "price": 8000, "power": 310, "level": 5, "image_url": None, "desc": "یکی از بزرگ‌ترین ناوشکن‌های جهان."},
    ]},
    "sea_sub": {"title": "زیردریایی 🌊", "parent": "sea", "items": [
        {"id": "sub_basic",    "name": "زیردریایی غدیر",    "price": 6000,  "power": 260, "level": 4, "image_url": None, "desc": "زیردریایی ساحلی چابک."},
        {"id": "sub_u212",     "name": "زیردریایی یو-۲۱۲",  "price": 8500,  "power": 320, "level": 5, "image_url": None, "desc": "سکوت صوتی بالا."},
        {"id": "sub_barracuda","name": "زیردریایی باراکودا","price": 11000, "power": 380, "level": 6, "image_url": None, "desc": "زیردریایی حمله‌ای هسته‌ای‌بر."},
    ]},
    "sea_carrier": {"title": "ناو هواپیمابر 🛳", "parent": "sea", "items": [
        {"id": "carrier_basic",          "name": "ناو هواپیمابر سبک",           "price": 15000, "power": 500, "level": 6, "image_url": None, "desc": "استقرار سریع نیروی هوایی در دریا."},
        {"id": "carrier_queenelizabeth", "name": "ناو هواپیمابر کوئین الیزابت", "price": 20000, "power": 600, "level": 7, "image_url": None, "desc": "یکی از بزرگ‌ترین ناوهای هواپیمابر جهان."},
        {"id": "carrier_nimitz",         "name": "ناو هواپیمابر نیمیتز",       "price": 26000, "power": 700, "level": 8, "image_url": None, "desc": "قدرت پروازی راهبردی."},
    ]},
}
AIR_CATS = ["air_defense", "air_drone", "air_fighter", "air_bomber", "air_missile"]
LAND_CATS = ["land_infantry", "land_tank", "land_support"]
SEA_CATS = ["sea_patrol", "sea_destroyer", "sea_sub", "sea_carrier"]

BUILDINGS = {
    "oil_rig":          {"name": "دکل نفت 🛢",                 "price": 2000, "resource": "oil",     "rate": 2},
    "iron_mine":        {"name": "معدن آهن ⛏",                 "price": 1800, "resource": "iron",    "rate": 2},
    "gold_mine":        {"name": "معدن طلا 🏆",                 "price": 2500, "resource": "gold",    "rate": 3},
    "uranium_facility": {"name": "تأسیسات استخراج اورانیوم ☢️", "price": 5000, "resource": "uranium", "rate": 1},
}
RESOURCE_NAMES = {
    "gold": f"دلار {CUR}", "oil": "نفت 🛢", "iron": "آهن ⛏",
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

def find_item_by_name_in_cat(cat_key, name):
    for it in SHOP[cat_key]["items"]:
        if name.startswith(it["name"]):
            return it
    return None

def missile_travel_seconds(power):
    return min(35, 4 + power // 25)

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
            tax_paid INTEGER DEFAULT 0,
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
    conn = db()
    conn.execute(
        "INSERT INTO users (user_id, username, country, region, gold, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, country_key, region, start_gold, datetime.now().strftime("%H:%M:%S %d-%m-%Y"))
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

def defense_power_of(army_dict):
    total = 0
    for item_id, count in army_dict.items():
        if shop_category_key_of(item_id) == "air_defense":
            it = item_lookup(item_id)
            total += count * it["power"]
    return total

def owns_recon_drone(army_dict):
    for item_id, count in army_dict.items():
        it = item_lookup(item_id)
        if it and it.get("recon") and count > 0:
            return True
    return False

def user_level(row):
    return max(1, row["xp"] // XP_PER_LEVEL + 1)

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

def current_exchange_rates():
    rates = dict(BASE_EXCHANGE_RATES)
    for key, s in STRAITS.items():
        srow = get_strait(key)
        if srow and srow["is_open"] == 0:
            rates[s["affects"]] = rates.get(s["affects"], 1) * s["close_mult"]
    return rates

# ------------------------------------------------------------------
# کیبوردهای پایین صفحه
# ------------------------------------------------------------------
def kb(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

MAIN_MENU = kb([
    ["خزانه 🏦", "فروشگاه 🛒"],
    ["حمله ⚔️", "تبادلات 📈"],
    ["بیانیه 📢", "اتحاد 🤝"],
    ["پشتیبانی 🛠", "دعوت از دوستان 👥"],
    ["وضعیت جهانی 🌍", "منطقه من 🗺"],
    ["تنگه‌ها ⚓", "حذف اکانت ❌"],
])

SHOP_MENU = kb([
    ["تجهیزات هوایی ✈️", "تجهیزات زمینی 🪖"],
    ["تجهیزات دریایی 🚢", "منابع و ساختمان‌ها ⛏"],
    ["بازگشت به منو اصلی ⬅️"],
])
AIR_SUB_MENU = kb([
    ["پدافند 🛡", "پهباد 🛸"],
    ["جنگنده ✈️", "بمب‌افکن 💣"],
    ["موشک ☄️"],
    ["بازگشت به فروشگاه ⬅️"],
])
LAND_SUB_MENU = kb([
    ["پیاده‌نظام 🪖", "تانک 🚜"],
    ["توپخانه و نفربر 🎯"],
    ["بازگشت به فروشگاه ⬅️"],
])
SEA_SUB_MENU = kb([
    ["ناوچه گشتی 🚤", "ناوشکن 🚢"],
    ["زیردریایی 🌊", "ناو هواپیمابر 🛳"],
    ["بازگشت به فروشگاه ⬅️"],
])
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
    ["🎯 ترور", "🔄 هدف دیگه (رندوم)"],
    ["لغو حمله ❌"],
])

def back_kb(label):
    return kb([[label]])

def item_list_keyboard(cat_key):
    items = SHOP[cat_key]["items"]
    rows = []
    for i in range(0, len(items), 2):
        chunk = items[i:i+2]
        rows.append([it["name"] for it in chunk])
    parent = SHOP[cat_key]["parent"]
    back_label = f"بازگشت به تجهیزات {PARENT_FA[parent]} ⬅️"
    rows.append([back_label])
    return kb(rows), back_label

BUILDINGS_MENU = kb([[b["name"]] for b in BUILDINGS.values()] + [["بازگشت به فروشگاه ⬅️"]])

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
# /start
# ------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    row = get_user(user.id)
    context.user_data.clear()
    if row:
        await update.message.reply_text(f"خوش برگشتی فرمانده {COUNTRIES.get(row['country'],{}).get('name','')}!", reply_markup=MAIN_MENU)
        return
    await update.message.reply_text("🌍 به «جنگ جهانی» خوش اومدی، فرمانده!\n\nاول یه قاره/منطقه انتخاب کن:", reply_markup=REGION_KEYBOARD)

async def pick_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    region_key = query.data.split(":")[1]
    conn = db()
    taken = {r["country"] for r in conn.execute("SELECT country FROM users").fetchall()}
    conn.close()
    await query.edit_message_text(
        f"منطقه {REGIONS[region_key]['emoji']} {REGIONS[region_key]['name']} انتخاب شد.\nحالا کشورت رو انتخاب کن:",
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
        f"💰 {country['start_gold']}{CUR} برای شروع دریافت کردی.\n"
        f"🎖 بونوس: {country['desc']}\n👥 جمعیت: {country['population']}"
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

    if text == "خزانه 🏦":
        await treasury(update, context); return
    if text == "فروشگاه 🛒":
        context.user_data.clear()
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text == "حمله ⚔️":
        await start_random_attack(update, context); return
    if text == "تبادلات 📈":
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

    if text == "تجهیزات هوایی ✈️":
        await update.message.reply_text("یه زیرشاخه‌ی هوایی انتخاب کن:", reply_markup=AIR_SUB_MENU); return
    if text == "تجهیزات زمینی 🪖":
        await update.message.reply_text("یه زیرشاخه‌ی زمینی انتخاب کن:", reply_markup=LAND_SUB_MENU); return
    if text == "تجهیزات دریایی 🚢":
        await update.message.reply_text("یه زیرشاخه‌ی دریایی انتخاب کن:", reply_markup=SEA_SUB_MENU); return
    if text == "منابع و ساختمان‌ها ⛏":
        await update.message.reply_text("⛏ ساختمان‌های تولید منابع (درآمد خودکار هر دقیقه):", reply_markup=BUILDINGS_MENU); return
    if text == "بازگشت به فروشگاه ⬅️":
        context.user_data["mode"] = None
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text.startswith("بازگشت به تجهیزات"):
        for parent, menu in PARENT_TO_SUBMENU.items():
            if PARENT_FA[parent] in text:
                await update.message.reply_text(f"یه زیرشاخه انتخاب کن:", reply_markup=menu); return

    if text in SUBMENU_LABEL_TO_CAT:
        cat_key = SUBMENU_LABEL_TO_CAT[text]
        listkb, _ = item_list_keyboard(cat_key)
        context.user_data["current_cat"] = cat_key
        label = "روی هرکدوم بزن تا اطلاعاتش رو ببینی:" if context.user_data.get("mode") != "attack" else "کدوم تجهیزات رو برای این عملیات می‌فرستی؟"
        await update.message.reply_text(f"{SHOP[cat_key]['title']}\n{label}", reply_markup=listkb)
        return

    cur_cat = context.user_data.get("current_cat")
    if cur_cat:
        item = find_item_by_name_in_cat(cur_cat, text)
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
    if text == "🎯 ترور":
        await do_assassinate(update, context); return
    if text == "🔄 هدف دیگه (رندوم)":
        await start_random_attack(update, context); return
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU); return

# ------------------------------------------------------------------
# خزانه
# ------------------------------------------------------------------
async def treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    country = COUNTRIES.get(row["country"], {})
    army = get_json_field(row, "army")
    buildings = get_json_field(row, "buildings")
    b_lines = [f"{BUILDINGS[b]['name']} × {c}" for b, c in buildings.items() if c] or ["چیزی نداری"]
    a_lines = [f"{item_lookup(i)['name']} × {c}" for i, c in army.items() if c] or ["چیزی نداری"]
    lines = [
        f"🌍 کشور: {country.get('name','')} | 👥 جمعیت: {country.get('population','-')}",
        f"🗺 منطقه: {REGIONS[row['region']]['name']}",
        f"🎖 لول: {user_level(row)} | تجربه: {row['xp']}",
        "",
        f"💵 دلار: {row['gold']}{CUR}",
        f"🛢 نفت: {row['oil']}   ⛏ آهن: {row['iron']}   🌿 تریاک: {row['opium']}",
        f"☢️ اورانیوم خام: {row['uranium']} | غنی ۳۰/۶۰/۹۰٪: {row['enriched_30']}/{row['enriched_60']}/{row['enriched_90']} گرم",
        "",
        "🏗 ساختمان‌ها:", *b_lines,
        "",
        "⚔️ تجهیزات:", *a_lines,
        "",
        f"💪 قدرت نظامی کل: {army_power(army, row['oil']>0)}" + (" ⚠️ (نفت صفره)" if row['oil']<=0 else ""),
        f"💀 تلفات کل: {row['casualties']}",
        f"🧾 مالیات پرداختی: {row['tax_paid']}{CUR} (هر ساعت {int(TAX_RATE*100)}٪)",
        f"📅 ثبت‌نام: {row['created_at']}",
    ]
    await send_card(update.message, f"🏦 خزانه‌ی {country.get('name','')}", lines, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# اطلاعات آیتم برای خرید
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
    lines = [
        f"💬 {item.get('desc','')}",
        f"💰 قیمت واحد: {price}{CUR}",
        f"💪 قدرت: {item['power']}",
        f"📦 تعداد فعلی تو: {owned}",
    ]
    if lvl < item["level"]:
        lines.append(f"🔒 نیاز به لول {item['level']} (لول تو: {lvl})")
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
        await update.message.reply_text(f"دلار کافی نداری! قیمت کل: {total}{CUR}، موجودی تو: {row['gold']}{CUR}")
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
    lines = [
        f"💰 قیمت واحد: {b['price']}{CUR}",
        f"📈 درآمد: +{b['rate']} {RESOURCE_NAMES[b['resource']]} در دقیقه به‌ازای هر واحد",
        f"📦 تعداد فعلی تو: {owned}",
        "برای خرید، تعداد رو بفرست:",
    ]
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
# درآمد خودکار + مالیات
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

async def tax_job(context: ContextTypes.DEFAULT_TYPE):
    for row in all_users():
        if row["gold"] <= 0:
            continue
        tax = int(row["gold"] * TAX_RATE)
        if tax > 0:
            add_resource(row["user_id"], "gold", -tax)
            update_field(row["user_id"], "tax_paid", row["tax_paid"] + tax)

# ------------------------------------------------------------------
# تبادلات
# ------------------------------------------------------------------
async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rates = current_exchange_rates()
    lines = []
    for res, rate in rates.items():
        extra = " ⚠️ (تنگه بسته‌ست)" if rate > BASE_EXCHANGE_RATES[res] else ""
        lines.append(f"{RESOURCE_NAMES[res]}: {int(rate)}{CUR}{extra}")
    lines.append("")
    lines.append("/sell <منبع> <تعداد>")
    lines.append("/send <username> <resource> <تعداد>")
    await send_card(update.message, "📈 مرکز تبادلات جهانی", lines, reply_markup=MAIN_MENU)

async def sell_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    row = get_user(user_id)
    if not row:
        await update.message.reply_text("اول /start بزن."); return
    rates = current_exchange_rates()
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
# تنگه‌ها — مالکیت ثابت، فقط باز/بسته
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
    await broadcast_to_all(context, f"🚨 {s['name']} توسط {COUNTRIES[s['true_owner_country']]['name']} بسته شد! قیمت {RESOURCE_NAMES[s['affects']]} به‌شدت افزایش یافت.")
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
    await broadcast_to_all(context, f"✅ {s['name']} دوباره باز شد. قیمت به حالت عادی برگشت.")
    await strait_info_callback(update, context)

async def broadcast_to_all(context, text):
    for row in all_users():
        try:
            await context.bot.send_message(row["user_id"], text)
        except Exception:
            pass

# ------------------------------------------------------------------
# حمله — انتخاب رندوم هدف توسط خود ربات
# ------------------------------------------------------------------
async def start_random_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    candidates = [r for r in all_users() if r["user_id"] != user.id]
    if not candidates:
        await update.message.reply_text("هنوز بازیکن دیگه‌ای ثبت‌نام نکرده که بهش حمله کنی.", reply_markup=MAIN_MENU)
        return
    target = random.choice(candidates)
    context.user_data.clear()
    context.user_data["attack_target_id"] = target["user_id"]
    tc = COUNTRIES.get(target["country"], {})
    t_power = army_power(get_json_field(target, "army"), target["oil"] > 0)
    lines = [
        f"🌍 کشور: {tc.get('name','ناشناس')}",
        f"👥 جمعیت: {tc.get('population','-')}",
        f"💪 قدرت نظامی: {t_power}",
        f"🛡 قدرت پدافند: {defense_power_of(get_json_field(target, 'army'))}",
        "",
        "نوع عملیات رو انتخاب کن 👇",
    ]
    await send_card(update.message, "🎯 هدف پیدا شد!", lines, reply_markup=ATTACK_TYPE_MENU)

# ------------------------------------------------------------------
# انتخاب تجهیزات برای حمله (تعداد دلخواه)
# ------------------------------------------------------------------
async def show_item_for_combat(update, context, cat_key, item):
    row = get_user(update.effective_user.id)
    owned = get_json_field(row, "army").get(item["id"], 0)
    if owned <= 0:
        await update.message.reply_text(f"چیزی از «{item['name']}» نداری! اول از فروشگاه بخر.")
        return
    is_missile = cat_key == "air_missile"
    lines = [
        f"💬 {item.get('desc','')}",
        f"💪 قدرت واحد: {item['power']}",
        f"📦 تعداد موجود: {owned}",
    ]
    if is_missile:
        lines.append(f"⏱ زمان رسیدن هر شلیک: تا {missile_travel_seconds(item['power'])} ثانیه")
        lines.append("⚠️ موشک‌ها مصرفی هستن و بعد از شلیک از انبار کم میشن.")
    else:
        lines.append("ℹ️ این نیروها پس از عملیات به کشورت برمی‌گردن (مصرف نمیشن)، ولی در برابر پدافند قوی ممکنه تلفات بدن.")
    lines.append("چند واحد از این رو به عملیات می‌فرستی؟ (عدد بفرست)")
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
    item = item_lookup(item_id)
    army = get_json_field(row, "army")
    owned = army.get(item_id, 0)
    if qty > owned:
        await update.message.reply_text(f"فقط {owned} تا از این داری.")
        return

    target_id = context.user_data.get("attack_target_id")
    target = get_user(target_id)
    if not target:
        await update.message.reply_text("این هدف دیگه در دسترس نیست.", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return

    now = int(time.time())
    if now - row["last_attack"] < ATTACK_COOLDOWN_SEC:
        wait = (ATTACK_COOLDOWN_SEC - (now - row["last_attack"])) // 60
        await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
        return
    update_field(row["user_id"], "last_attack", now)

    is_missile = cat_key == "air_missile"

    if is_missile:
        army[item_id] -= qty
        if army[item_id] <= 0:
            del army[item_id]
        set_json_field(row["user_id"], "army", army)
        travel = missile_travel_seconds(item["power"])
        context.user_data.clear()
        await update.message.reply_text(f"☄️ {qty} عدد {item['name']} شلیک شد! زمان تخمینی رسیدن: {travel} ثانیه...", reply_markup=MAIN_MENU)
        context.job_queue.run_once(
            deliver_combat_impact, when=travel,
            data={"attacker_id": row["user_id"], "target_id": target_id, "item_id": item_id, "qty": qty, "is_missile": True}
        )
    else:
        context.user_data.clear()
        await resolve_combat(context.bot, row["user_id"], target_id, item_id, qty, is_missile=False)

async def deliver_combat_impact(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await resolve_combat(context.bot, data["attacker_id"], data["target_id"], data["item_id"], data["qty"], is_missile=data["is_missile"])

async def resolve_combat(bot, attacker_id, target_id, item_id, qty, is_missile):
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not attacker or not target:
        return
    item = item_lookup(item_id)
    a_army = get_json_field(attacker, "army")
    d_army = get_json_field(target, "army")
    d_oil_ok = target["oil"] > 0
    a_oil_ok = attacker["oil"] > 0
    parent = category_of(item_id)

    committed_power = qty * item["power"]
    if parent == "air" and not a_oil_ok:
        committed_power = 0
    a_power = committed_power + random.randint(0, 40)

    defense = defense_power_of(d_army)
    d_power = army_power(d_army, d_oil_ok) + random.randint(0, 40)
    if parent in ("air",):
        d_power += int(defense * 0.5)  # پدافند مخصوصاً جلوی هوایی/موشکی قوی‌تره

    success = a_power > d_power

    # پدافند حداقل یه مقدار تلفات به مهاجم می‌زنه (اگه هدف پدافند داشته باشه)
    attacker_losses = 0
    if defense > 0 and parent == "air":
        loss_fraction = min(0.6, defense / (defense + a_power + 1))
        attacker_losses = max(1, math.ceil(qty * loss_fraction)) if qty > 0 else 0
        attacker_losses = min(attacker_losses, qty)
        if not is_missile and attacker_losses > 0:
            a_army[item_id] = max(0, a_army.get(item_id, 0) - attacker_losses)
            if a_army[item_id] <= 0:
                a_army.pop(item_id, None)
            set_json_field(attacker_id, "army", a_army)

    parent_fa = PARENT_FA.get(parent, "نظامی")
    lines_attacker = [f"⚔️ نتیجه‌ی حمله با {item['name']} × {qty}"]
    if success:
        loot = min(target["gold"], random.randint(100, 500) + qty * 5)
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        add_xp(attacker_id, 80 + qty * 5)
        lost = record_casualties(target_id, d_army)
        lines_attacker += [
            f"✅ موفقیت‌آمیز بود! ({a_power} در برابر {d_power})",
            f"🏆 غنیمت: {loot}{CUR}",
            f"💀 تلفات نظامی هدف: {lost}",
        ]
        if attacker_losses:
            lines_attacker.append(f"🛡 پدافند هدف {attacker_losses} واحد از نیروهات رو هم از پا درآورد.")
        await send_card_via_bot(bot, attacker_id, "🎉 عملیات موفق", lines_attacker)
        await notify_defender(bot, target_id, attacker, f"حمله {parent_fa} ({item['name']} × {qty})", f"{loot}{CUR} و {lost} قدرت نظامی از دست دادی!")
    else:
        lines_attacker.append(f"💥 دفع شد. ({a_power} در برابر {d_power})")
        if attacker_losses:
            lines_attacker.append(f"🛡 پدافند هدف {attacker_losses} واحد از نیروهات رو هم از پا درآورد.")
        await send_card_via_bot(bot, attacker_id, "❌ عملیات ناموفق", lines_attacker)

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
    try:
        await send_card_via_bot(bot, target_id, "🚨 حمله دریافت شد!", [f"نوع عملیات: {attack_name}", f"مهاجم: {attacker_name}", extra_text], reply_markup=kb_)
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
        await update.message.reply_text("برای جاسوسی به یه پهباد شناسایی نیاز داری (مثلاً پهباد رعد یا هرمس). اول از فروشگاه بخر.")
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
    lines = [
        f"💪 قدرت نظامی: {army_power(d_army, target['oil'] > 0)}",
        f"🛡 قدرت پدافند: {defense_power_of(d_army)}",
        f"💵 دلار: {target['gold']}{CUR}",
        "حالا امکان ترور این هدف برات باز شده.",
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
    if a_power + random.randint(0, 40) > d_power:
        update_field(target_id, "sabotaged_until", now + 60 * 15)
        await update.message.reply_text("🧨 خرابکاری موفق! درآمد ساختمان‌های هدف تا ۱۵ دقیقه ۷۰٪ کاهش یافت.", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "خرابکاری زیرساخت", "زیرساخت‌های اقتصادی‌ت خراب شد!")
    else:
        await update.message.reply_text("💥 خرابکاری شکست خورد.", reply_markup=MAIN_MENU)
    context.user_data.clear()

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
    if success:
        loot = min(target["gold"], random.randint(300, 800))
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        add_xp(attacker_id, 150)
        await update.message.reply_text(f"🎯 ترور موفق! غنیمت: {loot}{CUR}", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "ترور", f"عملیات ترور موفق! {loot}{CUR} از دست دادی.")
    else:
        await update.message.reply_text("💥 ترور شکست خورد و لو رفت.", reply_markup=MAIN_MENU)
        await notify_defender(context.bot, target_id, attacker, "تلاش ترور ناموفق", "یه تلاش ترور ناموفق علیه‌ت کشف شد!")
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

async def alliance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if row["alliance"]:
        await update.message.reply_text(f"🤝 عضو اتحاد «{row['alliance']}» هستی.\n/leave_alliance برای خروج")
        return
    await update.message.reply_text("🤝 /create_alliance <اسم>\n/join_alliance <اسم>")

async def create_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /create_alliance <اسم>"); return
    name = " ".join(context.args)[:30]
    update_field(update.effective_user.id, "alliance", name)
    await update.message.reply_text(f"✅ اتحاد «{name}» ساخته شد.")

async def join_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("فرمت درست: /join_alliance <اسم>"); return
    name = " ".join(context.args)[:30]
    update_field(update.effective_user.id, "alliance", name)
    await update.message.reply_text(f"✅ به اتحاد «{name}» پیوستی.")

async def leave_alliance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_field(update.effective_user.id, "alliance", None)
    await update.message.reply_text("از اتحادت خارج شدی.")

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    if not row["alliance"]:
        await update.message.reply_text("برای بیانیه باید عضو اتحاد باشی."); return
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
            await context.bot.send_message(m["user_id"], f"📢 بیانیه از {row['username']} ({row['alliance']}):\n{text}")
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"بیانیه برای {sent} عضو ارسال شد.")

async def statement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📢 برای بیانیه: /announce <متن پیام>", reply_markup=MAIN_MENU)

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
        "📖 راهنما:\n\n"
        "/start — ثبت‌نام (قاره → کشور)\n"
        "«حمله ⚔️» یه هدف رندوم از بین کسایی که ربات رو استارت زدن پیدا می‌کنه. بعد نوع عملیات و تجهیزات و تعدادش رو خودت انتخاب می‌کنی.\n"
        "جاسوسی فقط با داشتن پهباد شناسایی (رعد یا هرمس) ممکنه.\n"
        "پدافند هدف می‌تونه به مهاجم هم تلفات بزنه، مخصوصاً در حمله‌ی هوایی/موشکی.\n"
        "تنگه‌ها همیشه دست کشور واقعی صاحبشونه؛ فقط می‌تونن باز/بسته بشن.\n\n"
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
    app.add_handler(CommandHandler("create_alliance", create_alliance_command))
    app.add_handler(CommandHandler("join_alliance", join_alliance_command))
    app.add_handler(CommandHandler("leave_alliance", leave_alliance_command))
    app.add_handler(CommandHandler("announce", announce_command))
    app.add_handler(CommandHandler("redeem", redeem_command))

    app.add_handler(CallbackQueryHandler(pick_region_callback, pattern="^pickregion:"))
    app.add_handler(CallbackQueryHandler(back_to_region_callback, pattern="^backtoregion$"))
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

    print("🤖 World War Bot v5 در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
