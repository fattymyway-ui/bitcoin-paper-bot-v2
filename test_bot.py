import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import bot


class PaperBotTests(unittest.TestCase):
    def test_momentum(self):
        candles = [[i * 300, 0, 0, 0, p] for i, p in enumerate([100, 100, 100, 100.2, 100.4, 100.6, 100.8, 101])]
        self.assertEqual(bot.momentum_signal(candles), "UP")

    def test_settlement_before_due(self):
        entry = datetime(2026, 11, 1, tzinfo=timezone.utc)
        trade = {"created_at": entry.isoformat(), "direction": "UP", "entry_price": 100}
        self.assertIsNone(bot.settle_trade(trade, entry + timedelta(minutes=14), 101))

    def test_settlement_win_and_loss(self):
        entry = datetime(2026, 11, 1, tzinfo=timezone.utc)
        trade = {"created_at": entry.isoformat(), "direction": "UP", "entry_price": 100}
        self.assertEqual(bot.settle_trade(trade, entry + timedelta(minutes=15), 101)["pnl"], 8.0)
        self.assertEqual(bot.settle_trade(trade, entry + timedelta(minutes=15), 99)["pnl"], -10.0)

    def test_late_quote_void(self):
        entry = datetime(2026, 11, 1, tzinfo=timezone.utc)
        trade = {"created_at": entry.isoformat(), "direction": "DOWN", "entry_price": 100}
        row = bot.settle_trade(trade, entry + timedelta(minutes=18), 99)
        self.assertEqual((row["outcome"], row["pnl"]), ("VOID", 0.0))

    def test_tie_refunds(self):
        entry = datetime(2026, 11, 1, tzinfo=timezone.utc)
        trade = {"created_at": entry.isoformat(), "direction": "DOWN", "entry_price": 100}
        row = bot.settle_trade(trade, entry + timedelta(minutes=15), 100)
        self.assertEqual((row["outcome"], row["pnl"]), ("TIE", 0.0))


if __name__ == "__main__":
    unittest.main()
