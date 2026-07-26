# -*- coding: utf-8 -*-
"""
=====================================================================
World War Bot v4 — بازی استراتژیک متنی برای تلگرام
همه‌چیز توی همین یک فایله.

راه‌اندازی:
۱) BOT_TOKEN رو به عنوان متغیر محیطی ست کن.
۲) pip install -r requirements.txt  (باید python-telegram-bot[job-queue]==21.4 باشه)
۳) python bot.py

نکته: اعداد جمعیت/تجهیزات کشورها صرفاً برای فضاسازی بازی و تقریبی هستن،
نه داده‌ی رسمی یا محرمانه‌ی نظامی.
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

TOKEN = os.environ.get("BOT_TOKEN", "PUT-YOUR-TOKEN-HERE")
DB_PATH = os.path.join(os.path.dirname(__file__), "worldwar.db")

ATTACK_COOLDOWN_SEC = 60 * 10
SANCTION_COOLDOWN_SEC = 60 * 30
RECON_COOLDOWN_SEC = 60 * 5
STRAIT_ACTION_COOLDOWN_SEC = 60 * 15
INCOME_TICK_SEC = 60
TAX_TICK_SEC = 60 * 60
TAX_RATE = 0.03
XP_PER_LEVEL = 1000
XP_PER_DOLLAR_SPENT = 0.05  # هر دلار خرج‌شده کمی تجربه میده

GIFT_CODES = {"BOB": {"gold": 999999999}}

CUR = "$"  # نماد پول بازی

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
    "hormuz":        {"name": "تنگه هرمز",       "region": "middle_east", "affects": "oil",  "close_mult": 3.0},
    "malacca":       {"name": "تنگه مالاکا",     "region": "east_asia",   "affects": "gold", "close_mult": 2.0},
    "gibraltar":     {"name": "تنگه جبل‌الطارق", "region": "europe",      "affects": "oil",  "close_mult": 1.7},
    "bab_el_mandeb": {"name": "تنگه باب‌المندب", "region": "africa",      "affects": "gold", "close_mult": 1.8},
}

# ------------------------------------------------------------------
# کشورها — جمعیت و سرمایه‌ی اولیه تقریبی (برای تعادل بازی)
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
# فروشگاه
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
        {"id": "missile_scud",      "name": "موشک اسکاد",              "price": 1800,  "power": 90,   "level": 2},
        {"id": "missile_zolfaghar", "name": "موشک ذوالفقار",           "price": 2500,  "power": 120,  "level": 2},
        {"id": "missile_hoveizeh",  "name": "موشک کروز هویزه",         "price": 3200,  "power": 150,  "level": 3},
        {"id": "missile_emad",      "name": "موشک عماد",               "price": 4000,  "power": 180,  "level": 3},
        {"id": "missile_kheibar",   "name": "موشک خیبرشکن",            "price": 5000,  "power": 210,  "level": 4},
        {"id": "missile_fattah2",   "name": "موشک فتاح-۲",             "price": 6500,  "power": 260,  "level": 4},
        {"id": "missile_iskander",  "name": "موشک اسکندر",             "price": 7000,  "power": 280,  "level": 5},
        {"id": "missile_sejjil",    "name": "موشک سجیل",               "price": 8000,  "power": 300,  "level": 5},
        {"id": "missile_agni",      "name": "موشک قاره‌پیمای آگنی",    "price": 10000, "power": 340,  "level": 6},
        {"id": "missile_shaheen",   "name": "موشک شاهین",              "price": 9000,  "power": 320,  "level": 5},
        {"id": "missile_df17",      "name": "موشک دی‌اف-۱۷",           "price": 11000, "power": 360,  "level": 6},
        {"id": "missile_css4",      "name": "موشک قاره‌پیمای سی‌اس‌اس-۴", "price": 15000, "power": 420,  "level": 7},
        {"id": "missile_nuclear",   "name": "☢️ موشک هسته‌ای (نمادین)", "price": 50000, "power": 1000, "level": 10},
    ]},
    "land_infantry": {"title": "پیاده‌نظام 🪖", "parent": "land", "items": [
        {"id": "soldier",       "name": "گروهان پیاده‌نظام",  "price": 100,  "power": 5,  "level": 1},
        {"id": "special_force", "name": "نیروی ویژه",         "price": 600,  "power": 30, "level": 2},
        {"id": "commando",      "name": "تکاور دریایی",       "price": 1000, "power": 45, "level": 3},
    ]},
    "land_tank": {"title": "تانک 🚜", "parent": "land", "items": [
        {"id": "tank_basic",    "name": "تانک زره‌پوش کاویر",  "price": 1200,  "power": 60,  "level": 2},
        {"id": "tank_t90",      "name": "تانک تی-۹۰",          "price": 2600,  "power": 115, "level": 3},
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
        {"id": "sub_basic",    "name": "زیردریایی غدیر",    "price": 6000,  "power": 260, "level": 4},
        {"id": "sub_u212",     "name": "زیردریایی یو-۲۱۲",  "price": 8500,  "power": 320, "level": 5},
        {"id": "sub_barracuda","name": "زیردریایی باراکودا","price": 11000, "power": 380, "level": 6},
    ]},
    "sea_carrier": {"title": "ناو هواپیمابر 🛳", "parent": "sea", "items": [
        {"id": "carrier_basic",          "name": "ناو هواپیمابر سبک",           "price": 15000, "power": 500, "level": 6},
        {"id": "carrier_queenelizabeth", "name": "ناو هواپیمابر کوئین الیزابت", "price": 20000, "power": 600, "level": 7},
        {"id": "carrier_nimitz",         "name": "ناو هواپیمابر نیمیتز",       "price": 26000, "power": 700, "level": 8},
    ]},
}
AIR_CATS = ["air_defense", "air_drone", "air_fighter", "air_bomber", "air_missile"]
LAND_CATS = ["land_infantry", "land_tank", "land_support"]
SEA_CATS = ["sea_patrol", "sea_destroyer", "sea_sub", "sea_carrier"]
CAT_TITLES = {k: v["title"] for k, v in SHOP.items()}

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
        if it["name"] == name:
            return it
    return None

def missile_travel_seconds(power):
    """زمان رسیدن موشک؛ هرچی قدرت بالاتر (بردش بیشتر فرض میشه) کمی بیشتر، ولی سقف داره"""
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

def search_users(query):
    query = query.strip().lower()
    results = []
    for r in all_users():
        cname = COUNTRIES.get(r["country"], {}).get("name", "").lower()
        uname = (r["username"] or "").lower()
        if query in cname or query in uname:
            results.append(r)
    return results[:10]

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

def set_strait(key, owner_id=None, is_open=None):
    conn = db()
    if owner_id is not None:
        conn.execute("UPDATE straits SET owner_id=? WHERE strait_key=?", (owner_id, key))
    if is_open is not None:
        conn.execute("UPDATE straits SET is_open=? WHERE strait_key=?", (1 if is_open else 0, key))
    conn.commit()
    conn.close()

def current_exchange_rates():
    rates = dict(BASE_EXCHANGE_RATES)
    for key, s in STRAITS.items():
        srow = get_strait(key)
        if srow and srow["is_open"] == 0:
            rates[s["affects"]] = rates.get(s["affects"], 1) * s["close_mult"]
    return rates

# ------------------------------------------------------------------
# کیبوردهای پایین صفحه (Reply Keyboards) — ناوبری کامل غیرشیشه‌ای
# ------------------------------------------------------------------
def kb(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

MAIN_MENU = kb([
    ["خزانه 🏦", "فروشگاه 🛒"],
    ["حمله ⚔️", "تجهیزات 📋"],
    ["تبادلات 📈", "بیانیه 📢"],
    ["اتحاد 🤝", "پشتیبانی 🛠"],
    ["دعوت از دوستان 👥", "وضعیت جهانی 🌍"],
    ["منطقه من 🗺", "نقشه جهان 🗺"],
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

ATTACK_MENU = kb([
    ["🔎 جستجوی بازیکن", "🆔 وارد کردن یوزرنیم"],
    ["بازگشت به منو اصلی ⬅️"],
])
ATTACK_TYPE_MENU = kb([
    ["☄️ موشکی", "✈️ هوایی"],
    ["🚜 زمینی", "🚢 دریایی"],
    ["🕵️ جاسوسی", "🧨 خرابکاری"],
    ["🎯 ترور"],
    ["لغو حمله ❌"],
])

def back_kb(label="بازگشت به فروشگاه ⬅️"):
    return kb([[label]])

def item_list_keyboard(cat_key):
    items = SHOP[cat_key]["items"]
    rows = []
    for i in range(0, len(items), 2):
        chunk = items[i:i+2]
        rows.append([it["name"] for it in chunk])
    parent = SHOP[cat_key]["parent"]
    back_label = {"air": "بازگشت به تجهیزات هوایی ⬅️", "land": "بازگشت به تجهیزات زمینی ⬅️", "sea": "بازگشت به تجهیزات دریایی ⬅️"}[parent]
    rows.append([back_label])
    return kb(rows), back_label

BUILDINGS_MENU_ROWS = [[b["name"]] for b in BUILDINGS.values()] + [["بازگشت به فروشگاه ⬅️"]]
BUILDINGS_MENU = kb(BUILDINGS_MENU_ROWS)

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
# روتر مرکزی پیام‌های متنی — اول state، بعد منوها
# ------------------------------------------------------------------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    row = get_user(user.id)
    if not row:
        await update.message.reply_text("اول دستور /start رو بزن.")
        return

    state = context.user_data.get("state")

    # ---------- حالت‌های در انتظار ورودی متنی ----------
    if state == "await_purchase_qty":
        await handle_purchase_qty(update, context, row, text)
        return
    if state == "await_building_qty":
        await handle_building_qty(update, context, row, text)
        return
    if state == "await_attack_username":
        await handle_attack_username(update, context, text)
        return
    if state == "await_search_query":
        await handle_search_query(update, context, text)
        return

    # ---------- منوی اصلی ----------
    if text == "خزانه 🏦":
        await treasury(update, context); return
    if text == "فروشگاه 🛒":
        context.user_data.clear()
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text == "حمله ⚔️":
        context.user_data.clear()
        await update.message.reply_text("⚔️ چطور می‌خوای هدفت رو انتخاب کنی؟", reply_markup=ATTACK_MENU); return
    if text == "تجهیزات 📋":
        await equipment_info(update, context); return
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

    # ---------- زیرمنوی فروشگاه ----------
    if text == "تجهیزات هوایی ✈️":
        await update.message.reply_text("یه زیرشاخه‌ی هوایی انتخاب کن:", reply_markup=AIR_SUB_MENU); return
    if text == "تجهیزات زمینی 🪖":
        await update.message.reply_text("یه زیرشاخه‌ی زمینی انتخاب کن:", reply_markup=LAND_SUB_MENU); return
    if text == "تجهیزات دریایی 🚢":
        await update.message.reply_text("یه زیرشاخه‌ی دریایی انتخاب کن:", reply_markup=SEA_SUB_MENU); return
    if text == "منابع و ساختمان‌ها ⛏":
        await update.message.reply_text("⛏ ساختمان‌های تولید منابع (درآمد خودکار هر دقیقه):", reply_markup=BUILDINGS_MENU); return
    if text == "بازگشت به فروشگاه ⬅️":
        await update.message.reply_text("🛒 یه گروه انتخاب کن:", reply_markup=SHOP_MENU); return
    if text in ("بازگشت به تجهیزات هوایی ⬅️",):
        await update.message.reply_text("یه زیرشاخه‌ی هوایی انتخاب کن:", reply_markup=AIR_SUB_MENU); return
    if text in ("بازگشت به تجهیزات زمینی ⬅️",):
        await update.message.reply_text("یه زیرشاخه‌ی زمینی انتخاب کن:", reply_markup=LAND_SUB_MENU); return
    if text in ("بازگشت به تجهیزات دریایی ⬅️",):
        await update.message.reply_text("یه زیرشاخه‌ی دریایی انتخاب کن:", reply_markup=SEA_SUB_MENU); return

    if text in SUBMENU_LABEL_TO_CAT:
        cat_key = SUBMENU_LABEL_TO_CAT[text]
        listkb, _ = item_list_keyboard(cat_key)
        context.user_data["current_cat"] = cat_key
        await update.message.reply_text(f"{SHOP[cat_key]['title']}\nروی هرکدوم بزن تا اطلاعاتش رو ببینی:", reply_markup=listkb)
        return

    # اگه توی یه دسته‌ایم و اسم یه آیتم زده شده
    cur_cat = context.user_data.get("current_cat")
    if cur_cat:
        item = find_item_by_name_in_cat(cur_cat, text)
        if item:
            await show_item_info(update, context, cur_cat, item)
            return

    # ساختمان‌ها
    b_match = next((k for k, b in BUILDINGS.items() if b["name"] == text), None)
    if b_match:
        await show_building_info(update, context, b_match)
        return

    # ---------- زیرمنوی حمله ----------
    if text == "🔎 جستجوی بازیکن":
        context.user_data["state"] = "await_search_query"
        await update.message.reply_text("اسم کشور یا بخشی از یوزرنیم رو بفرست:", reply_markup=kb([["لغو حمله ❌"]]))
        return
    if text == "🆔 وارد کردن یوزرنیم":
        context.user_data["state"] = "await_attack_username"
        await update.message.reply_text("یوزرنیم بازیکن رو بفرست (بدون @):", reply_markup=kb([["لغو حمله ❌"]]))
        return
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU)
        return

    if text in ("☄️ موشکی", "✈️ هوایی", "🚜 زمینی", "🚢 دریایی", "🕵️ جاسوسی", "🧨 خرابکاری", "🎯 ترور"):
        await handle_attack_type_text(update, context, text)
        return

    # آیتم موشک برای شلیک انتخاب شده
    if context.user_data.get("state") == "await_missile_choice":
        await handle_missile_fire_text(update, context, text)
        return

    # نتیجه‌ی جستجو انتخاب شده
    search_map = context.user_data.get("search_results")
    if search_map and text in search_map:
        context.user_data["attack_target_id"] = search_map[text]
        context.user_data["state"] = None
        await update.message.reply_text("نوع عملیات رو انتخاب کن:", reply_markup=ATTACK_TYPE_MENU)
        return

# ------------------------------------------------------------------
# خزانه
# ------------------------------------------------------------------
async def treasury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    country = COUNTRIES.get(row["country"], {})
    army = get_json_field(row, "army")
    buildings = get_json_field(row, "buildings")
    b_lines = "\n".join(f"  {BUILDINGS[b]['name']} × {c}" for b, c in buildings.items() if c) or "  چیزی نداری"
    a_lines = "\n".join(f"  {item_lookup(i)['name']} × {c}" for i, c in army.items() if c) or "  چیزی نداری"
    text = (
        f"🏦 خزانه‌ی «{country.get('name','')}»\n"
        f"جمعیت کشور: {country.get('population','-')}\n"
        f"منطقه: {REGIONS[row['region']]['name']}\n"
        f"لول: {user_level(row)} (تجربه: {row['xp']})\n\n"
        f"دلار: {row['gold']}{CUR}\n"
        f"نفت: {row['oil']} 🛢\n"
        f"آهن: {row['iron']} ⛏\n"
        f"تریاک: {row['opium']} 🌿\n"
        f"اورانیوم خام: {row['uranium']} ☢️\n"
        f"اورانیوم غنی‌شده ۳۰٪/۶۰٪/۹۰٪: {row['enriched_30']}/{row['enriched_60']}/{row['enriched_90']} گرم\n\n"
        f"🏗 ساختمان‌ها:\n{b_lines}\n\n"
        f"⚔️ تجهیزات:\n{a_lines}\n\n"
        f"قدرت نظامی کل: {army_power(army, row['oil']>0)}"
        + (" ⚠️ (نفت صفره، هواپیماها کار نمی‌کنن)" if row['oil'] <= 0 else "") +
        f"\n💀 تلفات کل: {row['casualties']}\n"
        f"🧾 مالیات پرداختی تا امروز: {row['tax_paid']}{CUR} (هر ساعت {int(TAX_RATE*100)}٪ از دارایی)\n"
        f"تاریخ ثبت‌نام: {row['created_at']}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# تجهیزات (پنل اطلاعاتی کشورها)
# ------------------------------------------------------------------
async def equipment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    country = COUNTRIES.get(row["country"], {})
    lines = [f"📋 پروفایل نظامی {country.get('name','')} (تقریبی، صرفاً برای فضای بازی):\n"]
    for name, count in country.get("equipment_info", []):
        lines.append(f"  • {name}: {count}")
    lines.append(f"\n👥 جمعیت: {country.get('population','-')}")
    lines.append(f"🎖 بونوس اقتصادی: {country.get('desc','-')}")
    if country.get("faction"):
        lines.append(f"🏴 نیروی ویژه‌ی کشور: {country['faction']}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

# ------------------------------------------------------------------
# نمایش اطلاعات آیتم + شروع فرآیند خرید با تعداد
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
    lock_txt = "" if lvl >= item["level"] else f"\n🔒 نیاز به لول {item['level']} (لول تو: {lvl})"
    text = (
        f"📦 {item['name']}\n"
        f"قیمت واحد: {price}{CUR}\n"
        f"قدرت: {item['power']}\n"
        f"تعداد فعلی تو: {owned}"
        f"{lock_txt}\n\n"
        f'برای خرید، تعداد رو بفرست (مثلاً: 3)'
    )
    context.user_data["state"] = "await_purchase_qty"
    context.user_data["purchase_item"] = item["id"]
    context.user_data["purchase_cat"] = cat_key
    listkb, back_label = item_list_keyboard(cat_key)
    await update.message.reply_text(text, reply_markup=kb([[back_label]]))

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
        await update.message.reply_text("لطفاً فقط یه عدد مثبت بفرست (مثلاً 1 یا 5).")
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
    text = f"🏗 {b['name']}\nقیمت واحد: {b['price']}{CUR}\nدرآمد: +{b['rate']} {RESOURCE_NAMES[b['resource']]} در دقیقه به‌ازای هر واحد\nتعداد فعلی تو: {owned}\n\nبرای خرید، تعداد رو بفرست:"
    context.user_data["state"] = "await_building_qty"
    context.user_data["purchase_building"] = b_key
    await update.message.reply_text(text, reply_markup=kb([["بازگشت به فروشگاه ⬅️"]]))

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
    lines = ["📈 مرکز تبادلات جهانی — نرخ فروش منابع به دلار:\n"]
    for res, rate in rates.items():
        extra = " ⚠️ (تنگه بسته‌ست، قیمت بالا رفته!)" if rate > BASE_EXCHANGE_RATES[res] else ""
        lines.append(f"{RESOURCE_NAMES[res]}: هر واحد = {int(rate)}{CUR}{extra}")
    lines.append("\n/sell <منبع> <تعداد>\n/send <username> <resource> <تعداد>")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

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
# تنگه‌ها
# ------------------------------------------------------------------
async def straits_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb_rows = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        owner_row = get_user(srow["owner_id"]) if srow["owner_id"] else None
        owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک"
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb_rows.append([InlineKeyboardButton(f"{s['name']} | {owner_name} | {status}", callback_data=f"straitinfo:{key}")])
    await update.message.reply_text("⚓ تنگه‌های استراتژیک جهان:", reply_markup=InlineKeyboardMarkup(kb_rows))

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
    kb_rows = []
    for key, s in STRAITS.items():
        srow = get_strait(key)
        owner_row = get_user(srow["owner_id"]) if srow["owner_id"] else None
        owner_name = COUNTRIES.get(owner_row["country"], {}).get("name") if owner_row else "بدون مالک"
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        kb_rows.append([InlineKeyboardButton(f"{s['name']} | {owner_name} | {status}", callback_data=f"straitinfo:{key}")])
    await query.edit_message_text("⚓ تنگه‌های استراتژیک جهان:", reply_markup=InlineKeyboardMarkup(kb_rows))

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
        owner_power = 100
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
        await query.answer("این تنگه مال تو نیست!", show_alert=True); return
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
        await query.answer("این تنگه مال تو نیست!", show_alert=True); return
    set_strait(key, is_open=True)
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
# حمله — از طریق کیبورد پایین صفحه و state machine
# ------------------------------------------------------------------
async def handle_attack_username(update, context, text):
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU)
        return
    target = get_user_by_username(text.lstrip("@"))
    if not target:
        await update.message.reply_text("این بازیکن پیدا نشد. دوباره امتحان کن یا لغو کن.")
        return
    if target["user_id"] == update.effective_user.id:
        await update.message.reply_text("نمی‌تونی به خودت حمله کنی! یوزرنیم دیگه‌ای بفرست.")
        return
    context.user_data["attack_target_id"] = target["user_id"]
    context.user_data["state"] = None
    await update.message.reply_text(f"هدف: {COUNTRIES.get(target['country'],{}).get('name','')}\nنوع عملیات رو انتخاب کن:", reply_markup=ATTACK_TYPE_MENU)

async def handle_search_query(update, context, text):
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU)
        return
    results = search_users(text)
    results = [r for r in results if r["user_id"] != update.effective_user.id]
    if not results:
        await update.message.reply_text("چیزی پیدا نشد. دوباره امتحان کن یا لغو کن.")
        return
    search_map = {}
    rows_kb = []
    for r in results:
        label = COUNTRIES.get(r["country"], {}).get("name", r["username"])
        search_map[label] = r["user_id"]
        rows_kb.append([label])
    rows_kb.append(["لغو حمله ❌"])
    context.user_data["search_results"] = search_map
    context.user_data["state"] = None
    await update.message.reply_text("یکی رو انتخاب کن:", reply_markup=kb(rows_kb))

async def handle_attack_type_text(update, context, text):
    target_id = context.user_data.get("attack_target_id")
    if not target_id:
        await update.message.reply_text("اول باید هدف رو انتخاب کنی.", reply_markup=ATTACK_MENU)
        return
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not target:
        await update.message.reply_text("این بازیکن دیگه وجود نداره.", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return

    now = int(time.time())

    if text == "☄️ موشکی":
        army = get_json_field(attacker, "army")
        missiles = [i for i in army if shop_category_key_of(i) == "air_missile" and army[i] > 0]
        if not missiles:
            await update.message.reply_text("هیچ موشکی نداری! اول از فروشگاه بخر.")
            return
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
            return
        rows_kb = [[f"{item_lookup(m)['name']} ({army[m]} عدد)"] for m in missiles]
        rows_kb.append(["لغو حمله ❌"])
        context.user_data["missile_map"] = {f"{item_lookup(m)['name']} ({army[m]} عدد)": m for m in missiles}
        context.user_data["state"] = "await_missile_choice"
        await update.message.reply_text("کدوم موشک رو شلیک می‌کنی؟", reply_markup=kb(rows_kb))
        return

    if text in ("✈️ هوایی", "🚜 زمینی", "🚢 دریایی"):
        cat_map = {"✈️ هوایی": "air", "🚜 زمینی": "land", "🚢 دریایی": "sea"}
        parent = cat_map[text]
        if now - attacker["last_attack"] < ATTACK_COOLDOWN_SEC:
            wait = (ATTACK_COOLDOWN_SEC - (now - attacker["last_attack"])) // 60
            await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
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
            add_xp(attacker_id, 120)
            lost = record_casualties(target_id, d_army)
            await update.message.reply_text(f"⚔️ حمله {name_fa} موفق بود! ({a_power} vs {d_power})\n🏆 غنیمت: {loot}{CUR}\n💀 تلفات هدف: {lost}", reply_markup=MAIN_MENU)
            await notify_defender(context, target_id, attacker, f"حمله {name_fa}", f"{loot}{CUR} از دست دادی و {lost} قدرت نظامی تلفات دادی!")
        else:
            await update.message.reply_text(f"💥 حمله {name_fa} دفع شد. ({a_power} vs {d_power})", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return

    if text == "🕵️ جاسوسی":
        if now - attacker["last_recon"] < RECON_COOLDOWN_SEC:
            wait = (RECON_COOLDOWN_SEC - (now - attacker["last_recon"])) // 60
            await update.message.reply_text(f"⏳ {wait} دقیقه دیگه صبر کن.")
            return
        update_field(attacker_id, "last_recon", now)
        recon_list = get_json_field(attacker, "recon_targets")
        if target_id not in recon_list:
            recon_list.append(target_id)
        set_json_field(attacker_id, "recon_targets", recon_list)
        t_power = army_power(get_json_field(target, "army"), target["oil"] > 0)
        await update.message.reply_text(f"🕵️ شناسایی موفق!\nقدرت هدف: {t_power}\nدلار: {target['gold']}{CUR}\nحالا امکان ترور باز شده.", reply_markup=ATTACK_TYPE_MENU)
        return

    if text == "🧨 خرابکاری":
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
            await notify_defender(context, target_id, attacker, "خرابکاری زیرساخت", "زیرساخت‌های اقتصادی‌ت خراب شد!")
        else:
            await update.message.reply_text("💥 خرابکاری شکست خورد.", reply_markup=MAIN_MENU)
        context.user_data.clear()
        return

    if text == "🎯 ترور":
        recon_list = get_json_field(attacker, "recon_targets")
        if target_id not in recon_list:
            await update.message.reply_text("اول باید این هدف رو شناسایی (جاسوسی) کنی!")
            return
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
            await notify_defender(context, target_id, attacker, "ترور", f"عملیات ترور موفق! {loot}{CUR} از دست دادی.")
        else:
            await update.message.reply_text("💥 ترور شکست خورد و لو رفت.", reply_markup=MAIN_MENU)
            await notify_defender(context, target_id, attacker, "تلاش ترور ناموفق", "یه تلاش ترور ناموفق علیه‌ت کشف شد!")
        context.user_data.clear()
        return

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

async def handle_missile_fire_text(update, context, text):
    if text == "لغو حمله ❌":
        context.user_data.clear()
        await update.message.reply_text("لغو شد.", reply_markup=MAIN_MENU)
        return
    missile_map = context.user_data.get("missile_map", {})
    missile_id = missile_map.get(text)
    if not missile_id:
        await update.message.reply_text("یکی از گزینه‌های لیست رو انتخاب کن.")
        return
    target_id = context.user_data.get("attack_target_id")
    attacker_id = update.effective_user.id
    attacker = get_user(attacker_id)
    a_army = get_json_field(attacker, "army")
    if a_army.get(missile_id, 0) <= 0:
        await update.message.reply_text("این موشک رو دیگه نداری!")
        return

    now = int(time.time())
    update_field(attacker_id, "last_attack", now)
    a_army[missile_id] -= 1
    if a_army[missile_id] <= 0:
        del a_army[missile_id]
    set_json_field(attacker_id, "army", a_army)

    missile = item_lookup(missile_id)
    travel = missile_travel_seconds(missile["power"])
    await update.message.reply_text(f"☄️ {missile['name']} شلیک شد! زمان تخمینی رسیدن: {travel} ثانیه...", reply_markup=MAIN_MENU)
    context.user_data.clear()

    context.job_queue.run_once(
        deliver_missile_impact, when=travel,
        data={"attacker_id": attacker_id, "target_id": target_id, "missile_id": missile_id}
    )

async def deliver_missile_impact(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    attacker_id, target_id, missile_id = data["attacker_id"], data["target_id"], data["missile_id"]
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    if not attacker or not target:
        return
    missile = item_lookup(missile_id)
    a_army = get_json_field(attacker, "army")
    d_army = get_json_field(target, "army")
    a_power = army_power(a_army, attacker["oil"] > 0) + missile["power"] + random.randint(0, 50)
    d_power = army_power(d_army, target["oil"] > 0) + random.randint(0, 50)

    if a_power > d_power:
        loot = min(target["gold"], random.randint(80, 350))
        add_resource(target_id, "gold", -loot)
        add_resource(attacker_id, "gold", loot)
        add_xp(attacker_id, 100)
        lost = record_casualties(target_id, d_army)
        try:
            await context.bot.send_message(attacker_id, f"☄️ {missile['name']} به هدف اصابت کرد!\nقدرت: {a_power} vs {d_power}\n🏆 غنیمت: {loot}{CUR}\n💀 تلفات هدف: {lost}")
        except Exception:
            pass
        await notify_defender(context, target_id, attacker, f"حمله موشکی ({missile['name']})", f"{loot}{CUR} و {lost} قدرت نظامی از دست دادی!")
    else:
        try:
            await context.bot.send_message(attacker_id, f"💥 {missile['name']} توسط پدافند هدف رهگیری و دفع شد. ({a_power} vs {d_power})")
        except Exception:
            pass

async def notify_defender(context, target_id, attacker_row, attack_name, extra_text):
    kb_ = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ انتقام بگیر", callback_data=f"revenge:{attacker_row['user_id']}")]])
    attacker_name = COUNTRIES.get(attacker_row["country"], {}).get("name", attacker_row["username"])
    try:
        await context.bot.send_message(target_id, f"🚨 حمله دریافت شد!\nنوع عملیات: {attack_name}\nمهاجم: {attacker_name}\n{extra_text}", reply_markup=kb_)
    except Exception:
        pass

async def revenge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[1])
    context.user_data["attack_target_id"] = target_id
    await context.bot.send_message(update.effective_user.id, "نوع عملیات رو انتخاب کن:", reply_markup=ATTACK_TYPE_MENU)

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
    lines = ["🏆 جدول برترین فرماندهان:\n"]
    for i, r in enumerate(ranked, 1):
        score = army_power(get_json_field(r, "army")) + r["gold"]
        name = COUNTRIES.get(r["country"], {}).get("name", r["username"])
        lines.append(f"{i}. {name} — امتیاز {score} (لول {user_level(r)})")
    if not ranked:
        lines.append("هنوز کسی ثبت‌نام نکرده.")
    await update.message.reply_text("\n".join(lines))

async def world_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["🗺 نقشه‌ی جهان — وضعیت مناطق\n"]
    for key, r in REGIONS.items():
        res_str = ", ".join(f"{res}({mult}x)" for res, mult in r["resources"].items())
        ruler = region_ruler(key)
        lines.append(f"{r['emoji']} {r['name']}\nمنابع برتر: {res_str}\nمسلط: 👑 {ruler}\n")
    lines.append("⚓ تنگه‌های استراتژیک: (برای جزئیات، «تنگه‌ها» رو بزن)\n")
    for key, s in STRAITS.items():
        srow = get_strait(key)
        status = "باز 🟢" if srow["is_open"] else "بسته 🔴"
        lines.append(f"  {s['name']}: {status}")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_MENU)

async def my_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = get_user(update.effective_user.id)
    r = REGIONS[row["region"]]
    ruler = region_ruler(row["region"])
    text = f"{r['emoji']} منطقه‌ی تو: {r['name']}\nمنابع برتر: {', '.join(f'{k}({v}x)' for k,v in r['resources'].items())}\nحاکم فعلی: 👑 {ruler}"
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

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
        "همه‌چیز از منوی پایین صفحه قابل دسترسیه: خزانه، فروشگاه، حمله، تجهیزات، تبادلات و بقیه.\n"
        "توی فروشگاه: دسته رو انتخاب کن، آیتم رو بزن، اطلاعاتش رو ببین، بعد تعداد مدنظرت رو تایپ کن.\n"
        "توی حمله: یا جستجو کن یا یوزرنیم بزن، بعد نوع عملیات رو انتخاب کن.\n"
        "/sell, /send, /sanction, /leaderboard, /create_alliance, /join_alliance, /leave_alliance, /announce\n\n"
        "نکته: موشک‌ها موقع شلیک مصرف میشن و یه زمان رسیدن دارن. بدون نفت، هواپیماها کار نمی‌کنن. هر ساعت مالیات از دارایی‌ت کم میشه."
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
    app.add_handler(CallbackQueryHandler(strait_capture_callback, pattern="^straitcapture:"))
    app.add_handler(CallbackQueryHandler(strait_close_callback, pattern="^straitclose:"))
    app.add_handler(CallbackQueryHandler(strait_open_callback, pattern="^straitopen:"))
    app.add_handler(CallbackQueryHandler(revenge_callback, pattern="^revenge:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.job_queue.run_repeating(income_job, interval=INCOME_TICK_SEC, first=INCOME_TICK_SEC)
    app.job_queue.run_repeating(tax_job, interval=TAX_TICK_SEC, first=TAX_TICK_SEC)

    print("🤖 World War Bot v4 در حال اجراست...")
    app.run_polling()

if __name__ == "__main__":
    main()
