# Bitcoin strategy research lab

This repository now includes an **offline, non-trading** comparison tool:
`strategy_lab.py`.

Four fixed candidate strategies are compared: 15-minute momentum, sharp-move
mean reversion, momentum with a volatility filter, and trend plus volume
confirmation. No strategy is automatically selected for live or simulated
execution based on these results.

## Run the comparison

Provide a UTC 5-minute candle CSV with headers:

```csv
timestamp,open,high,low,close,volume
2026-01-01T00:00:00+00:00,100,101,99,100.5,10
```

At least 100 candles are required; use several months of representative
history for any meaningful study. Run:

```bash
python strategy_lab.py path/to/btc_5m.csv --output strategy_comparison.json
python -m unittest discover -p 'test_*.py' -v
```

Results use a chronological 70% training / 30% untouched holdout split.
Signals use only data known by the signal candle close; hypothetical entry
is the next candle open and exit is the close three candles later (15-minute
holding period). Missing 5-minute intervals are skipped. One trade at a
time, five trades per UTC day, and a $30 daily loss cap are simulated.

**Limits:** Candle-open entry and candle-close exit are approximations, not
actual timestamped execution quotes. The $8 win / $10 loss payoffs are
hypothetical, not Kalshi market quotes. No fees, spreads, slippage, or
exchange-specific settlement rules are modeled. Results are not evidence
of profitability or a recommendation to trade real money. The comparison
does not train an AI model. The existing forward paper-trading bot remains
separate; do not merge historical and new-method performance uncritically.
