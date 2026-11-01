import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import parallel_bot as p


def candles(move=0.004):
    # Last 3-candle move exceeds 0.30%, enabling opposing signals.
    prices = [100.0] * 5 + [100.1, 100.3, 100.5]
    return [[i * 300, 0, 0, 0, price] for i, price in enumerate(prices)]


class ParallelBotTests(unittest.TestCase):
    def setUp(self):
        self.current = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        self.state = {"portfolios": {name: p.new_portfolio() for name in p.STRATEGIES}}

    def test_opposite_signals_and_independent_entries(self):
        result = p.signals(candles())
        self.assertEqual(result, {"momentum": "UP", "mean_reversion": "DOWN"})
        p.advance(self.state, candles(), 101.0, self.current, self.current)
        self.assertEqual(len(self.state["portfolios"]["momentum"]["pending"]), 1)
        self.assertEqual(len(self.state["portfolios"]["mean_reversion"]["pending"]), 1)
        p.advance(self.state, candles(), 101.0, self.current, self.current)
        self.assertEqual(self.state["portfolios"]["momentum"]["trades_today"], 1)

    def test_independent_settlement(self):
        p.advance(self.state, candles(), 101.0, self.current, self.current)
        later = self.current + timedelta(minutes=15)
        rows = p.advance(self.state, candles(), 102.0, later, later)
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.state["portfolios"]["momentum"]["balance"], 1008.0)
        self.assertEqual(self.state["portfolios"]["mean_reversion"]["balance"], 990.0)
        self.assertEqual({r["strategy"] for r in rows}, set(p.STRATEGIES))

    def test_daily_limit_each_portfolio(self):
        for portfolio in self.state["portfolios"].values():
            portfolio["trades_today"] = 5
            portfolio["trade_day"] = self.current.date().isoformat()
        p.advance(self.state, candles(), 101.0, self.current, self.current)
        self.assertTrue(all(not v["pending"] for v in self.state["portfolios"].values()))


if __name__ == "__main__":
    unittest.main()
