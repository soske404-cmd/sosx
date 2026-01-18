import json
import asyncio
import threading
import os
from pyrogram import Client, idle
from flask import Flask

# Ensure DATA directory exists
if not os.path.exists("DATA"):
    os.makedirs("DATA")

# Ensure FILES directory exists for config
if not os.path.exists("FILES"):
    os.makedirs("FILES")

# Create default config if not exists
CONFIG_FILE = "FILES/config.json"
if not os.path.exists(CONFIG_FILE):
    default_config = {
        "API_ID": "YOUR_API_ID",
        "API_HASH": "YOUR_API_HASH",
        "BOT_TOKEN": "YOUR_BOT_TOKEN",
        "OWNER": "YOUR_OWNER_ID"
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=4)
    print("Please configure FILES/config.json with your credentials")

# Load bot credentials
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    DATA = json.load(f)
    API_ID = DATA.get("API_ID")
    API_HASH = DATA.get("API_HASH")
    BOT_TOKEN = DATA.get("BOT_TOKEN")

# Plugin directory - all .py files in root that are bot handlers
plugins = dict(root=".")

# Pyrogram client
bot = Client(
    "MY_BOT",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=plugins
)

# Flask App for health check
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/health")
def health():
    return {"status": "ok", "bot": "running"}

def run_flask():
    app.run(host="0.0.0.0", port=3000)

async def run_bot():
    await bot.start()
    print("Bot is running...")
    print("Commands Available:")
    print("  /au - Single Autostripe Check")
    print("  /mau - Mass Autostripe Check")
    print("  /addurl - Add site for Autostripe")
    print("  /myurl - View your current site")
    print("  /delurl - Delete your site")
    print("  /setpx - Set proxy for mass checking")
    print("  /register - Register user")
    print("  /start - Start bot")
    print("  /cmds - View all commands")

    await idle()
    await bot.stop()
    print("Bot stopped.")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    # Run Flask in a separate thread
    threading.Thread(target=run_flask, daemon=True).start()

    # Start bot loop
    asyncio.run(run_bot())
