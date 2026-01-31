import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "27247089"))
API_HASH = os.getenv("API_HASH", "2456e376e82f580ea1d1ed9d6444df8f")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7054914860:AAFC-EOt2NQiizkGVdCsbplmPZbs2Z0cnl0")

# Channel where payment proofs are sent for verification
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1003860392199")) 

# Channel where the bot indexes videos from
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-1003766049132")) 

OWNER_ID = int(os.getenv("OWNER_ID", "1251111009"))
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://pewiy55240:kswo56IGBu4BLQgW@cluster0.jv4874f.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = "bot_database"
