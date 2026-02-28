# Alpha191 Short-Cycle Trading Factors (A-Share)

Reference: QuantSeek - 美股短周期交易因子
Alpha191 factors originated from A-share market. The article tested them
on US stocks via DS-LASSO. Here we test representative factors on their
home market with Barra style factor controls.

## Factors
1. **Short_Reversal_3d**: Negative 3-day cumulative return (short-term reversal)
2. **Momentum_Accel**: 5d return - 10d return (momentum acceleration)
3. **Return_Consistency**: Fraction of positive days in 10d window
4. **Volatility_Asymmetry**: -downside_vol / total_vol (low downside risk premium)
5. **Autocorr_5d**: Lag-1 autocorrelation over 5 days

## Results (A-share, 2024-2025)

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| Short_Reversal_3d | 0.0220 | 0.13 | 57% | 2.2 | 0.23 |
| Momentum_Accel | 0.0116 | 0.08 | 51% | 4.3 | 0.62 |
| Return_Consistency | -0.0165 | -0.15 | 45% | -5.6 | -0.91 |
| Volatility_Asymmetry | -0.0241 | -0.22 | 38% | -6.8 | -1.07 |
| Autocorr_5d | 0.0026 | 0.03 | 51% | 3.4 | 0.71 |

## Analysis

1. **Volatility_Asymmetry**: IC=-0.0241 (negative), Sharpe=-1.07
2. **Short_Reversal_3d**: IC=0.0220 (positive), Sharpe=0.23
3. **Return_Consistency**: IC=-0.0165 (negative), Sharpe=-0.91
4. **Momentum_Accel**: IC=0.0116 (positive), Sharpe=0.62
5. **Autocorr_5d**: IC=0.0026 (positive), Sharpe=0.71

## Notes
- Alpha191 contains 191 factors; we test 5 representative ones
- Original paper found 17/191 significant after DS-LASSO with 151 controls
- Key insight: volume-price interaction factors capture retail trading behavior
- A-share market's high retail participation makes these factors particularly relevant
- DS-LASSO would further filter for independent predictive power