# Beta Anomaly: Regime-Switching Decomposition

Reference: QuantML - 非μ之错，P之罪：Beta异象背后的机制转换定价逻辑
Method: Decompose beta = correlation * relative_volatility
Rolling window: 60 trading days

## Beta Decomposition
- beta_i = corr(r_i, r_m) * (sigma_i / sigma_m)
- Correlation: systematic co-movement
- Relative Volatility: idiosyncratic risk relative to market

## Market Regime Distribution

- **correlation_driven**: 363 days (76%)
- **joint**: 113 days (24%)

## Results (A-share, 2024-2025)

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| Raw_Beta | -0.0063 | -0.02 | 48% | 7.2 | 0.59 |
| Correlation | 0.0291 | 0.20 | 60% | 11.3 | 1.66 |
| Rel_Volatility | -0.0324 | -0.14 | 44% | -3.2 | -0.28 |
| Low_Beta | 0.0063 | 0.02 | 52% | -7.2 | -0.59 |

## Analysis

- **Raw_Beta**: IC=-0.0063 (negative), Sharpe=0.59
- **Correlation**: IC=0.0291 (positive), Sharpe=1.66
- **Rel_Volatility**: IC=-0.0324 (negative), Sharpe=-0.28
- **Low_Beta**: IC=0.0063 (positive), Sharpe=-0.59

Low-Beta anomaly not significant in this period
**Dominant component**: Rel_Volatility (|IC|=0.0324)

## Notes
- Paper argues mispricing comes from regime transition probabilities, not within-regime beta
- Low-beta anomaly: low-beta stocks earn higher risk-adjusted returns than CAPM predicts
- A-share market has structural features (T+1, limits) that may amplify beta decomposition effects
- Correlation component captures systemic co-movement risk (crowding, momentum crashes)
- Relative volatility captures idiosyncratic risk pricing (lottery preferences)