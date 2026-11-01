# Parallel 30-day forward paper comparison

Two independent simulated portfolios start with **$1,000 each** when
`parallel_bot.py` first runs. The existing `bot.py` and its historical
`data/state.json` / `data/journal.csv` are not reset or combined.

- **Momentum:** BTC 15-minute completed-candle change > +0.15% predicts UP;
  below -0.15% predicts DOWN.
- **Mean reversion:** BTC 15-minute completed-candle change > +0.30%
  predicts DOWN; below -0.30% predicts UP.
- Both use one Coinbase observed BTC/USD ticker quote per run.
- Each has its own max five trades per UTC day, $30 realized-loss limit,
  one pending trade at a time, and hypothetical $10 stake / $8 win payout.
- Settlement is targeted 15 minutes after entry. If no quote is observed
  within two minutes of the target, it is marked VOID with $0 P&L.
- Exact price ties also have $0 P&L.

Records are kept separately in `data/parallel_state.json` and
`data/parallel_journal.csv`, tagged by strategy. GitHub Actions is
best-effort; runs may be delayed, missed, or fail. Check the Actions logs.

**Do not combine the old momentum bot history with these new results.**
Compare the two new portfolios over the same forward observation period.
A 30-day period starts at the first successful parallel run; this does
not automatically stop at day 30. No real-money execution is possible.

These are synthetic directional bets, not executable Kalshi contracts.
The 80% payout is an assumption, not an observed market price; fees and
slippage are not modeled. The 55.6% break-even rate only applies to the
hypothetical $8-win/$10-loss structure. No profitability is established.
