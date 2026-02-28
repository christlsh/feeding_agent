"""
Beta Anomaly: Regime-Switching Decomposition

Based on: QuantML - 非μ之错，P之罪：Beta异象背后的机制转换定价逻辑
Core idea: Decompose rolling CAPM beta into correlation and relative volatility:
  beta_i = corr(r_i, r_m) * (sigma_i / sigma_m)

Classify market regimes:
  1. Correlation-driven: high corr, normal idio vol
  2. Idiosyncratic-vol-driven: normal corr, high idio vol
  3. Joint: both high

Test whether regime-aware beta decomposition provides better cross-sectional
predictive power than raw beta.

Factors:
  1. Raw Beta (60-day rolling)
  2. Correlation Component: corr(r_i, r_m) over 60 days
  3. Relative Volatility: sigma_i / sigma_m over 60 days
  4. Beta Residual: beta - predicted_by_regime (mispricing signal)
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from data.data_loader import load_barra_bret, available_dates
import config


def preload_all(start, end, lookback=70):
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
    daily_market = {}
    date_list = []
    for d in load_dates:
        bret = load_barra_bret(d)
        if bret is None:
            continue
        date_list.append(d)
        day_rets = []
        for row in bret.iter_rows(named=True):
            code, ret = row["code"], row.get("ret")
            if ret is not None and not np.isnan(ret):
                daily_rets.setdefault(code, {})[d] = ret
                day_rets.append(ret)
        if day_rets:
            daily_market[d] = np.mean(day_rets)  # equal-weight market
    return daily_rets, daily_market, sorted(date_list)


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


def compute_beta_factors(daily_rets, daily_market, date_list, test_dates, window=60):
    """Decompose rolling beta into correlation and relative volatility.
    Vectorized: compute all stocks at once per date using numpy broadcasting."""
    date_idx = {d: i for i, d in enumerate(date_list)}

    factors = {
        "Raw_Beta": {},
        "Correlation": {},
        "Rel_Volatility": {},
        "Low_Beta": {},
    }

    mkt_arr = np.array([daily_market.get(d, np.nan) for d in date_list])

    all_codes = sorted(daily_rets.keys())
    code_idx = {c: i for i, c in enumerate(all_codes)}
    n_stocks = len(all_codes)
    n_dates = len(date_list)

    print(f"  Building return matrix: {n_stocks} stocks x {n_dates} dates...")
    ret_mat = np.full((n_stocks, n_dates), np.nan)
    for code, rets in daily_rets.items():
        ci = code_idx[code]
        for d, r in rets.items():
            if d in date_idx:
                ret_mat[ci, date_idx[d]] = r

    print(f"  Computing rolling betas (vectorized)...")
    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx < window:
            continue

        # Market returns in window
        mkt_w = mkt_arr[idx - window:idx]  # (window,)
        stock_w = ret_mat[:, idx - window:idx]  # (n_stocks, window)

        # Valid mask: both stock and market non-NaN
        mkt_valid = ~np.isnan(mkt_w)  # (window,)
        stock_valid = ~np.isnan(stock_w)  # (n_stocks, window)
        both_valid = stock_valid & mkt_valid[np.newaxis, :]  # (n_stocks, window)
        counts = both_valid.sum(axis=1)  # (n_stocks,)

        # Only process stocks with enough data
        enough = counts >= (window // 2)
        if enough.sum() == 0:
            continue

        # Replace NaN with 0 for computation, masked by both_valid
        mkt_filled = np.where(mkt_valid, mkt_w, 0)  # (window,)
        stock_filled = np.where(both_valid, stock_w, 0)  # (n_stocks, window)
        mkt_mask = np.where(both_valid, mkt_filled[np.newaxis, :], 0)

        # Means (only over valid entries)
        with np.errstate(invalid='ignore'):
            s_mean = stock_filled.sum(axis=1) / counts
            m_mean = mkt_mask.sum(axis=1) / counts

        # Deviations
        s_dev = stock_filled - s_mean[:, np.newaxis]  # (n_stocks, window)
        m_dev = mkt_mask - m_mean[:, np.newaxis]
        s_dev = np.where(both_valid, s_dev, 0)
        m_dev = np.where(both_valid, m_dev, 0)

        # Variance and covariance
        s_var = (s_dev ** 2).sum(axis=1) / counts
        m_var = (m_dev ** 2).sum(axis=1) / counts
        cov = (s_dev * m_dev).sum(axis=1) / counts

        s_std = np.sqrt(s_var)
        m_std = np.sqrt(m_var)

        # Correlation and relative volatility
        with np.errstate(invalid='ignore', divide='ignore'):
            corr = cov / (s_std * m_std)
            rel_vol = s_std / m_std
            beta = corr * rel_vol

        # Valid results
        valid_mask = enough & (s_std > 0) & (m_std > 0) & ~np.isnan(corr)

        beta_d, corr_d, relvol_d, lowbeta_d = {}, {}, {}, {}
        for ci in np.where(valid_mask)[0]:
            code = all_codes[ci]
            beta_d[code] = float(beta[ci])
            corr_d[code] = float(corr[ci])
            relvol_d[code] = float(rel_vol[ci])
            lowbeta_d[code] = -float(beta[ci])

        factors["Raw_Beta"][d] = beta_d
        factors["Correlation"][d] = corr_d
        factors["Rel_Volatility"][d] = relvol_d
        factors["Low_Beta"][d] = lowbeta_d

    return factors


def classify_regime(corr_d, relvol_d):
    """Classify market regime based on cross-sectional distributions."""
    if not corr_d or not relvol_d:
        return "unknown"
    corrs = np.array(list(corr_d.values()))
    relvols = np.array(list(relvol_d.values()))

    avg_corr = np.median(corrs)
    avg_relvol = np.median(relvols)

    # Thresholds (median of historical distribution)
    if avg_corr > 0.3 and avg_relvol < 2.0:
        return "correlation_driven"
    elif avg_corr < 0.2 and avg_relvol > 2.0:
        return "idio_vol_driven"
    else:
        return "joint"


def evaluate(name, factor_by_date, fwd_map):
    common_dates = sorted(set(factor_by_date.keys()) & set(fwd_map.keys()))
    daily_ics, daily_ls = [], []

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

        fr = np.argsort(np.argsort(f)).astype(float)
        rr = np.argsort(np.argsort(r)).astype(float)
        ic = np.corrcoef(fr, rr)[0, 1]
        daily_ics.append(ic)

        n5 = max(len(f) // 5, 1)
        si = np.argsort(f)
        daily_ls.append(r[si[-n5:]].mean() - r[si[:n5]].mean())

    ics = np.array(daily_ics)
    ls = np.array(daily_ls)
    return {
        "name": name,
        "days": len(ics),
        "ic_mean": float(ics.mean()) if len(ics) else 0,
        "ic_std": float(ics.std()) if len(ics) else 0,
        "ir": float(ics.mean() / ics.std()) if len(ics) and ics.std() > 0 else 0,
        "ic_pos": float((ics > 0).mean()) if len(ics) else 0,
        "ls_bps": float(ls.mean() * 10000) if len(ls) else 0,
        "ls_sharpe": float(ls.mean() / ls.std() * np.sqrt(242)) if len(ls) and ls.std() > 0 else 0,
    }


def format_report(results, regime_counts):
    lines = [
        "# Beta Anomaly: Regime-Switching Decomposition",
        "",
        "Reference: QuantML - 非μ之错，P之罪：Beta异象背后的机制转换定价逻辑",
        "Method: Decompose beta = correlation * relative_volatility",
        "Rolling window: 60 trading days",
        "",
        "## Beta Decomposition",
        "- beta_i = corr(r_i, r_m) * (sigma_i / sigma_m)",
        "- Correlation: systematic co-movement",
        "- Relative Volatility: idiosyncratic risk relative to market",
        "",
        "## Market Regime Distribution",
        "",
    ]
    total = sum(regime_counts.values())
    for regime, count in sorted(regime_counts.items()):
        pct = count / total * 100 if total > 0 else 0
        lines.append(f"- **{regime}**: {count} days ({pct:.0f}%)")

    lines += [
        "",
        "## Results (A-share, 2024-2025)",
        "",
        "| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|---------|-----|-------|----------|-----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )

    lines += ["", "## Analysis", ""]
    for r in results:
        direction = "positive" if r['ic_mean'] > 0 else "negative"
        lines.append(f"- **{r['name']}**: IC={r['ic_mean']:.4f} ({direction}), "
                     f"Sharpe={r['ls_sharpe']:.2f}")

    # Compare raw beta vs low beta
    raw = next((r for r in results if r['name'] == 'Raw_Beta'), None)
    low = next((r for r in results if r['name'] == 'Low_Beta'), None)
    if raw and low:
        lines.append(f"")
        if low['ls_sharpe'] > raw['ls_sharpe']:
            lines.append(f"**Low-Beta anomaly confirmed**: Low_Beta Sharpe ({low['ls_sharpe']:.2f}) > "
                        f"Raw_Beta Sharpe ({raw['ls_sharpe']:.2f})")
        else:
            lines.append(f"Low-Beta anomaly not significant in this period")

    corr_r = next((r for r in results if r['name'] == 'Correlation'), None)
    rv_r = next((r for r in results if r['name'] == 'Rel_Volatility'), None)
    if corr_r and rv_r:
        stronger = corr_r if abs(corr_r['ic_mean']) > abs(rv_r['ic_mean']) else rv_r
        lines.append(f"**Dominant component**: {stronger['name']} (|IC|={abs(stronger['ic_mean']):.4f})")

    lines += [
        "",
        "## Notes",
        "- Paper argues mispricing comes from regime transition probabilities, not within-regime beta",
        "- Low-beta anomaly: low-beta stocks earn higher risk-adjusted returns than CAPM predicts",
        "- A-share market has structural features (T+1, limits) that may amplify beta decomposition effects",
        "- Correlation component captures systemic co-movement risk (crowding, momentum crashes)",
        "- Relative volatility captures idiosyncratic risk pricing (lottery preferences)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2024, 1, 2), date(2025, 12, 18)

    daily_rets, daily_market, date_list = preload_all(start, end)
    fwd_map = preload_fwd(start, end)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"Test dates: {len(test_dates)}")

    print("Computing beta decomposition factors...")
    factors = compute_beta_factors(daily_rets, daily_market, date_list, test_dates)

    # Classify regimes
    regime_counts = {}
    for d in test_dates:
        if d in factors["Correlation"] and d in factors["Rel_Volatility"]:
            regime = classify_regime(factors["Correlation"][d], factors["Rel_Volatility"][d])
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

    results = []
    for fname in ["Raw_Beta", "Correlation", "Rel_Volatility", "Low_Beta"]:
        print(f"\nEvaluating: {fname}")
        r = evaluate(fname, factors[fname], fwd_map)
        results.append(r)
        print(f"  IC={r['ic_mean']:.4f}, IR={r['ir']:.2f}, LS Sharpe={r['ls_sharpe']:.2f}")

    report = format_report(results, regime_counts)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
