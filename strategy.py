def decide_action(data):
    position = data["position"]
    market_data = data.get("market_data", {})
    minutes_left = data.get("minutes_remaining", 0)


    # CASE 1: NO POSITION OPEN

    if not position["is_open"]:
        if not market_data:
            return {"action": "HOLD"}

        # Pick ticker with strongest absolute 24h move
        qualifying = set(data.get("qualifying_tickers", []))

        filtered_market_data = {
            ticker: info
            for ticker, info in market_data.items()
            if ticker in qualifying
}

        if not filtered_market_data:
          return {"action": "HOLD"}

        best_ticker, best_info = max(
    filtered_market_data.items(),
    key=lambda x: abs(x[1]["change_24h_pct"])
)


        change = best_info["change_24h_pct"]

        action = "OPEN_LONG" if change > 0 else "OPEN_SHORT"

        return {
            "action": action,
            "ticker": best_ticker,
            "leverage": 6,
            "size_pct": 60,
            "reason": "Momentum continuation on high-volatility asset"
        }


    # CASE 2: POSITION OPEN

    pnl_pct = position.get("unrealized_pnl_pct", 0)

    if pnl_pct >= 5:
        return {"action": "CLOSE", "reason": "Take profit"}

    if pnl_pct <= -3:
        return {"action": "CLOSE", "reason": "Stop loss"}

    if minutes_left < 30:
        return {"action": "CLOSE", "reason": "End of day risk management"}

    return {"action": "HOLD"}
