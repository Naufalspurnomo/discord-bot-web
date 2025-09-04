#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Discord Auto Message Bot with Flask Web UI
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import http.client, json, time, os, sys, random, logging, threading
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from collections import deque
from croniter import croniter
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import DictCursor
import cloudinary
import cloudinary.uploader
import cloudinary.api
from urllib.parse import urljoin

# --- INISIALISASI & KONFIGURASI ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-yang-aman')
app.config['UPLOAD_FOLDER'] = os.path.join(os.environ.get('RENDER_DATA_DIR', os.path.dirname(os.path.abspath(__file__))), 'temp_uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# PostgreSQL configuration
DB_CONFIG = {
    'dbname': os.environ.get('PG_DBNAME', 'discord_bot'),
    'user': os.environ.get('PG_USER', 'admin'),
    'password': os.environ.get('PG_PASSWORD', 'password'),
    'host': os.environ.get('PG_HOST', 'localhost'),
    'port': os.environ.get('PG_PORT', '5432')
}

bot_threads = {}
stop_events = {}
bot_status_lock = threading.Lock()
bot_status = {}
log = None  # Initialized in setup_logger

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
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT id, username, password_hash FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['password_hash'])
    return None

# --- DATABASE HELPER FUNCTIONS ---
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            profile_name VARCHAR(100) NOT NULL,
            token TEXT NOT NULL,
            channelid TEXT NOT NULL,
            schedule_mode VARCHAR(20) DEFAULT 'interval',
            interval_seconds INTEGER DEFAULT 300,
            cron_expression TEXT,
            messages JSONB NOT NULL,
            UNIQUE (user_id, profile_name)
        );
        CREATE TABLE IF NOT EXISTS sends (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            profile_name VARCHAR(100) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            success BOOLEAN NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# --- LOGGING ---
def setup_logger():
    global log
    log = logging.getLogger("discordbot")
    log.setLevel(logging.INFO)
    if log.hasHandlers():
        log.handlers.clear()
    log_path = os.path.join(os.environ.get('RENDER_DATA_DIR', os.path.dirname(os.path.abspath(__file__))), 'bot.log')
    fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(ch)
    return log

# --- DATA MANAGEMENT ---
def get_all_users():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT id, username, password_hash FROM users")
    users = {str(row['id']): {'username': row['username'], 'password_hash': row['password_hash']} for row in cur.fetchall()}
    cur.close()
    conn.close()
    return users

def get_user_profiles(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT profile_name, token, channelid, schedule_mode, interval_seconds, cron_expression, messages FROM profiles WHERE user_id = %s", (user_id,))
    profiles = {row['profile_name']: {
        'token': row['token'],
        'channelid': row['channelid'],
        'schedule_mode': row['schedule_mode'],
        'interval_seconds': row['interval_seconds'],
        'cron_expression': row['cron_expression'],
        'messages': row['messages']
    } for row in cur.fetchall()}
    cur.close()
    conn.close()
    return profiles

def get_profile_config(user_id, profile_name="default"):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT token, channelid, schedule_mode, interval_seconds, cron_expression, messages FROM profiles WHERE user_id = %s AND profile_name = %s", (user_id, profile_name))
    config = cur.fetchone()
    cur.close()
    conn.close()
    if not config:
        return {
            "token": "", "channelid": "", "schedule_mode": "interval",
            "interval_seconds": 300, "cron_expression": "",
            "messages": [{"type": "text", "content": "Hello World!"}]
        }
    return {
        "token": config['token'], "channelid": config['channelid'],
        "schedule_mode": config['schedule_mode'], "interval_seconds": config['interval_seconds'],
        "cron_expression": config['cron_expression'], "messages": config['messages']
    }

def log_send(user_id, profile_name, success):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO sends (user_id, profile_name, timestamp, success) VALUES (%s, %s, %s, %s)",
                (user_id, profile_name, datetime.now(), success))
    conn.commit()
    cur.close()
    conn.close()

def get_dashboard_data(user_id):
    profiles = get_user_profiles(user_id)
    active_count = sum(1 for profile_name in profiles if bot_status.get(profile_name, {}).get("running", False))
    stopped_count = len(profiles) - active_count
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cur.execute("SELECT success FROM sends WHERE user_id = %s AND timestamp >= %s", (user_id, today))
    rows = cur.fetchall()
    total_sent = len(rows)
    failed_sent = len([r for r in rows if not r['success']])
    cur.execute("SELECT message FROM logs WHERE user_id = %s ORDER BY timestamp DESC LIMIT 5", (user_id,))
    recent_logs = [row['message'] for row in cur.fetchall()]
    next_schedule, earliest_next_run = "None scheduled", None
    for profile_name in profiles:
        if bot_status.get(profile_name, {}).get("running", False):
            config = get_profile_config(user_id, profile_name)
            schedule_mode = config.get("schedule_mode", "interval")
            current_next_run = None
            if schedule_mode == "interval":
                interval = config.get("interval_seconds", 300)
                last_run_str = bot_status.get(profile_name, {}).get("last_run", "-")
                if last_run_str != "-":
                    try:
                        last_run = datetime.strptime(last_run_str, "%H:%M:%S")
                        current_next_run = datetime.combine(datetime.today(), last_run.time()) + timedelta(seconds=interval)
                    except ValueError:
                        pass
            elif schedule_mode in ["cron_simple", "cron_advanced"]:
                if cron_expr := config.get("cron_expression"):
                    try:
                        current_next_run = croniter(cron_expr, datetime.now()).get_next(datetime)
                    except Exception:
                        pass
            if current_next_run and (earliest_next_run is None or current_next_run < earliest_next_run):
                earliest_next_run = current_next_run
                next_schedule = f"'{profile_name}' at {earliest_next_run.strftime('%H:%M:%S')}"
    cur.close()
    conn.close()
    return {
        "status": f"{active_count} Active / {stopped_count} Stopped",
        "messages": f"{total_sent} Sent ({failed_sent} Failed)",
        "recent_logs": recent_logs or ["No logs available."],
        "next_schedule": next_schedule
    }

# --- BOT LOGIC ---
def send_message_logic(channel_id, token, message):
    try:
        content_to_send = ""
        msg_type = message.get('type')
        if msg_type == 'text':
            content_to_send = message.get('content', '').replace("{now}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        elif msg_type == 'embed':
            data = message.get('data', {})
            content_to_send = f"**{data.get('title', '')}**\n{data.get('description', '')}"
        elif msg_type == 'attachment':
            content_to_send = message.get('url', '')
            if not content_to_send:
                log.error("Attachment URL is empty, skipping.")
                return False
        if not content_to_send.strip():
            log.error("Content to send is empty, skipping.")
            return False
        headers = {"Authorization": token, "Content-Type": "application/json"}
        body = json.dumps({"content": content_to_send, "tts": False})
        log.info(f"Sending request to {channel_id} with content: {content_to_send[:100]}...")
        conn = http.client.HTTPSConnection("discord.com", 443, timeout=30)
        conn.request("POST", f"/api/v10/channels/{channel_id}/messages", body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read().decode(errors='ignore')
        if 200 <= resp.status < 300:
            log.info(f"Pesan berhasil dikirim ke channel {channel_id}")
            return True
        else:
            log.error(f"HTTP {resp.status} {resp.reason} | response: {resp_body}")
            return False
    except Exception as e:
        log.exception(f"Terjadi error saat mengirim pesan: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def bot_worker(user_id, profile_name):
    global bot_status, stop_events
    cfg = get_profile_config(user_id, profile_name)
    token, channel_id, messages, schedule_mode = (cfg.get(k, '') for k in ['token', 'channelid', 'messages', 'schedule_mode'])
    interval, cron_expr = int(cfg.get('interval_seconds', 300)), cfg.get('cron_expression', '')
    if not all([token, channel_id, messages]):
        log.error(f"Worker stopped [{profile_name}]: Missing config.")
        with bot_status_lock:
            bot_status[profile_name]["running"] = False
        return
    log.info(f"Bot worker started for profile: {profile_name}.")
    while not stop_events[profile_name].is_set():
        message = random.choice(messages)
        success = send_message_logic(channel_id, token, message)
        log_send(user_id, profile_name, success)
        if success:
            with bot_status_lock:
                bot_status[profile_name]["sent_count"] += 1
                bot_status[profile_name]["last_run"] = datetime.now().strftime("%H:%M:%S")
        if schedule_mode == 'interval':
            for _ in range(interval):
                if stop_events[profile_name].is_set():
                    break
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
    with bot_status_lock:
        bot_status[profile_name]["running"] = False

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        if user_data and check_password_hash(user_data['password_hash'], password):
            login_user(User(user_data['id'], user_data['username'], user_data['password_hash']), remember=True)
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            cur.close()
            conn.close()
            flash('Username sudah digunakan.', 'danger')
            return redirect(url_for('register'))
        password_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id", (username, password_hash))
        user_id = cur.fetchone()[0]
        cur.execute("INSERT INTO profiles (user_id, profile_name, token, channelid, schedule_mode, interval_seconds, cron_expression, messages) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (user_id, "default", "", "", "interval", 300, "", json.dumps([{"type": "text", "content": "Hello World!"}])))
        conn.commit()
        cur.close()
        conn.close()
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()
        log.info(f"User {current_user.id} logged out successfully.")
        return redirect(url_for('login'))
    except Exception as e:
        log.error(f"Logout failed for user {current_user.id}: {str(e)}")
        return jsonify({"message": f"Logout failed: {str(e)}"}), 500

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/upload_attachment', methods=['POST'])
@login_required
def upload_attachment():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(file, resource_type="auto")
        return jsonify({"message": "File uploaded", "filepath": upload_result['secure_url']})
    except Exception as e:
        log.error(f"Error uploading to Cloudinary: {e}")
        return jsonify({"message": f"Upload failed: {str(e)}"}), 500

@app.route('/api/start', methods=['POST'])
@login_required
def start_bot():
    profile_name = request.json.get("profile", "default")
    if profile_name in bot_threads and bot_threads[profile_name].is_alive():
        return jsonify({"message": "Bot sudah berjalan!"})
    with bot_status_lock:
        if profile_name not in stop_events:
            stop_events[profile_name] = threading.Event()
        stop_events[profile_name].clear()
        if profile_name not in bot_status:
            bot_status[profile_name] = {}
        bot_status[profile_name].update({"running": True, "sent_count": 0, "last_run": "-"})
    bot_threads[profile_name] = threading.Thread(target=bot_worker, args=(current_user.id, profile_name))
    bot_threads[profile_name].start()
    return jsonify({"message": f"Bot dimulai untuk profil '{profile_name}'."})

@app.route('/api/stop', methods=['POST'])
@login_required
def stop_bot():
    profile_name = request.json.get("profile", "default")
    if profile_name not in bot_threads or not bot_threads[profile_name].is_alive():
        return jsonify({"message": "Bot tidak berjalan."})
    stop_events[profile_name].set()
    bot_threads[profile_name].join(timeout=5)
    return jsonify({"message": "Bot dihentikan."})

@app.route('/api/send_once', methods=['POST'])
@login_required
def send_once():
    data = request.json
    profile_name, token, channel_id, messages = data.get("profile", "default"), data.get('token'), data.get('channelid'), data.get('messages')
    if not all([token, channel_id, messages]):
        return jsonify({"success": False, "message": "Konfigurasi tidak lengkap untuk tes."})
    message = random.choice(messages)
    success = send_message_logic(channel_id, token, message)
    log_send(current_user.id, profile_name, success)
    if success:
        return jsonify({"success": True, "message": "Pesan tes berhasil dikirim!"})
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
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    cur.execute("SELECT message FROM logs WHERE user_id = %s ORDER BY timestamp DESC LIMIT 15", (current_user.id,))
    logs = [row['message'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({"logs": "".join(logs) if logs else "No logs available."})

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
        if not profile_name:
            return jsonify({"message": "Nama profil tidak boleh kosong."}), 400
        messages = data.get("messages", [])
        if not messages:
            return jsonify({"message": "Pesan tidak boleh kosong."}), 400
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO profiles (user_id, profile_name, token, channelid, schedule_mode, interval_seconds, cron_expression, messages)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, profile_name) DO UPDATE
            SET token = EXCLUDED.token, channelid = EXCLUDED.channelid, schedule_mode = EXCLUDED.schedule_mode,
                interval_seconds = EXCLUDED.interval_seconds, cron_expression = EXCLUDED.cron_expression, messages = EXCLUDED.messages
        """, (current_user.id, profile_name, data.get("token", ""), data.get("channelid", ""), data.get("schedule_mode", "interval"),
              int(data.get("interval_seconds", 300)), data.get("cron_expression", ""), json.dumps(messages)))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": f"Profil '{profile_name}' berhasil disimpan!"})
    except Exception as e:
        log.error(f"Error saving profile: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/delete_profile', methods=['POST'])
@login_required
def delete_profile():
    try:
        profile_name = request.json.get("profile").strip()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM profiles WHERE user_id = %s", (current_user.id,))
        if cur.fetchone()[0] <= 1 and profile_name == "default":
            cur.close()
            conn.close()
            return jsonify({"message": "Tidak dapat menghapus satu-satunya profil."}), 400
        cur.execute("DELETE FROM profiles WHERE user_id = %s AND profile_name = %s", (current_user.id, profile_name))
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"message": f"Profil '{profile_name}' tidak ditemukan."}), 404
        cur.execute("DELETE FROM sends WHERE user_id = %s AND profile_name = %s", (current_user.id, profile_name))
        conn.commit()
        cur.close()
        conn.close()
        if profile_name in bot_threads and bot_threads[profile_name].is_alive():
            stop_events[profile_name].set()
            bot_threads[profile_name].join(timeout=5)
        with bot_status_lock:
            if profile_name in bot_status:
                del bot_status[profile_name]
        return jsonify({"message": f"Profil '{profile_name}' berhasil dihapus!"})
    except Exception as e:
        log.error(f"Error deleting profile: {e}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

@app.route('/api/duplicate_profile', methods=['POST'])
@login_required
def duplicate_profile():
    try:
        profile_name = request.json.get("profile_name").strip()
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT * FROM profiles WHERE user_id = %s AND profile_name = %s", (current_user.id, profile_name))
        profile = cur.fetchone()
        if not profile:
            cur.close()
            conn.close()
            return jsonify({"message": f"Profil '{profile_name}' tidak ditemukan."}), 404
        new_profile_name = f"{profile_name}_copy_{random.randint(100, 999)}"
        cur.execute("SELECT 1 FROM profiles WHERE user_id = %s AND profile_name = %s", (current_user.id, new_profile_name))
        while cur.fetchone():
            new_profile_name = f"{profile_name}_copy_{random.randint(100, 999)}"
        cur.execute("""
            INSERT INTO profiles (user_id, profile_name, token, channelid, schedule_mode, interval_seconds, cron_expression, messages)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_user.id, new_profile_name, profile['token'], profile['channelid'], profile['schedule_mode'],
              profile['interval_seconds'], profile['cron_expression'], json.dumps(profile['messages'])))
        conn.commit()
        cur.close()
        conn.close()
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM logs WHERE user_id = %s", (current_user.id,))
        conn.commit()
        cur.close()
        conn.close()
        log.info(f"Logs cleared by user {current_user.id}.")
        return jsonify({"message": "Log berhasil dibersihkan!"})
    except Exception as e:
        log.error(f"Failed to clear logs: {e}")
        return jsonify({"message": f"Gagal membersihkan log: {str(e)}"}), 500

@app.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    time_range = request.args.get('range', 'daily')
    limits = {'daily': 24*60*60, 'weekly': 7*24*60*60, 'monthly': 30*24*60*60}
    cutoff = datetime.now() - timedelta(seconds=limits.get(time_range, 24*60*60))
    current_profiles = list(get_user_profiles(current_user.id).keys())
    if not current_profiles:
        cur.close()
        conn.close()
        return jsonify({"dates": [], "success": 0, "failure": 0, "total": 0, "profiles": {}})
    placeholders = ','.join(['%s'] * len(current_profiles))
    cur.execute(f"""
        SELECT timestamp, success, profile_name
        FROM sends
        WHERE user_id = %s AND timestamp >= %s AND profile_name IN ({placeholders})
        ORDER BY timestamp ASC
    """, [current_user.id, cutoff] + current_profiles)
    rows = cur.fetchall()
    data = {
        "dates": [row['timestamp'].isoformat() for row in rows],
        "success": sum(1 for row in rows if row['success']),
        "failure": len(rows) - sum(1 for row in rows if row['success']),
        "total": len(rows),
        "profiles": {profile_name: {"success": 0, "failure": 0, "timestamps": {}} for profile_name in current_profiles}
    }
    for row in rows:
        profile_name = row['profile_name']
        if profile_name in data["profiles"]:
            data["profiles"][profile_name]["timestamps"][row['timestamp'].isoformat()] = row['success']
            if row['success']:
                data["profiles"][profile_name]["success"] += 1
            else:
                data["profiles"][profile_name]["failure"] += 1
    cur.close()
    conn.close()
    return jsonify(data)

# Initialize logger and database
setup_logger()
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)