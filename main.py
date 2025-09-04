#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discord Auto Message Bot
Runs 24/7, posts to a channel every N seconds
"""

import http.client
import json
import time
import os
import sys
import random
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE_DIR, 'config.json')
LOG_PATH = os.path.join(BASE_DIR, 'bot.log')

# --- Logging setup ---
def setup_logger():
    logger = logging.getLogger("discordbot")
    logger.setLevel(logging.INFO)

    # Rotate file logs (1MB, 3 backups)
    fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console logs (systemd/journald will capture)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger

log = setup_logger()

# --- Config loader ---
def load_config():
    with open(CFG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cfg = (data.get('Config') or [{}])[0]
    token = (cfg.get('token') or '').strip()
    channel_id = str(cfg.get('channelid') or '').strip()

    # Messages: either "messages" list or single "message"
    messages = cfg.get('messages')
    if not (messages and isinstance(messages, list) and len(messages) > 0):
        single = cfg.get('message') or "Hello from VPS!"
        messages = [single]

    interval = int(cfg.get('interval_seconds') or 3600)

    # Ensure token has "Bot " prefix
    if token and not token.lower().startswith("bot "):
        log.warning('Token missing "Bot " prefix. Adding automatically...')
        token = "Bot " + token

    if not token or not channel_id:
        raise ValueError("Config missing required fields: 'token' and 'channelid'.")

    return channel_id, token, messages, interval

# --- HTTP helpers ---
def get_headers(token):
    return {
        "Content-Type": "application/json",
        "User-Agent": "DiscordBot",
        "Authorization": token
    }

def get_connection():
    return http.client.HTTPSConnection("discord.com", 443, timeout=30)

# --- Message renderer ---
def render_message(template: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return template.replace("{now}", now)

# --- Send message ---
def send_message(channel_id, token, content):
    body = json.dumps({"content": content, "tts": False})
    headers = get_headers(token)
    conn = get_connection()
    try:
        conn.request("POST", f"/api/v10/channels/{channel_id}/messages", body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        if 199 < resp.status < 300:
            log.info("Message sent successfully.")
        else:
            snippet = (resp_body[:300] if resp_body else b'').decode(errors="ignore")
            log.error("HTTP %s %s | response: %s", resp.status, resp.reason, snippet)
    except Exception as e:
        log.exception("Exception while sending message: %s", e)
    finally:
        try:
            conn.close()
        except:
            pass

# --- Main loop ---
def main():
    channel_id, token, messages, interval = load_config()
    log.info("Bot started | channel=%s | interval=%ss | messages=%d",
             channel_id, interval, len(messages))

    while True:
        try:
            msg_template = random.choice(messages)
            content = render_message(msg_template)
            send_message(channel_id, token, content)
        except Exception as e:
            log.exception("Error in loop: %s", e)
        time.sleep(interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Stopped by user (KeyboardInterrupt).")
        sys.exit(0)
