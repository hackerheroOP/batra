from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user_subscriptions
import time
from datetime import datetime

async def my_subs_command(client: Client, message: Message):
    user_id = message.from_user.id
    subs = await get_user_subscriptions(user_id)
    
    if not subs:
        text = "❌ **You have no active subscriptions.**\n\nTap the button below to purchase one!"
    else:
        text = "📋 **Your Active Subscriptions:**\n\n"
        for sub in subs:
            expiry_ts = sub.get("expiry_date")
            if expiry_ts:
                expiry_date = datetime.fromtimestamp(expiry_ts).strftime('%Y-%m-%d %H:%M:%S')
            else:
                expiry_date = "Never"
                
            channel_id = sub.get("channel_id", "Unknown")
            # Try to get channel title if possible, or just ID
            try:
                chat = await client.get_chat(channel_id)
                channel_name = chat.title
            except:
                channel_name = str(channel_id)
            
            text += (
                f"📺 **Channel:** {channel_name}\n"
                f"🆔 **ID:** `{channel_id}`\n"
                f"📅 **Plan:** {sub.get('plan_type', 'Unknown')}\n"
                f"⏳ **Expires:** {expiry_date}\n"
                f"➖➖➖➖➖➖➖➖➖➖\n"
            )
            
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Subscription", callback_data="buy_sub")]
    ])
    
    await message.reply_text(text, reply_markup=buttons)

from pyrogram.handlers import MessageHandler

def register(app: Client):
    app.add_handler(MessageHandler(my_subs_command, filters.command(["my_subs", "subscriptions"]) & filters.private))
    print("✅ Plugin 'user_commands' registered")
