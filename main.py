from fractions import Fraction
import math
import os
import re
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# -------- Logging --------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------- Helper Functions --------

def parse_fraction(text: str) -> Fraction:
    text = text.strip()
    m = re.fullmatch(r"([+-]?\d+)\s*/\s*([+-]?\d+)", text)
    if not m:
        raise ValueError("Oops! Fractions must look like '1/2'. Try again!")
    num = int(m.group(1))
    den = int(m.group(2))
    if den == 0:
        raise ValueError("Uh-oh! The bottom of a fraction can't be zero.")
    return Fraction(num, den)

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def format_frac(fr: Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"

# -------- Explanation Functions (Kid-Friendly) --------

def explain_add_sub(a: Fraction, b: Fraction, op: str) -> str:
    A_num, A_den = a.numerator, a.denominator
    B_num, B_den = b.numerator, b.denominator

    the_lcm = lcm(A_den, B_den)

    lines = []
    action = 'add' if op == '+' else 'subtract'
    lines.append(f"Let's {action} {format_frac(a)} {op} {format_frac(b)} step by step! ✨")
    lines.append("")
    lines.append(f"1️⃣ Find the Least Common Denominator (LCD):")
    lines.append(f"   First bottom: {A_den}")
    lines.append(f"   Second bottom: {B_den}")
    lines.append(f"   LCD: {the_lcm}")
    lines.append("")

    mul1 = the_lcm // A_den
    newA_num = A_num * mul1
    lines.append(f"2️⃣ Change the first fraction to have the common bottom:")
    lines.append(f"   Top: {A_num} × {mul1} = {newA_num}")
    lines.append(f"   Bottom: {A_den} × {mul1} = {the_lcm}")
    lines.append(f"   First fraction now: {newA_num}/{the_lcm}")
    lines.append("")

    mul2 = the_lcm // B_den
    newB_num = B_num * mul2
    lines.append(f"   Change the second fraction:")
    lines.append(f"   Top: {B_num} × {mul2} = {newB_num}")
    lines.append(f"   Bottom: {B_den} × {mul2} = {the_lcm}")
    lines.append(f"   Second fraction now: {newB_num}/{the_lcm}")
    lines.append("")

    result_num = newA_num + newB_num if op == '+' else newA_num - newB_num
    lines.append(f"3️⃣ Now {action} the tops:")
    lines.append(f"   {newA_num}/{the_lcm} {op} {newB_num}/{the_lcm} = {result_num}/{the_lcm}")
    lines.append("")

    final = Fraction(result_num, the_lcm)
    lines.append(f"4️⃣ Simplify the fraction:")
    lines.append(f"   Final answer: {format_frac(final)} 🎉")

    return '\n'.join(lines)


def explain_mul(a: Fraction, b: Fraction) -> str:
    A_num, A_den = a.numerator, a.denominator
    B_num, B_den = b.numerator, b.denominator

    lines = []
    lines.append(f"Let's multiply {format_frac(a)} × {format_frac(b)} step by step! ✨")
    lines.append("")
    lines.append("1️⃣ Multiply tops and bottoms:")
    res_num = A_num * B_num
    res_den = A_den * B_den
    lines.append(f"   Top: {A_num} × {B_num} = {res_num}")
    lines.append(f"   Bottom: {A_den} × {B_den} = {res_den}")
    lines.append(f"   Result: {res_num}/{res_den}")
    lines.append("")
    final = Fraction(res_num, res_den)
    lines.append(f"2️⃣ Simplify: {format_frac(final)} 🎉")

    return '\n'.join(lines)


def explain_div(a: Fraction, b: Fraction) -> str:
    A_num, A_den = a.numerator, a.denominator
    B_num, B_den = b.numerator, b.denominator

    lines = []
    lines.append(f"Let's divide {format_frac(a)} ÷ {format_frac(b)} step by step! ✨")
    lines.append("")
    lines.append("1️⃣ Flip the second fraction and multiply:")
    lines.append(f"   Second fraction: {format_frac(b)} → flipped: {B_den}/{B_num}")
    lines.append("")

    res_num = A_num * B_den
    res_den = A_den * B_num
    lines.append(f"2️⃣ Multiply tops and bottoms:")
    lines.append(f"   Top: {A_num} × {B_den} = {res_num}")
    lines.append(f"   Bottom: {A_den} × {B_num} = {res_den}")
    lines.append(f"   Result: {res_num}/{res_den}")
    lines.append("")

    final = Fraction(res_num, res_den)
    lines.append(f"3️⃣ Simplify: {format_frac(final)} 🎉")

    return '\n'.join(lines)

# -------- Telegram Handlers --------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! 👋 I'm your friendly Fraction Bot. Send /help to see what I can do!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Here’s what I can do! ✨\n\n"
        "/add a/b c/d – Add fractions\n"
        "/sub a/b c/d – Subtract fractions\n"
        "/mul a/b c/d – Multiply fractions\n"
        "/div a/b c/d – Divide fractions\n\n"
        "Example: /add 1/2 1/3"
    )
    await update.message.reply_text(help_text)

async def handle_operation(update: Update, context: ContextTypes.DEFAULT_TYPE, op: str):
    msg = update.message.text or ""
    parts = msg.split()
    if len(parts) != 3:
        await update.message.reply_text("Try like this: /add 1/2 1/3")
        return
    try:
        f1 = parse_fraction(parts[1])
        f2 = parse_fraction(parts[2])
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    if op == 'add':
        text = explain_add_sub(f1, f2, '+')
    elif op == 'sub':
        text = explain_add_sub(f1, f2, '-')
    elif op == 'mul':
        text = explain_mul(f1, f2)
    elif op == 'div':
        if f2.numerator == 0:
            await update.message.reply_text("You can't divide by zero 😅")
            return
        text = explain_div(f1, f2)
    else:
        text = "Unknown operation"

    MAX = 3500
    for i in range(0, len(text), MAX):
        await update.message.reply_text(text[i:i+MAX])

async def add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_operation(update, context, 'add')

async def sub_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_operation(update, context, 'sub')

async def mul_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_operation(update, context, 'mul')

async def div_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_operation(update, context, 'div')

# -------- Run Bot --------

def main():
    token = os.environ.get('BOT_TOKEN') or 'PASTE_YOUR_TOKEN_HERE'
    if token == 'PASTE_YOUR_TOKEN_HERE':
        logger.error('Please set your bot token in BOT_TOKEN or in the code.')
        print('Please set your bot token in BOT_TOKEN or in the code.')
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('add', add_handler))
    app.add_handler(CommandHandler('sub', sub_handler))
    app.add_handler(CommandHandler('mul', mul_handler))
    app.add_handler(CommandHandler('div', div_handler))

    logger.info('Bot is running...')
    app.run_polling()

if __name__ == '__main__':
    main()
