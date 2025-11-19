import random
import sympy
import json
import os
import logging
import redis
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- تنظیمات لاگ‌گیری (Logging) ---
logging.basicConfig(level=logging.INFO)

# --- متغیرهای محیطی ---
TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TON_WALLET = os.environ.get("TON_WALLET_ADDRESS", "YOUR_WALLET")
REDIS_URL = os.environ.get("REDIS_URL")

# --- تنظیمات Gemini ---
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        logging.info("Gemini Model configured successfully.")
    except Exception as e:
        logging.error(f"Failed to configure Gemini model: {e}")

# --- تنظیمات Redis ---
r = None
if REDIS_URL:
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping() 
        logging.info("Successfully connected to Redis.")
    except Exception as e:
        logging.warning(f"Could not connect to Redis: {e}")
        r = None 

# --- توابع مدیریت داده ---
def get(uid):
    if r and r.exists(f"u:{uid}"):
        try:
            return json.loads(r.get(f"u:{uid}"))
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON for user {uid}")
    return {"lang":"en","c":0,"t":0,"exp":None,"prob":""}

def save(uid, d):
    if r:
        try:
            r.set(f"u:{uid}", json.dumps(d))
        except Exception as e:
            logging.error(f"Failed to save data to Redis for user {uid}: {e}")

# --- داده‌های ثابت ---
LANGS = {"en":"English 🇺🇸","es":"Español 🇪🇸","fr":"Français 🇫🇷","ar":"العربية 🇸🇦","hi":"हिन्दी 🇮🇳","fa":"فارسی 🇮🇷"}
OPS = {
    "en": ["➕ Add", "➖ Subtract", "✖️ Multiply", "➗ Divide"],
    "fa": ["➕ جمع", "➖ تفریق", "✖️ ضرب", "➗ تقسیم"],
    "es": ["➕ Sumar", "➖ Restar", "✖️ Multiplicar", "➗ Dividir"],
    "fr": ["➕ Addition", "➖ Soustraction", "✖️ Multiplication", "➗ Division"],
    "ar": ["➕ جمع", "➖ طرح", "✖️ ضرب", "➗ قسمة"],
    "hi": ["➕ जोड़", "➖ घटाव", "✖️ गुणा", "➗ भाग"],
}

TEXT = {
    "lang": {"en":"Choose language:", "fa":"زبان خود را انتخاب کنید:"},
    "op":   {"en":"Choose operation:", "fa":"عملیات را انتخاب کنید:"},
    "left": {"en":"free exercises left", "fa":"تمرین رایگان باقی‌مانده"},
    "correct": {"en":"✅ Correct!", "fa":"✅ عالی! درست بود!"},
    "wrong":    {"en":"❌ Wrong! Correct answer:", "fa":"❌ اشتباه! جواب درست:"},
    "explain": {"en":"📚 Smart explanation:", "fa":"📚 توضیح هوشمند:"},
}

# --- توابع محاسباتی ---
def problem(op):
    n1,n2 = random.randint(1,15),random.randint(1,15)
    d1,d2 = random.randint(2,12),random.randint(2,12)
    f1,f2 = sympy.Rational(n1,d1), sympy.Rational(n2,d2)
    
    if op=="+": res=f1+f2; txt=f"{f1} + {f2}"
    elif op=="-": 
        if f1<f2: f1,f2 = f2,f1
        res=f1-f2; txt=f"{f1} - {f2}"
    elif op=="*": res=f1*f2; txt=f"{f1} × {f2}"
    else: 
        if f2 == 0: f2 = sympy.Rational(1, d2)
        res=f1/f2; txt=f"{f1} ÷ {f2}"
    return txt, str(res)

def norm(a):
    a = a.strip().replace(" ","+")
    try: return str(sympy.Rational(a))
    except: return a.strip()

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    codes = list(LANGS.keys())
    for i in range(0, len(codes), 3):
        row = [InlineKeyboardButton(LANGS[codes[j]], callback_data=f"lang_{codes[j]}") for j in range(i, min(i+3, len(codes)))]
        keyboard.append(row)
    await update.message.reply_text("🌍 Choose your language:", reply_markup=InlineKeyboardMarkup(keyboard))

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = get(uid)

    if q.data.startswith("lang_"):
        data["lang"] = q.data[5:]
        save(uid, data)
        lang = data["lang"]
        kb = [
            [InlineKeyboardButton(OPS[lang][0], callback_data="+"), InlineKeyboardButton(OPS[lang][1], callback_data="-")],
            [InlineKeyboardButton(OPS[lang][2], callback_data="*"), InlineKeyboardButton(OPS[lang][3], callback_data="/")]
        ]
        await q.edit_message_text(TEXT["op"].get(lang, TEXT["op"]["en"]), reply_markup=InlineKeyboardMarkup(kb))
        return

    # سوال جدید
    prob_txt, answer = problem(q.data)
    data.update({"exp":answer, "prob":prob_txt, "t":data.get("t",0)+1})
    save(uid, data)
    left = max(0, 30 - data["t"])
    msg = f"{prob_txt} = ?\n\n{left} {TEXT['left'].get(data['lang'], TEXT['left']['en'])}\n\nWrite answer (e.g. 5/6, 1 1/2, 2.5)"
    await q.edit_message_text(msg)

# --- Message Handler ---
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ans = update.message.text
    data = get(uid)
    lang = data.get("lang","en")
    exp = data.get("exp")

    if not exp:
        await update.message.reply_text(TEXT["op"].get(lang, TEXT["op"]["en"]) + " " + (TEXT["op"].get(lang, TEXT["op"]["en"]) if lang!="fa" else "را انتخاب کنید!") )
        return

    # --- منطق بازخورد و توضیح Gemini ---
    if norm(ans) == exp:
        fb = TEXT["correct"][lang]
    else:
        explanation = "No explanation"
        if model:
            try:
                logging.info(f"Requesting brief explanation for: {data['prob']}")
                
                # --- بهینه‌سازی سرعت: محدود کردن تعداد توکن‌ها ---
                explanation = model.generate_content(
                    f"Provide a very brief, single-paragraph explanation in {lang} for the math problem: {data['prob']}\nCorrect Answer: {exp}",
                    config={"max_output_tokens": 100} 
                ).text
                
            except Exception as e:
                # --- اضافه کردن پیام خطای فنی به کاربر و لاگ‌ها ---
                error_msg = f"Gemini API FAILED. Error: {e.__class__.__name__}. Check Render logs."
                logging.error(f"Gemini API call failed for user {uid}: {error_msg}")
                explanation = f"**{error_msg}**" # نمایش برجسته پیام خطا
                
        # ساختار پیام خطا و توضیح
        fb = f"{TEXT['wrong'][lang]} **{exp}**\n\n{TEXT['explain'][lang]}\n{explanation}"

    data["c"] += 1 if norm(ans) == exp else 0
    data["exp"] = None
    save(uid, data)

    # نمایش دکمه‌های عملیات برای سوال بعدی
    kb = [
        [InlineKeyboardButton(OPS[lang][0], callback_data="+"), InlineKeyboardButton(OPS[lang][1], callback_data="-")],
        [InlineKeyboardButton(OPS[lang][2], callback_data="*"), InlineKeyboardButton(OPS[lang][3], callback_data="/")]
    ]
    
    # --- جداسازی پیام‌ها: پیام خطا و توضیح در پیام اول ---
    await update.message.reply_text(fb, parse_mode="Markdown")
    
    # --- جداسازی پیام‌ها: منوی عملیات در پیام دوم ---
    await update.message.reply_text("Choose next operation:", reply_markup=InlineKeyboardMarkup(kb))

# --- اجرای بات ---
if TOKEN is None:
    logging.error("BOT_TOKEN environment variable is not set!")
else:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    logging.info("Starting polling...")
    app.run_polling(poll_interval=1.0)
