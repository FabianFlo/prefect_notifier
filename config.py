import os

# Carga opcional desde .env si estás local
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

# PREFECT
PREFECT_USER = os.environ.get("PREFECT_USER")
PREFECT_PASS = os.environ.get("PREFECT_PASS")
PREFECT_URL = os.environ.get("PREFECT_URL")

# TELEGRAM
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


#venv\Scripts\activate
#python main.py