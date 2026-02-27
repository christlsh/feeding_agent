# Transaction Cost-Aware Factor Backtest

Reference: AQR Portfolio-ML — 考虑交易成本的组合ML算法

Core insight: many ML factors have positive gross returns but **negative net returns**
after accounting for realistic transaction costs (bid-ask spread + market impact).

## Summary Table (Long-Short Sharpe at different cost levels)

| Factor | Turnover | Gross Sharpe | 5bps | 10bps | 20bps | 30bps |
|--------|----------|-------------|------|-------|-------|-------|
| Reversal_5d | 36% | 0.35 | -0.00 | -0.35 | -1.04 | -1.73 |
| Volatility_20d | 7% | 0.62 | 0.55 | 0.48 | 0.35 | 0.21 |
| Momentum_20d | 16% | -1.00 | -1.16 | -1.32 | -1.63 | -1.95 |

### Reversal_5d
- Days: 476, Avg daily turnover: 36.0%
- Gross: 3.6 bps/day, Sharpe=0.35
- Cost 5bps: -0.0 bps/day, Sharpe=-0.00
- Cost 10bps: -3.6 bps/day, Sharpe=-0.35
- Cost 20bps: -10.8 bps/day, Sharpe=-1.04
- Cost 30bps: -18.0 bps/day, Sharpe=-1.73

### Volatility_20d
- Days: 476, Avg daily turnover: 7.2%
- Gross: 6.7 bps/day, Sharpe=0.62
- Cost 5bps: 5.9 bps/day, Sharpe=0.55
- Cost 10bps: 5.2 bps/day, Sharpe=0.48
- Cost 20bps: 3.8 bps/day, Sharpe=0.35
- Cost 30bps: 2.3 bps/day, Sharpe=0.21

### Momentum_20d
- Days: 476, Avg daily turnover: 15.8%
- Gross: -10.1 bps/day, Sharpe=-1.00
- Cost 5bps: -11.7 bps/day, Sharpe=-1.16
- Cost 10bps: -13.3 bps/day, Sharpe=-1.32
- Cost 20bps: -16.4 bps/day, Sharpe=-1.63
- Cost 30bps: -19.6 bps/day, Sharpe=-1.95

## Conclusion
- High-turnover factors (reversal) are most affected by transaction costs
- This validates AQR's core thesis: cost-aware optimization is essential
- Traditional factor sorts can flip from profitable to unprofitable at realistic cost levels
- A-share market: stamp tax (0.05%) + commission (~0.02%) ≈ 7bps one-way for large caps
- Small caps: additional 10-20bps market impact due to lower liquidity