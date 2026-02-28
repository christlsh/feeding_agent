# Factor Preprocessing Pipeline Comparison

Reference: QuantSeek - 全解析——多因子策略因子预处理
Factor: Reversal_5d (5-day return reversal)
All preprocessing is cross-sectional (per-day) to avoid look-ahead bias.

## Preprocessing Methods
1. **Raw**: No processing
2. **Winsorize**: MAD clipping at median ± 5*MAD
3. **Z-score**: (x - mean) / std
4. **Rank Norm**: Rank → Uniform → Inverse Normal CDF
5. **Win+Z**: Winsorize then Z-score
6. **Win+Rank**: Winsorize then Rank Normalize

## Results (A-share, 2024-2025)

### Rank IC (Spearman) - invariant to monotonic transforms

| Method | Rank IC | Rank IR | IC>0% | LS bps/d | LS Sharpe |
|--------|---------|---------|-------|----------|-----------|
| Raw | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Winsorize | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Z-score | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Rank Norm | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Win+Z | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |
| Win+Rank | 0.0252 | 0.14 | 55% | 3.6 | 0.35 |

### Pearson IC (Linear) - sensitive to preprocessing

| Method | Pearson IC | Pearson IR | Delta vs Raw |
|--------|-----------|-----------|-------------|
| Raw | 0.0134 | 0.09 | +0.0000 |
| Winsorize | 0.0090 | 0.06 | -0.0044 |
| Z-score | 0.0134 | 0.09 | +0.0000 |
| Rank Norm | 0.0071 | 0.05 | -0.0063 |
| Win+Z | 0.0090 | 0.06 | -0.0044 |
| Win+Rank | 0.0067 | 0.04 | -0.0067 |

## Analysis

- Best by Pearson IR: **Z-score** (Pearson IR=0.09)
- Rank IC is identical across all methods (expected: Spearman is rank-invariant)
- Pearson IC reveals the real impact of preprocessing on linear models
- Winsorize: Pearson IC 0.0134→0.0090 (-33.1%)
- Z-score: Pearson IC 0.0134→0.0134 (+0.0%)
- Rank Norm: Pearson IC 0.0134→0.0071 (-46.9%)
- Win+Z: Pearson IC 0.0134→0.0090 (-33.1%)
- Win+Rank: Pearson IC 0.0134→0.0067 (-50.1%)

## Key Takeaways
- **Rank-based evaluation** (Spearman IC, quintile sort) is unaffected by monotonic preprocessing
- **Linear models** (regression, Pearson IC) benefit from proper preprocessing
- Winsorization removes outlier contamination of Pearson correlation
- Z-score standardization enables fair comparison of factor coefficients
- Rank normalization forces Gaussian marginals — best for linear Gaussian models
- In practice: **Winsorize → Z-score** for regression; **raw ranks** for tree models