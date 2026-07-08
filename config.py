import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBAPP_URL = os.getenv("WEBAPP_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
_GROUP_CHAT_ID_RAW = os.getenv("GROUP_CHAT_ID")
# Normalize GROUP_CHAT_ID to int when possible (env vars are strings).
if _GROUP_CHAT_ID_RAW is None or _GROUP_CHAT_ID_RAW == "":
	GROUP_CHAT_ID = None
else:
	try:
		GROUP_CHAT_ID = int(_GROUP_CHAT_ID_RAW)
	except ValueError:
		# Fall back to original string if it's not a plain integer
		GROUP_CHAT_ID = _GROUP_CHAT_ID_RAW
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
