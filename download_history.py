"""Download historical Coinbase BTC-USD 5-minute candles for offline research.

Uses public candles API, limited to 300 bars per request. Skips missing
intervals rather than fabricating candles. No authentication or trades.
"""
import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def download(days, output):
    if not 7 <= days <= 90:
        raise ValueError("days must be between 7 and 90")
    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    end -= timedelta(minutes=end.minute % 5)
    start = end - timedelta(days=days)
    records = {}
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + timedelta(minutes=5 * 299), end)
        params = urllib.parse.urlencode({
            "start": cursor.isoformat(), "end": next_cursor.isoformat(),
            "granularity": 300
        })
        url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?" + params
        req = urllib.request.Request(url, headers={
            "User-Agent": "BTC-Paper-Research/1.0", "Accept": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    rows = json.load(response)
                if not isinstance(rows, list):
                    raise ValueError("Unexpected Coinbase response")
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        for row in rows:
            ts = int(row[0])
            if int(start.timestamp()) <= ts < int(end.timestamp()):
                records[ts] = row
        cursor = next_cursor
        time.sleep(0.4)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for ts, row in sorted(records.items()):
            writer.writerow([
                datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                row[3], row[2], row[1], row[4], row[5]
            ])
    print(f"Saved {len(records)} historical candles to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("btc_5m.csv"))
    args = parser.parse_args()
    download(args.days, args.output)
