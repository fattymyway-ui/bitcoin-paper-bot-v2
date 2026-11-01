"""Offline research only: compare four BTC 5-minute-candle strategies.

Input CSV: timestamp,open,high,low,close,volume (UTC timestamps).
Each signal uses candles through t, enters at next candle OPEN, and settles
at the CLOSE of the third candle after entry (15 minutes). This is a
candle-based proxy, NOT a quote-accurate or executable binary-options result.
Chronological 70/30 split; no parameter selection on test data.
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

STRATEGIES = ("momentum", "mean_reversion", "volatility_filter", "trend_volume")
STAKE = 10.0
WIN_PNL = 8.0
LOSS_PNL = -10.0


def read_candles(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("CSV must contain timestamp,open,high,low,close,volume")
    candles = []
    for row in rows:
        t = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        c = {"timestamp": t}
        for key in ("open", "high", "low", "close", "volume"):
            c[key] = float(row[key])
        if c["open"] <= 0 or c["close"] <= 0 or c["high"] < c["low"] or c["volume"] < 0:
            raise ValueError("Invalid candle values")
        candles.append(c)
    candles.sort(key=lambda c: c["timestamp"])
    if len({c["timestamp"] for c in candles}) != len(candles):
        raise ValueError("Duplicate candle timestamps")
    return candles


def signal(name, candles, i):
    if i < 20:
        return "NO_TRADE"
    closes = [c["close"] for c in candles]
    move = (closes[i] / closes[i - 3] - 1) * 100
    if name == "momentum":
        return "UP" if move > 0.15 else "DOWN" if move < -0.15 else "NO_TRADE"
    if name == "mean_reversion":
        return "DOWN" if move > 0.30 else "UP" if move < -0.30 else "NO_TRADE"
    returns = [abs((closes[j] / closes[j - 1] - 1) * 100) for j in range(i - 11, i + 1)]
    if name == "volatility_filter":
        if sum(returns) / len(returns) < 0.08:
            return "NO_TRADE"
        return "UP" if move > 0.15 else "DOWN" if move < -0.15 else "NO_TRADE"
    if name == "trend_volume":
        avg_volume = sum(c["volume"] for c in candles[i - 19:i]) / 19
        if candles[i]["volume"] <= avg_volume:
            return "NO_TRADE"
        avg_close = sum(closes[i - 19:i + 1]) / 20
        if move > 0.15 and closes[i] > avg_close:
            return "UP"
        if move < -0.15 and closes[i] < avg_close:
            return "DOWN"
        return "NO_TRADE"
    raise ValueError("Unknown strategy")


def simulate(candles, name, start, end):
    # No overlapping trades; max five/day, daily realized loss cap $30.
    trades = []
    last_exit = -1
    day = None
    count = 0
    daily_loss = 0.0
    for i in range(max(start, 20), min(end, len(candles) - 3)):
        if i <= last_exit:
            continue
        # Skip missing candle intervals: signal history and full horizon must be contiguous.
        window = candles[i - 20:i + 4]
        if any((b["timestamp"] - a["timestamp"]).total_seconds() != 300
               for a, b in zip(window, window[1:])):
            continue
        date = candles[i + 1]["timestamp"].date()
        if date != day:
            day, count, daily_loss = date, 0, 0.0
        if count >= 5 or daily_loss >= 30:
            continue
        direction = signal(name, candles, i)
        if direction == "NO_TRADE":
            continue
        entry = candles[i + 1]["open"]
        exit_price = candles[i + 3]["close"]
        pnl = 0.0 if exit_price == entry else (
            WIN_PNL if (exit_price > entry) == (direction == "UP") else LOSS_PNL
        )
        trades.append({"timestamp": candles[i + 1]["timestamp"].isoformat(),
                       "direction": direction, "pnl": pnl})
        count += 1
        daily_loss += max(0.0, -pnl)
        last_exit = i + 3
    return trades


def metrics(trades):
    decided = [t for t in trades if t["pnl"] != 0]
    wins = sum(t["pnl"] > 0 for t in decided)
    balance, peak, max_dd = 1000.0, 1000.0, 0.0
    for t in trades:
        balance += t["pnl"]
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
    return {"trades": len(trades), "decided": len(decided),
            "win_rate": round(wins / len(decided), 4) if decided else None,
            "net_pnl": round(sum(t["pnl"] for t in trades), 2),
            "max_drawdown_usd": round(max_dd, 2)}


def compare(candles):
    if len(candles) < 100:
        raise ValueError("At least 100 five-minute candles required")
    split = int(len(candles) * 0.7)
    results = {}
    for name in STRATEGIES:
        results[name] = {
            "training_period": metrics(simulate(candles, name, 20, split - 3)),
            "holdout_period": metrics(simulate(candles, name, split, len(candles) - 3))
        }
    return {"method": "candle proxy, hypothetical 80% payout; no fees; not executable",
            "split_index": split, "strategies": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("strategy_comparison.json"))
    args = parser.parse_args()
    report = compare(read_candles(args.csv_path))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
