# -*- coding: utf-8 -*-
# Zeno Host Bot — Credit: 𐌆ᴇɴᴏ
import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import sqlite3
import json
import logging
import signal
import threading
import re
import sys
import atexit
import requests
import hashlib
import io

# ==================== TEXT BOLD / STYLIZED UNICODE HELPER ====================
def make_bold_unicode(text):
    out = []
    for char in text:
        codepoint = ord(char)
        if 65 <= codepoint <= 90:  # A-Z
            out.append(chr(codepoint - 65 + 0x1D5D4))
        elif 97 <= codepoint <= 122:  # a-z
            out.append(chr(codepoint - 97 + 0x1D5EE))
        elif 48 <= codepoint <= 57:  # 0-9
            out.append(chr(codepoint - 48 + 0x1D7EC))
        else:
            out.append(char)
    return "".join(out)

class StyledKeyboardButton(types.KeyboardButton):
    def __init__(self, text, *args, **kwargs):
        kwargs.pop('style', None) 
        super().__init__(text=text, *args, **kwargs)

class StyledInlineKeyboardButton(types.InlineKeyboardButton):
    def __init__(self, text, *args, **kwargs):
        kwargs.pop('style', None)
        super().__init__(text=text, *args, **kwargs)

# --- Flask Keep Alive ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "𐌆ᴇɴᴏ Host Bot — Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==================== CONFIGURATION & MEDIA URLS ====================
TOKEN = '8944656955:AAG0euNjXMO0tTaGoJrA5R6nRJnOoLS5nfs'
OWNER_ID = 8271186073
ADMIN_ID  = 8271186073
YOUR_USERNAME = '@Zeno098'
WHATSAPP_LINK = 'https://wa.me/919800000000'  # Put your WhatsApp Link here
BOT_NAME = f"{make_bold_unicode('ZENO HOSTING')} 💗"
CREDIT = "𐌆ᴇɴᴏ"

WELCOME_IMAGE_URL = 'https://pin.it/49cqGezjz'
UPLOAD_IMAGE_URL = 'https://pin.it/49cqGezjz' 
SPEED_IMAGE_URL  = 'https://pin.it/49cqGezjz'
STATS_IMAGE_URL  = 'https://pin.it/49cqGezjz'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

FREE_USER_LIMIT = 10
SUBSCRIBED_USER_LIMIT = 15
ADMIN_LIMIT = 999
OWNER_LIMIT = float('inf')
REFER_REWARD_FILES = 1

# ==================== TARGETED SPAM PROTECTION & BAN SYSTEM ====================
user_heavy_action_timestamps = {}
temp_banned_users = {}

SPAM_WINDOW_SECONDS = 20    
MAX_HEAVY_ACTIONS = 10      
BAN_DURATION_MINUTES = 5    

def is_user_banned(user_id):
    if user_id in admin_ids:
        return False, None
    
    now = datetime.now()
    if user_id in temp_banned_users:
        unban_time = temp_banned_users[user_id]
        if now < unban_time:
            remaining = int((unban_time - now).total_seconds())
            return True, f"🚫 **Spam Protection Active!** You performed too many heavy actions.\n⏳ Try again in `{remaining} seconds`."
        else:
            del temp_banned_users[user_id]
            user_heavy_action_timestamps.pop(user_id, None)
            
    return False, None

def track_heavy_action(user_id):
    if user_id in admin_ids:
        return False, None

    now = datetime.now()
    if user_id not in user_heavy_action_timestamps:
        user_heavy_action_timestamps[user_id] = []
        
    timestamps = [t for t in user_heavy_action_timestamps[user_id] if (now - t).total_seconds() <= SPAM_WINDOW_SECONDS]
    timestamps.append(now)
    user_heavy_action_timestamps[user_id] = timestamps

    if len(timestamps) >= MAX_HEAVY_ACTIONS:
        temp_banned_users[user_id] = now + timedelta(minutes=BAN_DURATION_MINUTES)
        return True, f"🚨 **Auto Ban Executed!** Detected 10+ spam actions within 20s.\n🚫 You are banned for **{BAN_DURATION_MINUTES} minutes**!"
        
    return False, None

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)

bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}
bot_locked = False

fake_users_count = 0
fake_scripts_count = 0

processed_messages = set()

force_join_channels = set()
APPROVAL_CHANNEL = ""
UPDATE_CHANNEL = ""

MALWARE_SIGNATURES = [b'MZ', b'\x7fELF', b'\xfe\xed\xfa', b'\xce\xfa\xed\xfe', b'PK', b'Rar!']
ENCRYPTED_FILE_INDICATORS = [b'openssl', b'encrypted', b'cipher', b'AES', b'DES', b'RSA', b'GPG', b'PGP']
SUSPICIOUS_KEYWORDS = [b'ransomware', b'trojan', b'virus', b'malware', b'backdoor', b'exploit', b'payload', b'botnet', b'keylogger', b'rootkit']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_db():
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, expiry TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files (user_id INTEGER, file_name TEXT, file_type TEXT, status TEXT DEFAULT 'Pending', PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users (user_id INTEGER PRIMARY KEY, referred_by INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_type TEXT, channel_val TEXT PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)''')
        
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
            
        c.execute('INSERT OR IGNORE INTO channels VALUES (?, ?)', ('force_join', '@zenoexploit1'))
        c.execute('INSERT OR IGNORE INTO channels VALUES (?, ?)', ('approval', '@zenoexploit1'))
        c.execute('INSERT OR IGNORE INTO channels VALUES (?, ?)', ('update', '@zenoexploit1'))
        
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('fake_users', 0))
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('fake_scripts', 0))
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('free_limit', 10))
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('subscribed_limit', 15))
        c.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', ('refer_reward', 1))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")

def load_data():
    global APPROVAL_CHANNEL, UPDATE_CHANNEL, fake_users_count, fake_scripts_count, FREE_USER_LIMIT, SUBSCRIBED_USER_LIMIT, REFER_REWARD_FILES
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, expiry FROM subscriptions')
        for user_id, expiry in c.fetchall():
            try: user_subscriptions[user_id] = {'expiry': datetime.fromisoformat(expiry)}
            except ValueError: pass
        c.execute('SELECT user_id, file_name, file_type, status FROM user_files')
        for user_id, file_name, file_type, status in c.fetchall():
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id].append((file_name, file_type, status))
        c.execute('SELECT user_id FROM active_users')
        active_users.update(uid for (uid,) in c.fetchall())
        c.execute('SELECT user_id FROM admins')
        admin_ids.update(uid for (uid,) in c.fetchall())
        
        c.execute('SELECT channel_type, channel_val FROM channels')
        for ctype, cval in c.fetchall():
            if ctype == 'force_join': force_join_channels.add(cval)
            elif ctype == 'approval': APPROVAL_CHANNEL = cval
            elif ctype == 'update': UPDATE_CHANNEL = cval
            
        c.execute('SELECT key, value FROM settings')
        for k, v in c.fetchall():
            if k == 'fake_users': fake_users_count = v
            elif k == 'fake_scripts': fake_scripts_count = v
            elif k == 'free_limit': FREE_USER_LIMIT = v
            elif k == 'subscribed_limit': SUBSCRIBED_USER_LIMIT = v
            elif k == 'refer_reward': REFER_REWARD_FILES = v
            
        conn.close()
    except Exception as e: pass

init_db()
load_data()

DB_LOCK = threading.Lock()

def update_setting(key, val):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, val))
        conn.commit()
        conn.close()

def get_referral_count(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT count FROM referrals WHERE user_id=?', (user_id,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else 0

def increment_referral(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT INTO referrals(user_id, count) VALUES(?, 1) ON CONFLICT(user_id) DO UPDATE SET count=count+1', (user_id,))
        conn.commit()
        conn.close()

def save_user_file(user_id, file_name, file_type='py', status='Pending'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files VALUES (?,?,?,?)', (user_id, file_name, file_type, status))
            conn.commit()
            if user_id not in user_files: user_files[user_id] = []
            user_files[user_id] = [(fn,ft,st) for fn,ft,st in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type, status))
        except: pass
        finally: conn.close()

def update_file_status_db(user_id, file_name, status):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('UPDATE user_files SET status=? WHERE user_id=? AND file_name=?', (status, user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [(fn, ft, status if fn == file_name else st) for fn, ft, st in user_files[user_id]]
        except: pass
        finally: conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id=? AND file_name=?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]: del user_files[user_id]
        except: pass
        finally: conn.close()

def add_active_user(user_id, ref_by=0):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id, referred_by) VALUES (?, ?)', (user_id, ref_by))
            conn.commit()
        except: pass
        finally: conn.close()

def save_subscription(user_id, expiry):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO subscriptions VALUES (?,?)', (user_id, expiry.isoformat()))
            conn.commit()
            user_subscriptions[user_id] = {'expiry': expiry}
        except: pass
        finally: conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id=?', (user_id,))
            conn.commit()
            user_subscriptions.pop(user_id, None)
        except: pass
        finally: conn.close()

def add_admin_db(admin_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO admins VALUES (?)', (admin_id,))
            conn.commit()
            admin_ids.add(admin_id)
        except: pass
        finally: conn.close()

def remove_admin_db(admin_id):
    if admin_id == OWNER_ID: return False
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        removed = False
        try:
            c.execute('DELETE FROM admins WHERE user_id=?', (admin_id,))
            conn.commit()
            removed = c.rowcount > 0
            if removed: admin_ids.discard(admin_id)
        except: pass
        finally: conn.close()
        return removed

# ==================== KEYBOARDS ====================
def create_reply_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(StyledKeyboardButton(text=f"📤 {make_bold_unicode('UPLOAD FILE')}"))
    keyboard.row(
        StyledKeyboardButton(text=f"📂 {make_bold_unicode('MY FILES')}"),
        StyledKeyboardButton(text=f"⚡ {make_bold_unicode('SPEED TEST')}")
    )
    keyboard.row(
        StyledKeyboardButton(text=f"📊 {make_bold_unicode('STATISTICS')}"),
        StyledKeyboardButton(text=f"🎁 {make_bold_unicode('REFER & EARN')}")
    )
    keyboard.row(
        StyledKeyboardButton(text=f"📖 {make_bold_unicode('HOW TO USE')}"),
        StyledKeyboardButton(text=f"📦 {make_bold_unicode('MANUAL INSTALL')}")
    )
    if user_id in admin_ids:
        keyboard.row(
            StyledKeyboardButton(text=f"📤 {make_bold_unicode('SEND COMMAND')}"),
            StyledKeyboardButton(text=f"👑 {make_bold_unicode('ADMIN PANEL')}")
        )
    keyboard.row(StyledKeyboardButton(text=f"📞 {make_bold_unicode('CONTACT ADMIN (WHATSAPP)')}"))
    return keyboard

def create_admin_panel():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        StyledInlineKeyboardButton(text=f"💳 {make_bold_unicode('SUBSCRIPTIONS')}", callback_data='subscription'),
        StyledInlineKeyboardButton(text=f"📢 {make_bold_unicode('BROADCAST')}", callback_data='broadcast')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"👥 {make_bold_unicode('USERS LIST')}", callback_data='admin_users_list'),
        StyledInlineKeyboardButton(text=f"🔍 {make_bold_unicode('USER DETAILS')}", callback_data='admin_user_details')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"💬 {make_bold_unicode('DIRECT CHAT')}", callback_data='admin_direct_chat_init'),
        StyledInlineKeyboardButton(text=f"📢 {make_bold_unicode('CHANNELS SETTINGS')}", callback_data='admin_channel_settings')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"📈 {make_bold_unicode('FAKE STATS SETTINGS')}", callback_data='admin_fake_stats_settings'),
        StyledInlineKeyboardButton(text=f"⚙️ {make_bold_unicode('FILE LIMITS')}", callback_data='admin_limits_settings')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"🎁 {make_bold_unicode('REFER REWARD')}", callback_data='admin_refer_reward_setting')
    )
    lock_text = f"🔓 {make_bold_unicode('UNLOCK BOT')}" if bot_locked else f"🔒 {make_bold_unicode('LOCK BOT')}"
    cb_text = 'unlock_bot' if bot_locked else 'lock_bot'
    keyboard.row(
        StyledInlineKeyboardButton(text=lock_text, callback_data=cb_text),
        StyledInlineKeyboardButton(text=f"🟢 {make_bold_unicode('RUN ALL SCRIPTS')}", callback_data='run_all_scripts')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"➕ {make_bold_unicode('ADD ADMIN')}", callback_data='add_admin'),
        StyledInlineKeyboardButton(text=f"➖ {make_bold_unicode('REMOVE ADMIN')}", callback_data='remove_admin')
    )
    keyboard.row(StyledInlineKeyboardButton(text=f"📋 {make_bold_unicode('LIST ADMINS')}", callback_data='list_admins'))
    keyboard.row(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='back_to_main'))
    return keyboard

def create_main_menu_inline(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        StyledInlineKeyboardButton(text=f"📤 {make_bold_unicode('UPLOAD FILE')}", callback_data='upload'),
        StyledInlineKeyboardButton(text=f"📂 {make_bold_unicode('MY FILES')}", callback_data='check_files')
    )
    keyboard.row(
        StyledInlineKeyboardButton(text=f"⚡ {make_bold_unicode('SPEED TEST')}", callback_data='speed'),
        StyledInlineKeyboardButton(text=f"📊 {make_bold_unicode('STATISTICS')}", callback_data='stats')
    )
    if user_id in admin_ids:
        keyboard.row(
            StyledInlineKeyboardButton(text=f"📤 {make_bold_unicode('SEND COMMAND')}", callback_data='send_command'),
            StyledInlineKeyboardButton(text=f"👑 {make_bold_unicode('ADMIN PANEL')}", callback_data='admin_panel')
        )
    else:
        keyboard.row(StyledInlineKeyboardButton(text=f"📤 {make_bold_unicode('SEND COMMAND')}", callback_data='send_command'))
        
    keyboard.row(StyledInlineKeyboardButton(text=f"📞 {make_bold_unicode('WHATSAPP CONTACT')}", url=WHATSAPP_LINK))
    return keyboard

def create_control_buttons(owner_id, file_name, is_running=True):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        keyboard.row(
            StyledInlineKeyboardButton(text=f"🔴 {make_bold_unicode('STOP')}", callback_data=f'stop_{owner_id}_{file_name}'),
            StyledInlineKeyboardButton(text=f"🔄 {make_bold_unicode('RESTART')}", callback_data=f'restart_{owner_id}_{file_name}')
        )
        keyboard.row(
            StyledInlineKeyboardButton(text=f"🗑️ {make_bold_unicode('DELETE')}", callback_data=f'delete_{owner_id}_{file_name}'),
            StyledInlineKeyboardButton(text=f"📜 {make_bold_unicode('LOGS')}", callback_data=f'logs_{owner_id}_{file_name}')
        )
    else:
        keyboard.row(
            StyledInlineKeyboardButton(text=f"🟢 {make_bold_unicode('START')}", callback_data=f'start_{owner_id}_{file_name}'),
            StyledInlineKeyboardButton(text=f"🗑️ {make_bold_unicode('DELETE')}", callback_data=f'delete_{owner_id}_{file_name}')
        )
        keyboard.row(
            StyledInlineKeyboardButton(text=f"📜 {make_bold_unicode('VIEW LOGS')}", callback_data=f'logs_{owner_id}_{file_name}')
        )
    keyboard.row(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='check_files'))
    return keyboard

def create_subscription_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        StyledInlineKeyboardButton(text=f"➕ {make_bold_unicode('ADD SUB')}", callback_data='add_subscription'),
        StyledInlineKeyboardButton(text=f"➖ {make_bold_unicode('REMOVE SUB')}", callback_data='remove_subscription')
    )
    keyboard.row(StyledInlineKeyboardButton(text=f"🔍 {make_bold_unicode('CHECK SUB')}", callback_data='check_subscription'))
    keyboard.row(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='admin_panel'))
    return keyboard

def create_send_command_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        StyledInlineKeyboardButton(text=f"📝 {make_bold_unicode('SEND TO PROCESS')}", callback_data='send_to_process'),
        StyledInlineKeyboardButton(text=f"🗂️ {make_bold_unicode('VIEW ALL LOGS')}", callback_data='view_all_logs')
    )
    keyboard.row(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='back_to_main'))
    return keyboard

# ==================== HELPERS & AUTOMATED MODULES INSTALLER ====================
def is_member(user_id: int) -> bool:
    if user_id in admin_ids: return True
    if not force_join_channels: return True
    for ch in force_join_channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ['left', 'kicked']: return False
        except: pass
    return True

def is_suspicious_file(file_content, file_name):
    file_lower = file_name.lower()
    suspicious_ext = ['.exe','.dll','.bat','.cmd','.scr','.com','.pif','.application','.gadget','.msi','.msp','.hta','.cpl','.msc','.jar','.bin','.deb','.rpm','.apk','.app','.dmg','.iso','.img']
    if any(file_lower.endswith(e) for e in suspicious_ext): return True, f"Suspicious file extension: {file_name}"
    for sig in MALWARE_SIGNATURES:
        if file_content.startswith(sig): return True, f"Malware signature detected"
    sample = file_content[:4096]
    for ind in ENCRYPTED_FILE_INDICATORS:
        if ind in sample: return True, f"Encrypted file indicator: {ind.decode('utf-8', errors='ignore')}"
    sample_text = sample.decode('utf-8', errors='ignore').lower()
    for kw in SUSPICIOUS_KEYWORDS:
        if kw.decode('utf-8').lower() in sample_text: return True, f"Suspicious keyword: {kw.decode('utf-8')}"
    return False, "File appears safe"

def scan_file_for_malware(file_content, file_name, user_id):
    if user_id == OWNER_ID: return True, "Owner bypassed security check"
    is_sus, reason = is_suspicious_file(file_content, file_name)
    if is_sus:
        logger.warning(f"🚨 Malware in {file_name} from {user_id}: {reason}")
        return False, f"Security violation: {reason}"
    return True, "File passed security check"

def get_user_folder(user_id):
    folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(folder, exist_ok=True)
    return folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID: return OWNER_LIMIT
    if user_id in admin_ids: return ADMIN_LIMIT
    ref_count = get_referral_count(user_id)
    bonus_files = ref_count * REFER_REWARD_FILES
    if user_id in user_subscriptions and user_subscriptions[user_id]['expiry'] > datetime.now(): 
        return SUBSCRIBED_USER_LIMIT + bonus_files
    return FREE_USER_LIMIT + bonus_files

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def is_bot_running(owner_id, file_name):
    key = f"{owner_id}_{file_name}"
    info = bot_scripts.get(key)
    if info and info.get('process'):
        try:
            proc = info['process']
            if proc.poll() is None: return True
            else:
                _close_log(info)
                bot_scripts.pop(key, None)
                return False
        except: pass
    return False

def _close_log(info):
    lf = info.get('log_file')
    if lf and hasattr(lf, 'close') and not lf.closed:
        try: lf.close()
        except: pass

def kill_process_tree(process_info):
    key = process_info.get('script_key', 'N/A')
    _close_log(process_info)
    proc = process_info.get('process')
    if not proc: return
    try:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired: proc.kill()
    except: pass

TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI','telegram': 'python-telegram-bot', 'python_telegram_bot': 'python-telegram-bot','aiogram': 'aiogram',
    'pyrogram': 'pyrogram','telethon': 'telethon','requests': 'requests','pillow': 'Pillow', 'asyncio': None,'json': None,'datetime': None,
    'os': None,'sys': None, 'threading': None,'subprocess': None,'zipfile': None,'sqlite3': None
}

def attempt_install_pip(module_name, message=None):
    pkg = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if pkg is None: return False
    try:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        return r.returncode == 0
    except: return False

def attempt_install_npm(module_name, user_folder):
    try:
        r = subprocess.run(['npm', 'install', module_name], capture_output=True, text=True, cwd=user_folder, encoding='utf-8', errors='ignore')
        return r.returncode == 0
    except: return False

def auto_scan_and_install_deps(file_path, user_folder, msg_obj):
    if not os.path.exists(file_path): return
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.py':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            imports = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
            for mod in set(imports): attempt_install_pip(mod)
        except Exception as e: pass
        
    elif ext == '.js':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            requires = re.findall(r"require\(['\"]([^'\"]+)['\"]", content)
            for mod in set(requires):
                if not mod.startswith('.') and not mod.startswith('/'):
                    attempt_install_npm(mod, user_folder)
        except Exception as e: pass

def run_script(script_path, owner_id, user_folder, file_name, msg_obj, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(msg_obj, f"❌ Failed to run `{file_name}` after {max_attempts} attempts.")
        return
    key = f"{owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path): bot.reply_to(msg_obj, f"❌ Script `{file_name}` not found!"); return
        
        auto_scan_and_install_deps(script_path, user_folder, msg_obj)

        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        si = None; cf = 0
        if os.name == 'nt':
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen([sys.executable, script_path], cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE, startupinfo=si, creationflags=cf, encoding='utf-8', errors='ignore')
        bot_scripts[key] = {'process': process, 'log_file': log_file, 'file_name': file_name, 'chat_id': msg_obj.chat.id, 'script_owner_id': owner_id, 'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'py', 'script_key': key}
        bot.reply_to(msg_obj, f"✅ `{file_name}` started! (PID: {process.pid})", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(msg_obj, f"❌ Error: {e}")
        if key in bot_scripts: kill_process_tree(bot_scripts[key]); del bot_scripts[key]

def run_js_script(script_path, owner_id, user_folder, file_name, msg_obj, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        bot.reply_to(msg_obj, f"❌ Failed to run `{file_name}` after {max_attempts} attempts."); return
    key = f"{owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path): bot.reply_to(msg_obj, f"❌ Script `{file_name}` not found!"); return
        
        auto_scan_and_install_deps(script_path, user_folder, msg_obj)

        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        si = None
        if os.name == 'nt':
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen(['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE, startupinfo=si, encoding='utf-8', errors='ignore')
        bot_scripts[key] = {'process': process, 'log_file': log_file, 'file_name': file_name, 'chat_id': msg_obj.chat.id, 'script_owner_id': owner_id, 'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'js', 'script_key': key}
        bot.reply_to(msg_obj, f"✅ `{file_name}` started! (PID: {process.pid})", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(msg_obj, f"❌ Unexpected JS error: {e}")
        if key in bot_scripts: kill_process_tree(bot_scripts[key]); del bot_scripts[key]

# Dynamic Notification Helper
def notify_admins_and_channel(user_id, file_name, file_path):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        StyledInlineKeyboardButton(text=f"✅ {make_bold_unicode('APPROVE')}", callback_data=f"approve_{user_id}_{file_name}"),
        StyledInlineKeyboardButton(text=f"❌ {make_bold_unicode('REJECT')}", callback_data=f"reject_{user_id}_{file_name}")
    )
    markup.row(
        StyledInlineKeyboardButton(text=f"💬 {make_bold_unicode('CHAT WITH USER')}", callback_data=f"chat_{user_id}")
    )
    
    caption_text = f"📥 *New File Pending*\n\n👤 User: `{user_id}`\n📁 File: `{file_name}`"
    
    for admin in admin_ids:
        try:
            with open(file_path, 'rb') as f:
                bot.send_document(admin, f, caption=caption_text, reply_markup=markup, parse_mode='Markdown')
        except:
            bot.send_message(admin, caption_text, reply_markup=markup, parse_mode='Markdown')

    if APPROVAL_CHANNEL:
        try:
            with open(file_path, 'rb') as doc_file:
                bot.send_document(APPROVAL_CHANNEL, doc_file, caption=f"🚀 **New Hosted File Received!**\n\n📁 File Name: `{file_name}`\n👤 Developer ID: `{user_id}`", parse_mode='Markdown')
        except: pass

def handle_zip_file(content, zip_name, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    tmp = None
    if user_id != OWNER_ID:
        ok, reason = scan_file_for_malware(content, zip_name, user_id)
        if not ok: bot.reply_to(message, f"🚨 Security Alert: {reason}"); return
    try:
        tmp = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(tmp, zip_name)
        with open(zip_path, 'wb') as f: f.write(content)
        with zipfile.ZipFile(zip_path, 'r') as zr:
            if user_id != OWNER_ID:
                sus_ext = ['.exe','.dll','.bat','.cmd','.scr','.com']
                for m in zr.infolist():
                    if any(m.filename.lower().endswith(e) for e in sus_ext):
                        bot.reply_to(message, f"🚨 ZIP contains suspicious file: {m.filename}"); return
                    mp = os.path.abspath(os.path.join(tmp, m.filename))
                    if not mp.startswith(os.path.abspath(tmp)): raise zipfile.BadZipFile(f"Unsafe path")
            zr.extractall(tmp)

        target = tmp
        root_files = os.listdir(target)
        if not any(f.endswith(('.py','.js')) for f in root_files):
            for root, dirs, files in os.walk(tmp):
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
                if any(f.endswith(('.py','.js')) for f in files): target = root; break
        if target != tmp:
            for item in os.listdir(target):
                s = os.path.join(target, item); d = os.path.join(tmp, item)
                if os.path.exists(d): shutil.rmtree(d) if os.path.isdir(d) else os.remove(d)
                shutil.move(s, d)

        items = os.listdir(tmp)
        py_files = [f for f in items if f.endswith('.py')]
        js_files = [f for f in items if f.endswith('.js')]
        req_file = 'requirements.txt' if 'requirements.txt' in items else None
        pkg_json = 'package.json'     if 'package.json'      in items else None

        if req_file:
            bot.reply_to(message, "🔄 Installing Python deps...")
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', os.path.join(tmp, req_file)], check=True, capture_output=True, encoding='utf-8', errors='ignore')
            except: pass

        if pkg_json:
            bot.reply_to(message, "🔄 Installing Node deps...")
            try:
                subprocess.run(['npm', 'install'], check=True, capture_output=True, cwd=tmp, encoding='utf-8', errors='ignore')
            except: pass

        main_script = None; file_type = None
        for p in ['main.py','bot.py','app.py']:
            if p in py_files: main_script = p; file_type = 'py'; break
        if not main_script:
            for p in ['index.js','main.js','bot.js','app.js']:
                if p in js_files: main_script = p; file_type = 'js'; break
        if not main_script:
            if py_files: main_script = py_files[0]; file_type = 'py'
            elif js_files: main_script = js_files[0]; file_type = 'js'
        if not main_script:
            bot.reply_to(message, "❌ No `.py` or `.js` found in archive!"); return

        for item in os.listdir(tmp):
            if item == zip_name: continue
            s = os.path.join(tmp, item); d = os.path.join(user_folder, item)
            if os.path.exists(d): shutil.rmtree(d) if os.path.isdir(d) else os.remove(d)
            shutil.move(s, d)

        save_user_file(user_id, main_script, file_type, 'Pending')
        bot.reply_to(message, f"✅ File `{main_script}` uploaded & sent! ⏳ Waiting for Admin Approval.", parse_mode='Markdown')
        
        notify_admins_and_channel(user_id, main_script, os.path.join(user_folder, main_script))

    except Exception as e: bot.reply_to(message, f"❌ Error processing zip: {e}")
    finally:
        if tmp and os.path.exists(tmp):
            try: shutil.rmtree(tmp)
            except: pass

def handle_js_file(path, owner_id, folder, name, msg):
    save_user_file(owner_id, name, 'js', 'Pending')
    bot.reply_to(msg, f"✅ File `{name}` uploaded & sent! ⏳ Waiting for Admin Approval.", parse_mode='Markdown')
    notify_admins_and_channel(owner_id, name, path)

def handle_py_file(path, owner_id, folder, name, msg):
    save_user_file(owner_id, name, 'py', 'Pending')
    bot.reply_to(msg, f"✅ File `{name}` uploaded & sent! ⏳ Waiting for Admin Approval.", parse_mode='Markdown')
    notify_admins_and_channel(owner_id, name, path)

def send_to_process_init(message):
    user_id = message.from_user.id
    running = [(k, v) for k, v in bot_scripts.items() if (user_id == v['script_owner_id'] or user_id in admin_ids) and is_bot_running(v['script_owner_id'], v['file_name'])]
    if not running: bot.reply_to(message, "❌ No running scripts found."); return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, info in running: markup.add(StyledInlineKeyboardButton(text=f"{info['file_name']} (UID: {info['script_owner_id']})", callback_data=f'sendcmd_select_{key}'))
    markup.add(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='send_command'))
    bot.reply_to(message, "📝 Select script:", reply_markup=markup)

def process_send_command(message, script_key):
    if script_key not in bot_scripts: bot.reply_to(message, "❌ Script no longer running."); return
    info = bot_scripts[script_key]
    try:
        proc = info['process']
        if proc and proc.poll() is None:
            proc.stdin.write(message.text + '\n'); proc.stdin.flush()
            bot.reply_to(message, f"✅ Sent to `{info['file_name']}`:\n`{message.text}`", parse_mode='Markdown')
        else: bot.reply_to(message, f"❌ `{info['file_name']}` is not running.", parse_mode='Markdown')
    except Exception as e: bot.reply_to(message, f"❌ Error: {e}")

def view_all_logs(message):
    user_id = message.from_user.id
    folder = get_user_folder(user_id)
    logs = []
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.log'): logs.append((f, os.path.getsize(os.path.join(folder, f)), os.path.join(folder, f)))
    if not logs: bot.reply_to(message, "📜 No log files found."); return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for lf, sz, _ in sorted(logs): markup.add(StyledInlineKeyboardButton(text=f"{lf} ({sz/1024:.1f} KB)", callback_data=f'viewlog_{user_id}_{lf}'))
    markup.add(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='send_command'))
    bot.reply_to(message, "📜 Log files:", reply_markup=markup)

def send_log_file(message, log_path, log_filename):
    try:
        if os.path.getsize(log_path) > 50 * 1024 * 1024: bot.reply_to(message, "❌ Log too large (>50 MB)."); return
        with open(log_path, 'rb') as f: bot.send_document(message.chat.id, f, caption=f"📜 {log_filename}")
    except Exception as e: bot.reply_to(message, f"❌ Error sending log: {e}")

# ==================== LOGICS FOR ORIGINAL BUTTON HANDLERS ====================
def _logic_send_welcome(message):
    user_id  = message.from_user.id
    chat_id  = message.chat.id
    name     = message.from_user.first_name
    username = message.from_user.username

    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith('ref_'):
        try:
            referrer_id = int(text_parts[1].replace('ref_', ''))
            if referrer_id != user_id and user_id not in active_users:
                increment_referral(referrer_id)
                add_active_user(user_id, ref_by=referrer_id)
                try: bot.send_message(referrer_id, f"🎉 *New Referral Joined!* You earned +{REFER_REWARD_FILES} file upload slot!", parse_mode='Markdown')
                except: pass
        except: pass

    if bot_locked and user_id not in admin_ids:
        bot.send_message(chat_id, "⚠️ Bot is currently locked by admin. Try later."); return

    if not is_member(user_id):
        markup = types.InlineKeyboardMarkup()
        for idx, ch in enumerate(force_join_channels, 1):
            ch_clean = ch.lstrip('@')
            markup.add(StyledInlineKeyboardButton(text=f"✅ Join Channel #{idx}", url=f"https://t.me/{ch_clean}"))
        markup.add(StyledInlineKeyboardButton(text="🔄 I Joined — Verify", callback_data='verify_join'))
        bot.send_message(chat_id, f"👋 Welcome to *{BOT_NAME}*!\n\n⚠️ You must join our required channels first to continue.", reply_markup=markup, parse_mode='Markdown')
        return

    if user_id not in active_users:
        add_active_user(user_id)
        try:
            real_name_html = f'<a href="tg://user?id={user_id}">{name}</a>'
            new_user_alert = (
                f"🔍 <b>New User Joined</b>\n\n"
                f"🙂 User - {real_name_html}\n"
                f"✅ ID - <code>{user_id}</code>"
            )
            bot.send_message(OWNER_ID, new_user_alert, parse_mode='HTML')
        except: pass

    file_limit   = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str    = str(file_limit) if file_limit != float('inf') else "∞"
    expiry_info  = ""

    if user_id == OWNER_ID:        user_status = "👑 Owner"
    elif user_id in admin_ids:     user_status = "🛡️ Admin"
    elif user_id in user_subscriptions:
        exp = user_subscriptions[user_id].get('expiry')
        if exp and exp > datetime.now():
            user_status  = "⭐ Premium"
            expiry_info  = f"\n⏳ Expires in: {(exp - datetime.now()).days} day(s)"
        else:
            user_status = "🆓 Free User"
            remove_subscription_db(user_id)
    else: user_status = "🆓 Free User"

    welcome_text = (
        f"💀 *{BOT_NAME}*\n━━━━━━━━━━━━━━━━━━━\n👋 Hello, {name}!\n\n🆔 ID: `{user_id}`\n👤 Username: `@{username or 'Not set'}`\n🔰 Status: {user_status}{expiry_info}\n📁 Files: {current_files} / {limit_str}\n🎁 Total Referrals: `{get_referral_count(user_id)}`\n━━━━━━━━━━━━━━━━━━━\n🤖 Host & run Python or JS scripts.\nUpload `.py`, `.js`, or `.zip` archives.\n\n👇 Use the menu below to get started.\n━━━━━━━━━━━━━━━━━━━\n✨ Credit: {CREDIT}"
    )

    reply_kb = create_reply_keyboard(user_id)
    try: bot.send_photo(chat_id, WELCOME_IMAGE_URL, caption=welcome_text, reply_markup=reply_kb, parse_mode='Markdown')
    except: bot.send_message(chat_id, welcome_text, reply_markup=reply_kb, parse_mode='Markdown')

def _logic_upload_file(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids: bot.reply_to(message, "⚠️ Bot locked. Cannot accept files."); return
    limit = get_user_file_limit(user_id)
    count = get_user_file_count(user_id)
    if count >= limit: bot.reply_to(message, f"⚠️ File limit reached ({count}/{str(limit) if limit != float('inf') else '∞'}). Delete a file first."); return
    
    upload_msg = "📤 Send your `.py`, `.js`, or `.zip` file now."
    try: bot.send_photo(message.chat.id, UPLOAD_IMAGE_URL, caption=upload_msg, parse_mode='Markdown')
    except: bot.reply_to(message, upload_msg, parse_mode='Markdown')

# RESTORED ORIGINAL MY FILES FUNCTION (Lists uploaded files)
def _logic_check_files(message):
    user_id = message.from_user.id
    files   = user_files.get(user_id, [])
    if not files: 
        bot.reply_to(message, "📂 You have no files uploaded yet.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_item in sorted(files):
        fn, ft, st = file_item[0], file_item[1], file_item[2] if len(file_item) > 2 else 'Approved'
        if st == 'Pending': 
            markup.add(StyledInlineKeyboardButton(text=f"⏳ {fn} [{ft}] (Pending)", callback_data=f'file_{user_id}_{fn}'))
        else:
            running = is_bot_running(user_id, fn)
            markup.add(StyledInlineKeyboardButton(text=f"{'🟢' if running else '🔴'} {fn} [{ft}]", callback_data=f'file_{user_id}_{fn}'))
    bot.reply_to(message, "📂 *Your Files* — tap to manage:", reply_markup=markup, parse_mode='Markdown')

def _logic_bot_speed(message):
    t0   = time.time()
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        ms = round((time.time() - t0) * 1000, 2)
        uid = message.from_user.id
        if uid == OWNER_ID:     lvl = "👑 Owner"
        elif uid in admin_ids:  lvl = "🛡️ Admin"
        elif uid in user_subscriptions and user_subscriptions[uid].get('expiry', datetime.min) > datetime.now(): lvl = "⭐ Premium"
        else: lvl = "🆓 Free"
        text = f"⚡ *Speed Report*\n━━━━━━━━━━━━━━━\n📶 Ping: `{ms} ms`\n🚦 Bot: {'🔒 Locked' if bot_locked else '🟢 Online'}\n👤 You: {lvl}"
        
        try: bot.send_photo(message.chat.id, SPEED_IMAGE_URL, caption=text, parse_mode='Markdown')
        except: bot.reply_to(message, text, parse_mode='Markdown')
    except Exception as e: bot.reply_to(message, f"❌ Speed test failed: {e}")

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(StyledInlineKeyboardButton(text=f"💬 {make_bold_unicode('CONTACT')} {CREDIT}", url=f'https://t.me/{YOUR_USERNAME.lstrip("@")}'))
    bot.reply_to(message, "📞 Tap to contact the owner/developer:", reply_markup=markup)

def _logic_subscriptions_panel(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    bot.reply_to(message, "💳 *Subscription Manager*", reply_markup=create_subscription_menu(), parse_mode='Markdown')

def _logic_how_to_use(message):
    guide = (
        "📖 *HOW TO USE ZENO HOSTING BOT*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ *Upload Script:* Click **Upload File** button & send `.py`, `.js`, or `.zip` file.\n"
        "2️⃣ *Admin Approval:* Wait for admin to approve your uploaded file.\n"
        "3️⃣ *Start Script:* Go to **My Files**, select your approved file and click **START** 🟢.\n"
        "4️⃣ *Manual Module Install:* If your bot gives missing module error, use **Manual Install** button.\n"
        "5️⃣ *Refer & Earn:* Invite friends to increase your file hosting limits dynamically!\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, guide, parse_mode='Markdown')

def _logic_manual_install(message):
    msg = bot.reply_to(
        message, 
        "📦 *MANUAL MODULE INSTALLATION*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Type package name to install via Pip or NPM.\n"
        "💡 *Examples:*\n"
        "• `pip pyTelegramBotAPI`\n"
        "• `pip requests`\n"
        "• `npm express`\n\n"
        "✍️ Enter command now or type /cancel:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_manual_install)

def process_manual_install(message):
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    text = message.text.strip().split(maxsplit=1)
    if len(text) < 2:
        bot.reply_to(message, "❌ Invalid format. Use `pip <package>` or `npm <package>`.")
        return
    
    mgr, pkg = text[0].lower(), text[1].strip()
    wait = bot.reply_to(message, f"⏳ Installing `{pkg}` via `{mgr}`...", parse_mode='Markdown')
    
    success = False
    if mgr == 'pip':
        success = attempt_install_pip(pkg, message)
    elif mgr == 'npm':
        user_folder = get_user_folder(message.from_user.id)
        success = attempt_install_npm(pkg, user_folder)
        
    if success:
        bot.edit_message_text(f"✅ Package `{pkg}` installed successfully!", message.chat.id, wait.message_id, parse_mode='Markdown')
    else:
        bot.edit_message_text(f"❌ Failed to install `{pkg}`. Check package name.", message.chat.id, wait.message_id, parse_mode='Markdown')

def _logic_refer_earn(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    ref_count = get_referral_count(user_id)
    
    text = (
        f"🎁 *REFER & EARN SYSTEM*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Your Referrals: `{ref_count}`\n"
        f"⭐ File Slot Bonus Per Refer: `+{REFER_REWARD_FILES} Files`\n\n"
        f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
        f"💡 Share this link with your friends. When they join, you get extra file hosting slots!"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

def _logic_whatsapp_contact(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(StyledInlineKeyboardButton(text="💬 Open WhatsApp Contact", url=WHATSAPP_LINK))
    bot.reply_to(message, "📞 Click below to chat directly with Owner on WhatsApp:", reply_markup=markup)

def _logic_send_command(message):
    if bot_locked and message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Bot locked."); return
    bot.reply_to(message, "📤 *Send Command*", reply_markup=create_send_command_menu(), parse_mode='Markdown')

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    bot.reply_to(message, "👑 *Admin Panel*", reply_markup=create_admin_panel(), parse_mode='Markdown')

def _logic_statistics(message):
    user_id = message.from_user.id
    running_real = sum(1 for k, v in bot_scripts.items() if is_bot_running(v['script_owner_id'], v['file_name']))
    
    boostUsers = len(active_users) + fake_users_count
    boostOrders = running_real + fake_scripts_count
    total_files = sum(len(v) for v in user_files.values())

    chart_url = (
        f"https://quickchart.io/chart?bkg=white&c={{type:%27bar%27,data:{{labels:[%27Statistics%27],"
        f"datasets:[{{label:%27👥%20Users%27,data:[{boostUsers}],backgroundColor:%27rgba(54,162,235,0.5)%27,borderColor:%27rgb(54,162,235)%27,borderWidth:2}},"
        f"{{label:%27📦%20Orders%27,data:[{boostOrders}],backgroundColor:%27rgba(255,99,132,0.5)%27,borderColor:%27rgb(255,99,132)%27,borderWidth:2}}]}},"
        f"options:{{title:{{display:true,text:%27📊%20BOT%20OVERVIEW%27,fontSize:16}}}}}}"
    )

    caption_text = (
        f"📊 **Statistics**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 **Total Users**: {boostUsers}\n"
        f"📁 **File Records**: {total_files}\n"
        f"🟢 **Active Scripts**: {boostOrders}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✨ Credit: {CREDIT}"
    )

    try:
        response = requests.get(chart_url, timeout=10)
        if response.status_code == 200:
            photo_bytes = io.BytesIO(response.content)
            photo_bytes.name = 'chart.png'
            bot.send_photo(message.chat.id, photo_bytes, caption=caption_text, parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, caption_text, parse_mode='Markdown')
    except Exception:
        bot.send_message(message.chat.id, caption_text, parse_mode='Markdown')

def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids: 
        bot.reply_to(message, "⚠️ Admin only.")
        return
    guide_text = (
        "📢 *ADVANCED BROADCAST SYSTEM*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Send your message (Text, Photo, Video, Document). To add inline buttons, write them at the end of text:\n\n"
        "📝 *Format:* `Button Name - Link/Command - Color`\n\n"
        "🎨 *Available Colors:*\n"
        "• `primary` (Default/Blue)\n"
        "• `success` (Green/Safe)\n"
        "• `danger` (Red/Warning)\n"
        "• `secondary` (Grey/Neutral)\n\n"
        "💡 *Example Message:*\n"
        "```text\n"
        "Hello Users! We have updated servers.\n\n"
        "💎 Buy Premium - [https://t.me/Zeno098](https://t.me/Zeno098) - primary\n"
        "```\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 *Send broadcast message now, or type /cancel to abort.*"
    )
    msg = bot.send_message(message.chat.id, guide_text, parse_mode='Markdown', disable_web_page_preview=True)
    bot.register_next_step_handler(msg, process_broadcast_message)

def _logic_toggle_lock_bot(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    global bot_locked
    bot_locked = not bot_locked
    bot.reply_to(message, f"Bot is now {'🔒 Locked' if bot_locked else '🟢 Unlocked'}.")

def _logic_run_all_scripts(moc):
    if isinstance(moc, types.Message): uid = moc.from_user.id; cid = moc.chat.id; reply = lambda t, **kw: bot.reply_to(moc, t, **kw); msg_for_script = moc
    else: uid = moc.from_user.id; cid = moc.message.chat.id; bot.answer_callback_query(moc.id); reply = lambda t, **kw: bot.send_message(cid, t, **kw); msg_for_script = moc.message
    if uid not in admin_ids: reply("⚠️ Admin only."); return
    reply("⏳ Starting all stopped scripts...")
    started = 0; skipped = 0
    for tuid, files in dict(user_files).items():
        folder = get_user_folder(tuid)
        for file_item in files:
            fname, ftype, st = file_item[0], file_item[1], file_item[2] if len(file_item) > 2 else 'Approved'
            if st != 'Approved' or is_bot_running(tuid, fname): continue
            fpath = os.path.join(folder, fname)
            if not os.path.exists(fpath): skipped += 1; continue
            try:
                fn = run_script if ftype == 'py' else run_js_script
                threading.Thread(target=fn, args=(fpath, tuid, folder, fname, msg_for_script)).start()
                started += 1; time.sleep(0.5)
            except: skipped += 1
    reply(f"✅ Done! Started: {started} | Skipped: {skipped}")

# RESTORED EXACT FULL BUTTON MAPPING TO ORIGINAL FUNCTIONS
BUTTON_MAP = {
    f"📤 {make_bold_unicode('UPLOAD FILE')}":          _logic_upload_file,
    f"📂 {make_bold_unicode('MY FILES')}":             _logic_check_files,
    f"⚡ {make_bold_unicode('SPEED TEST')}":           _logic_bot_speed,
    f"📊 {make_bold_unicode('STATISTICS')}":           _logic_statistics,
    f"📖 {make_bold_unicode('HOW TO USE')}":           _logic_how_to_use,
    f"📦 {make_bold_unicode('MANUAL INSTALL')}":        _logic_manual_install,
    f"🎁 {make_bold_unicode('REFER & EARN')}":          _logic_refer_earn,
    f"📤 {make_bold_unicode('SEND COMMAND')}":         _logic_send_command,
    f"👑 {make_bold_unicode('ADMIN PANEL')}":          _logic_admin_panel,
    f"📞 {make_bold_unicode('CONTACT ADMIN (WHATSAPP)')}": _logic_whatsapp_contact,
}

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    banned, msg = is_user_banned(message.from_user.id)
    if banned: bot.reply_to(message, msg, parse_mode='Markdown'); return
    _logic_send_welcome(message)

@bot.message_handler(commands=['status'])
def cmd_status(message): 
    banned, msg = is_user_banned(message.from_user.id)
    if banned: bot.reply_to(message, msg, parse_mode='Markdown'); return
    _logic_statistics(message)

@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    banned, msg = is_user_banned(message.from_user.id)
    if banned: bot.reply_to(message, msg, parse_mode='Markdown'); return
    t0  = time.time()
    msg_res = bot.reply_to(message, "🏓 Pong!")
    bot.edit_message_text(f"🏓 Pong! `{round((time.time() - t0) * 1000, 2)} ms`", message.chat.id, msg_res.message_id, parse_mode='Markdown')

# ==================== ADMIN FAKE STATS CONTROL ====================
def admin_show_fake_stats_panel(chat_id, message_id=None):
    text = (
        f"📈 *FAKE STATS CONTROLLER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *Fake Users Extra Count:* `{fake_users_count}`\n"
        f"🟢 *Fake Active Scripts Extra Count:* `{fake_scripts_count}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 These numbers will be added on top of real users & scripts."
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        StyledInlineKeyboardButton(text="✏️ Set Fake Users", callback_data="set_fake_users"),
        StyledInlineKeyboardButton(text="✏️ Set Fake Scripts", callback_data="set_fake_scripts")
    )
    markup.row(
        StyledInlineKeyboardButton(text="🔄 Reset Extra Stats", callback_data="reset_fake_stats")
    )
    markup.row(StyledInlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    
    if message_id:
        try: bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except: pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def process_set_fake_users(message):
    global fake_users_count
    try:
        val = int(message.text.strip())
        fake_users_count = val
        update_setting('fake_users', val)
        bot.reply_to(message, f"✅ Fake Users count set to `{val}`!", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number format.")

def process_set_fake_scripts(message):
    global fake_scripts_count
    try:
        val = int(message.text.strip())
        fake_scripts_count = val
        update_setting('fake_scripts', val)
        bot.reply_to(message, f"✅ Fake Scripts count set to `{val}`!", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number format.")

# ==================== ADMIN DIRECT CHAT & USERS MANAGEMENT ====================
def admin_prompt_user_details(message):
    msg = bot.reply_to(message, "🔍 Enter User ID to fetch details:")
    bot.register_next_step_handler(msg, process_admin_user_details)

def process_admin_user_details(message):
    try:
        uid = int(message.text.strip())
        files = user_files.get(uid, [])
        file_list_str = ""
        for idx, f in enumerate(files, 1):
            fname, ftype = f[0], f[1]
            fstatus = f[2] if len(f) > 2 else 'Approved'
            status_icon = "⏳" if fstatus == 'Pending' else ("🟢" if is_bot_running(uid, fname) else "🔴")
            file_list_str += f"{idx}. {status_icon} `{fname}` `[{ftype}]` ({fstatus})\n"
            
        msg_text = (
            f"👤 *USER DETAILS*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 *User ID:* `{uid}`\n"
            f"📁 *Total Files:* `{len(files)}`\n\n"
            f"📋 *Files List:*\n"
            f"{file_list_str or 'No files uploaded.'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(StyledInlineKeyboardButton(text=f"💬 Chat with `{uid}`", callback_data=f"chat_{uid}"))
        bot.reply_to(message, msg_text, reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid User ID. Enter a numeric ID.")

def admin_prompt_direct_chat_id(message):
    msg = bot.reply_to(message, "💬 Enter target User ID for direct chat:")
    bot.register_next_step_handler(msg, process_admin_chat_target_id)

def process_admin_chat_target_id(message):
    try:
        target_uid = int(message.text.strip())
        msg = bot.reply_to(message, f"✍️ Send your message/media/sticker for `{target_uid}`:")
        bot.register_next_step_handler(msg, lambda m: process_direct_chat_reply(m, target_uid))
    except:
        bot.reply_to(message, "❌ Invalid User ID. Chat cancelled.")

# ==================== DYNAMIC CHANNELS SETTINGS ====================
def admin_show_channel_settings(chat_id, message_id=None):
    fj_str = "\n".join(f"• `{c}`" for c in force_join_channels) or "(None)"
    text = (
        f"⚙️ *CHANNELS MANAGEMENT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📣 *Force Join Channels:*\n{fj_str}\n\n"
        f"🚀 *Approval Channel:* `{APPROVAL_CHANNEL or 'None'}`\n"
        f"📢 *Update Channel:* `{UPDATE_CHANNEL or 'None'}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        StyledInlineKeyboardButton(text="➕ Add Force Join", callback_data="add_fj_chan"),
        StyledInlineKeyboardButton(text="➖ Remove Force Join", callback_data="rem_fj_chan")
    )
    markup.row(
        StyledInlineKeyboardButton(text="✏️ Set Approval Chan", callback_data="set_approval_chan"),
        StyledInlineKeyboardButton(text="✏️ Set Update Chan", callback_data="set_update_chan")
    )
    markup.row(StyledInlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    
    if message_id:
        try: bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except: pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def process_add_fj_chan(message):
    chan = message.text.strip()
    if not chan.startswith('@'): chan = '@' + chan
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO channels VALUES (?,?)', ('force_join', chan))
        conn.commit()
        conn.close()
    force_join_channels.add(chan)
    bot.reply_to(message, f"✅ Force Join Channel `{chan}` added!", parse_mode='Markdown')

def process_rem_fj_chan(message):
    chan = message.text.strip()
    if not chan.startswith('@'): chan = '@' + chan
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM channels WHERE channel_type=? AND channel_val=?', ('force_join', chan))
        conn.commit()
        conn.close()
    force_join_channels.discard(chan)
    bot.reply_to(message, f"✅ Force Join Channel `{chan}` removed!", parse_mode='Markdown')

def process_set_approval_chan(message):
    global APPROVAL_CHANNEL
    chan = message.text.strip()
    if not chan.startswith('@'): chan = '@' + chan
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM channels WHERE channel_type=?', ('approval',))
        c.execute('INSERT INTO channels VALUES (?,?)', ('approval', chan))
        conn.commit()
        conn.close()
    APPROVAL_CHANNEL = chan
    bot.reply_to(message, f"✅ Approval Channel set to `{chan}`!", parse_mode='Markdown')

def process_set_update_chan(message):
    global UPDATE_CHANNEL
    chan = message.text.strip()
    if not chan.startswith('@'): chan = '@' + chan
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM channels WHERE channel_type=?', ('update',))
        c.execute('INSERT INTO channels VALUES (?,?)', ('update', chan))
        conn.commit()
        conn.close()
    UPDATE_CHANNEL = chan
    bot.reply_to(message, f"✅ Update Channel set to `{chan}`!", parse_mode='Markdown')

# ==================== ADMIN CONTROL LOGICS ====================
def admin_show_limits_panel(chat_id, message_id=None):
    text = (
        f"⚙️ *FILE LIMITS CONTROLLER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆓 *Free User Allowed Files:* `{FREE_USER_LIMIT}`\n"
        f"⭐ *Subscription User Allowed Files:* `{SUBSCRIBED_USER_LIMIT}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        StyledInlineKeyboardButton(text="✏️ Set Free Limit", callback_data="set_free_limit"),
        StyledInlineKeyboardButton(text="✏️ Set Subscribed Limit", callback_data="set_sub_limit")
    )
    markup.row(StyledInlineKeyboardButton(text="🔙 Back", callback_data="admin_panel"))
    if message_id: bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
    else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

def process_set_free_limit(message):
    global FREE_USER_LIMIT
    try:
        val = int(message.text.strip())
        FREE_USER_LIMIT = val
        update_setting('free_limit', val)
        bot.reply_to(message, f"✅ Free User limit updated to `{val}` files!", parse_mode='Markdown')
    except: bot.reply_to(message, "❌ Invalid number.")

def process_set_sub_limit(message):
    global SUBSCRIBED_USER_LIMIT
    try:
        val = int(message.text.strip())
        SUBSCRIBED_USER_LIMIT = val
        update_setting('subscribed_limit', val)
        bot.reply_to(message, f"✅ Subscribed User limit updated to `{val}` files!", parse_mode='Markdown')
    except: bot.reply_to(message, "❌ Invalid number.")

def process_set_refer_reward(message):
    global REFER_REWARD_FILES
    try:
        val = int(message.text.strip())
        REFER_REWARD_FILES = val
        update_setting('refer_reward', val)
        bot.reply_to(message, f"✅ Referral Reward updated to `+{val}` Extra Upload Slots Per Refer!", parse_mode='Markdown')
    except: bot.reply_to(message, "❌ Invalid number.")

@bot.message_handler(func=lambda m: m.text is not None)
def handle_buttons(message):
    banned, msg = is_user_banned(message.from_user.id)
    if banned: bot.reply_to(message, msg, parse_mode='Markdown'); return
    fn = BUTTON_MAP.get(message.text)
    if fn: fn(message)

@bot.message_handler(commands=['uploadfile'])
def cmd_upload(m): _logic_upload_file(m)
@bot.message_handler(commands=['checkfiles'])
def cmd_check(m):  _logic_check_files(m)
@bot.message_handler(commands=['speed'])
def cmd_speed(m):  _logic_bot_speed(m)
@bot.message_handler(commands=['stats'])
def cmd_stats(m):  _logic_statistics(m)
@bot.message_handler(commands=['sendcommand'])
def cmd_sendcmd(m): _logic_send_command(m)
@bot.message_handler(commands=['contact'])
def cmd_contact(m): _logic_contact_owner(m)
@bot.message_handler(commands=['admin'])
def cmd_admin(m):  _logic_admin_panel(m)

# HEAVY ACTION: MULTI FILE UPLOADS TRACKING
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    banned, ban_msg = is_user_banned(user_id)
    if banned: bot.reply_to(message, ban_msg, parse_mode='Markdown'); return
    banned_now, ban_trigger_msg = track_heavy_action(user_id)
    if banned_now: bot.reply_to(message, ban_trigger_msg, parse_mode='Markdown'); return

    doc = message.document
    if not is_member(user_id): bot.reply_to(message, f"⚠️ Join channels first!"); return

    limit = get_user_file_limit(user_id)
    count = get_user_file_count(user_id)
    if count >= limit: bot.reply_to(message, f"⚠️ File limit ({count}/{str(limit) if limit != float('inf') else '∞'}) reached."); return

    fname = doc.file_name
    if not fname: bot.reply_to(message, "⚠️ File has no name."); return
    ext = os.path.splitext(fname)[1].lower()
    if ext not in ['.py', '.js', '.zip']: bot.reply_to(message, "⚠️ Only `.py`, `.js`, `.zip` allowed."); return
    if doc.file_size > 20 * 1024 * 1024: bot.reply_to(message, "⚠️ File too large (max 20 MB)."); return

    try:
        wait = bot.reply_to(message, f"⏳ Downloading `{fname}`...", parse_mode='Markdown')
        finfo = bot.get_file(doc.file_id)
        content = bot.download_file(finfo.file_path)

        if user_id != OWNER_ID:
            ok, reason = scan_file_for_malware(content, fname, user_id)
            if not ok: bot.edit_message_text(f"🚨 Security Alert: {reason}", message.chat.id, wait.message_id); return

        bot.edit_message_text(f"✅ Downloaded `{fname}`. Processing...", message.chat.id, wait.message_id, parse_mode='Markdown')
        user_folder = get_user_folder(user_id)

        if ext == '.zip': handle_zip_file(content, fname, message)
        else:
            fpath = os.path.join(user_folder, fname)
            with open(fpath, 'wb') as f: f.write(content)
            if ext == '.js': handle_js_file(fpath, user_id, user_folder, fname, message)
            else:            handle_py_file(fpath, user_id, user_folder, fname, message)

    except telebot.apihelper.ApiTelegramException as e: bot.reply_to(message, f"❌ Telegram API error: {e}")
    except Exception as e: bot.reply_to(message, f"❌ Unexpected error: {e}")

def parse_broadcast_text(raw_text):
    if not raw_text: return "", None
    lines = raw_text.split('\n')
    message_lines = []
    markup = types.InlineKeyboardMarkup(row_width=2)
    has_buttons = False
    for line in lines:
        parts = [p.strip() for p in line.split('-')]
        if len(parts) >= 3:
            btn_text, btn_target, btn_color = parts[0], parts[1], parts[2].lower()
            has_buttons = True
            if btn_target.startswith('http://') or btn_target.startswith('https://') or btn_target.startswith('t.me/'):
                url = btn_target if btn_target.startswith('http') else f"https://{btn_target}"
                markup.add(StyledInlineKeyboardButton(text=btn_text, url=url))
            else: markup.add(StyledInlineKeyboardButton(text=btn_text, callback_data=f"bcast_cmd_{btn_target}"))
        else: message_lines.append(line)
    final_text = "\n".join(message_lines).strip()
    return final_text, markup if has_buttons else None

def sendcmd_select_callback(call):
    key = call.data.replace('sendcmd_select_', '')
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, f"📝 Enter command for `{key}`:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, lambda m: process_send_command(m, key))

# HEAVY ACTION 2: DIRECT ADMIN CHAT SPAM TRACKING
def start_direct_chat_reply(call):
    bot.answer_callback_query(call.id)
    target_id = int(call.data.split('_')[1])
    msg = bot.send_message(call.message.chat.id, f"💬 Send your message, image, or sticker for User `{target_id}`:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, lambda m: process_direct_chat_reply(m, target_id))

def process_direct_chat_reply(message, target_id):
    sender_id = message.from_user.id

    banned, ban_msg = is_user_banned(sender_id)
    if banned:
        bot.reply_to(message, ban_msg, parse_mode='Markdown')
        return

    banned_now, ban_trigger_msg = track_heavy_action(sender_id)
    if banned_now:
        bot.reply_to(message, ban_trigger_msg, parse_mode='Markdown')
        return

    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "Message cancelled.")
        return
    
    sender_name = message.from_user.first_name
    
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(StyledInlineKeyboardButton(text="💬 Reply Back", callback_data=f"chat_{sender_id}"))
        
        header = f"📩 *Message from {'Admin' if sender_id in admin_ids else sender_name}:*"
        
        if message.text:
            bot.send_message(target_id, f"{header}\n\n{message.text}", reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(target_id, header, parse_mode='Markdown')
            bot.copy_message(target_id, message.chat.id, message.message_id, reply_markup=markup)
            
        bot.reply_to(message, f"✅ Delivered to `{target_id}`!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to send: {e}")

# ==================== CALLBACK ROUTER ====================
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    global bot_locked, fake_users_count, fake_scripts_count
    user_id = call.from_user.id
    data    = call.data

    bot.answer_callback_query(call.id)

    # 1. APPROVAL & REJECT HANDLERS
    if data.startswith('approve_'):
        if user_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True)
            return
        
        parts = data.split('_', 2)
        oid = int(parts[1])
        fname = parts[2]
        
        update_file_status_db(oid, fname, 'Approved')
        try:
            bot.edit_message_caption(f"✅ File `{fname}` from User `{oid}` has been **Approved**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except:
            try: bot.edit_message_text(f"✅ File `{fname}` from User `{oid}` has been **Approved**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            except: pass
            
        try:
            bot.send_message(oid, f"🎉 Your file `{fname}` has been approved by Admin! You can now manage and start it from **My Files**.", parse_mode='Markdown')
        except: pass
        return

    if data.startswith('reject_'):
        if user_id not in admin_ids:
            bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True)
            return
            
        parts = data.split('_', 2)
        oid = int(parts[1])
        fname = parts[2]
        
        remove_user_file_db(oid, fname)
        folder = get_user_folder(oid)
        try:
            fpath = os.path.join(folder, fname)
            if os.path.exists(fpath): os.remove(fpath)
        except: pass
        
        try:
            bot.edit_message_caption(f"❌ File `{fname}` from User `{oid}` has been **Rejected & Deleted**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except:
            try: bot.edit_message_text(f"❌ File `{fname}` from User `{oid}` has been **Rejected & Deleted**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
            except: pass
            
        try:
            bot.send_message(oid, f"❌ Your file `{fname}` was rejected by Admin.", parse_mode='Markdown')
        except: pass
        return

    # 2. OTHER HANDLERS
    if data.startswith('chat_'):
        start_direct_chat_reply(call)
        return

    if data == 'admin_limits_settings':
        if user_id in admin_ids: admin_show_limits_panel(call.message.chat.id, call.message.message_id)
        return

    if data == 'set_free_limit':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter maximum files for FREE USERS:")
        bot.register_next_step_handler(msg, process_set_free_limit)
        return

    if data == 'set_sub_limit':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter maximum files for SUBSCRIBED USERS:")
        bot.register_next_step_handler(msg, process_set_sub_limit)
        return

    if data == 'admin_refer_reward_setting':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter Extra File Upload Slots Per Successful Referral:")
        bot.register_next_step_handler(msg, process_set_refer_reward)
        return

    if data == 'admin_fake_stats_settings':
        if user_id in admin_ids:
            admin_show_fake_stats_panel(call.message.chat.id, call.message.message_id)
        return

    if data == 'set_fake_users':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter fake user count to add on stats:")
        bot.register_next_step_handler(msg, process_set_fake_users)
        return

    if data == 'set_fake_scripts':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter fake active scripts count to add on stats:")
        bot.register_next_step_handler(msg, process_set_fake_scripts)
        return

    if data == 'reset_fake_stats':
        fake_users_count = 0
        fake_scripts_count = 0
        update_setting('fake_users', 0)
        update_setting('fake_scripts', 0)
        bot.send_message(call.message.chat.id, "✅ Fake Stats Reset to 0.")
        admin_show_fake_stats_panel(call.message.chat.id)
        return

    if data == 'admin_users_list':
        if user_id in admin_ids:
            u_str = "\n".join(f"• `{uid}`" for uid in sorted(active_users)) or "No active users."
            bot.send_message(call.message.chat.id, f"👥 *ACTIVE USERS LIST* (`{len(active_users)}`):\n\n{u_str}", parse_mode='Markdown')
        return

    if data == 'admin_user_details':
        if user_id in admin_ids:
            admin_prompt_user_details(call.message)
        return

    if data == 'admin_direct_chat_init':
        if user_id in admin_ids:
            admin_prompt_direct_chat_id(call.message)
        return

    if data == 'admin_channel_settings':
        if user_id in admin_ids:
            admin_show_channel_settings(call.message.chat.id, call.message.message_id)
        return

    if data == 'add_fj_chan':
        msg = bot.send_message(call.message.chat.id, "➕ Enter Channel Username to ADD to Force Join (e.g., `@mychannel`):")
        bot.register_next_step_handler(msg, process_add_fj_chan)
        return

    if data == 'rem_fj_chan':
        msg = bot.send_message(call.message.chat.id, "➖ Enter Channel Username to REMOVE from Force Join:")
        bot.register_next_step_handler(msg, process_rem_fj_chan)
        return

    if data == 'set_approval_chan':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter new Approval Channel (e.g., `@approvalchan`):")
        bot.register_next_step_handler(msg, process_set_approval_chan)
        return

    if data == 'set_update_chan':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter new Update Channel (e.g., `@updatechan`):")
        bot.register_next_step_handler(msg, process_set_update_chan)
        return

    if data == 'verify_join':
        if is_member(user_id):
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except: pass
            _logic_send_welcome(call.message)
        else: bot.answer_callback_query(call.id, "❌ You haven't joined all required channels yet!", show_alert=True)
        return

    if bot_locked and user_id not in admin_ids and data not in ['back_to_main','speed','stats']:
        bot.answer_callback_query(call.id, "⚠️ Bot locked.", show_alert=True); return

    try:
        if   data == 'upload':           upload_callback(call)
        elif data == 'check_files':      check_files_callback(call)
        elif data.startswith('file_'):   file_control_callback(call)
        elif data.startswith('start_'):  start_bot_callback(call)
        elif data.startswith('stop_'):   stop_bot_callback(call)
        elif data.startswith('restart_'):restart_bot_callback(call)
        elif data.startswith('delete_'): delete_bot_callback(call)
        elif data.startswith('logs_'):   logs_bot_callback(call)
        elif data == 'speed':            speed_callback(call)
        elif data == 'back_to_main':     back_to_main_callback(call)
        elif data == 'send_command':     send_command_callback(call)
        elif data == 'send_to_process':  send_to_process_callback(call)
        elif data.startswith('sendcmd_select_'): sendcmd_select_callback(call)
        elif data == 'view_all_logs':    view_all_logs_callback(call)
        elif data.startswith('viewlog_'):viewlog_callback(call)
        elif data == 'subscription':     _admin_cb(call, subscription_management_callback)
        elif data == 'stats':            stats_callback(call)
        elif data == 'lock_bot':         _admin_cb(call, lock_bot_callback)
        elif data == 'unlock_bot':       _admin_cb(call, unlock_bot_callback)
        elif data == 'run_all_scripts':  _admin_cb(call, run_all_scripts_callback)
        elif data == 'broadcast':        
            if user_id in admin_ids:
                _logic_broadcast_init(call.message)
        elif data == 'admin_panel':      _admin_cb(call, admin_panel_callback)
        elif data == 'add_admin':        _owner_cb(call, add_admin_init_callback)
        elif data == 'remove_admin':     _owner_cb(call, remove_admin_init_callback)
        elif data == 'list_admins':      _admin_cb(call, list_admins_callback)
        elif data == 'add_subscription': _admin_cb(call, add_subscription_init_callback)
        elif data == 'remove_subscription': _admin_cb(call, remove_subscription_init_callback)
        elif data == 'check_subscription':  _admin_cb(call, check_subscription_init_callback)
        elif data.startswith('confirm_broadcast_'): handle_confirm_broadcast(call)
        elif data == 'cancel_broadcast': handle_cancel_broadcast(call)
        elif data.startswith('bcast_cmd_'):
            cmd_target = data.replace('bcast_cmd_', '')
            bot.answer_callback_query(call.id, f"Executed: {cmd_target}")
        else: pass
    except: pass

def _admin_cb(call, fn):
    if call.from_user.id not in admin_ids: bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True); return
    fn(call)

def _owner_cb(call, fn):
    if call.from_user.id != OWNER_ID: bot.answer_callback_query(call.id, "⚠️ Owner only.", show_alert=True); return
    fn(call)

def upload_callback(call):
    user_id = call.from_user.id
    limit = get_user_file_limit(user_id); count = get_user_file_count(user_id)
    if count >= limit: bot.answer_callback_query(call.id, f"⚠️ File limit ({count}/{str(limit) if limit != float('inf') else '∞'}) reached.", show_alert=True); return
    bot.send_message(call.message.chat.id, "📤 Send your `.py`, `.js`, or `.zip` file.", parse_mode='Markdown')

def check_files_callback(call):
    user_id = call.from_user.id
    files   = user_files.get(user_id, [])
    if not files:
        bot.answer_callback_query(call.id, "⚠️ No files uploaded.", show_alert=True)
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='back_to_main'))
            bot.edit_message_text("📂 No files yet.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_item in sorted(files):
        fn, ft, st = file_item[0], file_item[1], file_item[2] if len(file_item) > 2 else 'Approved'
        if st == 'Pending': markup.add(StyledInlineKeyboardButton(text=f"⏳ {fn} [{ft}] (Pending)", callback_data=f'file_{user_id}_{fn}'))
        else:
            icon = "🟢" if is_bot_running(user_id, fn) else "🔴"
            markup.add(StyledInlineKeyboardButton(text=f"{icon} {fn} [{ft}]", callback_data=f'file_{user_id}_{fn}'))
    markup.add(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='back_to_main'))
    try: bot.edit_message_text("📂 *Your Files*:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
    except: pass

def file_control_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        files = user_files.get(oid, [])
        file_record = next((f for f in files if f[0] == fname), None)
        if not file_record: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        ft, st = file_record[1], file_record[2] if len(file_record) > 2 else 'Approved'
        
        if st == 'Pending':
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(StyledInlineKeyboardButton(text=f"🗑️ {make_bold_unicode('DELETE')}", callback_data=f'delete_{oid}_{fname}'))
            markup.add(StyledInlineKeyboardButton(text=f"🔙 {make_bold_unicode('BACK')}", callback_data='check_files'))
            bot.edit_message_text(f"⚙️ *{fname}* `[{ft}]`\nStatus: ⏳ Pending Admin Approval", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            running = is_bot_running(oid, fname)
            status = "🟢 Running" if running else "🔴 Stopped"
            bot.edit_message_text(f"⚙️ *{fname}* `[{ft}]`\nOwner: `{oid}` | Status: {status}", call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(oid, fname, running), parse_mode='Markdown')
    except: bot.answer_callback_query(call.id, "Error.", show_alert=True)

def start_bot_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        files = user_files.get(oid, [])
        fi = next((f for f in files if f[0] == fname), None)
        if not fi: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        if (fi[2] if len(fi) > 2 else 'Approved') != 'Approved': bot.answer_callback_query(call.id, "⚠️ File is pending approval by Admin!", show_alert=True); return

        ft = fi[1]; folder = get_user_folder(oid); fpath = os.path.join(folder, fname)
        if not os.path.exists(fpath): bot.answer_callback_query(call.id, f"⚠️ File missing. Re-upload.", show_alert=True); remove_user_file_db(oid, fname); return
        if is_bot_running(oid, fname): bot.answer_callback_query(call.id, "⚠️ Already running.", show_alert=True); return
        fn = run_script if ft == 'py' else run_js_script
        threading.Thread(target=fn, args=(fpath, oid, folder, fname, call.message)).start()
        time.sleep(1.5)
        running = is_bot_running(oid, fname)
        try: bot.edit_message_text(f"⚙️ *{fname}* `[{ft}]`\nStatus: {'🟢 Running' if running else '🟡 Starting...'}", call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(oid, fname, running), parse_mode='Markdown')
        except: pass
    except: bot.answer_callback_query(call.id, "Error starting.", show_alert=True)

def stop_bot_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        files = user_files.get(oid, [])
        fi = next((f for f in files if f[0] == fname), None)
        if not fi: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        ft = fi[1]; key = f"{oid}_{fname}"
        if not is_bot_running(oid, fname): bot.answer_callback_query(call.id, "⚠️ Not running.", show_alert=True); return
        info = bot_scripts.get(key)
        if info: kill_process_tree(info); bot_scripts.pop(key, None)
        try: bot.edit_message_text(f"⚙️ *{fname}* `[{ft}]`\nStatus: 🔴 Stopped", call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(oid, fname, False), parse_mode='Markdown')
        except: pass
    except: bot.answer_callback_query(call.id, "Error stopping.", show_alert=True)

def restart_bot_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        files = user_files.get(oid, [])
        fi = next((f for f in files if f[0] == fname), None)
        if not fi: bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        if (fi[2] if len(fi) > 2 else 'Approved') != 'Approved': bot.answer_callback_query(call.id, "⚠️ File is pending approval!", show_alert=True); return
        ft = fi[1]; folder = get_user_folder(oid); fpath = os.path.join(folder, fname)
        if not os.path.exists(fpath): bot.answer_callback_query(call.id, "⚠️ File missing.", show_alert=True); remove_user_file_db(oid, fname); return
        key = f"{oid}_{fname}"
        if is_bot_running(oid, fname):
            info = bot_scripts.get(key)
            if info: kill_process_tree(info); bot_scripts.pop(key, None); time.sleep(1.5)
        fn = run_script if ft == 'py' else run_js_script
        threading.Thread(target=fn, args=(fpath, oid, folder, fname, call.message)).start()
        time.sleep(1.5)
        running = is_bot_running(oid, fname)
        try: bot.edit_message_text(f"⚙️ *{fname}* `[{ft}]`\nStatus: {'🟢 Running' if running else '🟡 Starting...'}", call.message.chat.id, call.message.message_id, reply_markup=create_control_buttons(oid, fname, running), parse_mode='Markdown')
        except: pass
    except: bot.answer_callback_query(call.id, "Error restarting.", show_alert=True)

def delete_bot_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        if not any(f[0] == fname for f in user_files.get(oid, [])): bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        key = f"{oid}_{fname}"
        if is_bot_running(oid, fname):
            info = bot_scripts.get(key)
            if info: kill_process_tree(info); bot_scripts.pop(key, None)
        folder = get_user_folder(oid)
        for p in [os.path.join(folder, fname), os.path.join(folder, f"{os.path.splitext(fname)[0]}.log")]:
            try:
                if os.path.exists(p): os.remove(p)
            except: pass
        remove_user_file_db(oid, fname)
        try: bot.edit_message_text(f"🗑️ `{fname}` deleted successfully!", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except: pass
    except: bot.answer_callback_query(call.id, "Error deleting.", show_alert=True)

def logs_bot_callback(call):
    try:
        _, oid_str, fname = call.data.split('_', 2); oid = int(oid_str); uid = call.from_user.id
        if not (uid == oid or uid in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        if not any(f[0] == fname for f in user_files.get(oid, [])): bot.answer_callback_query(call.id, "⚠️ File not found.", show_alert=True); return
        log_path = os.path.join(get_user_folder(oid), f"{os.path.splitext(fname)[0]}.log")
        if not os.path.exists(log_path): bot.answer_callback_query(call.id, "⚠️ No logs yet.", show_alert=True); return
        size = os.path.getsize(log_path)
        if size == 0: content = "(Log is empty)"
        elif size > 100 * 1024:
            with open(log_path, 'rb') as f: f.seek(-100*1024, os.SEEK_END); raw = f.read()
            content = "(Last 100 KB)\n...\n" + raw.decode('utf-8', errors='ignore')
        else:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        if len(content) > 4000: content = "...\n" + content[-3900:]
        if not content.strip(): content = "(Empty)"
        bot.send_message(call.message.chat.id, f"📜 *Logs* — `{fname}`:\n```\n{content}\n```", parse_mode='Markdown')
    except: bot.answer_callback_query(call.id, "Error fetching logs.", show_alert=True)

def speed_callback(call):
    uid = call.from_user.id; cid = call.message.chat.id
    t0  = time.time()
    try:
        bot.send_chat_action(cid, 'typing')
        ms = round((time.time() - t0) * 1000, 2)
        if uid == OWNER_ID:    lvl = "👑 Owner"
        elif uid in admin_ids: lvl = "🛡️ Admin"
        elif uid in user_subscriptions and user_subscriptions[uid].get('expiry', datetime.min) > datetime.now(): lvl = "⭐ Premium"
        else: lvl = "🆓 Free"
        text = f"⚡ *Speed Report*\n━━━━━━━━━━━━━━━\n📶 Ping: `{ms} ms`\n🚦 Bot: {'🔒 Locked' if bot_locked else '🟢 Online'}\n👤 You: {lvl}\n━━━━━━━━━━━━━━━"
        try:
            bot.edit_message_text(text, cid, call.message.message_id, reply_markup=create_main_menu_inline(uid), parse_mode='Markdown')
        except:
            bot.send_message(cid, text, reply_markup=create_main_menu_inline(uid), parse_mode='Markdown')
    except: bot.answer_callback_query(call.id, "Error.", show_alert=True)

def back_to_main_callback(call):
    uid = call.from_user.id
    limit = get_user_file_limit(uid); count = get_user_file_count(uid)
    ls = str(limit) if limit != float('inf') else "∞"
    if uid == OWNER_ID:    st = "👑 Owner"
    elif uid in admin_ids: st = "🛡️ Admin"
    elif uid in user_subscriptions:
        exp = user_subscriptions[uid].get('expiry')
        st  = "⭐ Premium" if exp and exp > datetime.now() else "🆓 Free"
    else: st = "🆓 Free"
    text = f"💀 *{BOT_NAME}*\n━━━━━━━━━━━━━━━\n👋 {call.from_user.first_name}\n🆔 `{uid}` | 🔰 {st}\n📁 Files: {count}/{ls}\n━━━━━━━━━━━━━━━"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=create_main_menu_inline(uid), parse_mode='Markdown')
    except: pass

def send_command_callback(call):
    try: bot.edit_message_text("📤 *Send Command*", call.message.chat.id, call.message.message_id, reply_markup=create_send_command_menu(), parse_mode='Markdown')
    except: pass

def send_to_process_callback(call):
    msg = bot.send_message(call.message.chat.id, "📝 Type your command:")
    bot.register_next_step_handler(msg, send_to_process_init)

def view_all_logs_callback(call):
    view_all_logs(call.message)

def viewlog_callback(call):
    try:
        _, uid_str, lf = call.data.split('_', 2); uid = int(uid_str); req = call.from_user.id
        if not (req == uid or req in admin_ids): bot.answer_callback_query(call.id, "⚠️ Permission denied.", show_alert=True); return
        lpath = os.path.join(get_user_folder(uid), lf)
        if not os.path.exists(lpath): bot.answer_callback_query(call.id, "❌ Log not found.", show_alert=True); return
        send_log_file(call.message, lpath, lf)
    except: bot.answer_callback_query(call.id, "Error.", show_alert=True)

def stats_callback(call):
    _logic_statistics(call.message)

def subscription_management_callback(call):
    try: bot.edit_message_text("💳 *Subscription Manager*", call.message.chat.id, call.message.message_id, reply_markup=create_subscription_menu(), parse_mode='Markdown')
    except: pass

def lock_bot_callback(call):
    global bot_locked; bot_locked = True
    try: bot.edit_message_text("👑 *Admin Panel*", call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel(), parse_mode='Markdown')
    except: pass

def unlock_bot_callback(call):
    global bot_locked; bot_locked = False
    try: bot.edit_message_text("👑 *Admin Panel*", call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel(), parse_mode='Markdown')
    except: pass

def run_all_scripts_callback(call): _logic_run_all_scripts(call)

def process_broadcast_message(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Broadcast cancelled."); return
    if not message.text and not (message.photo or message.video or message.document):
        msg = bot.reply_to(message, "⚠️ Empty message. Send content or /cancel.")
        bot.register_next_step_handler(msg, process_broadcast_message); return
    
    raw_text = message.text or message.caption or ""
    clean_text, broadcast_markup = parse_broadcast_text(raw_text)
    
    if not broadcast_markup: broadcast_markup = types.InlineKeyboardMarkup()
    
    broadcast_markup.row(
        StyledInlineKeyboardButton(text=f"✅ {make_bold_unicode('CONFIRM')}", callback_data=f"confirm_broadcast_{message.message_id}"),
        StyledInlineKeyboardButton(text=f"❌ {make_bold_unicode('CANCEL')}",  callback_data="cancel_broadcast")
    )
    preview = clean_text[:800] if clean_text else "(media/buttons)"
    bot.reply_to(message, f"📢 Broadcast to *{len(active_users)}* users?\n\nPreview:\n```\n{preview}\n```", reply_markup=broadcast_markup, parse_mode='Markdown')

def handle_confirm_broadcast(call):
    if call.from_user.id not in admin_ids: bot.answer_callback_query(call.id, "⚠️ Admin only.", show_alert=True); return
    try:
        orig = call.message.reply_to_message
        if not orig: raise ValueError("Original message not found.")
        text = photo = video = caption = None
        if orig.text:    text  = orig.text
        elif orig.photo: photo = orig.photo[-1].file_id; caption = orig.caption
        elif orig.video: video = orig.video.file_id;     caption = orig.caption
        else: raise ValueError("Unsupported media type.")
        bot.edit_message_text(f"📢 Broadcasting to {len(active_users)} users...", call.message.chat.id, call.message.message_id)
        threading.Thread(target=execute_broadcast, args=(text, photo, video, caption, call.message.chat.id)).start()
    except Exception as e: bot.edit_message_text(f"❌ Error: {e}", call.message.chat.id, call.message.message_id)

def handle_cancel_broadcast(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

def execute_broadcast(text, photo, video, caption, admin_cid):
    sent = failed = blocked = 0
    users = list(active_users)
    clean_text, broadcast_markup = parse_broadcast_text(text or caption or "")
    
    for i, uid in enumerate(users):
        try:
            if text:  bot.send_message(uid, clean_text, reply_markup=broadcast_markup, parse_mode='Markdown')
            elif photo: bot.send_photo(uid, photo, caption=clean_text, reply_markup=broadcast_markup, parse_mode='Markdown' if clean_text else None)
            elif video: bot.send_video(uid, video, caption=clean_text, reply_markup=broadcast_markup, parse_mode='Markdown' if clean_text else None)
            sent += 1
        except telebot.apihelper.ApiTelegramException as e:
            s = str(e).lower()
            if any(x in s for x in ["blocked","deactivated","not found","kicked"]): blocked += 1
            elif "flood" in s or "too many" in s:
                m = re.search(r"retry after (\d+)", s)
                wait = int(m.group(1)) + 1 if m else 5
                time.sleep(wait)
                try:
                    if text:  bot.send_message(uid, clean_text, reply_markup=broadcast_markup, parse_mode='Markdown')
                    elif photo: bot.send_photo(uid, photo, caption=clean_text, reply_markup=broadcast_markup)
                    elif video: bot.send_video(uid, video, caption=clean_text, reply_markup=broadcast_markup)
                    sent += 1
                except: failed += 1
            else: failed += 1
        except: failed += 1
        if (i+1) % 25 == 0: time.sleep(1.5)
        elif i % 5 == 0:    time.sleep(0.2)
    result = f"📢 *Broadcast Done!*\n✅ Sent: {sent} | ❌ Failed: {failed} | 🚫 Blocked: {blocked}\n👥 Total: {len(users)}"
    try: bot.send_message(admin_cid, result, parse_mode='Markdown')
    except: pass

def admin_panel_callback(call):
    try: bot.edit_message_text("👑 *Admin Panel*", call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel(), parse_mode='Markdown')
    except: pass

def add_admin_init_callback(call):
    msg = bot.send_message(call.message.chat.id, "👑 Enter User ID to promote. /cancel to abort.")
    bot.register_next_step_handler(msg, process_add_admin_id)

def process_add_admin_id(message):
    if message.from_user.id != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        nid = int(message.text.strip())
        if nid == OWNER_ID: bot.reply_to(message, "⚠️ Already owner."); return
        if nid in admin_ids: bot.reply_to(message, f"⚠️ `{nid}` is already admin."); return
        add_admin_db(nid)
        bot.reply_to(message, f"✅ User `{nid}` is now Admin.", parse_mode='Markdown')
        try: bot.send_message(nid, "🎉 You are now an Admin!")
        except: pass
    except ValueError:
        msg = bot.reply_to(message, "⚠️ Invalid ID. Try again or /cancel.")
        bot.register_next_step_handler(msg, process_add_admin_id)

def remove_admin_init_callback(call):
    msg = bot.send_message(call.message.chat.id, "👑 Enter Admin ID to demote. /cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_admin_id)

def process_remove_admin_id(message):
    if message.from_user.id != OWNER_ID: bot.reply_to(message, "⚠️ Owner only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        rid = int(message.text.strip())
        if rid == OWNER_ID: bot.reply_to(message, "⚠️ Cannot remove owner."); return
        if rid not in admin_ids: bot.reply_to(message, f"⚠️ `{rid}` is not an admin."); return
        if remove_admin_db(rid):
            bot.reply_to(message, f"✅ Admin `{rid}` removed.", parse_mode='Markdown')
            try: bot.send_message(rid, "ℹ️ You are no longer an Admin.")
            except: pass
        else: bot.reply_to(message, f"❌ Failed to remove `{rid}`.", parse_mode='Markdown')
    except ValueError:
        msg = bot.reply_to(message, "⚠️ Invalid ID. /cancel to abort.")
        bot.register_next_step_handler(msg, process_remove_admin_id)

def list_admins_callback(call):
    lines = "\n".join(f"• `{a}` {'👑' if a == OWNER_ID else ''}" for a in sorted(admin_ids))
    try: bot.edit_message_text(f"👑 *Admin List*:\n\n{lines or '(none)'}", call.message.chat.id, call.message.message_id, reply_markup=create_admin_panel(), parse_mode='Markdown')
    except: pass

def add_subscription_init_callback(call):
    msg = bot.send_message(call.message.chat.id, "💳 Enter: `USER_ID DAYS`\n/cancel to abort.", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_add_subscription_details)

def process_add_subscription_details(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        parts = message.text.split()
        if len(parts) != 2: raise ValueError("Format: USER_ID DAYS")
        uid, days = int(parts[0]), int(parts[1])
        if uid <= 0 or days <= 0: raise ValueError("Values must be positive")
        base = user_subscriptions.get(uid, {}).get('expiry', datetime.now())
        if base < datetime.now(): base = datetime.now()
        exp = base + timedelta(days=days)
        save_subscription(uid, exp)
        bot.reply_to(message, f"✅ Sub for `{uid}` extended by {days} days. Expires: `{exp:%Y-%m-%d}`", parse_mode='Markdown')
        try: bot.send_message(uid, f"🎉 Sub activated! Expires: {exp:%Y-%m-%d}")
        except: pass
    except ValueError as e:
        msg = bot.reply_to(message, f"⚠️ {e}. Try again or /cancel.")
        bot.register_next_step_handler(msg, process_add_subscription_details)

def remove_subscription_init_callback(call):
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID to remove sub. /cancel to abort.")
    bot.register_next_step_handler(msg, process_remove_subscription_id)

def process_remove_subscription_id(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        uid = int(message.text.strip())
        if uid not in user_subscriptions: bot.reply_to(message, f"⚠️ No sub found for `{uid}`.", parse_mode='Markdown'); return
        remove_subscription_db(uid)
        bot.reply_to(message, f"✅ Sub for `{uid}` removed.", parse_mode='Markdown')
        try: bot.send_message(uid, "ℹ️ Your subscription was removed by admin.")
        except: pass
    except ValueError:
        msg = bot.reply_to(message, "⚠️ Invalid ID. /cancel to abort.")
        bot.register_next_step_handler(msg, process_remove_subscription_id)

def check_subscription_init_callback(call):
    msg = bot.send_message(call.message.chat.id, "💳 Enter User ID to check. /cancel to abort.")
    bot.register_next_step_handler(msg, process_check_subscription_id)

def process_check_subscription_id(message):
    if message.from_user.id not in admin_ids: bot.reply_to(message, "⚠️ Admin only."); return
    if message.text and message.text.lower() == '/cancel': bot.reply_to(message, "Cancelled."); return
    try:
        uid = int(message.text.strip())
        if uid in user_subscriptions:
            exp = user_subscriptions[uid].get('expiry')
            if exp and exp > datetime.now():
                bot.reply_to(message, f"✅ `{uid}` has active sub.\nExpires: `{exp:%Y-%m-%d}` ({(exp - datetime.now()).days} days left)", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"⚠️ `{uid}` sub expired.", parse_mode='Markdown')
                remove_subscription_db(uid)
        else: bot.reply_to(message, f"ℹ️ `{uid}` has no subscription.", parse_mode='Markdown')
    except ValueError:
        msg = bot.reply_to(message, "⚠️ Invalid ID. /cancel to abort.")
        bot.register_next_step_handler(msg, process_check_subscription_id)

def cleanup():
    logger.warning("Shutting down — killing all scripts...")
    for key in list(bot_scripts.keys()):
        if key in bot_scripts: kill_process_tree(bot_scripts[key])
    logger.warning("Cleanup done.")

atexit.register(cleanup)

if __name__ == '__main__':
    logger.info(f"\n{'='*45}\n  💀 {BOT_NAME}\n  Credit : {CREDIT}\n  Owner  : {OWNER_ID}\n  Python : {sys.version.split()[0]}\n{'='*45}")
    keep_alive()
    logger.info("🚀 Bot polling started...")
    while True:
        try: bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except requests.exceptions.ReadTimeout: logger.warning("ReadTimeout — restarting in 5s..."); time.sleep(5)
        except requests.exceptions.ConnectionError as e: logger.error(f"ConnectionError: {e} — retry in 15s..."); time.sleep(15)
        except Exception as e: logger.critical(f"💥 Polling crashed: {e}", exc_info=True); time.sleep(30)
        finally: time.sleep(1)
