"""
Baseline Alpha Factor Testing

Based on: 北京大学 × 正仁量化 | GNN + LLM Alpha Factor Mining
These are traditional baseline factors used as benchmarks in the paper.
GPU not available, so we test the classic factors that GNN aims to beat.

Factors:
  1. Momentum_20d: 20-day return momentum
  2. Reversal_5d: 5-day return reversal
  3. Volatility_20d: low-volatility anomaly
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


def preload_returns(start: date, end: date, lookback: int = 25):
    """Preload all daily returns into a dict for fast access."""
    bret_dir = os.path.join(config.BARRA_DIR, "bret")
    all_dates = available_dates(bret_dir)

    # Find start with lookback buffer
    test_start_idx = 0
    for i, d in enumerate(all_dates):
        if d >= start:
            test_start_idx = max(0, i - lookback)
            break

    load_dates = [d for d in all_dates[test_start_idx:] if d <= end]
    print(f"Preloading returns for {len(load_dates)} dates...")

    # code -> date -> ret
    daily_rets = {}
    date_list = []
    for d in load_dates:
        bret = load_barra_bret(d)
        if bret is None:
            continue
        date_list.append(d)
        for row in bret.iter_rows(named=True):
            code = row["code"]
            ret = row.get("ret")
            if ret is not None and not np.isnan(ret):
                daily_rets.setdefault(code, {})[d] = ret

    print(f"Loaded {len(daily_rets)} stocks, {len(date_list)} dates")
    return daily_rets, sorted(date_list)


def preload_fwd_returns(start: date, end: date):
    """Preload forward returns for evaluation."""
    fwd_dir = config.FWD_RET_DIR
    all_dates = available_dates(fwd_dir)
    load_dates = [d for d in all_dates if start <= d <= end]
    print(f"Preloading forward returns for {len(load_dates)} dates...")

    # date -> code -> ret_T1d
    fwd_map = {}
    for d in load_dates:
        fwd = load_forward_returns(d)
        if fwd is None:
            continue
        # Use first bar of day for daily return
        if "time" in fwd.columns:
            first_time = fwd["time"].min()
            fwd = fwd.filter(pl.col("time") == first_time)
        code_col = "code"
        ret_col = "ret_T1d"
        if ret_col not in fwd.columns:
            continue
        day_map = {}
        for row in fwd.select([code_col, ret_col]).iter_rows(named=True):
            ret = row[ret_col]
            if ret is not None and not np.isnan(ret):
                day_map[row[code_col]] = ret
        fwd_map[d] = day_map

    print(f"Loaded forward returns for {len(fwd_map)} dates")
    return fwd_map


def compute_factor_series(daily_rets: dict, date_list: list[date],
                          test_dates: list[date]):
    """Compute all factors for all test dates from preloaded data."""
    factors = {
        "Momentum_20d": {},
        "Reversal_5d": {},
        "Volatility_20d": {},
    }

    date_idx = {d: i for i, d in enumerate(date_list)}

    for d in test_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]

        # Momentum 20d
        if idx >= 20:
            lookback = date_list[idx - 20:idx]
            mom = {}
            for code, rets in daily_rets.items():
                cum = sum(rets.get(ld, 0.0) for ld in lookback if ld in rets)
                count = sum(1 for ld in lookback if ld in rets)
                if count >= 10:
                    mom[code] = cum
            factors["Momentum_20d"][d] = mom

        # Reversal 5d
        if idx >= 5:
            lookback = date_list[idx - 5:idx]
            rev = {}
            for code, rets in daily_rets.items():
                cum = sum(rets.get(ld, 0.0) for ld in lookback if ld in rets)
                count = sum(1 for ld in lookback if ld in rets)
                if count >= 3:
                    rev[code] = -cum  # reversal = negative momentum
            factors["Reversal_5d"][d] = rev

        # Volatility 20d (negative: low-vol premium)
        if idx >= 20:
            lookback = date_list[idx - 20:idx]
            vol = {}
            for code, rets in daily_rets.items():
                ret_vals = [rets[ld] for ld in lookback if ld in rets]
                if len(ret_vals) >= 10:
                    vol[code] = -np.std(ret_vals)  # negative vol
            factors["Volatility_20d"][d] = vol

    return factors


def evaluate_factor(name: str, factor_by_date: dict, fwd_map: dict):
    """Compute IC series and quintile returns for a factor."""
    daily_ics = []
    daily_ls = []  # long-short returns
    stock_counts = []

    common_dates = sorted(set(factor_by_date.keys()) & set(fwd_map.keys()))

    for d in common_dates:
        fvals = factor_by_date[d]
        fwd = fwd_map[d]

        # Match stocks
        common_codes = set(fvals.keys()) & set(fwd.keys())
        if len(common_codes) < 50:
            continue

        codes = sorted(common_codes)
        f_arr = np.array([fvals[c] for c in codes])
        r_arr = np.array([fwd[c] for c in codes])

        # Remove NaN
        valid = ~(np.isnan(f_arr) | np.isnan(r_arr))
        f_arr = f_arr[valid]
        r_arr = r_arr[valid]

        if len(f_arr) < 50:
            continue

        stock_counts.append(len(f_arr))

        # Rank IC (Spearman)
        f_rank = np.argsort(np.argsort(f_arr)).astype(float)
        r_rank = np.argsort(np.argsort(r_arr)).astype(float)
        n = len(f_rank)
        ic = np.corrcoef(f_rank, r_rank)[0, 1]
        daily_ics.append(ic)

        # Long-short: top quintile - bottom quintile
        n5 = max(n // 5, 1)
        sorted_idx = np.argsort(f_arr)
        bot_ret = r_arr[sorted_idx[:n5]].mean()
        top_ret = r_arr[sorted_idx[-n5:]].mean()
        daily_ls.append(top_ret - bot_ret)

    ics = np.array(daily_ics)
    ls = np.array(daily_ls)

    return {
        "name": name,
        "days": len(ics),
        "avg_stocks": np.mean(stock_counts) if stock_counts else 0,
        "ic_mean": float(np.mean(ics)) if len(ics) > 0 else 0,
        "ic_std": float(np.std(ics)) if len(ics) > 0 else 0,
        "ir": float(np.mean(ics) / np.std(ics)) if len(ics) > 0 and np.std(ics) > 0 else 0,
        "ic_pos_pct": float(np.mean(ics > 0)) if len(ics) > 0 else 0,
        "ls_daily_bps": float(np.mean(ls) * 10000) if len(ls) > 0 else 0,
        "ls_annual": float(np.mean(ls) * 242) if len(ls) > 0 else 0,
        "ls_sharpe": float(np.mean(ls) / np.std(ls) * np.sqrt(242)) if len(ls) > 0 and np.std(ls) > 0 else 0,
    }


def format_report(results: list[dict]) -> str:
    lines = [
        "# Baseline Alpha Factor Test Report",
        "",
        "Reference: 北京大学 × 正仁量化 | GNN + LLM Alpha Factor Mining",
        "",
        "## Summary",
        "",
        "| Factor | Days | IC Mean | IR | IC>0% | LS bps/d | LS Sharpe |",
        "|--------|------|---------|-----|-------|----------|-----------|",
    ]

    for r in results:
        lines.append(
            f"| {r['name']} | {r['days']} | {r['ic_mean']:.4f} | {r['ir']:.2f} | "
            f"{r['ic_pos_pct']:.0%} | {r['ls_daily_bps']:.1f} | {r['ls_sharpe']:.2f} |"
        )

    lines += [""]

    for r in results:
        lines += [
            f"### {r['name']}",
            f"- Trading days: {r['days']}, Avg stocks: {r['avg_stocks']:.0f}",
            f"- IC: mean={r['ic_mean']:.4f}, std={r['ic_std']:.4f}, IR={r['ir']:.2f}",
            f"- IC positive rate: {r['ic_pos_pct']:.1%}",
            f"- Long-Short: {r['ls_daily_bps']:.1f} bps/day, annualized={r['ls_annual']:.2%}, Sharpe={r['ls_sharpe']:.2f}",
            "",
        ]

    lines += [
        "## Notes",
        "- Evaluation uses Barra bret daily returns and intraday forward returns",
        "- T+1 constraint: factor computed at market close, return starts next day",
        "- Full universe (~5000 A-share stocks)",
        "- The paper's GNN+LLM approach aims to significantly beat these baselines",
        "- GPU required for full model reproduction (not available)",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    start = date(2024, 1, 2)
    end = date(2025, 12, 18)

    # Preload all data
    daily_rets, date_list = preload_returns(start, end, lookback=25)
    fwd_map = preload_fwd_returns(start, end)

    # Get test dates (intersection of available dates)
    test_dates = [d for d in date_list if start <= d <= end and d in fwd_map]
    print(f"\nTest dates: {len(test_dates)}")

    # Compute factors
    print("Computing factors...")
    factors = compute_factor_series(daily_rets, date_list, test_dates)

    # Evaluate each factor
    results = []
    for name in ["Momentum_20d", "Reversal_5d", "Volatility_20d"]:
        print(f"\nEvaluating: {name}")
        r = evaluate_factor(name, factors[name], fwd_map)
        results.append(r)
        print(f"  IC={r['ic_mean']:.4f}, IR={r['ir']:.2f}, LS Sharpe={r['ls_sharpe']:.2f}")

    report = format_report(results)
    print("\n" + report)

    report_path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nSaved: {report_path}")
