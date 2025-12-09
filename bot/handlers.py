# bot/handlers.py

from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

async def send_global_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a global welcome/help message detailing all available modes and commands."""
    
    # NOTE: Using HTML tags for robust static formatting
    welcome_message = (
        "👋 <b>Welcome to the Bakery Bot!</b>\n\n"
        "I can help you manage your ingredients, track stock, and log costs.\n\n"
        "<h3>📝 Available Modes</h3>\n"
        "<ul>"
        "<li><b>Ingredient Manager Mode:</b> Type <code>Manage Ingredients</code> to switch the bot into natural language mode for tracking stock, costs, and purchases.</li>\n"
        "   <ul>"
        "   <li><b>In Manager Mode:</b> Send actions like <code>Bought 1 kg Flour for 5</code> or <code>Check stock for ING001</code>.</li>\n"
        "   <li><b>To Exit:</b> Type <code>STOP</code></li>\n"
        "   </ul>"
        "<li><b>[Future Mode 1]:</b> (e.g., Recipe Planner Mode)</li>\n"
        "<li><b>[Future Mode 2]:</b> (e.g., Financial Analysis Mode)</li>\n"
        "</ul>\n"
        "<h3>💬 Global Commands</h3>\n"
        "You can type <code>start</code>, <code>hello</code>, or <code>help</code> anytime to see this message."
    )
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode="HTML" # <--- IMPORTANT: Change the parse mode to HTML
    )