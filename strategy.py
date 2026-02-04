import numpy as np
from typing import Dict, List, Tuple, Optional

# ============================================================================
# GLOBAL STATE - Resets each day
# ============================================================================

daily_state = {
    "trades_today": 0,
    "max_daily_trades": 30,
    "balance_at_start": 1000.0,
    "peak_balance": 1000.0,
    "profit_locked": False,
    "consecutive_losses": 0,
    "consecutive_wins": 0,
    "last_trade_minute": -999,
    "winning_trades": [],
    "losing_trades": []
}


def reset_daily_state(initial_balance=1000.0):
    """Called from /start endpoint"""
    daily_state["trades_today"] = 0
    daily_state["balance_at_start"] = initial_balance
    daily_state["peak_balance"] = initial_balance
    daily_state["profit_locked"] = False
    daily_state["consecutive_losses"] = 0
    daily_state["consecutive_wins"] = 0
    daily_state["last_trade_minute"] = -999
    daily_state["winning_trades"] = []
    daily_state["losing_trades"] = []


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

def calculate_rsi(candles: List, period: int = 14) -> float:
    """Calculate RSI from candle data"""
    if len(candles) < period + 1:
        return 50.0  # Neutral
    
    closes = [float(c[4]) for c in candles[-(period+1):]]
    
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_trend_strength(candles: List, periods: List[int] = [15, 30, 60]) -> Dict:
    """
    Analyze trend across multiple timeframes
    Returns direction and strength
    """
    if len(candles) < max(periods):
        return {"direction": 0, "strength": 0, "aligned": False}
    
    trends = []
    
    for period in periods:
        if len(candles) >= period:
            recent = candles[-period:]
            start_price = float(recent[0][4])
            end_price = float(recent[-1][4])
            
            if start_price != 0:
                trend_pct = ((end_price - start_price) / start_price) * 100
                trends.append(trend_pct)
    
    if not trends:
        return {"direction": 0, "strength": 0, "aligned": False}
    
    # Check if all trends point same direction
    all_positive = all(t > 0 for t in trends)
    all_negative = all(t < 0 for t in trends)
    aligned = all_positive or all_negative
    
    direction = 1 if all_positive else (-1 if all_negative else 0)
    strength = sum(abs(t) for t in trends) / len(trends)
    
    return {
        "direction": direction,
        "strength": strength,
        "aligned": aligned,
        "trends": trends
    }


def calculate_volume_trend(candles: List, period: int = 30) -> Dict:
    """Analyze volume patterns"""
    if len(candles) < period * 2:
        return {"ratio": 1.0, "increasing": False}
    
    recent_volume = sum(float(c[5]) for c in candles[-period:])
    older_volume = sum(float(c[5]) for c in candles[-period*2:-period])
    
    if older_volume == 0:
        return {"ratio": 1.0, "increasing": False}
    
    ratio = recent_volume / older_volume
    
    return {
        "ratio": ratio,
        "increasing": ratio > 1.2,
        "strong_increase": ratio > 1.5
    }


def calculate_volatility(candles: List, period: int = 30) -> float:
    """Calculate recent volatility (standard deviation of returns)"""
    if len(candles) < period:
        return 0
    
    recent = candles[-period:]
    closes = [float(c[4]) for c in recent]
    
    returns = []
    for i in range(1, len(closes)):
        if closes[i-1] != 0:
            ret = (closes[i] - closes[i-1]) / closes[i-1]
            returns.append(ret)
    
    if not returns:
        return 0
    
    return float(np.std(returns) * 100)


# ============================================================================
# ENTRY LOGIC
# ============================================================================

def analyze_ticker(ticker: str, info: Dict, history: Dict) -> Optional[Dict]:
    """
    Comprehensive analysis of a ticker
    Returns analysis dict or None if not tradeable
    """
    candles = history.get(ticker, [])
    
    if len(candles) < 60:
        return None
    
    change_24h = info["change_24h_pct"]
    
    # Filter 1: Volatility must be in tradeable range
    if abs(change_24h) < 20:  # Below minimum
        return None
    if abs(change_24h) > 100:  # Too extreme, likely to reverse
        return None
    
    # Filter 2: Calculate technical indicators
    rsi = calculate_rsi(candles, period=14)
    trend = calculate_trend_strength(candles, periods=[15, 30, 60])
    volume = calculate_volume_trend(candles, period=30)
    volatility = calculate_volatility(candles, period=30)
    
    # Filter 3: Trend alignment required
    if not trend["aligned"]:
        return None
    
    # Filter 4: 24h trend must match multi-timeframe trend
    if change_24h > 0 and trend["direction"] < 0:
        return None
    if change_24h < 0 and trend["direction"] > 0:
        return None
    
    # Filter 5: Volume must be sustained
    if volume["ratio"] < 0.8:  # Volume dropping off
        return None
    
    # Filter 6: RSI filters (avoid extreme overbought/oversold)
    if change_24h > 0:  # For longs
        if rsi > 80:  # Too overbought
            return None
        if rsi < 40:  # Not enough momentum
            return None
    else:  # For shorts
        if rsi < 20:  # Too oversold
            return None
        if rsi > 60:  # Not enough downward momentum
            return None
    
    # Calculate composite score
    momentum_score = abs(change_24h) * 0.4
    trend_score = trend["strength"] * 0.3
    volume_score = min(volume["ratio"], 2.0) * 10 * 0.2
    rsi_score = (50 - abs(rsi - 50)) * 0.1  # Favor RSI near 50 (balanced)
    
    total_score = momentum_score + trend_score + volume_score + rsi_score
    
    return {
        "ticker": ticker,
        "score": total_score,
        "change_24h": change_24h,
        "rsi": rsi,
        "trend": trend,
        "volume": volume,
        "volatility": volatility,
        "direction": "LONG" if change_24h > 0 else "SHORT"
    }


def select_best_entry(market_data: Dict, qualifying_tickers: List, history: Dict) -> Optional[Dict]:
    """
    Analyze all tickers and select the best entry
    """
    candidates = []
    
    for ticker in qualifying_tickers:
        if ticker not in market_data:
            continue
        
        info = market_data[ticker]
        analysis = analyze_ticker(ticker, info, history)
        
        if analysis is not None:
            candidates.append(analysis)
    
    if not candidates:
        return None
    
    # Sort by score and return best
    best = max(candidates, key=lambda x: x["score"])
    
    # Require minimum score threshold
    if best["score"] < 15:
        return None
    
    return best


def calculate_position_size(analysis: Dict, current_balance: float) -> Tuple[int, int]:
    """
    Dynamic position sizing based on:
    - Volatility
    - Account balance
    - Win/loss streak
    """
    change_24h = abs(analysis["change_24h"])
    volatility = analysis.get("volatility", 5)
    
    # Base sizing on volatility
    if change_24h > 80 or volatility > 8:
        leverage = 2
        size_pct = 25
    elif change_24h > 60 or volatility > 6:
        leverage = 3
        size_pct = 30
    elif change_24h > 40 or volatility > 4:
        leverage = 4
        size_pct = 40
    elif change_24h > 25:
        leverage = 5
        size_pct = 50
    else:
        leverage = 6
        size_pct = 60
    
    # Reduce size if on losing streak
    if daily_state["consecutive_losses"] >= 2:
        size_pct = int(size_pct * 0.6)
        leverage = max(2, leverage - 1)
    
    # Reduce size if balance is down
    drawdown = (daily_state["balance_at_start"] - current_balance) / daily_state["balance_at_start"]
    if drawdown > 0.2:  # Down more than 20%
        size_pct = int(size_pct * 0.5)
        leverage = max(2, leverage - 1)
    
    # Increase slightly if on winning streak
    if daily_state["consecutive_wins"] >= 2:
        size_pct = min(100, int(size_pct * 1.1))
    
    return leverage, size_pct


# ============================================================================
# EXIT LOGIC
# ============================================================================

def should_close_position(position: Dict, analysis: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Advanced exit logic with dynamic stops
    Returns (should_close, reason)
    """
    pnl_pct = position.get("unrealized_pnl_pct", 0)
    leverage = position.get("leverage", 1)
    entry_time = position.get("entry_time", "")
    
    # Calculate how long we've been in position (rough estimate)
    # This is simplified - in production you'd parse timestamps properly
    
    # Exit 1: Take profit (tiered)
    if pnl_pct >= 15:
        return True, f"Major profit target: {pnl_pct:.1f}%"
    if pnl_pct >= 8:
        return True, f"Profit target: {pnl_pct:.1f}%"
    
    # Exit 2: Trailing stop
    if pnl_pct >= 5:
        # If we were up 5%+ and now below 2%, close
        if pnl_pct < 2:
            return True, f"Trailing stop from peak"
    
    # Exit 3: Dynamic stop loss based on leverage
    stop_loss_pct = -15 / leverage  # Higher leverage = tighter stop
    
    # Wider stop for very high volatility positions
    if leverage <= 3:
        stop_loss_pct = -20
    
    if pnl_pct <= stop_loss_pct:
        return True, f"Stop loss: {pnl_pct:.1f}%"
    
    # Exit 4: Time-based stop (if losing and held too long)
    # Simplified - just check if we're losing
    if pnl_pct < -3 and pnl_pct > stop_loss_pct:
        # Small loss, might want to cut early
        return True, f"Early exit on small loss: {pnl_pct:.1f}%"
    
    return False, "Hold position"


# ============================================================================
# MAIN DECISION FUNCTION
# ============================================================================

def decide_action(data: Dict) -> Dict:
    """
    Main trading decision logic called every minute
    """
    position = data.get("position", {})
    account = data.get("account", {})
    market_data = data.get("market_data", {})
    history = data.get("history", {})
    minutes_left = data.get("minutes_remaining", 0)
    minute_of_day = data.get("minute_of_day", 0)
    
    current_balance = account.get("balance", 1000)
    
    # Update peak balance tracking
    if current_balance > daily_state["peak_balance"]:
        daily_state["peak_balance"] = current_balance
    
    # ========================================================================
    # CIRCUIT BREAKERS
    # ========================================================================
    
    # CB1: Daily loss limit
    loss_pct = ((current_balance - daily_state["balance_at_start"]) / 
                daily_state["balance_at_start"] * 100)
    
    if loss_pct < -40:
        if position.get("is_open"):
            return {"action": "CLOSE", "reason": "Daily loss limit hit (-40%)"}
        return {"action": "HOLD", "reason": "Daily loss limit - no new trades"}
    
    # CB2: Profit lock - if up 40%+, become very conservative
    if loss_pct > 40 and not daily_state["profit_locked"]:
        daily_state["profit_locked"] = True
    
    # CB3: Max trades
    if daily_state["trades_today"] >= daily_state["max_daily_trades"]:
        if position.get("is_open"):
            return {"action": "CLOSE", "reason": "Max daily trades reached"}
        return {"action": "HOLD", "reason": "Trade limit reached"}
    
    # CB4: Cooling period after consecutive losses
    if daily_state["consecutive_losses"] >= 3:
        time_since_last = minute_of_day - daily_state["last_trade_minute"]
        if time_since_last < 30:
            return {"action": "HOLD", "reason": f"Cooling off ({30-time_since_last}min left)"}
        else:
            daily_state["consecutive_losses"] = 0  # Reset
    
    # CB5: Drawdown protection
    drawdown_from_peak = ((daily_state["peak_balance"] - current_balance) / 
                          daily_state["peak_balance"] * 100)
    
    if drawdown_from_peak > 25:
        if position.get("is_open"):
            return {"action": "CLOSE", "reason": "Drawdown protection (25% from peak)"}
        
    
    # CB6: Time-based filters
    if minute_of_day < 30:
        return {"action": "HOLD", "reason": "Market opening period - waiting"}
    
    if minutes_left < 45:
        if position.get("is_open"):
            return {"action": "CLOSE", "reason": "End of day risk management"}
        return {"action": "HOLD", "reason": "Too close to EOD"}
    
    # CB7: Profit lock mode - if up 40%, only take best setups
    if daily_state["profit_locked"]:
        if daily_state["trades_today"] >= 15:  # Reduced limit when protecting profit
            if position.get("is_open"):
                return {"action": "CLOSE", "reason": "Profit protected - reducing activity"}
            return {"action": "HOLD", "reason": "Protecting +40% profit"}
    
    # POSITION MANAGEMENT
    
    
    if position.get("is_open"):
        should_close, reason = should_close_position(position)
        
        if should_close:
            pnl_pct = position.get("unrealized_pnl_pct", 0)
            
            # Update streak tracking
            if pnl_pct > 0:
                daily_state["consecutive_wins"] += 1
                daily_state["consecutive_losses"] = 0
                daily_state["winning_trades"].append(pnl_pct)
            else:
                daily_state["consecutive_losses"] += 1
                daily_state["consecutive_wins"] = 0
                daily_state["losing_trades"].append(pnl_pct)
            
            daily_state["trades_today"] += 1
            daily_state["last_trade_minute"] = minute_of_day
            
            return {"action": "CLOSE", "reason": reason}
        
        return {"action": "HOLD", "reason": f"Monitoring: {position.get('unrealized_pnl_pct', 0):.1f}%"}
    

    # ENTRY LOGIC

    
    if not market_data:
        return {"action": "HOLD", "reason": "No market data"}
    
    qualifying = data.get("qualifying_tickers", [])
    if not qualifying:
        return {"action": "HOLD", "reason": "No qualifying tickers"}
    
    # Find best entry opportunity
    entry = select_best_entry(market_data, qualifying, history)
    
    if entry is None:
        return {"action": "HOLD", "reason": "No valid setups found"}
    
    # Calculate position size
    leverage, size_pct = calculate_position_size(entry, current_balance)
    
    action = "OPEN_LONG" if entry["direction"] == "LONG" else "OPEN_SHORT"
    
    return {
        "action": action,
        "ticker": entry["ticker"],
        "leverage": leverage,
        "size_pct": size_pct,
        "reason": f"Score: {entry['score']:.1f}, RSI: {entry['rsi']:.0f}, Vol: {entry['volume']['ratio']:.1f}x"
    }