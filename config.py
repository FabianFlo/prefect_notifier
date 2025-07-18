import os
from dotenv import load_dotenv

load_dotenv()

PREFECT_USER = os.getenv("PREFECT_USER")
PREFECT_PASS = os.getenv("PREFECT_PASS")
PREFECT_URL = os.getenv("PREFECT_URL")


#venv\Scripts\activate
#python main.py