# bot/handlers.py (Final reliable version)

from telegram import Update
from telegram.ext import ContextTypes


async def send_global_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a global welcome/help message using supported HTML tags for maximum compatibility."""

    # Using standard Python f-string or triple quotes with HTML tags (b and code)
    welcome_message = (
        "👋 <b>Welcome to the Precious Place Bot!</b>\n\n"
        "I can help you manage your Ingredients, Recipies, and Cash Flow in natural language.\n\n"
        "Enter the different modes with the commands below.\n\n"
             
        "<b>📝 Available Modes</b>\n"
        "• <b>Manage Ingredients:</b> Track Ingredients inventory, purchases and prices.\n"
        "• <b>[Future Mode 1]:</b> (e.g., Recipe Planner Mode)\n"
        "• <b>[Future Mode 2]:</b> (e.g., Financial Analysis Mode)\n\n"
        
        "Type \"Stop\" to return to this menu.\n\n"
        
        "<b>💬 Global Commands</b>\n"
        "You can type <code>start</code>, <code>hello</code>, or <code>help</code> anytime to see this message."
    )
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode="HTML" 
    )

async def global_fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catches any message that hasn't been handled by specific commands or state handlers.
    It provides a simple welcome menu and entry point instructions.
    """
    logging.info(f"FALLBACK: Received unhandled message from user {update.effective_user.id}: {update.message.text}")
    
    reply = (
        "👋 <b>Welcome to the Precious Place Bot!</b>\n\n"
        "I can help you manage your Ingredients, Recipies, and Cash Flow in natural language.\n\n"
        "Enter the different modes with the commands below.\n\n"
             
        "<b>📝 Available Modes</b>\n"
        "• <b>Manage Ingredients:</b> Track Ingredients inventory, purchases and prices.\n"
        "• <b>[Future Mode 1]:</b> (e.g., Recipe Planner Mode)\n"
        "• <b>[Future Mode 2]:</b> (e.g., Financial Analysis Mode)\n\n"
        
        "Type \"Stop\" to return to this menu.\n\n"
        
        "<b>💬 Global Commands</b>\n"
        "You can type <code>start</code>, <code>hello</code>, or <code>help</code> anytime to see this message."
    )
    
    # We use HTML parsing for formatting (bold, code blocks)
    await update.message.reply_text(reply, parse_mode="HTML")