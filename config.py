import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Channel where payment proofs are sent for verification
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "0")) 

# Channel where the bot indexes videos from
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "0")) 

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "bot_database"
