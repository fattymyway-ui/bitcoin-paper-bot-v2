"""Synthetic BTC direction paper trading; no exchange orders or credentials.

A 15-minute momentum heuristic (not AI). Prices are observed Coinbase ticker
quotes, not executable Kalshi binary-option prices. 80% payout is hypothetical.
"""
import csv
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path("data")
DATA.mkdir(exist_ok=True)
STATE = DATA / "state.json"
JOURNAL = DATA / "journal.csv"
INITIAL_BALANCE = 1000.0
STAKE = 10.0
PAYOUT = 0.80
HORIZON = timedelta(minutes=15)
MAX_SETTLEMENT_DELAY = timedelta(minutes=2)
MAX_PRICE_AGE = timedelta(minutes=2)
FIELDS = ["created_at", "settled_at", "direction", "entry_price",
          "exit_price", "stake", "pnl", "outcome"]


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "BTC-Paper-Bot/2.1", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def fetch_candles(current):
    raw = fetch_json("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=300")
    if not isinstance(raw, list):
        raise RuntimeError("Unexpected Coinbase candle response")
    cutoff = int(current.timestamp() // 300) * 300
    candles = sorted((c for c in raw if int(c[0]) < cutoff), key=lambda c: c[0])
    if len(candles) < 8 or cutoff - int(candles[-1][0]) > 900:
        raise RuntimeError("Missing or stale completed BTC/USD candles")
    return candles


def fetch_spot(current):
    ticker = fetch_json("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
    price = float(ticker["price"])
    if price <= 0:
        raise RuntimeError("Invalid BTC ticker price")
    observed = parse_time(ticker["time"])
    if observed > current + timedelta(seconds=15) or current - observed > MAX_PRICE_AGE:
        raise RuntimeError("BTC ticker timestamp is stale or in the future")
    return price, observed


def momentum_signal(candles):
    closes = [float(c[4]) for c in candles]
    change_pct = (closes[-1] / closes[-4] - 1) * 100
    if change_pct > 0.15:
        return "UP"
    if change_pct < -0.15:
        return "DOWN"
    return "NO_TRADE"


def read_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"balance": INITIAL_BALANCE, "pending": [], "last_signal_candle": None}


def save_state(state):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, STATE)


def write_rows(rows):
    if not rows:
        return
    new_file = not JOURNAL.exists()
    with JOURNAL.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def settle_trade(trade, observed, price):
    due = parse_time(trade["created_at"]) + HORIZON
    if observed < due:
        return None
    delay = observed - due
    # If the runner missed the 15-minute observation window, don't invent
    # an on-time result from a later quote. Keep an auditable VOID row.
    if delay > MAX_SETTLEMENT_DELAY:
        pnl, outcome = 0.0, "VOID"
    else:
        entry = float(trade["entry_price"])
        if price == entry:
            pnl, outcome = 0.0, "TIE"
        else:
            won = price > entry if trade["direction"] == "UP" else price < entry
            pnl = round(STAKE * PAYOUT if won else -STAKE, 2)
            outcome = "WIN" if won else "LOSS"
    return {
        "created_at": trade["created_at"], "settled_at": observed.isoformat(),
        "direction": trade["direction"], "entry_price": trade["entry_price"],
        "exit_price": price, "stake": STAKE, "pnl": pnl, "outcome": outcome
    }


def main():
    current = now_utc()
    candles = fetch_candles(current)
    spot, observed = fetch_spot(current)
    state = read_state()
    today = current.date().isoformat()
    if state.get("trade_day") != today:
        state["trade_day"] = today
        state["trades_today"] = 0
        state["loss_today"] = 0.0

    settled, pending = [], []
    for trade in state["pending"]:
        row = settle_trade(trade, observed, spot)
        if row is None:
            pending.append(trade)
        else:
            settled.append(row)
            state["balance"] = round(state["balance"] + row["pnl"], 2)
            if row["pnl"] < 0 and row["settled_at"][:10] == today:
                state["loss_today"] = round(state["loss_today"] - row["pnl"], 2)
    state["pending"] = pending
    write_rows(settled)

    direction = momentum_signal(candles)
    candle_id = int(candles[-1][0])
    allowed = (
        direction != "NO_TRADE"
        and not state["pending"]
        and state["trades_today"] < 5
        and state["loss_today"] < 30
        and state.get("last_signal_candle") != candle_id
        and state["balance"] >= STAKE
    )
    if allowed:
        state["pending"].append({
            "created_at": observed.isoformat(),
            "direction": direction,
            "entry_price": spot
        })
        state["trades_today"] += 1
        state["last_signal_candle"] = candle_id

    state["last_run"] = current.isoformat()
    state["last_btc_price"] = spot
    state["last_direction"] = direction
    save_state(state)
    print(json.dumps({
        "balance": state["balance"], "btc_usd": spot, "signal": direction,
        "settled_this_run": len(settled), "pending": len(state["pending"]),
        "trades_today": state["trades_today"],
        "loss_today": state["loss_today"],
        "note": "Synthetic payout; not a real exchange execution"
    }, indent=2))


if __name__ == "__main__":
    main()
