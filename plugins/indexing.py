from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from config import SOURCE_CHANNEL_ID
from database import add_video, get_settings

async def index_video(client: Client, message: Message):
    # Check if it's a video or a document that is a video
    video = message.video or message.document
    
    if not video:
        return
        
    # For documents, verify mime type if needed
    # But often video files are sent as documents (MKV, etc.)
    # We'll be lenient or strict based on typical usage. 
    # Let's assume anything in the source channel that has a file_id and is video/doc is valid.
    
    if message.document and "video" not in (message.document.mime_type or ""):
        # Optional: Allow MKV/MP4 specifically if mime_type is generic
        pass 

    file_id = video.file_id
    file_name = video.file_name or f"Video {message.id}"
    
    success = await add_video(file_id, file_name, message.id)
    if success:
        print(f"Indexed video: {file_name} (Msg ID: {message.id})")
        
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

def register(app: Client):
    app.add_handler(MessageHandler(index_video, filters.chat(SOURCE_CHANNEL_ID) & (filters.video | filters.document)))
    print("✅ Plugin 'indexing' registered")
