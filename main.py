import telebot
import ccxt
import time
import threading
import os  # اضافه شده برای خواندن متغیرهای محیطی

# توکن رو از متغیر محیطی بخون (در Render تعریف کن)
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# صرافی (بایننس) و سیمبل‌ها
exchange = ccxt.binance()
symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']

# آستانه تغییر قیمت برای "کندل قوی" (۱%)
THRESHOLD = 0.01  # 1%

# chat_id کاربر (برای ارسال هشدار)
user_chat_id = None

# تابع برای چک کردن تغییرات قیمت
def check_price_changes():
    while True:
        for symbol in symbols:
            try:
                # گرفتن ۳ کندل ۱ دقیقه‌ای اخیر (timeframe='1m' یعنی ۱ دقیقه)
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=3)
                
                strong_candles = 0
                for candle in ohlcv:
                    open_price = candle[1]
                    close_price = candle[4]
                    change = abs(close_price - open_price) / open_price
                    if change > THRESHOLD:
                        strong_candles += 1
                
                # اگر حداقل ۲ کندل قوی باشه، هشدار بده
                if strong_candles >= 2:
                    direction = "افزایش" if close_price > open_price else "کاهش"
                    message = f"هشدار! تغییر سریع در {symbol}: {strong_candles} کندل قوی در ۳ دقیقه اخیر (جهت: {direction}). قیمت فعلی: {close_price} USDT"
                    if user_chat_id:
                        bot.send_message(user_chat_id, message)
            except Exception as e:
                print(f"خطا در گرفتن داده {symbol}: {e}")
        
        # هر ۶۰ ثانیه چک کن (هماهنگ با کندل ۱ دقیقه‌ای)
        time.sleep(60)

# فرمان شروع ربات
@bot.message_handler(commands=['start'])
def start(message):
    global user_chat_id
    user_chat_id = message.chat.id
    bot.reply_to(message, "سلام! نظارت بر قیمت BTC, ETH و SOL با کندل‌های ۱ دقیقه‌ای شروع شد. اگر تغییر سریع رخ بده، اطلاع می‌دم.")
    
    # شروع thread برای چک مداوم
    threading.Thread(target=check_price_changes, daemon=True).start()

# شروع ربات
bot.polling()
