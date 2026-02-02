from database import get_active_subscriptions, get_next_video_for_sub, record_post, expire_subscriptions, get_settings, update_last_run
from pyrogram.errors import Forbidden, ChatWriteForbidden
import asyncio
import time

async def daily_post_job(client):
    """
    Checks if it's time to run the batch post job based on configured interval.
    If yes, posts configured number of videos.
    """
    settings = await get_settings()
    if not settings:
        return
        
    last_run = settings.get("last_run", 0)
    interval_hours = settings.get("interval_hours", 24)
    posts_per_run = settings.get("posts_per_run", 1)
    
    # Check if time passed
    time_passed = time.time() - last_run
    required_interval = interval_hours * 3600
    
    # print(f"DEBUG: Scheduler Check - Passed: {time_passed:.1f}s, Required: {required_interval:.1f}s")
    
    if time_passed < required_interval:
        # Not time yet
        return

    print(f"Starting batch post job (Limit: {posts_per_run})...")
    
    subs = await get_active_subscriptions()
    print(f"Found {len(subs)} active subscriptions.")
    
    for sub in subs:
        # Post 'posts_per_run' videos
        for i in range(posts_per_run):
            video = await get_next_video_for_sub(sub['id'])
            if not video:
                print(f"No new video for sub {sub['id']}")
                break
                
            try:
                print(f"Posting video {video['id']} to channel {sub['channel_id']} ({i+1}/{posts_per_run})")
                await client.send_video(
                    chat_id=sub['channel_id'],
                    video=video['file_id'],
                    caption=video['file_name']
                )
                await record_post(sub['id'], video['id'])
                
                # Small delay to prevent flood limits
                await asyncio.sleep(2)
                
            except (Forbidden, ChatWriteForbidden):
                print(f"Permission denied for channel {sub['channel_id']}")
                try:
                    await client.send_message(
                        sub['user_id'],
                        f"⚠️ **Alert:** I cannot post in your channel `{sub['channel_id']}`.\n"
                        "Please make sure I am an Admin with posting permissions.\n"
                        "Auto-posting will resume once fixed."
                    )
                except Exception:
                    pass
                break # Stop trying for this channel in this run
                    
            except Exception as e:
                print(f"Error posting to {sub['channel_id']}: {e}")
                # Don't break loop, try next video? No, maybe break to be safe.
                break

    # Update last run time
    await update_last_run()
    print("Batch post job completed.")

async def expiry_check_job(client):
    # Runs daily or frequently to check expiry
    await expire_subscriptions()
