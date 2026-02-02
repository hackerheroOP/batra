from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from config import OWNER_ID, ADMIN_CHANNEL_ID
from database import get_settings, update_settings, add_admin, remove_admin, get_all_admins, is_user_admin, check_admin_permission, update_admin_permission, get_admin_details

async def admin_filter(_, __, message: Message):
    if not message.from_user:
        return False
    is_adm = await is_user_admin(message.from_user.id)
    # print(f"DEBUG: admin_filter for {message.from_user.id} -> {is_adm}")
    return is_adm

# Create a filter object for reuse
is_admin = filters.create(admin_filter)

admin_states = {}
STATE_WAITING_INTERVAL = "WAITING_INTERVAL"
STATE_WAITING_POSTS = "WAITING_POSTS"

# --- Admin Management Commands ---

async def add_admin_command(client: Client, message: Message):
    # Only OWNER or admins with 'add_admin' permission can add admins
    if not await check_admin_permission(message.from_user.id, "add_admin"):
        await message.reply_text("❌ You don't have permission to add admins.")
        return
        
    if len(message.command) < 2:
        await message.reply_text("⚠️ Usage: `/add_admin <user_id>`")
        return
        
    try:
        new_admin_id = int(message.command[1])
        if await add_admin(new_admin_id, added_by=message.from_user.id):
            await message.reply_text(f"✅ User `{new_admin_id}` added as Admin.")
            try:
                await client.send_message(ADMIN_CHANNEL_ID, f"👮 **New Admin Added**\n👤 User: `{new_admin_id}`\n👑 Added By: {message.from_user.mention}")
            except:
                pass
        else:
            await message.reply_text("⚠️ Failed to add admin. Check logs.")
    except ValueError:
        await message.reply_text("❌ Invalid User ID.")

async def remove_admin_command(client: Client, message: Message):
    # Only OWNER or admins with 'add_admin' permission can remove admins
    if not await check_admin_permission(message.from_user.id, "add_admin"):
        await message.reply_text("❌ You don't have permission to remove admins.")
        return
        
    if len(message.command) < 2:
        await message.reply_text("⚠️ Usage: `/remove_admin <user_id>`")
        return
        
    try:
        target_id = int(message.command[1])
        if target_id == OWNER_ID:
            await message.reply_text("❌ Cannot remove the Owner.")
            return

        if await remove_admin(target_id):
            await message.reply_text(f"✅ User `{target_id}` removed from Admins.")
            try:
                await client.send_message(ADMIN_CHANNEL_ID, f"👮 **Admin Removed**\n👤 User: `{target_id}`\n👑 Removed By: {message.from_user.mention}")
            except:
                pass
        else:
            await message.reply_text("⚠️ User was not an admin.")
    except ValueError:
        await message.reply_text("❌ Invalid User ID.")

async def get_admin_list_data(client: Client):
    admins = await get_all_admins()
    
    text = "👮 **Admin List**\nSelect an admin to manage permissions:\n\n"
    text += f"👑 Owner: `{OWNER_ID}`\n"
    
    markup_rows = []
    
    other_admins = [uid for uid in admins if uid != OWNER_ID]
    
    if other_admins:
        # Try to fetch names
        user_map = {}
        try:
            # Batch request is more efficient
            users = await client.get_users(other_admins)
            if not isinstance(users, list):
                users = [users]
            
            for u in users:
                if u: # check if None (rare)
                    name = u.first_name or "Unknown"
                    if u.last_name:
                        name += f" {u.last_name}"
                    user_map[u.id] = name
        except Exception as e:
            # If batch fails (e.g. one user invalid), try individually
            for admin_id in other_admins:
                try:
                    u = await client.get_users(admin_id)
                    name = u.first_name or "Unknown"
                    if u.last_name:
                        name += f" {u.last_name}"
                    user_map[admin_id] = name
                except:
                    pass

        for admin_id in other_admins:
            name = user_map.get(admin_id, f"User {admin_id}")
            markup_rows.append([InlineKeyboardButton(f"👤 {name} ({admin_id})", callback_data=f"manage_admin_{admin_id}")])
    else:
        text += "No other admins."
        
    markup_rows.append([InlineKeyboardButton("❌ Close", callback_data="close_settings")])
    
    return text, InlineKeyboardMarkup(markup_rows)

async def list_admins_command(client: Client, message: Message):
    text, markup = await get_admin_list_data(client)
    await message.reply_text(text, reply_markup=markup)

async def manage_admin_callback(client: Client, callback_query: CallbackQuery):
    # Only Owner can manage permissions (as per requirement "owner can set which admin...")
    # Or maybe admins with 'add_admin' can? Let's restrict to Owner for safety unless requested otherwise.
    if callback_query.from_user.id != OWNER_ID:
        await callback_query.answer("❌ Only Owner can manage permissions.", show_alert=True)
        return

    data = callback_query.data
    if data.startswith("manage_admin_"):
        target_id = int(data.split("_")[2])
        await show_admin_permissions(client, callback_query, target_id)
        
    elif data.startswith("toggle_perm_"):
        parts = data.split("_")
        # toggle_perm_TARGETID_PERMISSION
        target_id = int(parts[2])
        permission = "_".join(parts[3:])
        
        # Get current state
        current_val = await check_admin_permission(target_id, permission)
        new_val = not current_val
        
        await update_admin_permission(target_id, permission, new_val)
        
        # Log it
        try:
             await client.send_message(ADMIN_CHANNEL_ID, f"🔑 **Permission Changed**\n👤 Target: `{target_id}`\n🛠️ Permission: `{permission}`\n🔄 Value: {'✅ True' if new_val else '❌ False'}\n👮 By: {callback_query.from_user.mention}")
        except:
             pass
             
        await show_admin_permissions(client, callback_query, target_id)

async def show_admin_permissions(client: Client, callback_query: CallbackQuery, target_id: int):
    admin_details = await get_admin_details(target_id)
    if not admin_details:
        await callback_query.answer("Admin not found.", show_alert=True)
        return
        
    perms = admin_details.get("permissions", {})
    
    # Define available permissions labels
    perm_labels = {
        "change_interval": "Change Interval",
        "change_posts": "Change Posts Count",
        "add_admin": "Add/Remove Admins",
        "manage_payments": "Manage Payments"
    }
    
    text = f"⚙️ **Managing Admin:** `{target_id}`\n\nTap to toggle permissions:"
    
    buttons = []
    for key, label in perm_labels.items():
        status = "✅" if perms.get(key, False) else "❌"
        buttons.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"toggle_perm_{target_id}_{key}")])
        
    buttons.append([InlineKeyboardButton("🔙 Back to List", callback_data="back_to_admin_list")])
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def back_to_list_callback(client: Client, callback_query: CallbackQuery):
    # Re-use list logic but edit message
    text, markup = await get_admin_list_data(client)
    await callback_query.message.edit_text(text, reply_markup=markup)


async def get_settings_markup(settings):
    interval = settings.get('interval_hours', 24)
    posts = settings.get('posts_per_run', 1)
    delete_after = settings.get('delete_after_forward', False)
    auto_index = settings.get('auto_index', True)
    
    delete_text = "✅ On" if delete_after else "❌ Off"
    auto_index_text = "✅ On" if auto_index else "❌ Off"
    
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🕒 Interval: {interval}h (Tap to Edit)", callback_data="set_interval_input"),
        ],
        [
            InlineKeyboardButton(f"📦 Posts per Run: {posts} (Tap to Edit)", callback_data="set_posts_input"),
        ],
        [
            InlineKeyboardButton(f"🗑️ Delete from Source: {delete_text}", callback_data="toggle_delete")
        ],
        [
            InlineKeyboardButton(f"📥 Auto-Index New Media: {auto_index_text}", callback_data="toggle_auto_index")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_settings")
        ]
    ])
    return markup

async def show_settings(client: Client, message: Message):
    settings = await get_settings()
    if not settings:
        await message.reply_text("❌ Settings not initialized yet.")
        return
        
    text = "⚙️ **Bot Settings Panel**\n\nUse the buttons below to change settings."
    await message.reply_text(text, reply_markup=await get_settings_markup(settings))

async def settings_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    settings = await get_settings()
    
    if not settings:
        await callback_query.answer("Settings not found!", show_alert=True)
        return

    interval = settings.get('interval_hours', 24)
    posts = settings.get('posts_per_run', 1)
    delete_after = settings.get('delete_after_forward', False)
    
    if data == "ignore":
        await callback_query.answer()
        return
        
    elif data == "close_settings":
        await callback_query.message.delete()
        return
        
    elif data == "set_interval_input":
        if not await check_admin_permission(callback_query.from_user.id, "change_interval"):
            await callback_query.answer("❌ You don't have permission to change interval.", show_alert=True)
            return

        admin_states[callback_query.from_user.id] = STATE_WAITING_INTERVAL
        await callback_query.message.reply_text(
            "🕒 **Set Interval**\n\n"
            "Please enter the new interval in **hours** (e.g. `0.5`, `1`, `24`).\n"
            "Send /cancel to cancel."
        )
        await callback_query.answer()
        return

    elif data == "set_posts_input":
        if not await check_admin_permission(callback_query.from_user.id, "change_posts"):
            await callback_query.answer("❌ You don't have permission to change posts count.", show_alert=True)
            return

        admin_states[callback_query.from_user.id] = STATE_WAITING_POSTS
        await callback_query.message.reply_text(
            "📦 **Set Posts per Run**\n\n"
            "Please enter the number of posts to send per batch (e.g. `1`, `5`).\n"
            "Send /cancel to cancel."
        )
        await callback_query.answer()
        return
        
    elif data == "toggle_delete":
        # Let's use 'change_interval' or 'change_posts' or maybe just 'change_posts' as it affects post behavior?
        # Or better, check if they have EITHER or create a new one. 
        # For simplicity, let's require 'change_posts' for this one as it relates to post handling.
        if not await check_admin_permission(callback_query.from_user.id, "change_posts"):
            await callback_query.answer("❌ You don't have permission to change this setting.", show_alert=True)
            return

        new_val = not delete_after
        await update_settings(delete_after_forward=new_val)
        
        # Log change
        try:
             log_msg = (
                 f"⚙️ **Setting Changed**\n"
                 f"👤 Admin: {callback_query.from_user.mention}\n"
                 f"🛠️ Setting: **Delete from Source**\n"
                 f"📉 Old: {'✅ On' if delete_after else '❌ Off'}\n"
                 f"📈 New: {'✅ On' if new_val else '❌ Off'}"
             )
             await client.send_message(ADMIN_CHANNEL_ID, log_msg)
        except Exception:
             pass

    elif data == "toggle_auto_index":
        if not await check_admin_permission(callback_query.from_user.id, "change_posts"):
            await callback_query.answer("❌ You don't have permission to change this setting.", show_alert=True)
            return

        current_val = settings.get('auto_index', True)
        new_val = not current_val
        await update_settings(auto_index=new_val)
        
        # Log change
        try:
             log_msg = (
                 f"⚙️ **Setting Changed**\n"
                 f"👤 Admin: {callback_query.from_user.mention}\n"
                 f"🛠️ Setting: **Auto-Index New Media**\n"
                 f"📉 Old: {'✅ On' if current_val else '❌ Off'}\n"
                 f"📈 New: {'✅ On' if new_val else '❌ Off'}"
             )
             await client.send_message(ADMIN_CHANNEL_ID, log_msg)
        except Exception:
             pass
        
    # Refresh the menu
    new_settings = await get_settings()
    try:
        await callback_query.message.edit_reply_markup(reply_markup=await get_settings_markup(new_settings))
    except Exception:
        pass # Message not modified

async def handle_admin_input(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in admin_states:
        return
        
    state = admin_states[user_id]
    text = message.text.strip()
    
    if text.lower() == "/cancel":
        del admin_states[user_id]
        await message.reply_text("❌ Action cancelled.")
        return
        
    try:
        # Get current settings for comparison
        current_settings = await get_settings()
        
        if state == STATE_WAITING_INTERVAL:
            try:
                val = float(text)
                if val <= 0:
                    raise ValueError
                
                old_val = current_settings.get('interval_hours', 24)
                await update_settings(interval_hours=val)
                await message.reply_text(f"✅ **Interval updated to {val} hours.**")
                
                # Log change
                try:
                     log_msg = (
                         f"⚙️ **Setting Changed**\n"
                         f"👤 Admin: {message.from_user.mention}\n"
                         f"🛠️ Setting: **Post Interval**\n"
                         f"📉 Old: `{old_val} hours`\n"
                         f"📈 New: `{val} hours`"
                     )
                     await client.send_message(ADMIN_CHANNEL_ID, log_msg)
                except Exception:
                     pass

            except ValueError:
                await message.reply_text("❌ Invalid input. Please enter a positive number.")
                return

        elif state == STATE_WAITING_POSTS:
            try:
                val = int(text)
                if val <= 0:
                    raise ValueError
                
                old_val = current_settings.get('posts_per_run', 1)
                await update_settings(posts_per_run=val)
                await message.reply_text(f"✅ **Posts per run updated to {val}.**")
                
                # Log change
                try:
                     log_msg = (
                         f"⚙️ **Setting Changed**\n"
                         f"👤 Admin: {message.from_user.mention}\n"
                         f"🛠️ Setting: **Posts per Run**\n"
                         f"📉 Old: `{old_val} posts`\n"
                         f"📈 New: `{val} posts`"
                     )
                     await client.send_message(ADMIN_CHANNEL_ID, log_msg)
                except Exception:
                     pass

            except ValueError:
                await message.reply_text("❌ Invalid input. Please enter a positive integer.")
                return
        
        # Clear state and show settings again
        del admin_states[user_id]
        await show_settings(client, message)
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

def register(app: Client):
    app.add_handler(MessageHandler(add_admin_command, filters.command("add_admin") & is_admin))
    app.add_handler(MessageHandler(remove_admin_command, filters.command("remove_admin") & is_admin))
    app.add_handler(MessageHandler(list_admins_command, filters.command("admins") & is_admin))
    
    app.add_handler(MessageHandler(show_settings, filters.command("settings") & is_admin))
    app.add_handler(CallbackQueryHandler(settings_callback, filters.regex(r"^(set_interval_input|set_posts_input|toggle_delete|toggle_auto_index|close_settings|ignore)")))
    app.add_handler(CallbackQueryHandler(manage_admin_callback, filters.regex(r"^(manage_admin_|toggle_perm_)")))
    app.add_handler(CallbackQueryHandler(back_to_list_callback, filters.regex(r"^back_to_admin_list$")))

    # Handler for admin text input (for editing settings) - Exclude commands
    async def no_cmd_filter(_, __, message):
        return message.text and not message.text.startswith("/")
    
    no_cmd = filters.create(no_cmd_filter)

    async def admin_state_filter(_, __, message):
        return message.from_user and message.from_user.id in admin_states

    has_admin_state = filters.create(admin_state_filter)

    app.add_handler(MessageHandler(handle_admin_input, no_cmd & is_admin & has_admin_state))
    print("✅ Plugin 'admin_settings' registered")
