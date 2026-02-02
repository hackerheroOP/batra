from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from config import SOURCE_CHANNEL_ID, OWNER_ID
from database import add_video, get_settings, delete_all_videos

async def index_content(client: Client, message: Message):
    media_type = "video"
    file_id = None
    file_name = None
    
    if message.photo:
        media_type = "photo"
        file_id = message.photo.file_id
        file_name = f"Photo {message.id}" # Photos don't have filenames usually
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
        file_name = message.video.file_name or f"Video {message.id}"
    elif message.document:
        # Check mime type
        mime = message.document.mime_type or ""
        if "video" in mime:
            media_type = "video"
            file_id = message.document.file_id
            file_name = message.document.file_name or f"Video {message.id}"
        elif "image" in mime:
             media_type = "photo"
             file_id = message.document.file_id
             file_name = message.document.file_name or f"Image {message.id}"
        else:
            return
    else:
        return

    if not file_id:
        return

    # Check settings
    settings = await get_settings()
    if not settings:
        settings = {}
        
    # If this is called from the listener (real-time), we must check if auto_index is enabled.
    # But how do we know if it's from listener or command?
    # We can inspect the stack or pass an arg, but message handler doesn't support args easily.
    # However, 'index_history_command' calls this function directly. 
    # We can add an optional argument to 'index_content' but the handler signature is fixed (client, message).
    # Wait, Python allows optional args in handlers? No, Pyrogram passes 2 args.
    # BUT we can wrap it or just check a context var.
    # EASIER: We check 'auto_index' here. 
    # IF it's disabled, we should ONLY allow it if it's being run manually.
    # But we can't easily distinguish.
    # ALTERNATIVE: Make 'index_content' ONLY the handler, and extract the logic to 'process_message'
    
    # Refactoring below...
    await process_message(client, message, settings)

async def process_message(client: Client, message: Message, settings: dict, force: bool = False):
    # Logic moved here
    media_type = "video"
    file_id = None
    file_name = None
    
    if message.photo:
        media_type = "photo"
        file_id = message.photo.file_id
        file_name = f"Photo {message.id}"
    elif message.video:
        media_type = "video"
        file_id = message.video.file_id
        file_name = message.video.file_name or f"Video {message.id}"
    elif message.document:
        mime = message.document.mime_type or ""
        if "video" in mime:
            media_type = "video"
            file_id = message.document.file_id
            file_name = message.document.file_name or f"Video {message.id}"
        elif "image" in mime:
             media_type = "photo"
             file_id = message.document.file_id
             file_name = message.document.file_name or f"Image {message.id}"
        else:
            return
    else:
        return

    if not file_id:
        return

    # Check auto_index setting if not forced
    if not force:
        # Default to True if missing
        if not settings.get('auto_index', True):
            # Auto-index is OFF, and this is not a forced (manual) run
            return

    success = await add_video(file_id, file_name, message.id, media_type)
    if success:
        print(f"Indexed {media_type}: {file_name} (Msg ID: {message.id})")
        
        if settings.get('delete_after_forward', False):
            try:
                await message.delete()
                print(f"Deleted message {message.id} from source channel.")
            except Exception as e:
                print(f"Failed to delete message {message.id}: {e}")

async def index_content(client: Client, message: Message):
    settings = await get_settings()
    await process_message(client, message, settings, force=False)

async def index_history_command(client: Client, message: Message):
    """
    Safely iterate over channel history for bots, bypassing get_chat_history restrictions
    by fetching messages by ID in batches.
    """
    # 1. Try to find the latest message ID
    last_msg_id = 0
    try:
        # Try search_messages (works for bots usually) to get latest
        async for msg in client.search_messages(chat_id, limit=1):
            last_msg_id = msg.id
    except Exception:
        pass

    if last_msg_id == 0:
        # Fallback: Assume a reasonably high number or just rely on consecutive empty check
        # We'll use the empty streak check primarily if last_msg_id is unknown
        pass
    else:
        print(f"DEBUG: Found last message ID: {last_msg_id}")

    current_id = 1
    batch_size = 200
    empty_streak_batches = 0
    MAX_EMPTY_STREAK_BATCHES = 5 # Stop after 1000 empty messages
    
    while True:
        if last_msg_id > 0 and current_id > last_msg_id:
            break
            
        ids = list(range(current_id, current_id + batch_size))
        try:
            messages = await client.get_messages(chat_id, ids)
        except Exception as e:
            print(f"DEBUG: get_messages failed for batch {current_id}: {e}")
            # If we fail completely, we might stop or skip
            # If channel is invalid, we stop
            break
            
        if not messages:
            break
            
        has_content = False
        # Ensure messages is a list (get_messages can return single if ids is len 1, but we send list)
        if not isinstance(messages, list):
            messages = [messages]

        for msg in messages:
            # Check if message exists and is not empty
            if msg and not msg.empty:
                has_content = True
                yield msg
        
        if not has_content:
            empty_streak_batches += 1
        else:
            empty_streak_batches = 0
            
        # Stop condition if we don't know the end
        if last_msg_id == 0 and empty_streak_batches >= MAX_EMPTY_STREAK_BATCHES:
            print("DEBUG: Stopped due to empty streak")
            break
            
        current_id += batch_size

async def index_history_command(client: Client, message: Message):
    # Only Owner can run this
    if message.from_user.id != OWNER_ID:
        return

    status_msg = await message.reply_text("⏳ **Starting historical indexing...**\nThis may take a while depending on channel size.\nUsing ID-based scan (Bot Mode).")
    
    count = 0
    added_count = 0
    
    # We fetch settings once
    settings = await get_settings()
    
    try:
        # Iterate over all history using safe method
        async for msg in get_all_history_safe(client, SOURCE_CHANNEL_ID):
            if msg.video or msg.photo or msg.document:
                # We call process_message with force=True to bypass auto_index check
                await process_message(client, msg, settings, force=True)
                added_count += 1
            
            count += 1
            if count % 50 == 0:
                try:
                    await status_msg.edit_text(f"⏳ **Indexing...**\nScanned: {count}\nAdded: {added_count}")
                except:
                    pass
                        
    except Exception as e:
        await status_msg.edit_text(f"❌ **Error during indexing:** {e}")
        return

    await status_msg.edit_text(f"✅ **Indexing Completed!**\nTotal Scanned: {count}\nTotal Added: {added_count}")

async def delete_index_command(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return
        
    status_msg = await message.reply_text("⏳ **Deleting all indexed files...**")
    
    success = await delete_all_videos()
    
    if success:
        await status_msg.edit_text("✅ **All indexed files have been deleted.**")
    else:
        await status_msg.edit_text("❌ **Failed to delete indexed files.**")

def register(app: Client):
    # Register listener for new messages
    app.add_handler(MessageHandler(index_content, filters.chat(SOURCE_CHANNEL_ID) & (filters.video | filters.document | filters.photo)))
    
    # Register command for historical indexing
    app.add_handler(MessageHandler(index_history_command, filters.command("index_all") & filters.user(OWNER_ID)))
    
    # Register command to delete index
    app.add_handler(MessageHandler(delete_index_command, filters.command("delete_index") & filters.user(OWNER_ID)))
    
    print("✅ Plugin 'indexing' registered")
