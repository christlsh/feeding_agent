"""
Factor Neutralization: Industry + Size

Based on: QuantSeek - 因子魔法：行业市值中性化
Core idea: Regress out Barra industry dummies + SIZE factor from raw factors.
The residual is the "pure alpha" component. Sometimes neutralization can
transform a useless factor into a useful one ("magic" effect).

Factors tested:
  1. Momentum_20d (raw vs neutralized)
  2. Reversal_5d (raw vs neutralized)
  3. Volatility_20d (raw vs neutralized)
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from data.data_loader import load_barra_bret, load_barra_loadings, available_dates
import config


STYLE_FACTORS = ["SIZE", "BETA", "MOMENTUM", "RESVOL", "SIZENL",
                 "BTOP", "LIQUIDTY", "EARNYILD", "GROWTH", "LEVERAGE"]
INDUSTRY_COLS = ["CM", "DQSB", "DZ", "FDC", "FYJR", "FZFZ", "GFJG", "GT",
                 "GYSY", "HB", "HG", "JSJ", "JTYS", "JXSB", "JYDQ", "JZCL",
                 "JZZS", "MRHL", "MT", "NLMY", "QC", "QGZZ", "SPYL", "SYMY",
                 "SYSH", "TX", "XXFW", "YH", "YSJS", "YYSW", "ZH"]


def preload_all(start, end, lookback=25):
    bret_dir = os.path.join(config.BARRA_DIR, "bret")
    all_dates = available_dates(bret_dir)
    start_idx = 0
    for i, d in enumerate(all_dates):
        if d >= start:
            start_idx = max(0, i - lookback)
            break
    load_dates = [d for d in all_dates[start_idx:] if d <= end]
    print(f"Preloading {len(load_dates)} dates of returns...")

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


def compute_raw_factors(daily_rets, date_list, test_dates, window=20):
    """Compute momentum, reversal, volatility from return series."""
    factors = {"Momentum_20d": {}, "Reversal_5d": {}, "Volatility_20d": {}}
    date_idx = {d: i for i, d in enumerate(date_list)}

    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx < window:
            continue

        lb20 = date_list[idx - 20:idx]
        lb5 = date_list[idx - 5:idx]
        mom, rev, vol = {}, {}, {}

        for code, rets in daily_rets.items():
            vals20 = [rets[ld] for ld in lb20 if ld in rets]
            vals5 = [rets[ld] for ld in lb5 if ld in rets]

            if len(vals20) >= 10:
                cum = 1.0
                for v in vals20:
                    cum *= (1 + v)
                mom[code] = cum - 1
                vol[code] = np.std(vals20)

            if len(vals5) >= 3:
                cum = 1.0
                for v in vals5:
                    cum *= (1 + v)
                rev[code] = -(cum - 1)  # negative = reversal

        factors["Momentum_20d"][d] = mom
        factors["Reversal_5d"][d] = rev
        factors["Volatility_20d"][d] = vol

    return factors


def neutralize_factor(factor_vals, loadings_df, mode="industry_size"):
    """
    Cross-sectional OLS neutralization.
    Regress factor values against industry dummies + SIZE, return residuals.
    mode: 'industry_size' = ind dummies + SIZE
          'full_style' = ind dummies + all 10 style factors
    """
    codes = list(factor_vals.keys())
    if len(codes) < 100:
        return factor_vals

    # Build loadings matrix for these codes
    load_map = {}
    for row in loadings_df.iter_rows(named=True):
        load_map[row["code"]] = row

    y = []
    X_rows = []
    valid_codes = []

    for code in codes:
        if code not in load_map:
            continue
        row = load_map[code]
        fval = factor_vals[code]
        if np.isnan(fval):
            continue

        if mode == "industry_size":
            x = [row.get(c, 0) for c in INDUSTRY_COLS] + [row.get("SIZE", 0)]
        else:
            x = [row.get(c, 0) for c in INDUSTRY_COLS] + [row.get(c, 0) for c in STYLE_FACTORS]

        if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in x):
            continue

        y.append(fval)
        X_rows.append(x)
        valid_codes.append(code)

    if len(valid_codes) < 100:
        return factor_vals

    Y = np.array(y)
    X = np.array(X_rows)
    # Add intercept
    X = np.column_stack([np.ones(len(X)), X])

    # OLS: beta = (X'X)^-1 X'Y, residual = Y - X*beta
    try:
        beta = np.linalg.lstsq(X, Y, rcond=None)[0]
        residuals = Y - X @ beta
    except np.linalg.LinAlgError:
        return factor_vals

    result = {}
    for i, code in enumerate(valid_codes):
        result[code] = float(residuals[i])
    return result


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


def format_report(results_raw, results_neut):
    lines = [
        "# Factor Neutralization: Industry + Size",
        "",
        "Reference: QuantSeek - 因子魔法：行业市值中性化",
        "Method: Cross-sectional OLS regression against Barra industry dummies + SIZE",
        "Residual = neutralized (pure alpha) factor value",
        "",
        "## Results (A-share, 2024-2025)",
        "",
        "### Raw Factors",
        "",
        "| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|---------|-----|-------|----------|-----------|",
    ]
    for r in results_raw:
        lines.append(
            f"| {r['name']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )
    lines += [
        "",
        "### After Industry + Size Neutralization",
        "",
        "| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|---------|-----|-------|----------|-----------|",
    ]
    for r in results_neut:
        lines.append(
            f"| {r['name']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )

    lines += [
        "",
        "### Comparison (Delta)",
        "",
        "| Factor | IC Delta | IR Delta | Sharpe Delta |",
        "|--------|----------|----------|--------------|",
    ]
    for raw, neut in zip(results_raw, results_neut):
        base_name = raw['name'].replace("_raw", "")
        lines.append(
            f"| {base_name} | {neut['ic_mean']-raw['ic_mean']:+.4f} | "
            f"{neut['ir']-raw['ir']:+.2f} | {neut['ls_sharpe']-raw['ls_sharpe']:+.2f} |"
        )

    lines += [
        "",
        "## Analysis",
        "",
    ]
    for raw, neut in zip(results_raw, results_neut):
        base = raw['name'].replace("_raw", "")
        ic_delta = neut['ic_mean'] - raw['ic_mean']
        sharpe_delta = neut['ls_sharpe'] - raw['ls_sharpe']
        effect = "improved" if sharpe_delta > 0.05 else ("degraded" if sharpe_delta < -0.05 else "similar")
        lines.append(f"- **{base}**: Neutralization {effect} "
                     f"(IC {raw['ic_mean']:.4f}→{neut['ic_mean']:.4f}, "
                     f"Sharpe {raw['ls_sharpe']:.2f}→{neut['ls_sharpe']:.2f})")

    lines += [
        "",
        "## Notes",
        "- Neutralization strips out industry/size beta, leaving pure stock selection signal",
        "- Factors driven purely by industry/size bets will lose power after neutralization",
        "- Factors with genuine stock-level alpha will retain or improve",
        "- 'Magic effect': sometimes noise from industry exposure masks underlying signal",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2024, 1, 2), date(2025, 12, 18)

    daily_rets, date_list = preload_all(start, end)
    fwd_map = preload_fwd(start, end)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"Test dates: {len(test_dates)}")

    print("Computing raw factors...")
    raw_factors = compute_raw_factors(daily_rets, date_list, test_dates)

    # Preload Barra loadings for neutralization
    print("Loading Barra loadings for neutralization...")
    loadings_cache = {}
    load_dir = os.path.join(config.BARRA_DIR, "loadings")
    for d in test_dates:
        path = os.path.join(load_dir, f"{d}.parquet")
        if os.path.exists(path):
            loadings_cache[d] = pl.read_parquet(path)

    # Neutralize each factor
    print("Neutralizing factors...")
    neut_factors = {}
    for fname in ["Momentum_20d", "Reversal_5d", "Volatility_20d"]:
        neut_factors[fname] = {}
        for d in test_dates:
            if d in raw_factors[fname] and d in loadings_cache:
                neut_factors[fname][d] = neutralize_factor(
                    raw_factors[fname][d], loadings_cache[d], mode="industry_size"
                )

    # Evaluate
    results_raw, results_neut = [], []
    for fname in ["Momentum_20d", "Reversal_5d", "Volatility_20d"]:
        print(f"\nEvaluating: {fname}")
        r_raw = evaluate(f"{fname}_raw", raw_factors[fname], fwd_map)
        r_neut = evaluate(f"{fname}_neut", neut_factors[fname], fwd_map)
        results_raw.append(r_raw)
        results_neut.append(r_neut)
        print(f"  Raw:  IC={r_raw['ic_mean']:.4f}, Sharpe={r_raw['ls_sharpe']:.2f}")
        print(f"  Neut: IC={r_neut['ic_mean']:.4f}, Sharpe={r_neut['ls_sharpe']:.2f}")

    report = format_report(results_raw, results_neut)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
