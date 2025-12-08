import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from starlette.responses import HTMLResponse

# --- Configuration ---
# Get the token from Render Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN is not set!")

# --- Application Setup ---
app = FastAPI(title="Telegram Bakery Bot Backend")

# Initialize the Application
application = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

# You will add command handlers here later, e.g.:
# application.add_handler(CommandHandler("start", start_command))

# --- FastAPI Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    A simple root endpoint to confirm the service is running.
    """
    return "<h1>Telegram Bakery Bot Backend is running and awaiting webhook! 🚀</h1>"

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Endpoint to receive all incoming updates from Telegram.
    """
    
     # --- CRITICAL FIX ---
    # The application must be initialized before processing the update.
    if not app_initialized:
        await application.initialize()
        app_initialized = True
    # --------------------
    try:
        # Get the JSON data from the request
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Pass the data to the python-telegram-bot Application
    update = Update.de_json(data, application.bot)
    await application.process_update(update)

    # Telegram requires an immediate 200 OK response
    return {"message": "Update processed"}

# --- Run Command (for local development only) ---
# if __name__ == "__main__":
#     # NOTE: Render will use the 'uvicorn main:app' Start Command
#     uvicorn.run(app, host="0.0.0.0", port=8000)