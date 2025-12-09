# bot/handlers.py

from telegram import Update
from telegram.ext import ContextTypes

async def send_global_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a global welcome/help message detailing all available modes and commands."""
    
    welcome_message = (
        "👋 **Welcome to the Bakery Bot!**\n\n"
        "I can help you manage your ingredients, track stock, and log costs.\n\n"
        "### 📝 **Available Modes**\n"
        "* **Ingredient Manager Mode:** Type `Manage Ingredients` to switch the bot into natural language mode for tracking stock, costs, and purchases.\n"
        "   * **In Manager Mode:** Send actions like `Bought 1 kg Flour for 5` or `Check stock for ING001`.\n"
        "   * **To Exit:** Type `STOP`\n"
        "* **[Future Mode 1]:** (e.g., Recipe Planner Mode)\n"
        "* **[Future Mode 2]:** (e.g., Financial Analysis Mode)\n\n"
        "### 💬 **Global Commands**\n"
        "You can type `start`, `hello`, or `help` anytime to see this message."
    )
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")