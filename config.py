import os

BITGET_BASE = "https://api.bitget.com"
PRODUCT_TYPE = "USDT-FUTURES"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BOARD_PASSWORD = os.getenv("BOARD_PASSWORD", "kutu318")
MIN_POPCOUNT = int(os.getenv("MIN_POPCOUNT", "6"))
MIN_COMBO = float(os.getenv("MIN_COMBO", "0.72"))
MIN_VOLUME = float(os.getenv("MIN_VOLUME", "3000000"))
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "60"))
STATE_PATH = "docs/board_state.json"
HTML_PATH = "docs/index.html"
DATA_PATH = "docs/board.json"
MODULES = ["VOL", "PRC", "MOM", "VLT", "TIME", "OB", "FVG", "FHS", "SCR", "REG"]
