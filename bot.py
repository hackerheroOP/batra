import asyncio
from pyrogram import Client, idle
from config import API_ID, API_HASH, BOT_TOKEN
from database import init_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# We will import scheduler tasks later
# from plugins.scheduler import daily_post_job, expiry_check_job

app = Client(
    "auto_post_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins"),
    in_memory=True
)

# Global scheduler
scheduler = AsyncIOScheduler()

async def main():
    # Initialize Database
    await init_db()
    
    # Start Bot
    await app.start()
    print("Bot Started")

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
