import unittest
from datetime import datetime, timedelta, timezone
import strategy_lab as lab


def candles(n=250, step=0.001):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(n):
        price = 100 * (1 + step) ** i
        result.append({"timestamp": start + timedelta(minutes=5 * i),
                       "open": price, "high": price * 1.001,
                       "low": price * 0.999, "close": price * 1.0005,
                       "volume": 100 + i % 5})
    return result


class StrategyLabTests(unittest.TestCase):
    def test_all_strategies_return_known_signal(self):
        data = candles()
        for name in lab.STRATEGIES:
            self.assertIn(lab.signal(name, data, 30), ("UP", "DOWN", "NO_TRADE"))

    def test_comparison_has_holdout(self):
        report = lab.compare(candles())
        self.assertEqual(set(report["strategies"]), set(lab.STRATEGIES))
        self.assertEqual(report["split_index"], 175)

    def test_no_overlap_and_daily_limit(self):
        trades = lab.simulate(candles(), "momentum", 20, 250)
        self.assertLessEqual(len(trades), 5)
        self.assertTrue(all(t["pnl"] in (8.0, -10.0, 0.0) for t in trades))

    def test_no_future_data_in_signal(self):
        data = candles()
        baseline = lab.signal("momentum", data, 30)
        data[31]["close"] *= 5
        self.assertEqual(baseline, lab.signal("momentum", data, 30))

    def test_missing_interval_skips_trades(self):
        data = candles()
        data[25]["timestamp"] += timedelta(minutes=1)
        trades = lab.simulate(data, "momentum", 25, 30)
        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
