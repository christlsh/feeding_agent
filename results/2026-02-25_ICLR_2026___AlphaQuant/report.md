# AlphaQuant: Basic Statistical Factor Test

Reference: ICLR 2026 AlphaQuant - LLM + Evolution Feature Engineering
These basic statistical features are the starting-point (few-shot prompts)
that seed the LLM's search. The paper's full pipeline can significantly
improve upon these baselines via evolutionary optimization.

## Results (A-share, 20-day window, 2024-2025)

| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|-----|-------|----------|-----------|
| Return_mean | -0.0379 | -0.21 | 41% | -10.1 | -1.00 |
| Return_std_neg | 0.0407 | 0.18 | 62% | 6.7 | 0.62 |
| Return_skew | 0.0237 | 0.25 | 61% | 6.9 | 1.22 |
| Return_kurt_neg | 0.0036 | 0.06 | 58% | 0.9 | 0.30 |
| Return_autocorr | -0.0040 | -0.04 | 47% | -3.4 | -0.65 |

## Analysis

1. **Return_std_neg**: IC=0.0407 (positive), Sharpe=0.62
2. **Return_mean**: IC=-0.0379 (negative), Sharpe=-1.00
3. **Return_skew**: IC=0.0237 (positive), Sharpe=1.22
4. **Return_autocorr**: IC=-0.0040 (negative), Sharpe=-0.65
5. **Return_kurt_neg**: IC=0.0036 (positive), Sharpe=0.30

## Notes
- These are the simplest statistical features from return series
- AlphaQuant uses LLM to generate progressively more complex features
- Quality-Diversity optimization evolves towards Spearman > 0.8
- GPU required for full LLM-based feature search (not available)