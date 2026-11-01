"""Parallel independent synthetic BTC paper portfolios; NO REAL ORDERS.

Uses the same observed Coinbase quote for both strategies. Each has its own
$1,000 virtual balance, max 5 entries per UTC day, and $30 realized-loss cap.
No API keys, broker connectivity, or execution capability.
"""
import csv
import json
import os
from datetime import timedelta
from pathlib import Path
from bot import (DATA, HORIZON, STAKE, PAYOUT, now_utc, parse_time,
                 fetch_candles, fetch_spot, momentum_signal, settle_trade)

STATE = DATA / "parallel_state.json"
JOURNAL = DATA / "parallel_journal.csv"
STRATEGIES = ("momentum", "mean_reversion")
FIELDS = ["strategy", "created_at", "settled_at", "direction", "entry_price",
          "exit_price", "stake", "pnl", "outcome"]


def signals(candles):
    closes = [float(c[4]) for c in candles]
    change = (closes[-1] / closes[-4] - 1) * 100
    reverse = "DOWN" if change > 0.30 else "UP" if change < -0.30 else "NO_TRADE"
    return {"momentum": momentum_signal(candles), "mean_reversion": reverse}


def new_portfolio():
    return {"balance": 1000.0, "pending": [], "last_signal_candle": None,
            "trade_day": None, "trades_today": 0, "loss_today": 0.0}


def read_state():
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        state = {"started_at": now_utc().isoformat(), "portfolios": {}}
    for name in STRATEGIES:
        state["portfolios"].setdefault(name, new_portfolio())
    return state


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


def advance(state, candles, price, observed, current):
    """Mutates separate virtual portfolios, returns settled journal rows."""
    choices = signals(candles)
    candle_id = int(candles[-1][0])
    today = current.date().isoformat()
    rows = []
    for name in STRATEGIES:
        portfolio = state["portfolios"][name]
        if portfolio.get("trade_day") != today:
            portfolio["trade_day"] = today
            portfolio["trades_today"] = 0
            portfolio["loss_today"] = 0.0
        remaining = []
        for trade in portfolio["pending"]:
            settled = settle_trade(trade, observed, price)
            if settled is None:
                remaining.append(trade)
                continue
            settled["strategy"] = name
            rows.append(settled)
            portfolio["balance"] = round(portfolio["balance"] + settled["pnl"], 2)
            if settled["pnl"] < 0 and settled["settled_at"][:10] == today:
                portfolio["loss_today"] = round(portfolio["loss_today"] - settled["pnl"], 2)
        portfolio["pending"] = remaining
        direction = choices[name]
        if (direction != "NO_TRADE"
                and not portfolio["pending"]
                and portfolio["trades_today"] < 5
                and portfolio["loss_today"] < 30
                and portfolio["balance"] >= STAKE
                and portfolio.get("last_signal_candle") != candle_id):
            portfolio["pending"].append({
                "created_at": observed.isoformat(),
                "direction": direction, "entry_price": price})
            portfolio["last_signal_candle"] = candle_id
            portfolio["trades_today"] += 1
        portfolio["last_direction"] = direction
        portfolio["last_run"] = current.isoformat()
    return rows


def main():
    current = now_utc()
    candles = fetch_candles(current)
    price, observed = fetch_spot(current)
    state = read_state()
    rows = advance(state, candles, price, observed, current)
    write_rows(rows)
    save_state(state)
    print(json.dumps({
        "mode": "synthetic paper only",
        "observed_at": observed.isoformat(),
        "settled": len(rows),
        "portfolios": {name: {
            "balance": state["portfolios"][name]["balance"],
            "pending": len(state["portfolios"][name]["pending"]),
            "signal": state["portfolios"][name]["last_direction"]
        } for name in STRATEGIES}
    }, indent=2))


if __name__ == "__main__":
    main()
