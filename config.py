import os
from dotenv import load_dotenv

load_dotenv()

# PAGINA PREFECT
PREFECT_USER = os.getenv("PREFECT_USER")
PREFECT_PASS = os.getenv("PREFECT_PASS")
PREFECT_URL = os.getenv("PREFECT_URL")

# TELEGRAM MSJ
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


#venv\Scripts\activate
#python main.py