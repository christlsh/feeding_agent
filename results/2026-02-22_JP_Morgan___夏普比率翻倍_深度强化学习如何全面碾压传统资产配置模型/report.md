## MVO Backtest Report

**Period**: 2024-01-02 to 2025-12-18 (475 trading days)

### Portfolio (Momentum + Inverse-Variance MVO)
- Annual Return: 23.54%
- Annual Volatility: 24.72%
- Sharpe Ratio: 0.95
- Max Drawdown: -21.66%
- Daily Mean: 9.73 bps

### Benchmark (Equal-Weight CSI300)
- Annual Return: 17.99%
- Sharpe Ratio: 0.91

### Excess (Portfolio - Benchmark)
- Annual Alpha: 5.55%
- Information Ratio: 0.36

### Setup
- Universe: CSI300
- Signal: 20-day momentum (cumulative return)
- Risk model: Barra GYCNE5 (factor cov + specific risk)
- Weighting: inverse-variance * momentum, long-only, max 5%/stock
- Reference: JP Morgan DRL vs MVO paper (MVO baseline)
