import asyncio
import logging
from pyrogram import Client, idle, filters
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from database import init_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scheduler_tasks import daily_post_job, expiry_check_job
from web_server import start_server

# Import plugins manually
from plugins import start, payment, indexing, admin_settings

app = Client(
    "auto_post_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# Register handlers manually
start.register(app)
payment.register(app)
indexing.register(app)
admin_settings.register(app)

@app.on_message(filters.command("ping"))
async def ping_handler(client, message):
    logger.info(f"Ping received from {message.from_user.id}")
    await message.reply_text("🏓 Pong! Bot is alive.")

# Global scheduler
scheduler = AsyncIOScheduler()

async def main():
    # Initialize Database
    await init_db()
    
    # Start Bot
    await app.start()
    print("Bot Started")
    
    # Notify Owner
    try:
        if OWNER_ID:
            await app.send_message(OWNER_ID, "🤖 Bot restarted successfully!")
    except Exception as e:
        logger.error(f"Failed to send startup message: {e}")

    # Start Web Server
    await start_server()
    
    # Start Scheduler
    # Run the checker frequently (e.g. every 5 minutes) so it can respond to interval changes
    scheduler.add_job(daily_post_job, "interval", minutes=5, args=[app])
    scheduler.add_job(expiry_check_job, "interval", hours=1, args=[app])
    scheduler.start()
    
    # Keep running
    await idle()
    
    await app.stop()

if __name__ == "__main__":
    try:
        app.run(main())
    except KeyboardInterrupt:
        pass
