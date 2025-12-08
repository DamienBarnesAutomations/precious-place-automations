from fastapi import FastAPI
from starlette.responses import HTMLResponse

# Create the main FastAPI application instance
app = FastAPI(title="Telegram Bakery Bot Backend")

@app.get("/", response_class=HTMLResponse)
async def root():
    """
    A simple root endpoint to confirm the service is running.
    """
    return "<h1>Telegram Bakery Bot Backend is running! 🚀</h1>"

# You will add your Telegram webhook logic here later.