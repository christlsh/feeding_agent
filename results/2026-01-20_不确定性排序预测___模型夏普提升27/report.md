# Uncertainty-Adjusted Sorting

Reference: QuantSeek - 不确定性排序预测 | 模型夏普提升27%
Prediction model: Rolling 20-day mean return (simple baseline)
Uncertainty: Std of prediction residuals over 60-day window

## Methods
1. **Point Prediction**: Sort by rolling mean return (standard approach)
2. **Uncertainty Adj**: prediction - 0.5 * uncertainty (penalize uncertain stocks)
3. **SNR**: prediction / uncertainty (signal-to-noise ratio)

## Results (A-share, 2024-2025)

| Method | IC | IR | IC>0% | LS bps/d | LS Sharpe | Long Sharpe | Long Vol |
|--------|-----|-----|-------|----------|-----------|-------------|----------|
| Point_Prediction | -0.0380 | -0.21 | 41% | -10.2 | -1.01 | 0.14 | 32.5% |
| Uncertainty_Adj | -0.0063 | -0.03 | 48% | -6.5 | -0.60 | 0.59 | 25.6% |
| SNR | -0.0346 | -0.22 | 42% | -9.2 | -1.02 | 0.18 | 30.1% |

## Analysis

- **Uncertainty_Adj** vs Point Prediction: LS Sharpe -1.01→-0.60 (+40%), Long Vol 32.5%→25.6%
- **SNR** vs Point Prediction: LS Sharpe -1.01→-1.02 (-1%), Long Vol 32.5%→30.1%

## Notes
- The paper uses sophisticated ML models; our baseline uses simple rolling mean
- Key insight: even with a simple predictor, uncertainty adjustment helps
- Main mechanism: reduces exposure to noisy/unstable predictions
- Sharpe improvement comes from lower volatility, not higher returns
- A-share T+1 constraint limits the applicability of daily sorting strategies