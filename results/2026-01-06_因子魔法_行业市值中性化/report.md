# Factor Neutralization: Industry + Size

Reference: QuantSeek - 因子魔法：行业市值中性化
Method: Cross-sectional OLS regression against Barra industry dummies + SIZE
Residual = neutralized (pure alpha) factor value

## Results (A-share, 2024-2025)

### Raw Factors

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| Momentum_20d_raw | -0.0368 | -0.20 | 42% | -10.2 | -1.00 |
| Reversal_5d_raw | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Volatility_20d_raw | -0.0407 | -0.18 | 38% | -6.7 | -0.62 |

### After Industry + Size Neutralization

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| Momentum_20d_neut | -0.0315 | -0.31 | 38% | -11.4 | -2.05 |
| Reversal_5d_neut | 0.0264 | 0.27 | 58% | 8.0 | 1.38 |
| Volatility_20d_neut | -0.0373 | -0.31 | 35% | -5.5 | -0.92 |

### Comparison (Delta)

| Factor | IC Delta | IR Delta | Sharpe Delta |
|--------|----------|----------|--------------|
| Momentum_20d | +0.0052 | -0.11 | -1.06 |
| Reversal_5d | +0.0012 | +0.12 | +1.04 |
| Volatility_20d | +0.0034 | -0.13 | -0.30 |

## Analysis

- **Momentum_20d**: Neutralization degraded (IC -0.0368→-0.0315, Sharpe -1.00→-2.05)
- **Reversal_5d**: Neutralization improved (IC 0.0252→0.0264, Sharpe 0.35→1.38)
- **Volatility_20d**: Neutralization degraded (IC -0.0407→-0.0373, Sharpe -0.62→-0.92)

## Notes
- Neutralization strips out industry/size beta, leaving pure stock selection signal
- Factors driven purely by industry/size bets will lose power after neutralization
- Factors with genuine stock-level alpha will retain or improve
- 'Magic effect': sometimes noise from industry exposure masks underlying signal