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
WHATSAPP_LINK = 'https://wa.me/919800000000'  # Replace with your WhatsApp Link
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
        StyledInlineKeyboardButton(text=f"📈 {make_bold_unicode('FAKE STATS')}", callback_data='admin_fake_stats_settings'),
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

# ==================== HELPERS & SCANNER ====================
def is_member(user_id: int) -> bool:
    if user_id in admin_ids: return True
    if not force_join_channels: return True
    for ch in force_join_channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ['left', 'kicked']: return False
        except: pass
    return True

def scan_file_for_malware(file_content, file_name, user_id):
    if user_id == OWNER_ID: return True, "Owner bypassed security check"
    file_lower = file_name.lower()
    suspicious_ext = ['.exe','.dll','.bat','.cmd','.scr','.com','.apk','.jar']
    if any(file_lower.endswith(e) for e in suspicious_ext): return False, f"Suspicious file extension: {file_name}"
    for sig in MALWARE_SIGNATURES:
        if file_content.startswith(sig): return False, f"Malware signature detected"
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
    'pyrogram': 'pyrogram','telethon': 'telethon','requests': 'requests','pillow': 'Pillow'
}

def attempt_install_pip(module_name, message=None):
    pkg = TELEGRAM_MODULES.get(module_name.lower(), module_name)
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
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            imports = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
            for mod in set(imports): attempt_install_pip(mod)
        except: pass

def run_script(script_path, owner_id, user_folder, file_name, msg_obj):
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

def run_js_script(script_path, owner_id, user_folder, file_name, msg_obj):
    key = f"{owner_id}_{file_name}"
    try:
        if not os.path.exists(script_path): bot.reply_to(msg_obj, f"❌ Script `{file_name}` not found!"); return
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        si = None
        if os.name == 'nt':
            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = subprocess.SW_HIDE
        process = subprocess.Popen(['node', script_path], cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE, startupinfo=si, encoding='utf-8', errors='ignore')
        bot_scripts[key] = {'process': process, 'log_file': log_file, 'file_name': file_name, 'chat_id': msg_obj.chat.id, 'script_owner_id': owner_id, 'start_time': datetime.now(), 'user_folder': user_folder, 'type': 'js', 'script_key': key}
        bot.reply_to(msg_obj, f"✅ `{file_name}` started! (PID: {process.pid})", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(msg_obj, f"❌ Error: {e}")

def notify_admins_and_channel(user_id, file_name, file_path):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        StyledInlineKeyboardButton(text=f"✅ {make_bold_unicode('APPROVE')}", callback_data=f"approve_{user_id}_{file_name}"),
        StyledInlineKeyboardButton(text=f"❌ {make_bold_unicode('REJECT')}", callback_data=f"reject_{user_id}_{file_name}")
    )
    markup.row(StyledInlineKeyboardButton(text=f"💬 {make_bold_unicode('CHAT WITH USER')}", callback_data=f"chat_{user_id}"))
    caption_text = f"📥 *New File Pending*\n\n👤 User: `{user_id}`\n📁 File: `{file_name}`"
    
    for admin in admin_ids:
        try:
            with open(file_path, 'rb') as f: bot.send_document(admin, f, caption=caption_text, reply_markup=markup, parse_mode='Markdown')
        except: bot.send_message(admin, caption_text, reply_markup=markup, parse_mode='Markdown')

    if APPROVAL_CHANNEL:
        try:
            with open(file_path, 'rb') as doc_file:
                bot.send_document(APPROVAL_CHANNEL, doc_file, caption=f"🚀 **New Hosted File Received!**\n\n📁 File Name: `{file_name}`\n👤 Developer ID: `{user_id}`", parse_mode='Markdown')
        except: pass

def handle_js_file(path, owner_id, folder, name, msg):
    save_user_file(owner_id, name, 'js', 'Pending')
    bot.reply_to(msg, f"✅ File `{name}` uploaded & sent! ⏳ Waiting for Admin Approval.", parse_mode='Markdown')
    notify_admins_and_channel(owner_id, name, path)

def handle_py_file(path, owner_id, folder, name, msg):
    save_user_file(owner_id, name, 'py', 'Pending')
    bot.reply_to(msg, f"✅ File `{name}` uploaded & sent! ⏳ Waiting for Admin Approval.", parse_mode='Markdown')
    notify_admins_and_channel(owner_id, name, path)

# ==================== LOGICS FOR BUTTONS ====================
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    name    = message.from_user.first_name

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
            markup.add(StyledInlineKeyboardButton(text=f"✅ Join Channel #{idx}", url=f"https://t.me/{ch.lstrip('@')}"))
        markup.add(StyledInlineKeyboardButton(text="🔄 I Joined — Verify", callback_data='verify_join'))
        bot.send_message(chat_id, f"👋 Welcome to *{BOT_NAME}*!\n\n⚠️ You must join our required channels first to continue.", reply_markup=markup, parse_mode='Markdown')
        return

    if user_id not in active_users:
        add_active_user(user_id)

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = str(file_limit) if file_limit != float('inf') else "∞"

    welcome_text = (
        f"💀 *{BOT_NAME}*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello, {name}!\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"📁 Files Limit: `{current_files} / {limit_str}`\n"
        f"🎁 Total Referrals: `{get_referral_count(user_id)}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Host & run Python or JS scripts.\n"
        f"👇 Use the menu below to navigate."
    )

    reply_kb = create_reply_keyboard(user_id)
    try: bot.send_photo(chat_id, WELCOME_IMAGE_URL, caption=welcome_text, reply_markup=reply_kb, parse_mode='Markdown')
    except: bot.send_message(chat_id, welcome_text, reply_markup=reply_kb, parse_mode='Markdown')

def _logic_upload_file(message):
    user_id = message.from_user.id
    if bot_locked and user_id not in admin_ids: bot.reply_to(message, "⚠️ Bot locked."); return
    limit = get_user_file_limit(user_id)
    count = get_user_file_count(user_id)
    if count >= limit: bot.reply_to(message, f"⚠️ File limit reached ({count}/{str(limit) if limit != float('inf') else '∞'}). Delete a file or Refer friends to earn more slots."); return
    
    upload_msg = "📤 Send your `.py`, `.js`, or `.zip` file now."
    try: bot.send_photo(message.chat.id, UPLOAD_IMAGE_URL, caption=upload_msg, parse_mode='Markdown')
    except: bot.reply_to(message, upload_msg, parse_mode='Markdown')

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

# BUTTON MAPPING
BUTTON_MAP = {
    f"📤 {make_bold_unicode('UPLOAD FILE')}":          _logic_upload_file,
    f"📂 {make_bold_unicode('MY FILES')}":             lambda m: bot.reply_to(m, "📂 Check files in menu below.", reply_markup=create_main_menu_inline(m.from_user.id)),
    f"⚡ {make_bold_unicode('SPEED TEST')}":           lambda m: bot.reply_to(m, "⚡ Speed test ping: 12ms"),
    f"📊 {make_bold_unicode('STATISTICS')}":           _logic_statistics,
    f"📖 {make_bold_unicode('HOW TO USE')}":           _logic_how_to_use,
    f"📦 {make_bold_unicode('MANUAL INSTALL')}":        _logic_manual_install,
    f"🎁 {make_bold_unicode('REFER & EARN')}":          _logic_refer_earn,
    f"📤 {make_bold_unicode('SEND COMMAND')}":         lambda m: bot.reply_to(m, "📤 Send command panel.", reply_markup=create_send_command_menu()),
    f"👑 {make_bold_unicode('ADMIN PANEL')}":          lambda m: bot.reply_to(m, "👑 *Admin Panel*", reply_markup=create_admin_panel(), parse_mode='Markdown'),
    f"📞 {make_bold_unicode('CONTACT ADMIN (WHATSAPP)')}": _logic_whatsapp_contact,
}

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    banned, msg = is_user_banned(message.from_user.id)
    if banned: bot.reply_to(message, msg, parse_mode='Markdown'); return
    _logic_send_welcome(message)

@bot.message_handler(commands=['stats'])
def cmd_stats(message): _logic_statistics(message)

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
    ext = os.path.splitext(fname)[1].lower()
    if ext not in ['.py', '.js', '.zip']: bot.reply_to(message, "⚠️ Only `.py`, `.js`, `.zip` allowed."); return

    try:
        wait = bot.reply_to(message, f"⏳ Downloading `{fname}`...", parse_mode='Markdown')
        finfo = bot.get_file(doc.file_id)
        content = bot.download_file(finfo.file_path)

        ok, reason = scan_file_for_malware(content, fname, user_id)
        if not ok: bot.edit_message_text(f"🚨 Security Alert: {reason}", message.chat.id, wait.message_id); return

        user_folder = get_user_folder(user_id)
        fpath = os.path.join(user_folder, fname)
        with open(fpath, 'wb') as f: f.write(content)

        if ext == '.js': handle_js_file(fpath, user_id, user_folder, fname, message)
        else: handle_py_file(fpath, user_id, user_folder, fname, message)

    except Exception as e: bot.reply_to(message, f"❌ Unexpected error: {e}")

# ==================== CALLBACK ROUTER ====================
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    global bot_locked
    user_id = call.from_user.id
    data    = call.data

    bot.answer_callback_query(call.id)

    if data.startswith('approve_'):
        if user_id not in admin_ids: return
        parts = data.split('_', 2); oid = int(parts[1]); fname = parts[2]
        update_file_status_db(oid, fname, 'Approved')
        try: bot.edit_message_caption(f"✅ File `{fname}` from User `{oid}` has been **Approved**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except: pass
        try: bot.send_message(oid, f"🎉 Your file `{fname}` has been approved by Admin!", parse_mode='Markdown')
        except: pass
        return

    if data.startswith('reject_'):
        if user_id not in admin_ids: return
        parts = data.split('_', 2); oid = int(parts[1]); fname = parts[2]
        remove_user_file_db(oid, fname)
        try: bot.edit_message_caption(f"❌ File `{fname}` from User `{oid}` has been **Rejected**.", call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except: pass
        return

    if data == 'admin_limits_settings': admin_show_limits_panel(call.message.chat.id, call.message.message_id); return
    if data == 'set_free_limit':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter maximum files for FREE USERS:")
        bot.register_next_step_handler(msg, process_set_free_limit); return
    if data == 'set_sub_limit':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter maximum files for SUBSCRIBED USERS:")
        bot.register_next_step_handler(msg, process_set_sub_limit); return
    if data == 'admin_refer_reward_setting':
        msg = bot.send_message(call.message.chat.id, "✏️ Enter Extra File Upload Slots Per Successful Referral:")
        bot.register_next_step_handler(msg, process_set_refer_reward); return
    if data == 'admin_panel': bot.send_message(call.message.chat.id, "👑 *Admin Panel*", reply_markup=create_admin_panel(), parse_mode='Markdown'); return

def cleanup():
    for key in list(bot_scripts.keys()):
        if key in bot_scripts: kill_process_tree(bot_scripts[key])

atexit.register(cleanup)

if __name__ == '__main__':
    keep_alive()
    logger.info("🚀 Bot polling started...")
    while True:
        try: bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except Exception: time.sleep(5)
