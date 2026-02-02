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
            "delete_after_forward": False,
            "auto_index": True,
            "last_run": 0
        })

async def add_pending_subscription(user_id, channel_id, plan_type, payment_method, payment_details):
    result = await db.subscriptions.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "plan_type": plan_type,
        "payment_method": payment_method,
        "payment_details": payment_details,
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
    result = await db.subscriptions.update_one(
        {"_id": ObjectId(sub_id)},
        {"$set": {
            "status": "active",
            "start_date": start_time,
            "expiry_date": expiry_time
        }}
    )
    return result.modified_count > 0 or result.matched_count > 0

async def reject_subscription(sub_id):
    result = await db.subscriptions.delete_one({"_id": ObjectId(sub_id)})
    return result.deleted_count > 0

async def get_active_subscriptions():
    cursor = db.subscriptions.find({"status": "active"})
    subs = []
    async for sub in cursor:
        sub['id'] = str(sub['_id'])
        subs.append(sub)
    return subs

async def add_video(file_id, file_name, message_id, media_type="video"):
    try:
        await db.videos.insert_one({
            "file_id": file_id,
            "file_name": file_name,
            "message_id": message_id,
            "media_type": media_type
        })
        return True
    except Exception:
        # Duplicate error likely due to unique index
        return False

async def delete_all_videos():
    try:
        await db.videos.delete_many({})
        return True
    except Exception:
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

async def update_settings(posts_per_run=None, interval_hours=None, delete_after_forward=None, auto_index=None):
    update_data = {}
    if posts_per_run is not None:
        update_data["posts_per_run"] = posts_per_run
    if interval_hours is not None:
        update_data["interval_hours"] = interval_hours
    if delete_after_forward is not None:
        update_data["delete_after_forward"] = delete_after_forward
    if auto_index is not None:
        update_data["auto_index"] = auto_index
    
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

# --- Admin Management ---

DEFAULT_PERMISSIONS = {
    "change_interval": False,
    "change_posts": False,
    "add_admin": False,
    "manage_payments": True
}

async def add_admin(user_id, added_by=None):
    try:
        # Check if exists to preserve permissions if re-added? No, reset or keep? 
        # Let's keep existing permissions if exists, or set default.
        existing = await db.admins.find_one({"user_id": user_id})
        if existing:
            return True

        await db.admins.insert_one({
            "user_id": user_id, 
            "added_at": time.time(),
            "added_by": added_by,
            "permissions": DEFAULT_PERMISSIONS.copy()
        })
        return True
    except Exception:
        return False

async def remove_admin(user_id):
    result = await db.admins.delete_one({"user_id": user_id})
    return result.deleted_count > 0

async def get_all_admins():
    cursor = db.admins.find({})
    admins = []
    async for doc in cursor:
        admins.append(doc['user_id'])
    return admins

async def get_admin_details(user_id):
    return await db.admins.find_one({"user_id": user_id})

async def update_admin_permission(user_id, permission, value):
    """
    Update a single permission for an admin.
    """
    key = f"permissions.{permission}"
    await db.admins.update_one(
        {"user_id": user_id},
        {"$set": {key: value}}
    )

async def check_admin_permission(user_id, permission):
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    
    admin = await db.admins.find_one({"user_id": user_id})
    if not admin:
        return False
    
    # Return permission value, default to False if key missing
    return admin.get("permissions", {}).get(permission, False)

async def get_admins_with_permission(permission):
    """
    Get list of admin user_ids who have a specific permission.
    Owner is always included.
    """
    from config import OWNER_ID
    
    query = {f"permissions.{permission}": True}
    cursor = db.admins.find(query)
    
    admins = {OWNER_ID} # Use set to avoid duplicates if owner is in DB
    async for doc in cursor:
        admins.add(doc['user_id'])
        
    return list(admins)

async def is_user_admin(user_id):
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    
    doc = await db.admins.find_one({"user_id": user_id})
    return doc is not None
