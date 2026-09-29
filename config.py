import os

from dotenv import load_dotenv

load_dotenv()


def _ids(v: str):
    return [int(x) for x in v.replace(" ", "").split(",") if x.lstrip("-").isdigit()]


def _f(name: str, default: str) -> float:
    return float(os.getenv(name, default))


# ---- required ----
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = _ids(os.getenv("ADMIN_IDS", ""))

# ---- branding / links (all optional) ----
BRAND = os.getenv("BRAND_NAME", "Premium Verse")
WELCOME_PHOTO = os.getenv("WELCOME_PHOTO", "")      # image URL or Telegram file_id
SUPPORT_URL = os.getenv("SUPPORT_URL", "")          # e.g. https://t.me/yourusername
PROOFS_URL = os.getenv("PROOFS_URL", "")            # your proofs channel link
MINIAPP_URL = os.getenv("MINIAPP_URL", "")          # https URL of a Telegram Mini App

# ---- payments ----
UPI_ID = os.getenv("UPI_ID", "")
UPI_NAME = os.getenv("UPI_NAME", BRAND)
USDT_ADDRESS = os.getenv("USDT_ADDRESS", "")
USDT_NETWORK = os.getenv("USDT_NETWORK", "TRC20")
INR_PER_USD = _f("INR_PER_USD", "90")
STARS_PER_USD = _f("STARS_PER_USD", "60")           # adjust to current Stars pricing

# ---- wallet / points / referral ----
POINTS_PER_INR = _f("POINTS_PER_INR", "1")           # points earned per rupee spent
POINTS_PER_WALLET_INR = int(_f("POINTS_PER_WALLET_INR", "10"))  # 10 points = Rs 1
REFERRAL_BONUS_POINTS = int(_f("REFERRAL_BONUS_POINTS", "50"))

# ---- discounts: (min items, percent) ----
COMBO_TIERS = [(2, 10), (3, 20), (4, 30), (5, 40), (6, 50), (8, 60)]
MAX_DISCOUNT = 60

# ---- storage / web ----
DB_PATH = os.getenv("DB_PATH", "premium.db")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
API_KEY = os.getenv("API_KEY", "")                  # for /api/premium (your other bots)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")    # for /webhook/credit (payment auto-verify)
