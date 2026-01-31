from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    text = (
        "👋 **Welcome to the Auto Post Bot!**\n\n"
        "I can help you manage your channel content automatically.\n"
        "Please purchase a subscription to get started."
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Subscription", callback_data="buy_sub")]
    ])
    await message.reply_text(text, reply_markup=buttons)
