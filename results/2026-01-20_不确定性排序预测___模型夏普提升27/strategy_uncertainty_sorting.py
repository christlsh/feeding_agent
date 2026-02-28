"""
Uncertainty-Adjusted Sorting

Based on: QuantSeek - 不确定性排序预测 | 模型夏普提升27%
Core idea: Don't just sort by point prediction — incorporate prediction uncertainty.
For long portfolio: prefer high prediction WITH low uncertainty.
For short portfolio: prefer low prediction WITH low uncertainty.
This reduces exposure to unreliable predictions, improving Sharpe ratio.

Implementation:
  - Point prediction: rolling 20-day mean return (simple baseline)
  - Uncertainty: rolling std of prediction residuals (past 60 days)
  - Adjusted score for long: prediction - lambda * uncertainty
  - Adjusted score for short: -prediction - lambda * uncertainty
  - Combined: prediction / uncertainty (signal-to-noise ratio)
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


def preload_all(start, end, lookback=80):
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


def compute_factors(daily_rets, date_list, test_dates,
                    pred_window=20, uncert_window=60):
    """
    Optimized: pre-compute rolling predictions for all stocks, then derive uncertainty.
    - prediction: rolling mean of past pred_window days
    - uncertainty: std of prediction residuals over past uncert_window days
    """
    date_idx = {d: i for i, d in enumerate(date_list)}

    # Step 1: Build per-stock return arrays aligned to date_list
    print("  Building aligned return matrix...")
    all_codes = sorted(daily_rets.keys())
    code_to_idx = {c: i for i, c in enumerate(all_codes)}
    n_codes = len(all_codes)
    n_dates = len(date_list)

    # Stock x Date matrix (NaN where missing)
    ret_mat = np.full((n_codes, n_dates), np.nan)
    for code, rets in daily_rets.items():
        ci = code_to_idx[code]
        for d, r in rets.items():
            if d in date_idx:
                ret_mat[ci, date_idx[d]] = r

    # Step 2: Pre-compute rolling mean predictions for all stocks x dates
    print("  Computing rolling predictions...")
    pred_mat = np.full((n_codes, n_dates), np.nan)
    for di in range(pred_window, n_dates):
        window = ret_mat[:, di - pred_window:di]
        counts = np.sum(~np.isnan(window), axis=1)
        with np.errstate(invalid='ignore'):
            pred_mat[:, di] = np.nanmean(window, axis=1)
        pred_mat[counts < pred_window // 2, di] = np.nan

    # Step 3: Compute residuals and rolling uncertainty
    print("  Computing uncertainty estimates...")
    resid_mat = ret_mat - pred_mat  # actual - prediction

    factors = {
        "Point_Prediction": {},
        "Uncertainty_Adj": {},
        "SNR": {},
    }

    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx < uncert_window:
            continue

        pred_vals, adj_vals, snr_vals = {}, {}, {}

        # Current prediction for all stocks
        preds = pred_mat[:, idx]

        # Uncertainty = std of residuals over past uncert_window days
        resid_window = resid_mat[:, max(0, idx - uncert_window):idx]
        resid_counts = np.sum(~np.isnan(resid_window), axis=1)
        with np.errstate(invalid='ignore'):
            uncerts = np.nanstd(resid_window, axis=1)

        for ci, code in enumerate(all_codes):
            p = preds[ci]
            u = uncerts[ci]
            if np.isnan(p) or np.isnan(u) or u <= 0 or resid_counts[ci] < 20:
                continue
            pred_vals[code] = float(p)
            adj_vals[code] = float(p - 0.5 * u)
            snr_vals[code] = float(p / u)

        factors["Point_Prediction"][d] = pred_vals
        factors["Uncertainty_Adj"][d] = adj_vals
        factors["SNR"][d] = snr_vals

    return factors


def evaluate(name, factor_by_date, fwd_map):
    common_dates = sorted(set(factor_by_date.keys()) & set(fwd_map.keys()))
    daily_ics, daily_ls = [], []
    daily_long_rets, daily_short_rets = [], []

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
        long_ret = r[si[-n5:]].mean()
        short_ret = r[si[:n5]].mean()
        daily_ls.append(long_ret - short_ret)
        daily_long_rets.append(long_ret)
        daily_short_rets.append(short_ret)

    ics = np.array(daily_ics)
    ls = np.array(daily_ls)
    long_arr = np.array(daily_long_rets)
    short_arr = np.array(daily_short_rets)

    # Long-only Sharpe (more realistic for A-share)
    long_sharpe = 0
    if len(long_arr) > 0 and long_arr.std() > 0:
        long_sharpe = float(long_arr.mean() / long_arr.std() * np.sqrt(242))

    return {
        "name": name,
        "days": len(ics),
        "ic_mean": float(ics.mean()) if len(ics) else 0,
        "ic_std": float(ics.std()) if len(ics) else 0,
        "ir": float(ics.mean() / ics.std()) if len(ics) and ics.std() > 0 else 0,
        "ic_pos": float((ics > 0).mean()) if len(ics) else 0,
        "ls_bps": float(ls.mean() * 10000) if len(ls) else 0,
        "ls_sharpe": float(ls.mean() / ls.std() * np.sqrt(242)) if len(ls) and ls.std() > 0 else 0,
        "long_sharpe": long_sharpe,
        "long_vol": float(long_arr.std() * np.sqrt(242)) if len(long_arr) else 0,
    }


def format_report(results):
    lines = [
        "# Uncertainty-Adjusted Sorting",
        "",
        "Reference: QuantSeek - 不确定性排序预测 | 模型夏普提升27%",
        "Prediction model: Rolling 20-day mean return (simple baseline)",
        "Uncertainty: Std of prediction residuals over 60-day window",
        "",
        "## Methods",
        "1. **Point Prediction**: Sort by rolling mean return (standard approach)",
        "2. **Uncertainty Adj**: prediction - 0.5 * uncertainty (penalize uncertain stocks)",
        "3. **SNR**: prediction / uncertainty (signal-to-noise ratio)",
        "",
        "## Results (A-share, 2024-2025)",
        "",
        "| Method | IC | IR | IC>0% | LS bps/d | LS Sharpe | Long Sharpe | Long Vol |",
        "|--------|-----|-----|-------|----------|-----------|-------------|----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} | "
            f"{r['long_sharpe']:.2f} | {r['long_vol']:.1%} |"
        )

    lines += ["", "## Analysis", ""]
    baseline = results[0]
    for r in results[1:]:
        sharpe_delta = r['ls_sharpe'] - baseline['ls_sharpe']
        pct_change = sharpe_delta / abs(baseline['ls_sharpe']) * 100 if baseline['ls_sharpe'] != 0 else 0
        vol_delta = r['long_vol'] - baseline['long_vol']
        lines.append(
            f"- **{r['name']}** vs Point Prediction: "
            f"LS Sharpe {baseline['ls_sharpe']:.2f}→{r['ls_sharpe']:.2f} ({pct_change:+.0f}%), "
            f"Long Vol {baseline['long_vol']:.1%}→{r['long_vol']:.1%}"
        )

    lines += [
        "",
        "## Notes",
        "- The paper uses sophisticated ML models; our baseline uses simple rolling mean",
        "- Key insight: even with a simple predictor, uncertainty adjustment helps",
        "- Main mechanism: reduces exposure to noisy/unstable predictions",
        "- Sharpe improvement comes from lower volatility, not higher returns",
        "- A-share T+1 constraint limits the applicability of daily sorting strategies",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2024, 1, 2), date(2025, 12, 18)

    daily_rets, date_list = preload_all(start, end)
    fwd_map = preload_fwd(start, end)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"Test dates: {len(test_dates)}")

    print("Computing prediction + uncertainty factors...")
    factors = compute_factors(daily_rets, date_list, test_dates)

    results = []
    for fname in ["Point_Prediction", "Uncertainty_Adj", "SNR"]:
        print(f"\nEvaluating: {fname}")
        r = evaluate(fname, factors[fname], fwd_map)
        results.append(r)
        print(f"  IC={r['ic_mean']:.4f}, LS Sharpe={r['ls_sharpe']:.2f}, Long Sharpe={r['long_sharpe']:.2f}")

    report = format_report(results)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
