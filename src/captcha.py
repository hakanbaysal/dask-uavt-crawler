"""reCAPTCHA v2 solver using 2Captcha API."""
import time
from twocaptcha import TwoCaptcha
from src.config import CAPTCHA_API_KEY, DASK_RECAPTCHA_SITEKEY, DASK_ADDRESS_PAGE


def solve_recaptcha():
    """Solve reCAPTCHA v2 and return the g-recaptcha-response token."""
    if not CAPTCHA_API_KEY:
        raise ValueError("CAPTCHA_API_KEY not set! Get one from https://2captcha.com")

    solver = TwoCaptcha(CAPTCHA_API_KEY)

    print("🔑 Solving reCAPTCHA v2...")
    start = time.time()

    result = solver.recaptcha(
        sitekey=DASK_RECAPTCHA_SITEKEY,
        url=DASK_ADDRESS_PAGE
    )

    elapsed = time.time() - start
    print(f"✅ reCAPTCHA solved in {elapsed:.1f}s")

    return result["code"]
