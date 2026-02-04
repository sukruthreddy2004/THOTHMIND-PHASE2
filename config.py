import os


API_KEY = os.environ.get("API_KEY", "sk_thothmind_phase2_7xK9pM2vQ8rT3wY")


DEBUG = os.environ.get("DEBUG", "False").lower() == "true"


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


MAX_DAILY_TRADES = int(os.environ.get("MAX_DAILY_TRADES", "30"))
DAILY_LOSS_LIMIT = float(os.environ.get("DAILY_LOSS_LIMIT", "-40.0"))
PROFIT_LOCK_THRESHOLD = float(os.environ.get("PROFIT_LOCK_THRESHOLD", "40.0"))
MAX_LEVERAGE = int(os.environ.get("MAX_LEVERAGE", "6"))
MIN_LEVERAGE = int(os.environ.get("MIN_LEVERAGE", "2"))
RSI_PERIOD = int(os.environ.get("RSI_PERIOD", "14"))
VOLUME_LOOKBACK = int(os.environ.get("VOLUME_LOOKBACK", "30"))
TRADING_START_DELAY = int(os.environ.get("TRADING_START_DELAY", "30"))  
TRADING_END_BUFFER = int(os.environ.get("TRADING_END_BUFFER", "45"))   