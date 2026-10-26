
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
PAYOUT = 0.80  # Hypothetical payout, not a Kalshi quote
HORIZON = timedelta(minutes=15)

FIELDS = [
    "created_at", "settled_at", "direction",
    "entry_price", "exit_price", "stake", "pnl", "outcome"
]


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_candles():
    url = (
        "https://api.exchange.coinbase.com/"
        "products/BTC-USD/candles?granularity=300"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "BTC-Paper-Bot/2.0",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = json.load(response)

    if not isinstance(raw, list):
        raise RuntimeError("Unexpected Coinbase response")

    candles = sorted(raw, key=lambda row: row[0])
    cutoff = int(now_utc().timestamp() // 300) * 300

    # Exclude the current unfinished candle.
    candles = [c for c in candles if int(c[0]) < cutoff]

    if len(candles) < 8:
        raise RuntimeError("Not enough BTC/USD candles")

    if cutoff - int(candles[-1][0]) > 900:
        raise RuntimeError("BTC/USD candles are stale")

    return candles


def read_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))

    return {
        "balance": INITIAL_BALANCE,
        "pending": [],
        "last_signal_candle": None
    }


def save_state(state):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8"
    )
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


def main():
    candles = fetch_candles()
    state = read_state()
    current = now_utc()

    latest = candles[-1]
    latest_price = float(latest[4])

    settled = []
    still_pending = []

    for trade in state["pending"]:
        due = parse_time(trade["created_at"]) + HORIZON

        matches = [
            c for c in candles
            if datetime.fromtimestamp(
                int(c[0]) + 300, timezone.utc
            ) >= due
        ]

        if current >= due and matches:
            exit_candle = matches[0]
            exit_price = float(exit_candle[4])

            if trade["direction"] == "UP":
                won = exit_price > trade["entry_price"]
            else:
                won = exit_price < trade["entry_price"]

            pnl = round(
                STAKE * PAYOUT if won else -STAKE, 2
            )

            state["balance"] = round(
                state["balance"] + pnl, 2
            )

            settled.append({
                "created_at": trade["created_at"],
                "settled_at": datetime.fromtimestamp(
                    int(exit_candle[0]) + 300,
                    timezone.utc
                ).isoformat(),
                "direction": trade["direction"],
                "entry_price": trade["entry_price"],
                "exit_price": exit_price,
                "stake": STAKE,
                "pnl": pnl,
                "outcome": "WIN" if won else "LOSS"
            })
        else:
            still_pending.append(trade)

    state["pending"] = still_pending
    write_rows(settled)

    closes = [float(c[4]) for c in candles]

    # Simple momentum heuristic, not trained AI.
    recent_change = (
        closes[-1] / closes[-4] - 1
    ) * 100

    if recent_change > 0.15:
        direction = "UP"
    elif recent_change < -0.15:
        direction = "DOWN"
    else:
        direction = "NO_TRADE"

    candle_id = int(latest[0])
    today = current.date().isoformat()

    if state.get("trade_day") != today:
        state["trade_day"] = today
        state["trades_today"] = 0
        state["loss_today"] = 0.0

    state["loss_today"] = round(
        state.get("loss_today", 0) +
        sum(
            -r["pnl"] for r in settled
            if r["pnl"] < 0
            and r["settled_at"][:10] == today
        ),
        2
    )

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
            "created_at": current.isoformat(),
            "direction": direction,
            "entry_price": latest_price
        })
        state["trades_today"] += 1
        state["last_signal_candle"] = candle_id
        print("SIMULATED SIGNAL:", direction)
    else:
        print("NO NEW PAPER TRADE")

    state["last_run"] = current.isoformat()
    state["last_btc_price"] = latest_price
    state["last_direction"] = direction

    save_state(state)

    print(json.dumps({
        "balance": state["balance"],
        "btc_usd": latest_price,
        "signal": direction,
        "settled_this_run": len(settled),
        "pending": len(state["pending"]),
        "trades_today": state["trades_today"]
    }, indent=2))


if __name__ == "__main__":
    main()
