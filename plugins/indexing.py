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

    success = await add_video(file_id, file_name, message.id, media_type)
    if success:
        print(f"Indexed {media_type}: {file_name} (Msg ID: {message.id})")
        
        # Check if we should delete from source
        settings = await get_settings()
        if settings and settings.get('delete_after_forward', False):
            try:
                await message.delete()
                print(f"Deleted message {message.id} from source channel.")
            except Exception as e:
                print(f"Failed to delete message {message.id}: {e}")
    else:
        # Duplicate or error
        pass

async def index_history_command(client: Client, message: Message):
    # Only Owner can run this
    if message.from_user.id != OWNER_ID:
        return

    status_msg = await message.reply_text("⏳ **Starting historical indexing...**\nThis may take a while depending on channel size.")
    
    count = 0
    added_count = 0
    
    try:
        # Iterate over all history
        async for msg in client.get_chat_history(SOURCE_CHANNEL_ID):
            if msg.video or msg.photo or msg.document:
                # We call index_content to reuse logic (including DB add and optional delete)
                # Note: This might be slow if 'delete_after_forward' is ON and it tries to delete every message.
                await index_content(client, msg)
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
