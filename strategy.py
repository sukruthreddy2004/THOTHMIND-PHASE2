# =========================
# GLOBAL STATE
# =========================

current_day = None
daily_pnl = 0.0
last_trade_minute = None
traded_today = set()

# =========================
# STRATEGY PARAMS
# =========================

LEVERAGE = 4
SIZE_PCT = 40

DAILY_PROFIT_LOCK = 600
DAILY_LOSS_CAP = -400

COOLDOWN_MINUTES = 10

TP_PCT = 8
SL_PCT = -4

# =========================
# MAIN LOGIC
# =========================

def decide_action(data):
    global current_day, daily_pnl, last_trade_minute, traded_today

    day = data.get("day")
    minute = data.get("minute_of_day", 0)
    minutes_left = data.get("minutes_remaining", 0)

    account = data.get("account", {})
    position = data.get("position", {})
    market_data = data.get("market_data", {})
    qualifying = set(data.get("qualifying_tickers", []))

    # =========================
    # DAILY RESET
    # =========================
    if current_day != day:
        current_day = day
        daily_pnl = 0.0
        last_trade_minute = None
        traded_today.clear()

    # =========================
    # UPDATE DAILY PNL
    # =========================
    daily_pnl = account.get("unrealized_pnl", daily_pnl)

    # =========================
    # DAILY LOCKS
    # =========================
    if daily_pnl >= DAILY_PROFIT_LOCK:
        return {"action": "HOLD", "reason": "Daily profit target reached"}

    if daily_pnl <= DAILY_LOSS_CAP:
        return {"action": "HOLD", "reason": "Daily loss cap reached"}

    # =========================
    # POSITION MANAGEMENT
    # =========================
    if position.get("is_open"):
        pnl_pct = position.get("unrealized_pnl_pct", 0)

        if pnl_pct >= TP_PCT:
            last_trade_minute = minute
            traded_today.add(position["ticker"])
            return {"action": "CLOSE", "reason": "Take profit"}

        if pnl_pct <= SL_PCT:
            last_trade_minute = minute
            traded_today.add(position["ticker"])
            return {"action": "CLOSE", "reason": "Stop loss"}

        if minutes_left < 30:
            return {"action": "CLOSE", "reason": "End of day exit"}

        return {"action": "HOLD"}

    # =========================
    # COOLDOWN
    # =========================
    if last_trade_minute is not None:
        if minute - last_trade_minute < COOLDOWN_MINUTES:
            return {"action": "HOLD"}

    # =========================
    # ENTRY LOGIC
    # =========================
    candidates = {}

    for ticker, info in market_data.items():
        if ticker not in qualifying:
            continue
        if ticker in traded_today:
            continue

        change = abs(info.get("change_24h_pct", 0))
        if 22 <= change <= 35:
            candidates[ticker] = info

    if not candidates:
        return {"action": "HOLD"}

    best_ticker, best_info = max(
        candidates.items(),
        key=lambda x: abs(x[1]["change_24h_pct"])
    )

    direction = "OPEN_LONG" if best_info["change_24h_pct"] > 0 else "OPEN_SHORT"

    return {
        "action": direction,
        "ticker": best_ticker,
        "leverage": LEVERAGE,
        "size_pct": SIZE_PCT,
        "reason": "Momentum continuation"
    }
