import random
import sympy
import json
import os
import logging
from google import genai
from google.genai import types 
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

# --- Setup and Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Configuration and Data Persistence ---
DATA_FILE = 'user_data.json'
USER_SCORES = {}

# Final tiered pricing structure in TON
TON_PRICING_TIERS = {
    '1': {'months': 1, 'price': 3, 'desc': 'Monthly'},
    '3': {'months': 3, 'price': 8, 'desc': 'Quarterly (~11% Savings)'},
    '6': {'months': 6, 'price': 15, 'desc': 'Semi-Annual (~16.6% Savings)'},
    '12': {'months': 12, 'price': 28, 'desc': 'Annual (Best Offer - ~22.2% Savings)'},
}

# --- Client Initialization (Secure Reading of Keys) ---
def initialize_gemini():
    """Reads Gemini API key securely from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY") 
    if not api_key:
        logging.warning("GEMINI_API_KEY environment variable is missing!")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logging.error(f"Error initializing Gemini Client: {e}")
        return None

GEMINI_CLIENT = initialize_gemini()
# Securely read the TON wallet address for manual payment
TON_WALLET_ADDRESS = os.environ.get("TON_WALLET_ADDRESS", "YOUR_TON_WALLET_ADDRESS_GOES_IN_THE_SERVER_SETTINGS")

# --- Data Persistence Functions ---
def load_data():
    global USER_SCORES
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                USER_SCORES = json.load(f)
        except json.JSONDecodeError:
            logging.error("Error loading user data from JSON.")
            USER_SCORES = {}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(USER_SCORES, f, indent=4)

def get_user_data(user_id):
    user_id_str = str(user_id)
    if user_id_str not in USER_SCORES:
        USER_SCORES[user_id_str] = {'correct': 0, 'total': 0, 'topic': '+', 
                                    'expected_answer': None, 'd1': 0, 'd2': 0,
                                    'is_subscribed': False, 
                                    'trial_count': 0,
                                    'problem_text': ''}
    return USER_SCORES[user_id_str]

# --- 2. Business Logic: Manual TON Payment & Trial Control ---
def generate_manual_ton_invoice():
    """Generates the subscription message showing static address for manual payment."""
    invoice_text = "⭐️ **Your free trial has ended!**\n\n"
    invoice_text += "Please choose one of the subscription plans:\n"
    
    # Display tiers
    for key, tier in TON_PRICING_TIERS.items():
        invoice_text += f"   - {tier['months']} Months: **{tier['price']} TON**\n"
        
    invoice_text += "\nTo pay manually, transfer the **exact TON amount** to the address below:\n\n"
    invoice_text += f"``` {TON_WALLET_ADDRESS} ```\n\n"
    invoice_text += "❗ **IMPORTANT:** Please send a screenshot of the successful transaction to the admin for manual activation."
    return invoice_text

async def check_subscription(user_data):
    """Checks the subscription status and the 30-exercise trial limit."""
    if user_data['is_subscribed']:
        return True, None 
    
    if user_data['total'] < 30: 
        return True, f"🎁 {30 - user_data['total']} free exercises remaining."
    
    return False, generate_manual_ton_invoice() 

# --- 3. Core Logic: SymPy Math and Gemini AI Explanation ---

def generate_llm_explanation(op, problem_text, answer, d1, d2):
    """Calls the Gemini API to get a real step-by-step explanation."""
    
    if not GEMINI_CLIENT:
        return f"Smart Tutor is offline. The correct answer is {answer}."
    
    # Prompt customization based on operation
    if op in ['+', '-']:
        common_denom = sympy.lcm(d1, d2)
        prompt = (f"You are a math tutor. Explain step-by-step how to solve the fraction problem: {problem_text}. "
                  f"Clearly state that the common denominator (LCM) of {d1} and {d2} is {common_denom}. "
                  f"The final simplified answer is {answer}. Focus on the educational steps for a student.")
    else:
        prompt = (f"You are a math tutor. Explain step-by-step how to solve the fraction problem: {problem_text}. "
                  f"The final simplified answer is {answer}.")

    try:
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return f"Error connecting to the Smart Tutor: The correct answer is {answer}."

def generate_random_fraction_problem(operation):
    """Generates a random fraction problem based on the operation."""
    n1, n2 = random.randint(1, 5), random.randint(1, 5)
    d1, d2 = random.randint(2, 7), random.randint(2, 7)
    
    f1 = sympy.Rational(n1, d1)
    f2 = sympy.Rational(n2, d2)
    
    if operation == '+': problem_text, answer = f"{f1} + {f2}", f1 + f2
    elif operation == '-': problem_text, answer = f"{f1} - {f2}", f1 - f2
    elif operation == '*': problem_text, answer = f"{f1} * {f2}", f1 * f2
    elif operation == '/':
        if f2 == 0: return generate_random_fraction_problem(operation) # Prevents division by zero
        problem_text, answer = f"{f1} / {f2}", f1 / f2
    
    return problem_text, str(answer), f1.q, f2.q

# --- 4. Telegram Handler Functions (async) ---

def build_operation_keyboard():
    """Builds the inline keyboard for math operations."""
    keyboard = [
        [InlineKeyboardButton("➕ Add", callback_data='+'),
         InlineKeyboardButton("➖ Subtract", callback_data='-')],
        [InlineKeyboardButton("✖️ Multiply", callback_data='*'),
         InlineKeyboardButton("➗ Divide", callback_data='/')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context):
    """Handles the /start command."""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    score, total = user_data['correct'], user_data['total']
    accuracy = (score / total) * 100 if total > 0 else 0
    
    message = (f"🤖 Welcome to the Smart Practice Bot!\n"
               f"Accuracy: {accuracy:.2f}%\n"
               f"✅ Correct: {score} | ❓ Total Questions: {total}\n"
               "\n**Please select an operation to begin:**")

    await update.message.reply_text(message, reply_markup=build_operation_keyboard())

async def handle_callback_query(update: Update, context):
    """Handles button presses (+, -, *, /)."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    operation = query.data
    
    await handle_operation_selection(user_id, operation, query) 

async def handle_operation_selection(user_id, operation, query):
    """Core logic to check subscription and generate question."""
    user_data = get_user_data(user_id)
    
    is_allowed, prompt_or_status = await check_subscription(user_data)
    
    if not is_allowed:
        await query.edit_message_text(prompt_or_status) 
        return

    problem, final_answer, d1, d2 = generate_random_fraction_problem(operation)
    
    user_data.update({'expected_answer': final_answer, 'topic': operation, 'd1': d1, 'd2': d2, 'problem_text': problem})
    save_data()
    
    status_text = f"\n💡 Status: {prompt_or_status}" if prompt_or_status else ""
    
    message = (f"🔢 Random Practice: {operation}{status_text}\n"
               f"Problem: **{problem}** = ?\n"
               "Please enter your answer simplified (e.g., 5/6).")
               
    await query.edit_message_text(message)

async def handle_user_answer(update: Update, context):
    """Checks the user's answer, updates score, and provides educational feedback."""
    user_id = update.effective_user.id
    user_answer = update.message.text
    user_data = get_user_data(user_id)
    expected_answer = user_data.get('expected_answer')

    if not expected_answer:
        await update.message.reply_text("⚠️ Please select an operation from the menu first using /start.")
        return

    user_data['total'] += 1
    if user_answer.strip() == expected_answer:
        user_data['correct'] += 1
        feedback_text = "Awesome! Your answer is completely correct. 🎉"
    else:
        # Incorrect answer: Generate detailed LLM explanation
        d1, d2, op, problem_text = user_data['d1'], user_data['d2'], user_data['topic'], user_data['problem_text']
        
        explanation = generate_llm_explanation(op, problem_text, expected_answer, d1, d2)
        
        feedback_text = (f"❌ Incorrect! The correct answer is {expected_answer}.\n"
                         f"💡 **Smart Tutor Explanation:**\n{explanation}")

    save_data()
    
    await update.message.reply_text(feedback_text)
    
    # Prompt the user to select the next question
    await start_command(update, context)


# --- 5. Main Application Loop ---

def main():
    """Starts the bot by initializing the Application and registering handlers."""
    # Read BOT_TOKEN securely from the environment
    TOKEN = os.environ.get("BOT_TOKEN") 
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set. Cannot run bot without token.")
    
    load_data()
    application = Application.builder().token(TOKEN).build()

    # Register Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_answer))

    logging.info("Bot started polling...")
    application.run_polling() 

if __name__ == '__main__':
    main()
