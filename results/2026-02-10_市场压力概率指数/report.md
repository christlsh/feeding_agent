# Market Stress Probability Index (MSPI)

Reference: QuantML - 市场压力概率指数
Method: Cross-sectional fragility signals → Expanding-window Lasso-Logit

## Fragility Signals
1. **Return Dispersion**: Cross-sectional std of daily returns
2. **Skewness**: Cross-sectional skewness of returns
3. **Kurtosis**: Cross-sectional excess kurtosis
4. **Down Ratio**: Fraction of stocks with negative returns
5. **Tail Ratio**: 5th/95th percentile ratio
6. **Realized Volatility**: Annualized monthly vol
7. **Max Drop**: Worst single-day market return

## Stress Definition
- Stress month: monthly market return ≤ -3.05% (bottom 20%)

## Market Timing Evaluation (A-share, 2022-2025)

| Metric | Buy & Hold | MSPI Timed |
|--------|-----------|------------|
| Months | 48 | 48 |
| Cumulative Return | 31.74% | 139.27% |
| Sharpe (annualized) | 0.41 | 1.34 |
| Max Drawdown | -44.36% | -60.84% |
| Stress Detection Rate | - | 82% (11 months) |

Timing rule: 30% exposure when MSPI > 0.5, 100% otherwise.

## MSPI Time Series (recent months)

| Month | Market Return | MSPI | Stress? |
|-------|-------------|------|---------|
| 2025-01 | -1.56% | 0.432 |  |
| 2025-02 | 7.47% | 0.002 |  |
| 2025-03 | 0.28% | 0.110 |  |
| 2025-04 | -2.21% | 0.154 |  |
| 2025-05 | 5.12% | 0.006 |  |
| 2025-06 | 6.30% | 0.001 |  |
| 2025-07 | 5.25% | 0.005 |  |
| 2025-08 | 8.59% | 0.001 |  |
| 2025-09 | 1.11% | 0.127 |  |
| 2025-10 | 1.64% | 0.055 |  |
| 2025-11 | -0.21% | 0.084 |  |
| 2025-12 | -1.88% | 0.487 |  |

## Notes
- Original paper uses CRSP data (US); we adapt to A-share market
- Expanding window ensures no look-ahead bias
- MSPI probability is calibrated — 0.5+ indicates elevated stress risk
- A-share markets show higher cross-sectional correlation → dispersion signal may differ
- Useful as risk overlay / position sizing signal, not standalone trading strategy