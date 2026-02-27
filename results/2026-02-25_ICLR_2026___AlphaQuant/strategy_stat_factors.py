"""
Basic Statistical Factor Testing

Based on: ICLR 2026 AlphaQuant - LLM + Evolution for Feature Engineering
The paper starts with basic statistical functions (mean, variance, std, skew, kurt)
as few-shot prompts to seed the LLM. Here we test these starting-point factors.

Factors (computed from 20-day return series):
  1. Return_mean: avg daily return
  2. Return_std: return volatility (negative = low-vol premium)
  3. Return_skew: return skewness
  4. Return_kurt: return kurtosis (negative = low tail-risk)
  5. Return_autocorr: lag-1 autocorrelation
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from data.data_loader import load_barra_bret, load_forward_returns, available_dates
import config


def preload_returns(start, end, lookback=25):
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
        fwd = load_forward_returns(d)
        if fwd is None:
            continue
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


def compute_stat_factors(daily_rets, date_list, test_dates, window=20):
    """Compute basic statistical features from return window."""
    factors = {
        "Return_mean": {},
        "Return_std_neg": {},
        "Return_skew": {},
        "Return_kurt_neg": {},
        "Return_autocorr": {},
    }
    date_idx = {d: i for i, d in enumerate(date_list)}

    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx < window:
            continue

        lb = date_list[idx - window:idx]
        mean_f, std_f, skew_f, kurt_f, ac_f = {}, {}, {}, {}, {}

        for code, rets in daily_rets.items():
            vals = [rets[ld] for ld in lb if ld in rets]
            if len(vals) < window // 2:
                continue
            arr = np.array(vals)
            n = len(arr)
            mu = arr.mean()
            std = arr.std()

            mean_f[code] = mu

            # Negative std: low-vol premium
            std_f[code] = -std if std > 0 else 0

            # Skewness
            if std > 0 and n > 2:
                skew = ((arr - mu) ** 3).mean() / (std ** 3)
                skew_f[code] = -skew  # negative skew = crash risk premium
            else:
                skew_f[code] = 0

            # Kurtosis (excess)
            if std > 0 and n > 3:
                kurt = ((arr - mu) ** 4).mean() / (std ** 4) - 3
                kurt_f[code] = -kurt  # negative kurtosis = less tail risk
            else:
                kurt_f[code] = 0

            # Lag-1 autocorrelation
            if n > 2 and std > 0:
                ac = np.corrcoef(arr[:-1], arr[1:])[0, 1]
                ac_f[code] = ac if not np.isnan(ac) else 0
            else:
                ac_f[code] = 0

        factors["Return_mean"][d] = mean_f
        factors["Return_std_neg"][d] = std_f
        factors["Return_skew"][d] = skew_f
        factors["Return_kurt_neg"][d] = kurt_f
        factors["Return_autocorr"][d] = ac_f

    return factors


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

        # Rank IC
        fr, rr = np.argsort(np.argsort(f)).astype(float), np.argsort(np.argsort(r)).astype(float)
        ic = np.corrcoef(fr, rr)[0, 1]
        daily_ics.append(ic)

        # LS
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


def format_report(results):
    lines = [
        "# AlphaQuant: Basic Statistical Factor Test",
        "",
        "Reference: ICLR 2026 AlphaQuant - LLM + Evolution Feature Engineering",
        "These basic statistical features are the starting-point (few-shot prompts)",
        "that seed the LLM's search. The paper's full pipeline can significantly",
        "improve upon these baselines via evolutionary optimization.",
        "",
        "## Results (A-share, 20-day window, 2024-2025)",
        "",
        "| Factor | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|---------|-----|-------|----------|-----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos']:.0%} | {r['ls_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )
    lines += [
        "",
        "## Analysis",
        "",
    ]
    # Sort by absolute IC
    best = sorted(results, key=lambda x: abs(x['ic_mean']), reverse=True)
    for i, r in enumerate(best):
        direction = "positive" if r['ic_mean'] > 0 else "negative"
        lines.append(f"{i+1}. **{r['name']}**: IC={r['ic_mean']:.4f} ({direction}), "
                     f"Sharpe={r['ls_sharpe']:.2f}")

    lines += [
        "",
        "## Notes",
        "- These are the simplest statistical features from return series",
        "- AlphaQuant uses LLM to generate progressively more complex features",
        "- Quality-Diversity optimization evolves towards Spearman > 0.8",
        "- GPU required for full LLM-based feature search (not available)",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2024, 1, 2), date(2025, 12, 18)

    daily_rets, date_list = preload_returns(start, end)
    fwd_map = preload_fwd(start, end)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"Test dates: {len(test_dates)}")

    print("Computing statistical factors...")
    factors = compute_stat_factors(daily_rets, date_list, test_dates)

    results = []
    for name in ["Return_mean", "Return_std_neg", "Return_skew",
                  "Return_kurt_neg", "Return_autocorr"]:
        print(f"\nEvaluating: {name}")
        r = evaluate(name, factors[name], fwd_map)
        results.append(r)
        print(f"  IC={r['ic_mean']:.4f}, IR={r['ir']:.2f}, LS Sharpe={r['ls_sharpe']:.2f}")

    report = format_report(results)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
