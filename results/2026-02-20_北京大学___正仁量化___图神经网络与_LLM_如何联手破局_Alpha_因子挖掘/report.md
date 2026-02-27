# Baseline Alpha Factor Test Report

Reference: 北京大学 × 正仁量化 | GNN + LLM Alpha Factor Mining

## Summary

| Factor | Days | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|------|---------|-----|-------|----------|-----------|
| Momentum_20d | 476 | -0.0379 | -0.21 | 41% | -10.1 | -1.00 |
| Reversal_5d | 476 | 0.0260 | 0.15 | 56% | 3.6 | 0.35 |
| Volatility_20d | 476 | 0.0407 | 0.18 | 62% | 6.7 | 0.62 |

### Momentum_20d
- Trading days: 476, Avg stocks: 5124
- IC: mean=-0.0379, std=0.1803, IR=-0.21
- IC positive rate: 40.8%
- Long-Short: -10.1 bps/day, annualized=-24.43%, Sharpe=-1.00

### Reversal_5d
- Trading days: 476, Avg stocks: 5127
- IC: mean=0.0260, std=0.1774, IR=0.15
- IC positive rate: 55.7%
- Long-Short: 3.6 bps/day, annualized=8.69%, Sharpe=0.35

### Volatility_20d
- Trading days: 476, Avg stocks: 5124
- IC: mean=0.0407, std=0.2204, IR=0.18
- IC positive rate: 61.6%
- Long-Short: 6.7 bps/day, annualized=16.12%, Sharpe=0.62

## Notes
- Evaluation uses Barra bret daily returns and intraday forward returns
- T+1 constraint: factor computed at market close, return starts next day
- Full universe (~5000 A-share stocks)
- The paper's GNN+LLM approach aims to significantly beat these baselines
- GPU required for full model reproduction (not available)