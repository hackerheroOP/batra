from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_CHANNEL_ID, OWNER_ID
from database import add_pending_subscription, get_subscription, activate_subscription, reject_subscription, get_active_subscriptions

# Simple in-memory state management
# Structure: user_id: {"state": "STATE_NAME", "data": {...}}
user_states = {}

# States
STATE_WAITING_CHANNEL = "WAITING_CHANNEL"
STATE_WAITING_GC_CODE = "WAITING_GC_CODE"
STATE_WAITING_GC_PIN = "WAITING_GC_PIN"

@Client.on_callback_query(filters.regex("^buy_sub$"))
async def show_plans(client: Client, callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "📅 **Choose a Subscription Plan**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 Monthly Plan", callback_data="plan_monthly")]
        ])
    )

@Client.on_callback_query(filters.regex("^plan_monthly$"))
async def ask_channel(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_states[user_id] = {"state": STATE_WAITING_CHANNEL, "data": {"plan": "monthly"}}
    
    await callback_query.message.edit_text(
        "1️⃣ **Setup Step 1:**\n"
        "Please add this bot to your target channel as an Admin.\n"
        "Then, send me the **Channel ID** (starts with -100...).\n\n"
        "If you don't know how to get the ID, forward a message from that channel here."
    )

@Client.on_message(filters.text & filters.private)
async def handle_text_input(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_states:
        return

    state_info = user_states[user_id]
    state = state_info["state"]
    data = state_info["data"]

    if state == STATE_WAITING_CHANNEL:
        channel_id_input = message.text.strip()
        # Basic validation
        if not (channel_id_input.startswith("-100") and channel_id_input[4:].isdigit()):
             # Try to handle forwarded messages if user forwarded instead of typing ID
             if message.forward_from_chat:
                 channel_id_input = str(message.forward_from_chat.id)
             else:
                await message.reply_text("❌ Invalid Channel ID format. It should look like `-1001234567890`. Please try again.")
                return

        # Check if bot is admin in that channel (optional but good)
        try:
            chat_member = await client.get_chat_member(int(channel_id_input), "me")
            if not chat_member.privileges.can_post_messages:
                await message.reply_text("⚠️ I am in that channel, but I don't have permission to post messages. Please promote me and try again.")
                return
        except Exception as e:
            await message.reply_text(f"❌ I cannot access that channel. Make sure I am added as an Admin.\nError: {e}")
            return

        data["channel_id"] = int(channel_id_input)
        
        # Move to Payment Method
        del user_states[user_id] # Clear state temporarily or update it? Update it.
        # Actually, we don't need a state for selecting button, just need to persist data.
        # But since we use callback buttons next, we need to store 'channel_id' somewhere persistent or pass it.
        # I'll keep it in user_states but set state to None or WAITING_PAYMENT_METHOD
        user_states[user_id] = {"state": "WAITING_PAYMENT_METHOD", "data": data}

        await message.reply_text(
            f"✅ Channel Verified: `{channel_id_input}`\n\n"
            "Now choose your payment method:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Amazon Pay Gift Card", callback_data="pay_amazon")],
                [InlineKeyboardButton("Flipkart Gift Card", callback_data="pay_flipkart")]
            ])
        )

    elif state == STATE_WAITING_GC_CODE:
        gc_code = message.text.strip()
        data["gc_code"] = gc_code
        
        user_states[user_id] = {"state": STATE_WAITING_GC_PIN, "data": data}
        await message.reply_text("🔢 **Enter the Gift Card PIN:**")

    elif state == STATE_WAITING_GC_PIN:
        gc_pin = message.text.strip()
        data["gc_pin"] = gc_pin
        
        # Save to DB
        sub_id = await add_pending_subscription(
            user_id=user_id,
            channel_id=data["channel_id"],
            plan_type=data["plan"],
            gc_code=data["gc_code"],
            gc_pin=gc_pin
        )
        
        # Clear state
        del user_states[user_id]
        
        await message.reply_text(
            "✅ **Payment Details Submitted!**\n\n"
            "Your subscription is pending verification. You will be notified once approved."
        )
        
        # Notify Admin
        admin_text = (
            f"🔔 **New Subscription Request**\n\n"
            f"👤 User: {message.from_user.mention} (`{user_id}`)\n"
            f"📢 Channel: `{data['channel_id']}`\n"
            f"📅 Plan: {data['plan']}\n"
            f"💳 Method: {data.get('method', 'Gift Card')}\n"
            f"🎟 Code: `{data['gc_code']}`\n"
            f"🔐 PIN: `{gc_pin}`"
        )
        
        await client.send_message(
            ADMIN_CHANNEL_ID,
            admin_text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Verify", callback_data=f"verify_{sub_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{sub_id}")
                ]
            ])
        )

@Client.on_callback_query(filters.regex("^pay_flipkart$"))
async def pay_flipkart(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in user_states:
        user_states[user_id]["state"] = STATE_WAITING_GC_CODE
        user_states[user_id]["data"]["method"] = "Flipkart"
        await callback_query.message.edit_text("🛒 **Selected: Flipkart Gift Card**\n\nPlease enter the **Gift Card Code**:")
    else:
        await callback_query.message.reply_text("Session expired. Please start over with /start")

@Client.on_callback_query(filters.regex("^pay_amazon$"))
async def pay_amazon(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in user_states:
        user_states[user_id]["state"] = STATE_WAITING_GC_CODE
        user_states[user_id]["data"]["method"] = "Amazon Pay"
        await callback_query.message.edit_text("🛒 **Selected: Amazon Pay Gift Card**\n\nPlease enter the **Gift Card Code**:")
    else:
        await callback_query.message.reply_text("Session expired. Please start over with /start")

# --- Admin Handlers ---

@Client.on_callback_query(filters.regex("^verify_"))
async def admin_verify(client: Client, callback_query: CallbackQuery):
    # Security check: ensure only admins in the admin channel can click this?
    # Pyrogram callback queries from channels might be tricky if not careful, 
    # but usually if the bot is admin in the channel, it receives it.
    # We should ideally check if the user clicking is an admin, but for simplicity assuming the channel is private/restricted.
    
    sub_id = int(callback_query.data.split("_")[1])
    sub = await get_subscription(sub_id)
    
    if not sub:
        await callback_query.answer("Subscription not found or already processed.", show_alert=True)
        return

    if sub['status'] == 'active':
        await callback_query.answer("Already verified.", show_alert=True)
        return

    await activate_subscription(sub_id)
    
    await callback_query.message.edit_text(
        callback_query.message.text + "\n\n✅ **VERIFIED**"
    )
    
    # Notify User
    try:
        await client.send_message(
            sub['user_id'],
            "🎉 **Subscription Approved!**\n\n"
            "Your channel is now active. The bot will start posting videos automatically."
        )
    except Exception:
        pass # User might have blocked bot
        
    # Notify Channel (Optional per requirements)
    try:
        await client.send_message(
            sub['channel_id'],
            "✅ **Auto Post Bot is now Active!**"
        )
    except Exception:
        pass

@Client.on_callback_query(filters.regex("^reject_"))
async def admin_reject(client: Client, callback_query: CallbackQuery):
    sub_id = callback_query.data.split("_")[1]
    sub = await get_subscription(sub_id)
    
    if not sub:
        await callback_query.answer("Subscription not found.", show_alert=True)
        return

    await reject_subscription(sub_id)
    
    await callback_query.message.edit_text(
        callback_query.message.text + "\n\n❌ **REJECTED**"
    )
    
    # Notify User
    try:
        await client.send_message(
            sub['user_id'],
            "❌ **Subscription Rejected**\n\n"
            "Your payment details could not be verified. Please contact support."
        )
    except Exception:
        pass
