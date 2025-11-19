import random
import sympy
import json
import os
import logging
import redis
import google.generativeai as genai
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ====================== زبان‌ها ======================
LANGUAGES = {
    "fa": {"name": "فارسی", "flag": "Iran"},
    "en": {"name": "English", "flag": "USA"},
    "es": {"name": "Español", "flag": "Spain"},
    "fr": {"name": "Français", "flag": "France"},
    "ar": {"name": "العربية", "flag": "Saudi Arabia"},
    "hi": {"name": "हिन्दी", "flag": "India"},
}

# پیام‌ها به ۶ زبان
TEXT = {
    "welcome": {
        "fa": "به ربات تمرین هوشمند کسرها خوش آمدید!",
        "en": "Welcome to the Smart Fraction Practice Bot!",
        "es": "¡Bienvenido al Bot de Práctica Inteligente de Fracciones!",
        "fr": "Bienvenue dans le Bot d'Entraînement Intelligent aux Fractions !",
        "ar": "مرحباً بك في بوت التدريب الذكي على الكسور!",
        "hi": "स्मार्ट फ्रैक्शन प्रैक्टिस बॉट में आपका स्वागत है!",
    },
    "select_lang": {
        "fa": "لطفاً زبان خود را انتخاب کنید:",
        "en": "Please select your language:",
        "es": "Por favor selecciona tu idioma:",
        "fr": "Veuillez sélectionner votre langue :",
        "ar": "يرجى اختيار لغتك:",
        "hi": "कृपया अपनी भाषा चुनें:",
    },
    "accuracy": {
        "fa": "دقت فعلی: {acc}%\nدرست: {correct} | کل: {total}",
        "en": "Current accuracy: {acc}%\nCorrect: {correct} | Total: {total}",
        "es": "Precisión actual: {acc}%\nCorrectas: {correct} | Total: {total}",
        "fr": "Précision actuelle : {acc}%\nCorrectes : {correct} | Total : {total}",
        "ar": "الدقة الحالية: {acc}%\nصحيح: {correct} | المجموع: {total}",
        "hi": "वर्तमान सटीकता: {acc}%\nसही: {correct} | कुल: {total}",
    },
    "choose_op": {
        "fa": "یک عملیات را انتخاب کنید:",
        "en": "Choose an operation:",
        "es": "Elige una operación:",
        "fr": "Choisissez une opération :",
        "ar": "اختر عملية:",
        "hi": "एक ऑपरेशन चुनें:",
    },
    "trial_left": {
        "fa": "تمرین رایگان باقی‌مانده",
        "en": "free exercises left",
        "es": "ejercicios gratis restantes",
        "fr": "exercices gratuits restants",
        "ar": "تمارين مجانية متبقية",
        "hi": "मुफ्त अभ्यास बाकी",
    },
    "trial_over": {
        "fa": "آزمایش رایگان تموم شد!",
        "en": "Free trial has ended!",
        "es": "¡Prueba gratuita terminada!",
        "fr": "Essai gratuit terminé !",
        "ar": "انتهت الفترة التجريبية المجانية!",
        "hi": "मुफ्त ट्रायल समाप्त!",
    },
    "send_proof": {
        "fa": "اسکرین‌شات تراکنش را برای ادمین بفرستید",
        "en": "Send transaction screenshot to admin",
        "es": "Envía captura de la transacción al admin",
        "fr": "Envoyez une capture d’écran au admin",
        "ar": "أرسل لقطة شاشة المعاملة للأدمن",
        "hi": "लेनदेन का स्क्रीनशॉट एडमिन को भेजें",
    },
    "correct": {
        "fa": "عالی! جواب کاملاً درست است",
        "en": "Perfect! Your answer is correct",
        "es": "¡Perfecto! Respuesta correcta",
        "fr": "Parfait ! Bonne réponse",
        "ar": "ممتاز! الإجابة صحيحة",
        "hi": "शानदार! आपका जवाब सही है",
    },
    "wrong": {
        "fa": "اشتباه! جواب درست:",
        "en": "Wrong! Correct answer:",
        "es": "¡Incorrecto! Respuesta correcta:",
        "fr": "Faux ! Bonne réponse :",
        "ar": "خطأ! الإجابة الصحيحة:",
        "hi": "गलत! सही जवाब:",
    },
    "smart_explanation": {
        "fa": "توضیح هوشمند:",
        "en": "Smart Explanation:",
        "es": "Explicación Inteligente:",
        "fr": "Explication Intelligente :",
        "ar": "شرح ذكي:",
        "hi": "स्मार्ट स्पष्टीकरण:",
    },
    "next_question": {
        "fa": "عملیات بعدی را انتخاب کنید:",
        "en": "Choose next operation:",
        "es": "Elige la siguiente operación:",
        "fr": "Choisissez la prochaine opération :",
        "ar": "اختر العملية التالية:",
        "hi": "अगला ऑपरेशन चुनें:",
    },
}

# عملیات‌ها به زبان‌های مختلف
OP_BUTTONS = {
    "fa": ["جمع", "تفریق", "ضرب", "تقسیم"],
    "en": ["Add", "Subtract", "Multiply", "Divide"],
    "es": ["Sumar", "Restar", "Multiplicar", "Dividir"],
    "fr": ["Addition", "Soustraction", "Multiplication", "Division"],
    "ar": ["جمع", "طرح", "ضرب", "قسمة"],
    "hi": ["जोड़", "घटाव", "गुणा", "भाग"],
}

# ====================== تنظیمات ======================
REDIS_CLIENT = None
GEMINI_MODEL = None
TON_WALLET = os.environ.get("TON_WALLET_ADDRESS", "UQ...your_wallet")

DEFAULT_USER_DATA = {
    "lang": "en", "correct": 0, "total": 0, "topic": "+", "expected_answer": None,
    "d1": 0, "d2": 0, "problem_text": "", "is_subscribed": False
}

def init_clients():
    global GEMINI_MODEL, REDIS_CLIENT
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")

    url = os.environ.get("REDIS_URL")
    if url:
        try:
            REDIS_CLIENT = redis.from_url(url, decode_responses=True)
            REDIS_CLIENT.ping()
            logging.info("Redis connected")
        except: pass

init_clients()

# ====================== کمکی ======================
def t(user_data, key, **kwargs):
    lang = user_data.get("lang", "en")
    return TEXT[key].get(lang, TEXT[key]["en"]).format(**kwargs)

def get_user_data(user_id):
    if REDIS_CLIENT and REDIS_CLIENT.exists(f"user:{user_id}"):
        return json.loads(REDIS_CLIENT.get(f"user:{user_id}"))
    return DEFAULT_USER_DATA.copy()

def save_data(user_id, data):
    if REDIS_CLIENT:
        REDIS_CLIENT.set(f"user:{user_id}", json.dumps(data))

def lang_keyboard():
    row = []
    for code, info in LANGUAGES.items():
        row.append(InlineKeyboardButton(f"{info['flag']} {info['name']}", callback_data=f"lang_{code}"))
        if len(row) == 3:
            yield row
            row = []
    if row: yield row

def op_keyboard(lang):
    labels = OP_BUTTONS[lang]
    keyboard = [
        [InlineKeyboardButton(f"➕ {labels[0]}", callback_data='+'),
         InlineKeyboardButton(f"➖ {labels[1]}", callback_data='-')],
        [InlineKeyboardButton(f"✖️ {labels[2]}", callback_data='*'),
         InlineKeyboardButton(f"➗ {labels[3]}", callback_data='/')],
    ]
    return InlineKeyboardMarkup(keyboard)

# ====================== تولید سوال ======================
def generate_problem(op):
    n1, n2 = random.randint(1, 15), random.randint(1, 15)
    d1, d2 = random.randint(2, 12), random.randint(2, 12)
    f1, f2 = sympy.Rational(n1, d1), sympy.Rational(n2, d2)

    if op == '+':
        res = f1 + f2
        text = f"{f1} + {f2}"
    elif op == '-':
        if f1 < f2: f1, f2 = f2, f1
        res = f1 - f2
        text = f"{f1} - {f2}"
    elif op == '*':
        res = f1 * f2
        text = f"{f1} × {f2}"
    else:  # تقسیم
        if f2 == 0: f2 = sympy.Rational(1, 2)
        res = f1 / f2
        text = f"{f1} ÷ {f2}"

    return text, str(res), d1, d2

def normalize_answer(ans: str) -> str:
    ans = ans.strip().replace(' ', '+')
    try: return str(sympy.Rational(ans))
    except: return ans.strip()

async def check_sub(user_data):
    if user_data['is_subscribed']: return True, None
    if user_data['total'] < 30:
        left = 30 - user_data['total']
        return True, f"{left} {t(user_data, 'trial_left')}"
    invoice = f"{t(user_data, 'trial_over')}\n\n"
    for m, p, _ in [(1,3), (3,8), (6,15), (12,28)]:
        invoice += f"• {m} month{'s' if m>1 else ''} → {p} TON\n"
    invoice += f"\nSend exact amount to:\n`{TON_WALLET}`\n\n{t(user_data, 'send_proof')}"
    return False, invoice

def gemini_explain(lang, op, problem, answer, d1, d2):
    if not GEMINI_MODEL: return f"The correct answer is {answer}"
    prompts = {
        "fa": f"به فارسی ساده و گام به گام توضیح بده: {problem}\nمخرج مشترک = {sympy.lcm(d1,d2)}\nجواب نهایی: {answer}",
        "en": f"Explain step-by-step in English: {problem}\nCommon denominator (LCM) = {sympy.lcm(d1,d2)}\nFinal answer: {answer}",
        "es": f"Explica paso a paso en español: {problem}\nMínimo común múltiplo = {sympy.lcm(d1,d2)}\nRespuesta final: {answer}",
        "fr": f"Explique étape par étape en français : {problem}\nPPCM = {sympy.lcm(d1,d2)}\nRéponse finale : {answer}",
        "ar": f"اشرح بالعربية خطوة بخطوة: {problem}\nالمقام المشترك الأصغر = {sympy.lcm(d1,d2)}\nالإجابة النهائية: {answer}",
        "hi": f"हिन्दी में स्टेप-बाय-स्टेप समझाइए: {problem}\nलघुत्तम समापवर्तक = {sympy.lcm(d1,d2)}\nअंतिम उत्तर: {answer}",
    }
    try:
        resp = GEMINI_MODEL.generate_content(prompts.get(lang, prompts["en"]))
        return resp.text
    except Exception as e:
        logging.error(e)
        return f"Correct answer: {answer}"

# ====================== هندلرها ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["select_lang"]["en"],
        reply_markup=InlineKeyboardMarkup(list(lang_keyboard()))
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("lang_"):
        lang = query.data[5:]
        user_id = query.from_user.id
        data = get_user_data(user_id)
        data["lang"] = lang
        save_data(user_id, data)

        acc = round(data['correct']/max(data['total'],1)*100, 1)
        welcome = t(data, "welcome")
        stats = t(data, "accuracy", acc=acc, correct=data['correct'], total=data['total'])
        await query.edit_message_text(
            f"{welcome}\n\n{stats}\n\n{t(data, 'choose_op')}",
            reply_markup=op_keyboard(lang)
        )
        return

    # عملیات ریاضی
    op = query.data
    user_id = query.from_user.id
    data = get_user_data(user_id)
    allowed, msg = await check_sub(data)

    if not allowed:
        await query.edit_message_text(msg)
        return

    problem, answer, d1, d2 = generate_problem(op)
    data.update({"expected_answer": answer, "topic": op, "problem_text": problem, "d1": d1, "d2": d2})
    save_data(user_id, data)

    status = f"\n\n{msg}" if msg else ""
    await query.edit_message_text(
        f"{problem} = ?\n{status}\n\nWrite your answer (e.g. 5/6 or 1 1/2)"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    data = get_user_data(user_id)
    expected = data.get("expected_answer")
    lang = data.get("lang", "en")

    if not expected:
        await update.message.reply_text("Please /start first")
        return

    data["total"] += 1
    if normalize_answer(text) == expected:
        feedback = t(data, "correct")
        data["correct"] += 1
    else:
        expl = gemini_explain(lang, data["topic"], data["problem_text"], expected, data["d1"], data["d2"])
        feedback = f"{t(data, 'wrong')} **{expected}**\n\n{t(data, 'smart_explanation')}\n{expl}"

    save_data(user_id, data)
    await update.message.reply_text(feedback + f"\n\n{t(data, 'next_question')}", reply_markup=op_keyboard(lang))

# ====================== اجرا ======================
def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN required!")
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logging.info("Multi-language Fraction Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
