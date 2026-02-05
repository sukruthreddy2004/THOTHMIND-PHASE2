import os
import json
from flask import Flask, request, jsonify
from config import API_KEY
from strategy import decide_action, reset_daily_state, daily_state
import logging
from datetime import datetime

# LOGGING SETUP


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# PERFORMANCE TRACKING


performance_log = {
    "days": [],
    "total_trades": 0,
    "total_profit": 0
}


def log_trade_decision(data, action, balance):
    
    logger.info(
        f"Min {data.get('minute_of_day', '?'):3d} | "
        f"Bal: ${balance:7.2f} | "
        f"Action: {action.get('action'):11s} | "
        f"Trades: {daily_state['trades_today']:2d}/{daily_state['max_daily_trades']} | "
        f"{action.get('reason', '')[:50]}"
    )



# ENDPOINTS

@app.route("/", methods=["GET"])
def home(): 
    return jsonify({
        "status": "ThothMind Phase 2 Trading Bot - Running Successfully ",
        
        "endpoints": ["/health", "/reset", "/start", "/tick", "/end"],
        "daily_stats": {
            "trades_today": daily_state["trades_today"],
            "consecutive_wins": daily_state["consecutive_wins"],
            "consecutive_losses": daily_state["consecutive_losses"],
            "profit_locked": daily_state["profit_locked"]
        }
    })


def authorized(req):
    return req.headers.get("X-API-Key") == API_KEY


@app.route("/health", methods=["GET"])
def health():
    if not authorized(request):
        logger.warning("Unauthorized health check attempt")
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({
        "status": "ok",

    })


@app.route("/reset", methods=["POST"])
def reset():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    reason = data.get("reason", "No reason provided")
    
    logger.info(f"=" * 80)
    logger.info(f"RESET CALLED: {reason}")
    logger.info(f"=" * 80)
    
    reset_daily_state()
    performance_log["days"] = []
    performance_log["total_trades"] = 0
    performance_log["total_profit"] = 0
    
    return jsonify({"status": "reset_complete"})


@app.route("/start", methods=["POST"])
def start():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    day = data.get("day", "?")
    date = data.get("date", "?")
    initial_balance = data.get("initial_balance", 1000.0)
    
    logger.info("=" * 80)
    logger.info(f"DAY {day} STARTING ({date})")
    logger.info(f"Initial Balance: ${initial_balance:.2f}")
    logger.info("=" * 80)
    
    # Initialize daily state
    reset_daily_state(initial_balance)
    
    return jsonify({"status": "ready"})


@app.route("/tick", methods=["POST"])
def tick():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        data = request.json
        
        # Extract key metrics
        timestamp = data.get("timestamp", "?")
        minute = data.get("minute_of_day", 0)
        minutes_left = data.get("minutes_remaining", 0)
        account = data.get("account", {})
        position = data.get("position", {})
        
        balance = account.get("balance", 0)
        equity = account.get("equity", 0)
        unrealized_pnl = account.get("unrealized_pnl", 0)
        
        # Make trading decision
        action = decide_action(data)
        
        # Log the decision
        log_trade_decision(data, action, balance)
        
        # Special logging for important events
        if action.get("action") in ["OPEN_LONG", "OPEN_SHORT"]:
            logger.info(f">>> OPENING {action.get('action')}: {action.get('ticker')} "
                       f"@ {action.get('leverage')}x leverage, {action.get('size_pct')}% size")
        
        if action.get("action") == "CLOSE":
            if position.get("is_open"):
                pnl = position.get("unrealized_pnl_pct", 0)
                logger.info(f"<<< CLOSING {position.get('side')}: {position.get('ticker')} "
                           f"@ {pnl:+.2f}% P&L")
        
        
        if minute % 60 == 0 and minute > 0:
            win_rate = 0
            if daily_state["winning_trades"] or daily_state["losing_trades"]:
                total = len(daily_state["winning_trades"]) + len(daily_state["losing_trades"])
                win_rate = len(daily_state["winning_trades"]) / total * 100 if total > 0 else 0
            
            logger.info("-" * 80)
            logger.info(f"HOURLY UPDATE: Minute {minute}/960")
            logger.info(f"Balance: ${balance:.2f} | Equity: ${equity:.2f} | Unrealized: ${unrealized_pnl:+.2f}")
            logger.info(f"Trades: {daily_state['trades_today']} | Win Rate: {win_rate:.1f}%")
            logger.info(f"Streak: {daily_state['consecutive_wins']}W / {daily_state['consecutive_losses']}L")
            logger.info("-" * 80)
        
        return jsonify(action)
    
    except Exception as e:
        logger.error(f"ERROR in tick: {str(e)}", exc_info=True)
        
        return jsonify({
            "action": "HOLD",
            "reason": f"Error occurred: {str(e)[:50]}"
        })


@app.route("/end", methods=["POST"])
def end():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    day = data.get("day", "?")
    date = data.get("date", "?")
    final_balance = data.get("final_balance", 0)
    daily_pnl = data.get("daily_pnl", 0)
    trades = data.get("trades_today", 0)
    
    # Calculate performance metrics
    starting_balance = daily_state.get("balance_at_start", 1000)
    pnl_pct = (daily_pnl / starting_balance) * 100 if starting_balance > 0 else 0
    
    win_rate = 0
    avg_win = 0
    avg_loss = 0
    
    if daily_state["winning_trades"] or daily_state["losing_trades"]:
        total = len(daily_state["winning_trades"]) + len(daily_state["losing_trades"])
        win_rate = len(daily_state["winning_trades"]) / total * 100 if total > 0 else 0
        
        if daily_state["winning_trades"]:
            avg_win = sum(daily_state["winning_trades"]) / len(daily_state["winning_trades"])
        
        if daily_state["losing_trades"]:
            avg_loss = sum(daily_state["losing_trades"]) / len(daily_state["losing_trades"])
    
    # Log end of day summary
    logger.info("=" * 80)
    logger.info(f"DAY {day} COMPLETE ({date})")
    logger.info(f"Final Balance: ${final_balance:.2f}")
    logger.info(f"Daily P&L: ${daily_pnl:+.2f} ({pnl_pct:+.2f}%)")
    logger.info(f"Trades: {trades}")
    logger.info(f"Win Rate: {win_rate:.1f}%")
    logger.info(f"Avg Win: {avg_win:+.2f}% | Avg Loss: {avg_loss:+.2f}%")
    logger.info(f"Peak Balance Today: ${daily_state['peak_balance']:.2f}")
    logger.info("=" * 80)
    
    # Store day summary
    day_summary = {
        "day": day,
        "date": date,
        "pnl": daily_pnl,
        "pnl_pct": pnl_pct,
        "trades": trades,
        "win_rate": win_rate,
        "final_balance": final_balance
    }
    performance_log["days"].append(day_summary)
    performance_log["total_trades"] += trades
    performance_log["total_profit"] += daily_pnl
    
    return jsonify({"status": "done"})



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info("=" * 80)
    logger.info(f"ThothMind Trading Bot Starting on port {port}")
    logger.info("Features: Advanced TA, Circuit Breakers, Risk Management")
    logger.info("=" * 80)
    app.run(host="0.0.0.0", port=port)


