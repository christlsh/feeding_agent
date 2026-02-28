# Flash Crash Prediction: VPIN + Orderbook Microstructure Factors

Reference: QuantSeek - "闪崩"全解析 (VPIN + ML crash prediction)
Data: A-share L2 orderbook (10-level bid/ask) aggregated to daily cross-section

## Factors
1. **OB_Imbalance**: (bid_vol - ask_vol) / total_vol (buying pressure)
2. **Spread_neg**: -avg(bid-ask spread) (liquidity, negative = low spread = liquid)
3. **Depth_Ratio**: bid_depth / ask_depth (supply-demand at orderbook level)
4. **VPIN_Proxy_neg**: -std(imbalance) (flow toxicity proxy, negative = low toxicity)
5. **Price_Impact_neg**: -|return|/sqrt(vol) (Kyle's lambda, negative = low impact)

## Results (A-share, 2024-2025)

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| OB_Imbalance | 0.0095 | 0.09 | 57% | 40.1 | 11.01 |
| Spread_neg | -0.0229 | -0.15 | 44% | -15.9 | -2.72 |
| Depth_Ratio | -0.3245 | -4.41 | 0% | -134.7 | -36.95 |
| VPIN_Proxy_neg | -0.0580 | -0.59 | 29% | -76.8 | -17.02 |
| Price_Impact_neg | -0.0402 | -0.17 | 38% | -49.1 | -5.30 |

## Analysis

1. **Depth_Ratio**: IC=-0.3245 (negative), Sharpe=-36.95
2. **VPIN_Proxy_neg**: IC=-0.0580 (negative), Sharpe=-17.02
3. **Price_Impact_neg**: IC=-0.0402 (negative), Sharpe=-5.30
4. **Spread_neg**: IC=-0.0229 (negative), Sharpe=-2.72
5. **OB_Imbalance**: IC=0.0095 (positive), Sharpe=11.01

## Notes
- Full VPIN requires tick-level volume bucketing; we use snapshot-based proxy
- Original paper achieves AUC 0.9+ for 15s/90s flash crash prediction (intraday)
- Our daily aggregation tests whether microstructure signals predict next-day returns
- A-share limit-up/down mechanism provides natural 'flash crash' boundaries
- Orderbook imbalance is a well-known short-term alpha source in literature
- These factors are most useful at intraday frequency, less so at daily