from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID
from database import get_settings, update_settings

@Client.on_message(filters.command("settings") & filters.user(OWNER_ID))
async def show_settings(client: Client, message: Message):
    settings = await get_settings()
    if not settings:
        await message.reply_text("❌ Settings not initialized yet.")
        return
        
    text = (
        "⚙️ **Current Settings**\n\n"
        f"🕒 **Post Interval:** `{settings.get('interval_hours', 24)} hours`\n"
        f"📦 **Posts per Run:** `{settings.get('posts_per_run', 1)} posts`\n\n"
        "**Commands:**\n"
        "`/set_interval <hours>`\n"
        "`/set_posts <number>`"
    )
    await message.reply_text(text)

@Client.on_message(filters.command("set_interval") & filters.user(OWNER_ID))
async def set_interval(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/set_interval <hours>`")
            return
            
        hours = float(message.command[1])
        if hours <= 0:
            await message.reply_text("❌ Interval must be greater than 0.")
            return
            
        await update_settings(interval_hours=hours)
        await message.reply_text(f"✅ **Interval updated to {hours} hours.**")
        
    except ValueError:
        await message.reply_text("❌ Invalid number format.")

@Client.on_message(filters.command("set_posts") & filters.user(OWNER_ID))
async def set_posts_count(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/set_posts <number>`")
            return
            
        count = int(message.command[1])
        if count <= 0:
            await message.reply_text("❌ Count must be greater than 0.")
            return
            
        await update_settings(posts_per_run=count)
        await message.reply_text(f"✅ **Posts per run updated to {count}.**")
        
    except ValueError:
        await message.reply_text("❌ Invalid number format.")
