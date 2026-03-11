import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "dask_uavt")
DB_USER = os.getenv("DB_USER", "dask")
DB_PASS = os.getenv("DB_PASS", "dask123")

CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")

DASK_BASE_URL = "https://dask.gov.tr"
DASK_ADDRESS_PAGE = f"{DASK_BASE_URL}/adreskodu"
DASK_RECAPTCHA_SITEKEY = "6Levh-8UAAAAADKgSrLuFDo1PNopWkk-Ife5Im8y"

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
