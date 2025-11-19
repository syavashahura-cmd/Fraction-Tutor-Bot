import random
import sympy
import json
import os
import logging
import redis
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

# ====================== تنظیمات ======================
TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TON_WALLET = os.environ.get("TON_WALLET_ADDRESS", "YOUR_WALLET")
REDIS_URL = os.environ.get("REDIS_URL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None

# Redis
r = None
if REDIS_URL:
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
    except:
        pass

def get(user_id):
    if r and r.exists(f"u:{user_id}"):
        return json.loads(r.get(f"u:{user_id}"))
    return {"lang":"en","c":0,"t":0,"exp":None,"d1":0,"d2":0,"op":"","prob":""}

def save(user_id, data):
    if r:
        r.set(f"u:{user_id}", json.dumps(data))

# ====================== زبان‌ها ======================
LANGS = {"en":"English","es":"Español","fr":"Français","ar":"العربية","hi":"हिन्दी","fa":"فارسی"}
FLAGS = {"en":"US","es":"ES","fr":"FR","ar":"SA","hi":"IN","fa":"IR"}

TEXT = {
    "lang": {"en":"Choose language:", "fa":"زبان را انتخاب کنید:", "es":"Elige idioma:", "fr":"Choisissez la langue :", "ar":"اختر اللغة:", "hi":"भाषा चुनें:"},
    "op":   {"en":"Choose operation:", "fa":"عملیات را انتخاب کنید:", "es":"Elige operación:", "fr":"Choisissez l’opération :", "ar":"اختر العملية:", "hi":"ऑपरेशन चुनें:"},
    "left": {"en":"free exercises left", "fa":"تمرین رایگان باقی‌مانده", "es":"ejercicios gratis", "fr":"exercices gratuits", "ar":"تمارين مجانية", "hi":"मुफ्त अभ्यास बाकी"},
    "correct": {"en":"Correct! Well done!", "fa":"عالی! درست بود!", "es":"¡Correcto!", "fr":"Correct !", "ar":"صحيح!", "hi":"सही!"},
    "wrong":   {"en":"Wrong! Correct answer:", "fa":"اشتباه! جواب درست:", "es":"¡Incorrecto! Respuesta:", "fr":"Faux ! Bonne réponse :", "ar":"خطأ! الإجابة:", "hi":"गलत! सही जवाब:"},
    "explain": {"en":"Explanation:", "fa":"توضیح هوشمند:", "es":"Explicación:", "fr":"Explication :", "ar":"شرح:", "hi":"व्याख्या:"},
}

OPS = {
    "en": ["+ Add", "- Subtract", "× Multiply", "÷ Divide"],
    "fa": ["جمع ➕", "تفریق ➖", "ضرب ✖️", "تقسیم ➗"],
    "es": ["Sumar ➕", "Restar ➖", "Multiplicar ✖️", "Dividir ➗"],
    "fr": ["Addition ➕", "Soustraction ➖", "Multiplication ✖️", "Division ➗"],
    "ar": ["جمع ➕", "طرح ➖", "ضرب ✖️", "قسمة ➗"],
    "hi": ["जोड़ ➕", "घटाव ➖", "गुणा ✖️", "भाग ➗"],
}

# ====================== تولید سوال ======================
def problem(op):
    n1, n2 = random.randint(1,15), random.randint(1,15)
    d1, d2 = random.randint(2,12), random.randint(2,12)
    f1, f2 = sympy.Rational(n1,d1), sympy.Rational(n2,d2)
    if op == "+": res = f1 + f2; txt = f"{f1} + {f2}"
    elif op == "-":
        if f1 < f2: f1,f2 = f2,f1
        res = f1 - f2; txt = f"{f1} - {f2}"
    elif op == "*": res = f1*f2; txt = f"{f1} × {f2}"
    else:
        if f2 == 0: f2 = sympy.Rational(1,2)
        res = f1/f2; txt = f"{f1} ÷ {f2}"
    return txt, str(res), d1, d2

def norm(ans):
    ans = ans.strip().replace(" ", "+")
    try: return str(sympy.Rational(ans))
    except: return ans.strip()

# ====================== هندلرها ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(f"{FLAGS[c]} {LANGS[c]}", callback_data=f"lang_{c}") for c in list(LANGS.keys())[i:i+3]] for i in range(0,6,3)]
    await update.message.reply_text("Choose your language / زبان خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = get(uid)

    if q.data.startswith("lang_"):
        data["lang"] = q.data[5:]
        save(uid, data)
        kb = [[InlineKeyboardButton(OPS[data["lang"]][i], callback_data=["+","-","*","/"][i]) for i in range(2)],
              [InlineKeyboardButton(OPS[data["lang"]][i], callback_data=["+","-","*","/"][i]) for i in range(2,4)]]
        await q.edit_message_text(TEXT["op"][data["lang"]], reply_markup=InlineKeyboardMarkup(kb))
        return

    # عملیات جدید
    op = q.data
    prob_txt, answer, d1, d2 = problem(op)
    data.update({"exp":answer, "op":op, "prob":prob_txt, "d1":d1, "d2":d2, "t":data.get("t",0)+1})
    save(uid, data)
    left = max(0, 30 - data["t"])
    msg = f"{prob_txt} = ?\n\n{left} {TEXT['left'][data.get('lang','en')]}\n\nWrite answer (e.g. 5/6 or 1 1/2)"
    await q.edit_message_text(msg)

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ans = update.message.text
    data = get(uid)
    lang = data.get("lang", "en")
    exp = data.get("exp")

    if not exp:
        await update.message.reply_text("Please choose an operation first!")
        return

    data["t"] += 1
    if norm(ans) == exp:
        data["c"] += 1
        fb = TEXT["correct"][lang]
    else:
        expl = "No explanation" if not model else model.generate_content(
            f"In {LANGS[lang]} explain step-by-step: {data['prob']}\nAnswer: {exp}").text
        fb = f"{TEXT['wrong'][lang]} **{exp}**\n\n{TEXT['explain'][lang]}\n{expl}"

    data["exp"] = None
    save(uid, data)
    await update.message.reply_text(fb + "\n\nChoose next operation:", reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton(OPS[lang][i], callback_data=["+","-","*","/"][i]) for i in range(2)],
         [InlineKeyboardButton(OPS[lang][i], callback_data=["+","-","*","/"][i]) for i in range(2,4)]]
    ))

# ====================== اجرا ======================
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(cb))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))

app.run_polling()
