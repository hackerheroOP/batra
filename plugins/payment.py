from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from config import ADMIN_CHANNEL_ID, OWNER_ID
from database import add_pending_subscription, get_subscription, activate_subscription, reject_subscription, get_active_subscriptions

# Simple in-memory state management
# Structure: user_id: {"state": "STATE_NAME", "data": {...}}
user_states = {}

# States
STATE_WAITING_CHANNEL = "WAITING_CHANNEL"
STATE_WAITING_GC_CODE = "WAITING_GC_CODE"
STATE_WAITING_GC_PIN = "WAITING_GC_PIN"

async def show_plans(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.message.edit_text(
            "📅 **Choose a Subscription Plan**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Monthly Plan", callback_data="plan_monthly")]
            ])
        )
    except Exception as e:
        print(f"Edit text error: {e}")
        # Fallback if edit fails (e.g. message too old or same content)
        await callback_query.message.reply_text(
             "📅 **Choose a Subscription Plan**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Monthly Plan", callback_data="plan_monthly")]
            ])
        )

async def ask_channel(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user_states[user_id] = {"state": STATE_WAITING_CHANNEL, "data": {"plan": "monthly"}}
    
    try:
        await callback_query.message.edit_text(
            "1️⃣ **Setup Step 1:**\n"
            "Please add this bot to your target channel as an Admin.\n"
            "Then, send me the **Channel ID** (starts with -100...).\n\n"
            "If you don't know how to get the ID, forward a message from that channel here."
        )
    except Exception:
         await callback_query.message.reply_text(
            "1️⃣ **Setup Step 1:**\n"
            "Please add this bot to your target channel as an Admin.\n"
            "Then, send me the **Channel ID** (starts with -100...).\n\n"
            "If you don't know how to get the ID, forward a message from that channel here."
        )

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
            payment_method=data["payment_method"],
            payment_details=f"Code: {data['gc_code']}, PIN: {gc_pin}"
        )
        
        # Notify Admin
        admin_text = (
            f"🔔 **New Subscription Request**\n"
            f"👤 User: {message.from_user.mention} (`{user_id}`)\n"
            f"� Channel: `{data['channel_id']}`\n"
            f" Method: {data['payment_method']}\n"
            f"🔢 Code: `{data['gc_code']}`\n"
            f"� PIN: `{gc_pin}`\n"
            f"🆔 Sub ID: `{sub_id}`"
        )
        
        admin_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{sub_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{sub_id}")
            ]
        ])
        
        try:
            await client.send_message(ADMIN_CHANNEL_ID, admin_text, reply_markup=admin_markup)
        except Exception as e:
            await message.reply_text(f"⚠️ Error sending to admin: {e}")
            
        del user_states[user_id]
        await message.reply_text("✅ **Request Sent!**\nWe will verify your payment and activate your subscription shortly.")

async def ask_gc_details(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_states:
        await callback_query.answer("Session expired. Please /start again.", show_alert=True)
        return

    payment_method = "Amazon Pay" if "amazon" in callback_query.data else "Flipkart"
    user_states[user_id]["data"]["payment_method"] = payment_method
    user_states[user_id]["state"] = STATE_WAITING_GC_CODE
    
    await callback_query.message.edit_text(
        f"� **Payment Method: {payment_method}**\n\n"
        "Please enter the **Gift Card Code**:"
    )

async def handle_admin_action(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    action, sub_id = data.split("_", 1)
    
    # In MongoDB, sub_id is an ObjectId string.
    
    if action == "approve":
        success = await activate_subscription(sub_id)
        if success:
            sub = await get_subscription(sub_id)
            if sub:
                try:
                    await client.send_message(sub['user_id'], "🎉 **Your subscription has been activated!**\nThe bot will now start posting to your channel.")
                except:
                    pass
            await callback_query.message.edit_text(f"{callback_query.message.text}\n\n✅ **APPROVED**")
        else:
            await callback_query.answer("Failed to approve.", show_alert=True)
            
    elif action == "reject":
        success = await reject_subscription(sub_id)
        if success:
             sub = await get_subscription(sub_id)
             if sub:
                try:
                    await client.send_message(sub['user_id'], "❌ **Your subscription request was rejected.**\nPlease contact support if you think this is a mistake.")
                except:
                    pass
             await callback_query.message.edit_text(f"{callback_query.message.text}\n\n❌ **REJECTED**")

def register(app: Client):
    app.add_handler(CallbackQueryHandler(show_plans, filters.regex("^buy_sub$")))
    app.add_handler(CallbackQueryHandler(ask_channel, filters.regex("^plan_monthly$")))
    app.add_handler(MessageHandler(handle_text_input, filters.text & filters.private))
    app.add_handler(CallbackQueryHandler(ask_gc_details, filters.regex("^pay_")))
    app.add_handler(CallbackQueryHandler(handle_admin_action, filters.regex("^(approve|reject)_")))
    print("✅ Plugin 'payment' registered")
