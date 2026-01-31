from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

async def start_command(client: Client, message: Message):
    print(f"Start command received from {message.from_user.id}")
    text = (
        "👋 **Welcome to the Auto Post Bot!**\n\n"
        "I can help you manage your channel content automatically.\n"
        "Please purchase a subscription to get started."
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Subscription", callback_data="buy_sub")]
    ])
    await message.reply_text(text, reply_markup=buttons)

def register(app: Client):
    app.add_handler(MessageHandler(start_command, filters.command("start") & filters.private))
    print("✅ Plugin 'start' registered")

from pyrogram.handlers import MessageHandler
