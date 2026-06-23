import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBAPP_URL = os.getenv("WEBAPP_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK")
