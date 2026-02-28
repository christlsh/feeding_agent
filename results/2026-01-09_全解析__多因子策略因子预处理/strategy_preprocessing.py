"""
Factor Preprocessing Pipeline

Based on: QuantSeek - 全解析——多因子策略因子预处理
Core idea: Proper cross-sectional preprocessing of factors is crucial.
Steps tested:
  1. Raw (no processing)
  2. MAD Winsorization (clip at median ± 5*MAD)
  3. Z-score Standardization
  4. Rank Normalization (uniform → normal via inverse CDF)
  5. Full pipeline: Winsorize → Standardize
  6. Rank pipeline: Winsorize → Rank Normalize

All operations are cross-sectional (per-day) to avoid look-ahead bias.
Tested on Reversal_5d factor (known to have some A-share signal).
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from scipy import stats as scipy_stats
from datetime import date
from data.data_loader import load_barra_bret, available_dates
import config


def preload_returns(start, end, lookback=10):
    bret_dir = os.path.join(config.BARRA_DIR, "bret")
    all_dates = available_dates(bret_dir)
    start_idx = 0
    for i, d in enumerate(all_dates):
        if d >= start:
            start_idx = max(0, i - lookback)
            break
    load_dates = [d for d in all_dates[start_idx:] if d <= end]
    print(f"Preloading {len(load_dates)} dates...")
    daily_rets = {}
    date_list = []
    for d in load_dates:
        bret = load_barra_bret(d)
        if bret is None:
            continue
        date_list.append(d)
        for row in bret.iter_rows(named=True):
            code, ret = row["code"], row.get("ret")
            if ret is not None and not np.isnan(ret):
                daily_rets.setdefault(code, {})[d] = ret
    return daily_rets, sorted(date_list)


def preload_fwd(start, end):
    fwd_dir = config.FWD_RET_DIR
    all_dates = available_dates(fwd_dir)
    load_dates = [d for d in all_dates if start <= d <= end]
    print(f"Preloading fwd for {len(load_dates)} dates...")
    fwd_map = {}
    for d in load_dates:
        fwd = pl.read_parquet(os.path.join(fwd_dir, f"{d}.parquet"))
        if "time" in fwd.columns:
            fwd = fwd.filter(pl.col("time") == fwd["time"].min())
        if "ret_T1d" not in fwd.columns:
            continue
        day_map = {}
        for row in fwd.select(["code", "ret_T1d"]).iter_rows(named=True):
            r = row["ret_T1d"]
            if r is not None and not np.isnan(r):
                day_map[row["code"]] = r
        fwd_map[d] = day_map
    return fwd_map


def compute_reversal(daily_rets, date_list, test_dates, window=5):
    """Raw 5-day reversal factor."""
    factor = {}
    date_idx = {d: i for i, d in enumerate(date_list)}
    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx < window:
            continue
        lb = date_list[idx - window:idx]
        day_vals = {}
        for code, rets in daily_rets.items():
            vals = [rets[ld] for ld in lb if ld in rets]
            if len(vals) >= 3:
                cum = 1.0
                for v in vals:
                    cum *= (1 + v)
                day_vals[code] = -(cum - 1)
        factor[d] = day_vals
    return factor


# --- Preprocessing functions (cross-sectional) ---

def winsorize_mad(vals_dict, n_mad=5.0):
    """MAD winsorization: clip at median ± n_mad * MAD."""
    codes = list(vals_dict.keys())
    vals = np.array([vals_dict[c] for c in codes])
    med = np.median(vals)
    mad = np.median(np.abs(vals - med))
    if mad == 0:
        mad = np.std(vals) * 0.6745  # fallback
    lower = med - n_mad * mad
    upper = med + n_mad * mad
    clipped = np.clip(vals, lower, upper)
    return {codes[i]: float(clipped[i]) for i in range(len(codes))}


def zscore_standardize(vals_dict):
    """Z-score standardization: (x - mean) / std."""
    codes = list(vals_dict.keys())
    vals = np.array([vals_dict[c] for c in codes])
    mu = vals.mean()
    std = vals.std()
    if std == 0:
        return vals_dict
    z = (vals - mu) / std
    return {codes[i]: float(z[i]) for i in range(len(codes))}


def rank_normalize(vals_dict):
    """Rank normalization: rank → uniform → inverse normal CDF."""
    codes = list(vals_dict.keys())
    vals = np.array([vals_dict[c] for c in codes])
    n = len(vals)
    ranks = np.argsort(np.argsort(vals)).astype(float)
    # Transform to (0,1) avoiding 0 and 1
    u = (ranks + 0.5) / n
    # Inverse normal CDF
    normed = scipy_stats.norm.ppf(u)
    return {codes[i]: float(normed[i]) for i in range(len(codes))}


def apply_preprocessing(raw_factor, method):
    """Apply preprocessing to each day's cross-section."""
    processed = {}
    for d, vals in raw_factor.items():
        if len(vals) < 50:
            continue
        if method == "raw":
            processed[d] = vals
        elif method == "winsorize":
            processed[d] = winsorize_mad(vals)
        elif method == "zscore":
            processed[d] = zscore_standardize(vals)
        elif method == "rank_norm":
            processed[d] = rank_normalize(vals)
        elif method == "win_zscore":
            processed[d] = zscore_standardize(winsorize_mad(vals))
        elif method == "win_rank":
            processed[d] = rank_normalize(winsorize_mad(vals))
    return processed


def evaluate(name, factor_by_date, fwd_map):
    common_dates = sorted(set(factor_by_date.keys()) & set(fwd_map.keys()))
    daily_rank_ics, daily_pearson_ics, daily_ls = [], [], []

    for d in common_dates:
        fvals, fwd = factor_by_date[d], fwd_map[d]
        common = sorted(set(fvals.keys()) & set(fwd.keys()))
        if len(common) < 50:
            continue
        f = np.array([fvals[c] for c in common])
        r = np.array([fwd[c] for c in common])
        valid = ~(np.isnan(f) | np.isnan(r))
        f, r = f[valid], r[valid]
        if len(f) < 50:
            continue

        # Rank IC (Spearman)
        fr = np.argsort(np.argsort(f)).astype(float)
        rr = np.argsort(np.argsort(r)).astype(float)
        rank_ic = np.corrcoef(fr, rr)[0, 1]
        daily_rank_ics.append(rank_ic)

        # Pearson IC (linear) - this shows preprocessing effects
        pearson_ic = np.corrcoef(f, r)[0, 1]
        if not np.isnan(pearson_ic):
            daily_pearson_ics.append(pearson_ic)

        n5 = max(len(f) // 5, 1)
        si = np.argsort(f)
        daily_ls.append(r[si[-n5:]].mean() - r[si[:n5]].mean())

    rics = np.array(daily_rank_ics)
    pics = np.array(daily_pearson_ics)
    ls = np.array(daily_ls)
    return {
        "name": name,
        "days": len(rics),
        "rank_ic": float(rics.mean()) if len(rics) else 0,
        "rank_ir": float(rics.mean() / rics.std()) if len(rics) and rics.std() > 0 else 0,
        "pearson_ic": float(pics.mean()) if len(pics) else 0,
        "pearson_ir": float(pics.mean() / pics.std()) if len(pics) and pics.std() > 0 else 0,
        "ic_pos": float((rics > 0).mean()) if len(rics) else 0,
        "ls_bps": float(ls.mean() * 10000) if len(ls) else 0,
        "ls_sharpe": float(ls.mean() / ls.std() * np.sqrt(242)) if len(ls) and ls.std() > 0 else 0,
    }


def format_report(results):
    lines = [
        "# Factor Preprocessing Pipeline Comparison",
        "",
        "Reference: QuantSeek - 全解析——多因子策略因子预处理",
        "Factor: Reversal_5d (5-day return reversal)",
        "All preprocessing is cross-sectional (per-day) to avoid look-ahead bias.",
        "",
        "## Preprocessing Methods",
        "1. **Raw**: No processing",
        "2. **Winsorize**: MAD clipping at median ± 5*MAD",
        "3. **Z-score**: (x - mean) / std",
        "4. **Rank Norm**: Rank → Uniform → Inverse Normal CDF",
        "5. **Win+Z**: Winsorize then Z-score",
        "6. **Win+Rank**: Winsorize then Rank Normalize",
        "",
        "## Results (A-share, 2024-2025)",
        "",
        "### Rank IC (Spearman) - invariant to monotonic transforms",
        "",
        "| Method | Rank IC | Rank IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|---------|---------|-------|----------|-----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['rank_ic']:.4f} | {r['rank_ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )

    lines += [
        "",
        "### Pearson IC (Linear) - sensitive to preprocessing",
        "",
        "| Method | Pearson IC | Pearson IR | Delta vs Raw |",
        "|--------|-----------|-----------|-------------|",
    ]
    raw = next(r for r in results if r['name'] == 'Raw')
    for r in results:
        delta = r['pearson_ic'] - raw['pearson_ic']
        lines.append(
            f"| {r['name']} | {r['pearson_ic']:.4f} | {r['pearson_ir']:.2f} | "
            f"{delta:+.4f} |"
        )

    lines += [
        "",
        "## Analysis",
        "",
    ]
    best_p = max(results, key=lambda x: abs(x['pearson_ir']))
    lines.append(f"- Best by Pearson IR: **{best_p['name']}** (Pearson IR={best_p['pearson_ir']:.2f})")
    lines.append(f"- Rank IC is identical across all methods (expected: Spearman is rank-invariant)")
    lines.append(f"- Pearson IC reveals the real impact of preprocessing on linear models")

    for r in results:
        if r['name'] == 'Raw':
            continue
        pd = r['pearson_ic'] - raw['pearson_ic']
        pct = pd / abs(raw['pearson_ic']) * 100 if raw['pearson_ic'] != 0 else 0
        lines.append(f"- {r['name']}: Pearson IC {raw['pearson_ic']:.4f}→{r['pearson_ic']:.4f} ({pct:+.1f}%)")

    lines += [
        "",
        "## Key Takeaways",
        "- **Rank-based evaluation** (Spearman IC, quintile sort) is unaffected by monotonic preprocessing",
        "- **Linear models** (regression, Pearson IC) benefit from proper preprocessing",
        "- Winsorization removes outlier contamination of Pearson correlation",
        "- Z-score standardization enables fair comparison of factor coefficients",
        "- Rank normalization forces Gaussian marginals — best for linear Gaussian models",
        "- In practice: **Winsorize → Z-score** for regression; **raw ranks** for tree models",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2024, 1, 2), date(2025, 12, 18)

    daily_rets, date_list = preload_returns(start, end)
    fwd_map = preload_fwd(start, end)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"Test dates: {len(test_dates)}")

    print("Computing raw reversal factor...")
    raw_factor = compute_reversal(daily_rets, date_list, test_dates)

    methods = ["raw", "winsorize", "zscore", "rank_norm", "win_zscore", "win_rank"]
    method_names = ["Raw", "Winsorize", "Z-score", "Rank Norm", "Win+Z", "Win+Rank"]

    results = []
    for method, mname in zip(methods, method_names):
        print(f"\nProcessing & evaluating: {mname}")
        processed = apply_preprocessing(raw_factor, method)
        r = evaluate(mname, processed, fwd_map)
        results.append(r)
        print(f"  Rank IC={r['rank_ic']:.4f}, Pearson IC={r['pearson_ic']:.4f}, LS Sharpe={r['ls_sharpe']:.2f}")

    report = format_report(results)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
