import os
import json
import random
import sympy
import logging
import redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================== اتصال Redis ==================
REDIS_URL = os.environ.get("REDIS_URL")
REDIS_CLIENT = redis.from_url(REDIS_URL, decode_responses=True)

# ================== تنظیمات ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USDT_WALLET = os.environ.get("USDT_WALLET")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
FREE_TRIAL = 5  # تعداد سوالات رایگان برای کاربران عادی

# ================== زبان‌ها ==================
LANGUAGES = ["fa", "en", "es", "fr", "ar", "hi"]

TEXT = {
    "welcome": {
        "fa": "به ربات آموزش کسرها خوش آمدید! 👋",
        "en": "Welcome to Fraction Learning Bot! 👋",
    },
    "choose_op": {
        "fa": "یک عملیات را انتخاب کنید:",
        "en": "Choose an operation:",
    },
    "trial_left": {
        "fa": "سوال رایگان باقی‌مانده",
        "en": "free questions left",
    },
    "trial_over": {
        "fa": "سوالات رایگان تمام شد! لطفاً اشتراک بخرید.",
        "en": "Free questions finished! Please buy subscription.",
    },
    "send_proof": {
        "fa": f"پرداخت را به کیف پول زیر واریز کنید و اسکرین‌شات را به {ADMIN_USERNAME} بفرستید:\n{USDT_WALLET}",
        "en": f"Send payment to {USDT_WALLET} and proof to {ADMIN_USERNAME}",
    },
    "correct": {
        "fa": "✅ پاسخ درست است!",
        "en": "✅ Correct answer!",
    },
    "wrong": {
        "fa": "❌ پاسخ اشتباه است. جواب درست:",
        "en": "❌ Wrong answer. Correct answer:",
    },
    "next_question": {
        "fa": "سوال بعدی:",
        "en": "Next question:",
    }
}

OP_BUTTONS = {
    "fa": ["جمع", "تفریق", "ضرب", "تقسیم"],
    "en": ["Add", "Subtract", "Multiply", "Divide"],
}

# ================== کیبورد ==================
def op_keyboard(lang="en"):
    labels = OP_BUTTONS.get(lang, OP_BUTTONS["en"])
    keyboard = [
        [InlineKeyboardButton(f"➕ {labels[0]}", callback_data='+'),
         InlineKeyboardButton(f"➖ {labels[1]}", callback_data='-')],
        [InlineKeyboardButton(f"✖️ {labels[2]}", callback_data='*'),
         InlineKeyboardButton(f"➗ {labels[3]}", callback_data='/')],
    ]
    return InlineKeyboardMarkup(keyboard)

# ================== کمکی ==================
def t(lang, key, **kwargs):
    return TEXT[key].get(lang, TEXT[key]["en"]).format(**kwargs)

def get_user(user_id):
    if REDIS_CLIENT.exists(f"user:{user_id}"):
        return json.loads(REDIS_CLIENT.get(f"user:{user_id}"))
    return {"lang":"fa","trial":FREE_TRIAL,"is_vip":False,"total":0,"correct":0,"topic":"+","expected_answer":None,"f1_tuple":(0,1),"f2_tuple":(0,1)}

def save_user(user_id, data):
    REDIS_CLIENT.set(f"user:{user_id}", json.dumps(data))

# ================== تولید سوال ==================
def generate_problem(op, vip=False):
    max_num = 30 if vip else 15
    max_den = 20 if vip else 12
    n1, n2 = random.randint(1,max_num), random.randint(1,max_num)
    d1, d2 = random.randint(2,max_den), random.randint(2,max_den)
    f1, f2 = sympy.Rational(n1,d1), sympy.Rational(n2,d2)
    if op == '+':
        res = f1+f2
        text = f"{f1} + {f2}"
    elif op=='-':
        if f1<f2: f1,f2=f2,f1
        res = f1-f2
        text = f"{f1} - {f2}"
    elif op=='*':
        res=f1*f2
        text=f"{f1} × {f2}"
    else:
        if f2==0: f2=sympy.Rational(1,2)
        res=f1/f2
        text=f"{f1} ÷ {f2}"
    return text,str(res),(n1,d1),(n2,d2)

def normalize(ans):
    ans = ans.strip().replace(" ","+")
    try: return str(sympy.Rational(ans))
    except: return ans.strip()

# ================== توضیح گام‌به‌گام ==================
def explain(f1_tuple, f2_tuple, op, answer):
    f1 = sympy.Rational(f1_tuple[0], f1_tuple[1])
    f2 = sympy.Rational(f2_tuple[0], f2_tuple[1])
    explanation = f"سوال: {f1} {op} {f2}\n\n"

    if op in ['+','-']:
        # جمع و تفریق با مخرج مشترک
        lcm = sympy.lcm(f1.q,f2.q)
        explanation += f"مرحله 1: یافتن مخرج مشترک بین {f1.q} و {f2.q} → {lcm}\n"
        explanation += f"توضیح: کوچک‌ترین عددی که هر دو مخرج در آن بخش‌پذیر باشند.\n"
        f1_new = f1*(lcm//f1.q)
        f2_new = f2*(lcm//f2.q)
        explanation += f"مرحله 2: تبدیل کسرها به مخرج مشترک:\n"
        explanation += f"  {f1} → {f1_new}\n"
        explanation += f"  {f2} → {f2_new}\n"
        res = f1_new+f2_new if op=='+' else f1_new-f2_new
        explanation += f"مرحله 3: {f1_new} {op} {f2_new} = {res}\n"
        if res>1:
            whole = res.p//res.q
            remainder = res-whole
            if remainder>0:
                explanation += f"مرحله 4: عدد مخلوط → {whole} و {remainder}\n"
            else:
                explanation += f"مرحله 4: پاسخ نهایی = {whole}\n"
        else:
            explanation += f"مرحله 4: پاسخ نهایی = {res}\n"

    elif op=='*':
        res = f1*f2
        explanation += f"مرحله 1: ضرب کسرها: {f1} × {f2} = {res}\n"
        if res>1:
            whole = res.p//res.q
            remainder = res-whole
            if remainder>0:
                explanation += f"مرحله 2: عدد مخلوط → {whole} و {remainder}\n"
            else:
                explanation += f"مرحله 2: پاسخ نهایی = {whole}\n"
        else:
            explanation += f"مرحله 2: پاسخ نهایی = {res}\n"

    else:  # تقسیم
        explanation += f"مرحله 1: تبدیل تقسیم به ضرب معکوس:\n"
        explanation += f"  {f1} ÷ {f2} = {f1} × {f2.q}/{f2.p} = {f1} × {sympy.Rational(f2.q,f2.p)}\n"
        res = f1 * sympy.Rational(f2.q,f2.p)
        explanation += f"مرحله 2: انجام ضرب: {f1} × {sympy.Rational(f2.q,f2.p)} = {res}\n"
        if res>1:
            whole = res.p//res.q
            remainder = res-whole
            if remainder>0:
                explanation += f"مرحله 3: عدد مخلوط → {whole} و {remainder}\n"
            else:
                explanation += f"مرحله 3: پاسخ نهایی = {whole}\n"
        else:
            explanation += f"مرحله 3: پاسخ نهایی = {res}\n"

    return explanation

# ================== هندلرها ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    save_user(user_id,user)
    await update.message.reply_text("انتخاب زبان / Choose language:",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("FA",callback_data="lang_fa"),InlineKeyboardButton("EN",callback_data="lang_en")]
    ]))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if query.data.startswith("lang_"):
        user['lang']=query.data.split("_")[1]
        save_user(user_id,user)
        await query.edit_message_text(t(user['lang'],"welcome")+"\n\n"+t(user['lang'],"choose_op"),reply_markup=op_keyboard(user['lang']))
        return
    
    op=query.data
    if not user['is_vip'] and user['trial']<=0:
        await query.edit_message_text(t(user['lang'],'trial_over')+"\n\n"+t(user['lang'],'send_proof'))
        return
    
    problem,answer,f1_tuple,f2_tuple=generate_problem(op,vip=user['is_vip'])
    user.update({"expected_answer":answer,"topic":op,"problem_text":problem,"f1_tuple":f1_tuple,"f2_tuple":f2_tuple})
    if not user['is_vip']:
        user['trial']-=1
    save_user(user_id,user)
    await query.edit_message_text(f"{problem} = ?\n\n{t(user['lang'],'trial_left')}: {user['trial']}\n\nجواب خود را وارد کنید:")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = get_user(user_id)
    if not user.get("expected_answer"):
        await update.message.reply_text("لطفاً ابتدا /start را بزنید")
        return
    user['total']+=1
    if normalize(text)==user['expected_answer']:
        user['correct']+=1
        feedback = t(user['lang'],'correct')
    else:
        feedback = f"{t(user['lang'],'wrong')} {user['expected_answer']}\n\n{explain(user['f1_tuple'],user['f2_tuple'],user['topic'],user['expected_answer'])}"
    save_user(user_id,user)
    await update.message.reply_text(feedback+"\n\n"+t(user['lang'],'next_question'),reply_markup=op_keyboard(user['lang']))

# ================== اجرا ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,message_handler))
    logging.info("Fraction Bot started!")
    app.run_polling()

if __name__=="__main__":
    main()
