import random, sympy, json, os, logging, redis
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TON_WALLET = os.environ.get("TON_WALLET_ADDRESS", "YOUR_WALLET")
REDIS_URL = os.environ.get("REDIS_URL")

# Gemini
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

# Redis
r = None
if REDIS_URL:
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
    except: pass

def get(uid): 
    if r and r.exists(f"u:{uid}"): 
        return json.loads(r.get(f"u:{uid}"))
    return {"lang":"en","c":0,"t":0,"exp":None,"prob":""}

def save(uid, d): 
    if r: r.set(f"u:{uid}", json.dumps(d))

# زبان‌ها
LANGS = {"en":"English","es":"Español","fr":"Français","ar":"العربية","hi":"हिन्दी","fa":"فارسی"}
FLAGS = {"en":"US","es":"ES","fr":"FR","ar":"SA","hi":"IN","fa":"IR"}
OPS = {
    "en": ["+ Add", "- Subtract", "× Multiply", "÷ Divide"],
    "fa": ["جمع ➕", "تفریق ➖", "ضرب ✖️", "تقسیم ➗"],
    "es": ["Sumar ➕", "Restar ➖", "Multiplicar ✖️", "Dividir ➗"],
    "fr": ["Addition ➕", "Soustraction ➖", "Multiplication ✖️", "Division ➗"],
    "ar": ["جمع ➕", "طرح ➖", "ضرب ✖️", "قسمة ➗"],
    "hi": ["जोड़ ➕", "घटाव ➖", "गुणा ✖️", "भाग ➗"],
}

TEXT = {
    "lang": {"en":"Choose language:", "fa":"زبان خود را انتخاب کنید:"},
    "op":   {"en":"Choose operation:", "fa":"عملیات را انتخاب کنید:"},
    "left": {"en":"free exercises left", "fa":"تمرین رایگان باقی‌مانده"},
    "correct": {"en":"Correct! Well done!", "fa":"عالی! درست بود!"},
    "wrong":   {"en":"Wrong! Correct answer:", "fa":"اشتباه! جواب درست:"},
    "explain": {"en":"Smart explanation:", "fa":"توضیح هوشمند:"},
}

def problem(op):
    n1,n2 = random.randint(1,15),random.randint(1,15)
    d1,d2 = random.randint(2,12),random.randint(2,12)
    f1,f2 = sympy.Rational(n1,d1), sympy.Rational(n2,d2)
    if op=="+": res=f1+f2; txt=f"{f1} + {f2}"
    elif op=="-": 
        if f1<f2: f1,f2=f2,f1
        res=f1-f2; txt=f"{f1} - {f2}"
    elif op=="*": res=f1*f2; txt=f"{f1} × {f2}"
    else: res=f1/f2; txt=f"{f1} ÷ {f2}"
    return txt, str(res)

def norm(a): 
    a = a.strip().replace(" ","+")
    try: return str(sympy.Rational(a))
    except: return a.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton(f"{FLAGS[c]} {LANGS[c]}", callback_data=f"lang_{c}") for c in list(LANGS)[i:i+3]] for i in range(0,6,3)]
    await update.message.reply_text("Choose language / زبان:", reply_markup=InlineKeyboardMarkup(kb))

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; data = get(uid)
    if q.data.startswith("lang_"):
        data["lang"] = q.data[5:]
        save(uid, data)
        kb = [[InlineKeyboardButton(OPS[data["lang"]][i], callback_data=["+","-","*","/"][i]) for i in range(2)],
              [InlineKeyboardButton(OPS[data["lang"]][i], callback_data=["+","-","*","/"][i]) for i in range(2,4)]]
        await q.edit_message_text(TEXT["op"][data["lang"]], reply_markup=InlineKeyboardMarkup(kb))
        return

    # سوال جدید
    prob_txt, answer = problem(q.data)
    data.update({"exp":answer, "prob":prob_txt, "t":data.get("t",0)+1})
    save(uid, data)
    left = max(0, 30 - data["t"])
    await q.edit_message_text(f"{prob_txt} = ?\n\n{left} {TEXT['left'][data.get('lang','en')]}\n\nWrite answer (e.g. 5/6, 1 1/2, 2.5)")

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ans = update.message.text
    data = get(uid)
    lang = data.get("lang","en")
    exp = data.get("exp")

    if not exp:
        await update.message.reply_text("Please choose an operation first!")
        return

    # حتماً بعد از چک کردن جواب، exp رو پاک کن!
    data["exp"] = None
    if norm(ans) == exp:
        data["c"] = data.get("c",0) + 1
        fb = TEXT["correct"][lang]
    else:
        expl = "No explanation" if not model else model.generate_content(f"In {LANGS[lang]} explain step-by-step: {data['prob']}\nFinal answer: {exp}").text
        fb = f"{TEXT['wrong'][lang]} **{exp}**\n\n{TEXT['explain'][lang]}\n{expl}"

    save(uid, data)
    # دوباره کیبورد عملیات رو نشون بده
    kb = [[InlineKeyboardButton(OPS[lang][i], callback_data=["+","-","*","/"][i]) for i in range(2)],
          [InlineKeyboardButton(OPS[lang][i], callback_data=["+","-","*","/"][i]) for i in range(2,4)]]
    await update.message.reply_text(fb + "\n\nChoose next:", reply_markup=InlineKeyboardMarkup(kb))

# اجرا
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(cb))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
app.run_polling()
