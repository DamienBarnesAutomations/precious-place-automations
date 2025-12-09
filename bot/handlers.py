# bot/handlers.py (Final reliable version)

from telegram import Update
from telegram.ext import ContextTypes


async def send_global_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a global welcome/help message using supported HTML tags for maximum compatibility."""

    # Using standard Python f-string or triple quotes with HTML tags (b and code)
    welcome_message = (
        "👋 <b>Welcome to the Bakery Bot!</b>\n\n"
        "I can help you manage your ingredients, track stock, and log costs.\n\n"
        
        "<b>📝 Available Modes</b>\n"
        "• <b>Ingredient Manager Mode:</b> Type <code>Manage Ingredients</code> to switch the bot into natural language mode for tracking stock, costs, and purchases.\n"
        "  • <b>In Manager Mode:</b> Send actions like <code>Bought 1 kg Flour for 5</code> or <code>Check stock for ING001</code>.\n"
        "  • <b>To Exit:</b> Type <code>STOP</code>\n"
        "• <b>[Future Mode 1]:</b> (e.g., Recipe Planner Mode)\n"
        "• <b>[Future Mode 2]:</b> (e.g., Financial Analysis Mode)\n\n"
        
        "<b>💬 Global Commands</b>\n"
        "You can type <code>start</code>, <code>hello</code>, or <code>help</code> anytime to see this message."
    )
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode="HTML" 
    )