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
TON_PRICING_TIERS = { # (pricing structure remains the same) ... }

# --- Client Initialization (Secure Reading of Keys) ---
def initialize_gemini():
    """Reads Gemini API key securely from environment variable."""
    # Reads the key from the environment variable (NOT hardcoded)
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

# --- Data Persistence Functions (load_data, save_data, get_user_data) ---
# ... (Include the standard load_data, save_data, get_user_data functions here) ...

# --- 2. Business Logic: Manual TON Payment & Trial Control ---
def generate_manual_ton_invoice():
    """Generates the subscription message showing static address for manual payment."""
    # (Uses the TON_WALLET_ADDRESS read securely from the environment)
    invoice_text = "⭐️ **Your free trial has ended!**\n\n"
    # ... (pricing tiers displayed) ...
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
# ... (Include generate_llm_explanation and generate_random_fraction_problem here) ...

# --- 4. Telegram Handler Functions (start_command, handle_callback_query, etc.) ---
# ... (Include all async functions: start_command, handle_callback_query, handle_operation_selection, handle_user_answer) ...

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
