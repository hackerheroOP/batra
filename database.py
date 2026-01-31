import time
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

async def init_db():
    # MongoDB creates collections lazily, but we can create indexes here
    await db.videos.create_index("file_id", unique=True)
    await db.subscriptions.create_index("status")
    await db.post_history.create_index([("subscription_id", 1), ("video_id", 1)])
    
    # Initialize default settings if not exists
    settings = await db.settings.find_one({"_id": "config"})
    if not settings:
        await db.settings.insert_one({
            "_id": "config",
            "posts_per_run": 1,
            "interval_hours": 24,
            "last_run": 0
        })

async def add_pending_subscription(user_id, channel_id, plan_type, gc_code, gc_pin):
    result = await db.subscriptions.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "plan_type": plan_type,
        "gc_code": gc_code,
        "gc_pin": gc_pin,
        "status": "pending",
        "start_date": time.time(),
        "expiry_date": None
    })
    return str(result.inserted_id)

async def get_subscription(sub_id):
    try:
        sub = await db.subscriptions.find_one({"_id": ObjectId(sub_id)})
        if sub:
            sub['id'] = str(sub['_id'])
            return sub
    except Exception:
        pass
    return None

async def activate_subscription(sub_id, duration_days=30):
    start_time = time.time()
    expiry_time = start_time + (duration_days * 24 * 60 * 60)
    await db.subscriptions.update_one(
        {"_id": ObjectId(sub_id)},
        {"$set": {
            "status": "active",
            "start_date": start_time,
            "expiry_date": expiry_time
        }}
    )

async def reject_subscription(sub_id):
    await db.subscriptions.delete_one({"_id": ObjectId(sub_id)})

async def get_active_subscriptions():
    cursor = db.subscriptions.find({"status": "active"})
    subs = []
    async for sub in cursor:
        sub['id'] = str(sub['_id'])
        subs.append(sub)
    return subs

async def add_video(file_id, file_name, message_id):
    try:
        await db.videos.insert_one({
            "file_id": file_id,
            "file_name": file_name,
            "message_id": message_id
        })
        return True
    except Exception:
        # Duplicate error likely due to unique index
        return False

async def get_next_video_for_sub(subscription_id):
    """
    Get a video that hasn't been posted to this subscription yet.
    """
    # 1. Get list of video IDs already posted
    pipeline = [
        {"$match": {"subscription_id": str(subscription_id)}},
        {"$project": {"video_id": 1, "_id": 0}}
    ]
    posted_cursor = db.post_history.aggregate(pipeline)
    posted_ids = [doc['video_id'] async for doc in posted_cursor]
    
    query = {}
    if posted_ids:
        query["_id"] = {"$nin": posted_ids}

    video = await db.videos.find_one(query, sort=[("message_id", 1)])
    
    if video:
        video['id'] = video['_id'] # Keep as ObjectId for referencing
        return video
    return None

async def record_post(subscription_id, video_id):
    await db.post_history.insert_one({
        "subscription_id": str(subscription_id),
        "video_id": video_id,
        "posted_at": time.time()
    })

async def expire_subscriptions():
    now = time.time()
    await db.subscriptions.update_many(
        {"status": "active", "expiry_date": {"$lt": now}},
        {"$set": {"status": "expired"}}
    )

# --- Settings ---

async def get_settings():
    return await db.settings.find_one({"_id": "config"})

async def update_settings(posts_per_run=None, interval_hours=None):
    update_data = {}
    if posts_per_run is not None:
        update_data["posts_per_run"] = posts_per_run
    if interval_hours is not None:
        update_data["interval_hours"] = interval_hours
    
    if update_data:
        await db.settings.update_one(
            {"_id": "config"},
            {"$set": update_data}
        )

async def update_last_run():
    await db.settings.update_one(
        {"_id": "config"},
        {"$set": {"last_run": time.time()}}
    )
