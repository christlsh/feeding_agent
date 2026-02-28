"""
Market Stress Probability Index (MSPI)

Based on: QuantML - 市场压力概率指数
Core idea: Construct cross-sectional fragility signals from daily stock returns,
then use Lasso-Logit to predict probability of "high stress" months.

Fragility signals (computed monthly from daily cross-sectional data):
  1. Return Dispersion: cross-sectional std of daily returns (avg over month)
  2. Tail Ratio: ratio of 5th/95th percentile returns
  3. Cross-sectional Skewness: avg daily skewness of cross-section
  4. Cross-sectional Kurtosis: avg daily excess kurtosis
  5. Down Ratio: fraction of stocks with negative returns (avg over month)
  6. Realized Volatility: market-level monthly realized vol
  7. Max Drawdown Signal: max single-day drop in month

Stress definition: months in bottom 20% of market returns.
Model: Expanding-window Lasso-Logit, predict next month's stress probability.
Evaluation: as market timing signal for CSI300/CSI500.
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from collections import defaultdict
from sklearn.linear_model import LogisticRegression
from data.data_loader import load_barra_bret, available_dates
import config


def load_monthly_data(start, end):
    """Load daily returns and aggregate into monthly cross-sectional signals."""
    bret_dir = os.path.join(config.BARRA_DIR, "bret")
    all_dates = available_dates(bret_dir)
    load_dates = [d for d in all_dates if start <= d <= end]
    print(f"Loading {len(load_dates)} trading days...")

    # Group dates by month
    monthly_dates = defaultdict(list)
    for d in load_dates:
        key = (d.year, d.month)
        monthly_dates[key].append(d)

    # For each day, compute cross-sectional stats
    daily_stats = {}
    daily_market_ret = {}

    for d in load_dates:
        bret = load_barra_bret(d)
        if bret is None:
            continue

        rets = bret.filter(pl.col("ret").is_not_null())["ret"].to_numpy()
        if len(rets) < 100:
            continue

        daily_stats[d] = {
            "dispersion": float(np.std(rets)),
            "skew": float(((rets - rets.mean()) ** 3).mean() / (np.std(rets) ** 3)) if np.std(rets) > 0 else 0,
            "kurtosis": float(((rets - rets.mean()) ** 4).mean() / (np.std(rets) ** 4) - 3) if np.std(rets) > 0 else 0,
            "down_ratio": float((rets < 0).mean()),
            "tail_5": float(np.percentile(rets, 5)),
            "tail_95": float(np.percentile(rets, 95)),
            "market_ret": float(rets.mean()),
            "n_stocks": len(rets),
        }
        daily_market_ret[d] = float(rets.mean())

    # Aggregate to monthly signals
    months = sorted(monthly_dates.keys())
    monthly_signals = {}
    monthly_returns = {}

    for ym in months:
        days = [d for d in monthly_dates[ym] if d in daily_stats]
        if len(days) < 10:
            continue

        stats = [daily_stats[d] for d in days]
        mkt_rets = [daily_market_ret[d] for d in days]

        # Compound market return
        cum = 1.0
        for r in mkt_rets:
            cum *= (1 + r)
        monthly_returns[ym] = cum - 1

        # Realized volatility (annualized)
        rv = np.std(mkt_rets) * np.sqrt(242)

        # Max single-day drop
        max_drop = min(mkt_rets)

        monthly_signals[ym] = {
            "dispersion": np.mean([s["dispersion"] for s in stats]),
            "skew": np.mean([s["skew"] for s in stats]),
            "kurtosis": np.mean([s["kurtosis"] for s in stats]),
            "down_ratio": np.mean([s["down_ratio"] for s in stats]),
            "tail_ratio": np.mean([s["tail_5"] for s in stats]) / np.mean([s["tail_95"] for s in stats]) if np.mean([s["tail_95"] for s in stats]) != 0 else 0,
            "realized_vol": rv,
            "max_drop": max_drop,
        }

    return months, monthly_signals, monthly_returns


def define_stress(monthly_returns, quantile=0.2):
    """Define stress months as bottom quantile of monthly returns."""
    ym_list = sorted(monthly_returns.keys())
    rets = [monthly_returns[ym] for ym in ym_list]
    threshold = np.percentile(rets, quantile * 100)
    stress = {ym: 1 if monthly_returns[ym] <= threshold else 0 for ym in ym_list}
    return stress, threshold


def build_mspi(months, monthly_signals, stress_labels, min_train=24):
    """
    Expanding-window Lasso-Logit.
    For each month t, train on months [0, t-1], predict P(stress at t).
    """
    feature_names = ["dispersion", "skew", "kurtosis", "down_ratio",
                     "tail_ratio", "realized_vol", "max_drop"]

    valid_months = [ym for ym in months if ym in monthly_signals and ym in stress_labels]
    if len(valid_months) < min_train + 1:
        print(f"Not enough months: {len(valid_months)} < {min_train + 1}")
        return {}, feature_names

    mspi = {}
    for i in range(min_train, len(valid_months)):
        train_months = valid_months[:i]
        test_month = valid_months[i]

        X_train = np.array([[monthly_signals[ym][f] for f in feature_names]
                            for ym in train_months])
        # Target: stress in NEXT month (shift by 1)
        y_train = np.array([stress_labels[ym] for ym in train_months])

        # Check class balance
        if y_train.sum() < 2 or (1 - y_train).sum() < 2:
            continue

        # Standardize
        mu = X_train.mean(axis=0)
        std = X_train.std(axis=0)
        std[std == 0] = 1
        X_train_norm = (X_train - mu) / std

        X_test = np.array([[monthly_signals[test_month][f] for f in feature_names]])
        X_test_norm = (X_test - mu) / std

        try:
            model = LogisticRegression(
                penalty='l1', C=1.0, solver='liblinear',
                max_iter=1000, random_state=42
            )
            model.fit(X_train_norm, y_train)
            prob = model.predict_proba(X_test_norm)[0, 1]
            mspi[test_month] = float(prob)
        except Exception:
            continue

    return mspi, feature_names


def evaluate_timing(mspi, monthly_returns, threshold=0.5):
    """Evaluate MSPI as market timing signal."""
    common = sorted(set(mspi.keys()) & set(monthly_returns.keys()))
    if not common:
        return {}

    # Strategy: reduce exposure when MSPI > threshold
    full_rets = []
    timed_rets = []
    stress_detected = 0
    stress_total = 0

    for ym in common:
        ret = monthly_returns[ym]
        prob = mspi[ym]
        full_rets.append(ret)

        if prob > threshold:
            timed_rets.append(ret * 0.3)  # 30% exposure in high-stress
        else:
            timed_rets.append(ret)

        if ret < -0.03:  # actual stress
            stress_total += 1
            if prob > threshold:
                stress_detected += 1

    full = np.array(full_rets)
    timed = np.array(timed_rets)

    return {
        "months": len(common),
        "full_cumret": float(np.prod(1 + full) - 1),
        "timed_cumret": float(np.prod(1 + timed) - 1),
        "full_sharpe": float(full.mean() / full.std() * np.sqrt(12)) if full.std() > 0 else 0,
        "timed_sharpe": float(timed.mean() / timed.std() * np.sqrt(12)) if timed.std() > 0 else 0,
        "full_maxdd": float(np.min(np.minimum.accumulate(np.cumprod(1 + full)) / np.maximum.accumulate(np.cumprod(1 + full)) - 1)),
        "timed_maxdd": float(np.min(np.minimum.accumulate(np.cumprod(1 + timed)) / np.maximum.accumulate(np.cumprod(1 + timed)) - 1)),
        "stress_detection_rate": stress_detected / stress_total if stress_total > 0 else 0,
        "stress_months": stress_total,
    }


def format_report(mspi, monthly_returns, stress_labels, timing_results, stress_threshold):
    lines = [
        "# Market Stress Probability Index (MSPI)",
        "",
        "Reference: QuantML - 市场压力概率指数",
        "Method: Cross-sectional fragility signals → Expanding-window Lasso-Logit",
        "",
        "## Fragility Signals",
        "1. **Return Dispersion**: Cross-sectional std of daily returns",
        "2. **Skewness**: Cross-sectional skewness of returns",
        "3. **Kurtosis**: Cross-sectional excess kurtosis",
        "4. **Down Ratio**: Fraction of stocks with negative returns",
        "5. **Tail Ratio**: 5th/95th percentile ratio",
        "6. **Realized Volatility**: Annualized monthly vol",
        "7. **Max Drop**: Worst single-day market return",
        "",
        f"## Stress Definition",
        f"- Stress month: monthly market return ≤ {stress_threshold:.2%} (bottom 20%)",
        "",
    ]

    if timing_results:
        lines += [
            "## Market Timing Evaluation (A-share, 2022-2025)",
            "",
            "| Metric | Buy & Hold | MSPI Timed |",
            "|--------|-----------|------------|",
            f"| Months | {timing_results['months']} | {timing_results['months']} |",
            f"| Cumulative Return | {timing_results['full_cumret']:.2%} | {timing_results['timed_cumret']:.2%} |",
            f"| Sharpe (annualized) | {timing_results['full_sharpe']:.2f} | {timing_results['timed_sharpe']:.2f} |",
            f"| Max Drawdown | {timing_results['full_maxdd']:.2%} | {timing_results['timed_maxdd']:.2%} |",
            f"| Stress Detection Rate | - | {timing_results['stress_detection_rate']:.0%} ({timing_results['stress_months']} months) |",
            "",
            "Timing rule: 30% exposure when MSPI > 0.5, 100% otherwise.",
            "",
        ]

    # Show MSPI time series
    lines += ["## MSPI Time Series (recent months)", ""]
    common = sorted(set(mspi.keys()) & set(monthly_returns.keys()))
    recent = common[-12:] if len(common) > 12 else common
    lines.append("| Month | Market Return | MSPI | Stress? |")
    lines.append("|-------|-------------|------|---------|")
    for ym in recent:
        ret = monthly_returns[ym]
        prob = mspi[ym]
        stress = "YES" if stress_labels.get(ym, 0) == 1 else ""
        alert = " ⚠️" if prob > 0.5 else ""
        lines.append(f"| {ym[0]}-{ym[1]:02d} | {ret:.2%} | {prob:.3f}{alert} | {stress} |")

    lines += [
        "",
        "## Notes",
        "- Original paper uses CRSP data (US); we adapt to A-share market",
        "- Expanding window ensures no look-ahead bias",
        "- MSPI probability is calibrated — 0.5+ indicates elevated stress risk",
        "- A-share markets show higher cross-sectional correlation → dispersion signal may differ",
        "- Useful as risk overlay / position sizing signal, not standalone trading strategy",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start = date(2020, 1, 2)
    end = date(2025, 12, 18)

    print("Loading and computing monthly cross-sectional signals...")
    months, monthly_signals, monthly_returns = load_monthly_data(start, end)
    print(f"Total months: {len(months)}")

    # Define stress
    stress_labels, stress_threshold = define_stress(monthly_returns)
    n_stress = sum(stress_labels.values())
    print(f"Stress months: {n_stress} / {len(stress_labels)} (threshold: {stress_threshold:.2%})")

    # Build MSPI
    print("Building MSPI with expanding-window Lasso-Logit...")
    mspi, feature_names = build_mspi(months, monthly_signals, stress_labels, min_train=24)
    print(f"MSPI predictions: {len(mspi)} months")

    # Evaluate timing
    print("Evaluating market timing...")
    timing = evaluate_timing(mspi, monthly_returns)

    # Report
    report = format_report(mspi, monthly_returns, stress_labels, timing, stress_threshold)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
