#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Discord Auto Message Bot with Flask Web UI
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import http.client, json, time, os, sys, random, logging, threading, uuid
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from collections import deque
from croniter import croniter
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

# --- INISIALISASI & KONFIGURASI ---
app = Flask(__name__)
# Gunakan Environment Variable untuk keamanan
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-yang-aman')

# Render menyediakan 'data directory' untuk penyimpanan file persisten
DATA_DIR = os.environ.get('RENDER_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(DATA_DIR, 'config.json')
LOG_PATH = os.path.join(DATA_DIR, 'bot.log')
DB_PATH = os.path.join(DATA_DIR, 'analytics.db') # Path database SQLite
USERS_PATH = os.path.join(DATA_DIR, 'users.json')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

bot_threads = {}
stop_events = {}
bot_status_lock = threading.Lock()
bot_status = {}

# --- FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

@login_manager.user_loader
def load_user(user_id):
    users = get_all_users()
    user_data = users.get(user_id)
    if user_data:
        return User(user_id, user_data.get('username'), user_data.get('password_hash'))
    return None

# --- LOGGING & DATA MANAGEMENT ---
def setup_logger():
    logger = logging.getLogger("discordbot")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): logger.handlers.clear()
    fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger
log = setup_logger()

def get_all_users():
    if not os.path.exists(USERS_PATH):
        default_users = {"1": {"username": "admin", "password_hash": generate_password_hash("password")}}
        with open(USERS_PATH, 'w') as f: json.dump(default_users, f, indent=2)
        return default_users
    with open(USERS_PATH, 'r', encoding='utf-8') as f: return json.load(f)

def get_all_profiles():
    if not os.path.exists(CFG_PATH):
        default_config = {"users": {"1": {"profiles": {"default": {"token": "", "channelid": "", "schedule_mode": "interval", "interval_seconds": 300, "cron_expression": "", "messages": [{"type": "text", "content": "Hello World!"}]}}}}}
        with open(CFG_PATH, 'w') as f: json.dump(default_config, f, indent=2)
        return default_config
    with open(CFG_PATH, 'r', encoding='utf-8') as f: return json.load(f)

def get_user_profiles(user_id):
    config = get_all_profiles()
    return config.get("users", {}).get(str(user_id), {}).get("profiles", {})

def get_profile_config(user_id, profile_name="default"):
    profiles = get_user_profiles(user_id)
    config = profiles.get(profile_name, {})
    return {
        "token": config.get("token", ""), "channelid": config.get("channelid", ""),
        "schedule_mode": config.get("schedule_mode", "interval"), "interval_seconds": config.get("interval_seconds", 300),
        "cron_expression": config.get("cron_expression", ""),
        "messages": config.get("messages", [{"type": "text", "content": "Hello World!"}])
    }

def setup_analytics_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sends (id INTEGER PRIMARY KEY, user_id TEXT, profile_name TEXT, timestamp DATETIME, success BOOLEAN)''')
    conn.commit()
    conn.close()
setup_analytics_db()

def log_send(user_id, profile_name, success):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO sends (user_id, profile_name, timestamp, success) VALUES (?, ?, ?, ?)", (str(user_id), profile_name, datetime.now(), success))
    conn.commit()
    conn.close()

def get_dashboard_data(user_id):
    profiles = get_user_profiles(user_id)
    active_count = sum(1 for profile_name in profiles if bot_status.get(profile_name, {}).get("running", False))
    stopped_count = len(profiles) - active_count
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    c.execute("SELECT success FROM sends WHERE user_id = ? AND timestamp >= ?", (str(user_id), today))
    rows = c.fetchall()
    total_sent, failed_sent = len(rows), len([r for r in rows if not r[0]])
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f: recent_logs = deque(f, 5)
    except FileNotFoundError: recent_logs = ["No logs available."]
    next_schedule, earliest_next_run = "None scheduled", None
    for profile_name in profiles:
        if bot_status.get(profile_name, {}).get("running", False):
            config = get_profile_config(user_id, profile_name)
            schedule_mode, current_next_run = config.get("schedule_mode", "interval"), None
            if schedule_mode == "interval":
                interval, last_run_str = config.get("interval_seconds", 300), bot_status[profile_name].get("last_run", "-")
                if last_run_str != "-":
                    try: current_next_run = datetime.combine(datetime.today(), datetime.strptime(last_run_str, "%H:%M:%S").time()) + timedelta(seconds=interval)
                    except ValueError: pass
            elif schedule_mode in ["cron_simple", "cron_advanced"]:
                if cron_expr := config.get("cron_expression"):
                    try: current_next_run = croniter(cron_expr, datetime.now()).get_next(datetime)
                    except Exception: pass
            if current_next_run and (earliest_next_run is None or current_next_run < earliest_next_run):
                earliest_next_run = current_next_run
                next_schedule = f"'{profile_name}' at {earliest_next_run.strftime('%H:%M:%S')}"
    conn.close()
    return {"status": f"{active_count} Active / {stopped_count} Stopped", "messages": f"{total_sent} Sent ({failed_sent} Failed)", "recent_logs": list(recent_logs), "next_schedule": next_schedule}

# --- FUNGSI BOT (FIXED for Attachment) ---
def send_message_logic(channel_id, token, message):
    try:
        content_to_send = ""
        msg_type = message.get('type')

        if msg_type == 'text':
            content_to_send = message.get('content', '')
        elif msg_type == 'embed':
            data = message.get('data', {})
            content_to_send = f"**{data.get('title', '')}**\n{data.get('description', '')}"
        elif msg_type == 'attachment':
            source_type = message.get('source', 'url')
            path = message.get('path', '')
            if source_type == 'local':
                filename = os.path.basename(path)
                content_to_send = url_for('uploaded_file', filename=filename, _external=True)
            else:
                content_to_send = path

        if not content_to_send or not content_to_send.strip():
            log.error("Content to send is empty, skipping.")
            return False

        headers = {"Authorization": token, "Content-Type": "application/json"}
        body = json.dumps({"content": content_to_send, "tts": False})
        log.info(f"Sending request to {channel_id} with content: {content_to_send[:100]}...")
        conn = http.client.HTTPSConnection("discord.com", 443, timeout=30)
        conn.request("POST", f"/api/v10/channels/{channel_id}/messages", body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read().decode(errors='ignore')
        if 199 < resp.status < 300:
            log.info(f"Pesan berhasil dikirim ke channel {channel_id}")
            return True
        else:
            log.error(f"HTTP {resp.status} {resp.reason} | response: {resp_body}")
            return False
    except Exception as e:
        log.exception(f"Terjadi error saat mengirim pesan: {e}")
        return False
    finally:
        if 'conn' in locals() and conn: conn.close()

# --- WORKER BOT ---
def bot_worker(user_id, profile_name):
    global bot_status, stop_events
    cfg = get_profile_config(user_id, profile_name)
    token, channel_id, messages, schedule_mode = (cfg.get(k, '') for k in ['token', 'channelid', 'messages', 'schedule_mode'])
    interval, cron_expr = int(cfg.get('interval_seconds', 300)), cfg.get('cron_expression', '')
    if not all([token, channel_id, messages]):
        log.error(f"Worker stopped [{profile_name}]: Missing config.")
        with bot_status_lock: bot_status[profile_name]["running"] = False
        return
    log.info(f"Bot worker started for profile: {profile_name}.")
    while not stop_events[profile_name].is_set():
        message = random.choice(messages)
        if message.get('type') == 'text':
            message['content'] = message.get('content', '').replace("{now}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        success = send_message_logic(channel_id, token, message)
        log_send(user_id, profile_name, success)
        if success:
            with bot_status_lock:
                bot_status[profile_name]["sent_count"] += 1
                bot_status[profile_name]["last_run"] = datetime.now().strftime("%H:%M:%S")
        if schedule_mode == 'interval':
            for _ in range(interval):
                if stop_events[profile_name].is_set(): break
                time.sleep(1)
        elif schedule_mode in ['cron_simple', 'cron_advanced'] and cron_expr:
            try:
                sleep_duration = (croniter(cron_expr, datetime.now()).get_next(datetime) - datetime.now()).total_seconds()
                while sleep_duration > 0 and not stop_events[profile_name].is_set():
                    time.sleep(min(1, sleep_duration))
                    sleep_duration -= 1
            except Exception as e:
                log.error(f"Cron error for '{profile_name}': {e}. Stopping.")
                break
    log.info(f"Bot worker stopped for profile: {profile_name}.")
    with bot_status_lock: bot_status[profile_name]["running"] = False

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username, password, users = request.form['username'], request.form['password'], get_all_users()
        user_id = next((uid for uid, u in users.items() if u['username'] == username), None)
        if user_id and check_password_hash(users[user_id]['password_hash'], password):
            login_user(User(user_id, username, users[user_id]['password_hash']), remember=True)
            return redirect(url_for('index'))
        else: flash('Username atau password salah.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username, password, users = request.form['username'], request.form['password'], get_all_users()
        if any(u['username'] == username for u in users.values()):
            flash('Username sudah digunakan.', 'danger')
            return redirect(url_for('register'))
        new_user_id = str(max(map(int, users.keys())) + 1 if users else 1)
        users[new_user_id] = {'username': username, 'password_hash': generate_password_hash(password)}
        with open(USERS_PATH, 'w') as f: json.dump(users, f, indent=2)
        all_profiles = get_all_profiles()
        if "users" not in all_profiles: all_profiles["users"] = {}
        all_profiles["users"][new_user_id] = {"profiles": {"default": {"token": "", "channelid": "", "messages": []}}}
        with open(CFG_PATH, 'w') as f: json.dump(all_profiles, f, indent=2)
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- API ROUTES ---
@app.route('/api/upload_attachment', methods=['POST'])
@login_required
def upload_attachment():
    if 'file' not in request.files: return jsonify({"message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"message": "No selected file"}), 400
    if file:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        return jsonify({"message": "File uploaded", "filepath": filepath})
    return jsonify({"message": "Upload failed"}), 500

@app.route('/api/start', methods=['POST'])
@login_required
def start_bot():
    global bot_threads, stop_events, bot_status
    profile_name = request.json.get("profile", "default")
    if profile_name in bot_threads and bot_threads[profile_name].is_alive(): return jsonify({"message": "Bot sudah berjalan!"})
    with bot_status_lock:
        if profile_name not in stop_events: stop_events[profile_name] = threading.Event()
        stop_events[profile_name].clear()
        if profile_name not in bot_status: bot_status[profile_name] = {}
        bot_status[profile_name].update({"running": True, "sent_count": 0, "last_run": "-"})
    bot_threads[profile_name] = threading.Thread(target=bot_worker, args=(current_user.id, profile_name))
    bot_threads[profile_name].start()
    return jsonify({"message": f"Bot dimulai untuk profil '{profile_name}'."})

@app.route('/api/stop', methods=['POST'])
@login_required
def stop_bot():
    global stop_events, bot_threads
    profile_name = request.json.get("profile", "default")
    if profile_name not in bot_threads or not bot_threads[profile_name].is_alive(): return jsonify({"message": "Bot tidak berjalan."})
    stop_events[profile_name].set()
    bot_threads[profile_name].join(timeout=5)
    return jsonify({"message": "Bot dihentikan."})

@app.route('/api/send_once', methods=['POST'])
@login_required
def send_once():
    data = request.json
    profile_name, token, channel_id, messages = data.get("profile", "default"), data.get('token'), data.get('channelid'), data.get('messages')
    if not all([token, channel_id, messages]): return jsonify({"success": False, "message": "Konfigurasi tidak lengkap untuk tes."})
    message = random.choice(messages)
    if message.get('type') == 'text' and message.get('content'):
        message['content'] = message['content'].replace("{now}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    success = send_message_logic(channel_id, token, message)
    log_send(current_user.id, profile_name, success)
    if success: return jsonify({"success": True, "message": "Pesan tes berhasil dikirim!"})
    return jsonify({"success": False, "message": "Gagal mengirim pesan tes. Cek log."})

@app.route('/api/status')
@login_required
def get_status():
    with bot_status_lock:
        for profile in list(bot_status.keys()):
            if bot_status[profile].get("running") and (profile not in bot_threads or not bot_threads[profile].is_alive()):
                bot_status[profile]["running"] = False
        return jsonify(bot_status)

@app.route('/api/logs')
@login_required
def get_logs():
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f: return jsonify({"logs": "".join(deque(f, 15))})
    except FileNotFoundError: return jsonify({"logs": "File log belum dibuat."})

@app.route('/api/profiles', methods=['GET'])
@login_required
def get_profiles_list():
    profiles = get_user_profiles(current_user.id)
    return jsonify({"profiles": list(profiles.keys()) if profiles else ["default"]})

@app.route('/api/profile/<profile_name>', methods=['GET'])
@login_required
def get_profile_details(profile_name):
    return jsonify(get_profile_config(current_user.id, profile_name))

@app.route('/api/save_profile', methods=['POST'])
@login_required
def save_profile():
    data = request.json
    try:
        profile_name = data.get("profile_name", "default").strip()
        if not profile_name: return jsonify({"message": "Nama profil tidak boleh kosong."}), 400
        all_data, user_id = get_all_profiles(), str(current_user.id)
        if "users" not in all_data: all_data["users"] = {}
        if user_id not in all_data["users"]: all_data["users"][user_id] = {"profiles": {}}
        messages = data.get("messages", [])
        if not messages: return jsonify({"message": "Pesan tidak boleh kosong."}), 400
        all_data["users"][user_id]["profiles"][profile_name] = {"token": data.get("token", ""), "channelid": data.get("channelid", ""), "schedule_mode": data.get("schedule_mode", "interval"), "interval_seconds": int(data.get("interval_seconds", 300)), "cron_expression": data.get("cron_expression", ""), "messages": messages}
        with open(CFG_PATH, 'w', encoding='utf-8') as f: json.dump(all_data, f, indent=2)
        return jsonify({"message": f"Profil '{profile_name}' berhasil disimpan!"})
    except Exception as e:
        log.error(f"Error saving profile: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/delete_profile', methods=['POST'])
@login_required
def delete_profile():
    try:
        profile_name = request.json.get("profile").strip()
        if profile_name == "default" and len(get_user_profiles(current_user.id)) <= 1:
            return jsonify({"message": "Tidak dapat menghapus satu-satunya profil."}), 400
        all_data, user_id = get_all_profiles(), str(current_user.id)
        if user_id in all_data["users"] and profile_name in all_data["users"][user_id]["profiles"]:
            del all_data["users"][user_id]["profiles"][profile_name]
            with open(CFG_PATH, 'w', encoding='utf-8') as f: json.dump(all_data, f, indent=2)
            if profile_name in bot_threads and bot_threads[profile_name].is_alive():
                stop_events[profile_name].set()
                bot_threads[profile_name].join(timeout=5)
            with bot_status_lock:
                if profile_name in bot_status: del bot_status[profile_name]
            return jsonify({"message": f"Profil '{profile_name}' berhasil dihapus!"})
        return jsonify({"message": f"Profil '{profile_name}' tidak ditemukan."}), 404
    except Exception as e:
        log.error(f"Error deleting profile: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/duplicate_profile', methods=['POST'])
@login_required
def duplicate_profile():
    try:
        profile_name = request.json.get("profile_name").strip()
        all_data, user_id = get_all_profiles(), str(current_user.id)
        user_profiles = all_data.get("users", {}).get(user_id, {}).get("profiles", {})
        if profile_name not in user_profiles: return jsonify({"message": f"Profil '{profile_name}' tidak ditemukan."}), 404
        new_profile_name = f"{profile_name}_copy_{random.randint(100, 999)}"
        while new_profile_name in user_profiles: new_profile_name = f"{profile_name}_copy_{random.randint(100, 999)}"
        user_profiles[new_profile_name] = user_profiles[profile_name].copy()
        with open(CFG_PATH, 'w', encoding='utf-8') as f: json.dump(all_data, f, indent=2)
        return jsonify({"message": f"Profil '{profile_name}' diduplikasi sebagai '{new_profile_name}'!", "new_profile_name": new_profile_name})
    except Exception as e:
        log.error(f"Error duplicating profile: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/dashboard')
@login_required
def get_dashboard():
    return jsonify(get_dashboard_data(current_user.id))

@app.route('/api/clear_logs', methods=['POST'])
@login_required
def clear_logs():
    try:
        with open(LOG_PATH, 'w') as f: pass
        log.info("Log file has been cleared by user.")
        return jsonify({"message": "Log berhasil dibersihkan!"})
    except Exception as e:
        log.error(f"Failed to clear log file: {e}")
        return jsonify({"message": f"Gagal membersihkan log: {str(e)}"}), 500

@app.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    time_range, limits = request.args.get('range', 'daily'), {'daily': 24*60*60, 'weekly': 7*24*60*60, 'monthly': 30*24*60*60}
    cutoff = datetime.now() - timedelta(seconds=limits.get(time_range, 24*60*60))
    
    # Get current profiles for the user
    current_profiles = list(get_user_profiles(current_user.id).keys())
    
    if not current_profiles:
        conn.close()
        return jsonify({"dates": [], "success": 0, "failure": 0, "total": 0, "profiles": {}})
    
    # Ambil data dari database yang cocok
    c.execute("SELECT timestamp, success, profile_name FROM sends WHERE user_id = ? AND timestamp >= ? AND profile_name IN ({}) ORDER BY timestamp ASC".format(','.join('?' * len(current_profiles))), 
             [current_user.id, cutoff] + current_profiles)
    rows = c.fetchall()
    
    # --- LOGIKA BARU DIMULAI DI SINI ---
    
    # 1. Siapkan struktur data utama
    data = {
        "dates": [r[0] for r in rows],
        "success": sum(1 for r in rows if r[1]),
        "failure": len(rows) - sum(1 for r in rows if r[1]),
        "total": len(rows),
        "profiles": {}
    }
    
    # 2. Inisialisasi SEMUA profil dengan nilai 0
    for profile_name in current_profiles:
        data["profiles"][profile_name] = {"success": 0, "failure": 0, "timestamps": {}}

    # 3. Perbarui hitungan berdasarkan data yang ada di database
    for row in rows:
        timestamp, success, profile_name = row
        # Pastikan profil dari database masih ada di daftar profil saat ini
        if profile_name in data["profiles"]:
            data["profiles"][profile_name]["timestamps"][timestamp] = success
            if success: 
                data["profiles"][profile_name]["success"] += 1
            else: 
                data["profiles"][profile_name]["failure"] += 1
    
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    # Pastikan debug=False untuk produksi
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)