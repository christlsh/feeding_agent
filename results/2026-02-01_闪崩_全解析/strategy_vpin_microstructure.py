"""
Flash Crash Prediction: VPIN + Orderbook Microstructure Factors

Based on: QuantSeek - "闪崩"全解析
Core idea: Use L2 orderbook data to construct:
  1. VPIN-like flow toxicity indicator
  2. Orderbook imbalance features
  3. Test as cross-sectional factors predicting next-day returns

Factors (computed from L2 orderbook snapshots, daily aggregation):
  1. OB_Imbalance: (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)
  2. Spread: (best_ask - best_bid) / mid_price
  3. Depth_Ratio: bid_depth / ask_depth (levels 1-5)
  4. VPIN_Proxy: abs(buy_vol - sell_vol) / total_vol (simplified VPIN)
  5. Price_Impact: |return| / sqrt(volume) (Kyle's lambda proxy)

Note: Full VPIN requires tick-level volume bucketing. We use a simplified
proxy from snapshot-level data.
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from data.data_loader import available_dates
import config


def compute_daily_ob_factors(trade_date):
    """Compute orderbook factors from L2 snapshots for one day.
    Uses lazy scan to minimize memory usage."""
    path = os.path.join(config.L2_OB_DIR, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None

    try:
        # Lazy scan with only needed columns
        cols = ["symbol", "current", "volume", "money",
                "a1_p", "a1_v", "a2_v", "a3_v", "a4_v", "a5_v",
                "b1_p", "b1_v", "b2_v", "b3_v", "b4_v", "b5_v",
                "total_bid_volume", "total_ask_volume"]
        ob = (
            pl.scan_parquet(path)
            .select(cols)
            .filter(
                (pl.col("current") > 0) &
                (pl.col("a1_p") > 0) &
                (pl.col("b1_p") > 0)
            )
            .with_columns([
                ((pl.col("a1_p") - pl.col("b1_p")) /
                 ((pl.col("a1_p") + pl.col("b1_p")) / 2)).alias("spread"),
                ((pl.col("total_bid_volume") - pl.col("total_ask_volume")) /
                 (pl.col("total_bid_volume") + pl.col("total_ask_volume") + 1)).alias("imbalance"),
                ((pl.col("b1_v") + pl.col("b2_v") + pl.col("b3_v") + pl.col("b4_v") + pl.col("b5_v")) /
                 (pl.col("a1_v") + pl.col("a2_v") + pl.col("a3_v") + pl.col("a4_v") + pl.col("a5_v") + 1)).alias("depth_ratio"),
            ])
            .group_by("symbol")
            .agg([
                pl.col("spread").mean().alias("avg_spread"),
                pl.col("imbalance").mean().alias("avg_imbalance"),
                pl.col("depth_ratio").mean().alias("avg_depth_ratio"),
                pl.col("imbalance").std().alias("imbalance_vol"),
                pl.col("volume").max().alias("total_vol"),
                pl.col("current").last().alias("close_p"),
                pl.col("current").first().alias("open_p"),
            ])
            .collect()
        )
    except Exception as e:
        return None

    if len(ob) < 100:
        return None

    # Compute price impact
    daily = ob.with_columns([
        (((pl.col("close_p") / pl.col("open_p") - 1).abs()) /
         (pl.col("total_vol").sqrt() + 1) * 1e6).alias("price_impact"),
    ])

    # Convert to factor dict
    factors = {
        "OB_Imbalance": {},
        "Spread_neg": {},
        "Depth_Ratio": {},
        "VPIN_Proxy_neg": {},
        "Price_Impact_neg": {},
    }

    for row in daily.iter_rows(named=True):
        sym = row["symbol"]
        if len(sym) == 6:
            code = f"{sym}.XSHE" if sym.startswith(("0", "3")) else f"{sym}.XSHG"
        else:
            code = sym

        imb = row["avg_imbalance"]
        if imb is not None and not np.isnan(imb):
            factors["OB_Imbalance"][code] = float(imb)

        spr = row["avg_spread"]
        if spr is not None and not np.isnan(spr):
            factors["Spread_neg"][code] = -float(spr)  # negative: low spread = more liquid

        dr = row["avg_depth_ratio"]
        if dr is not None and not np.isnan(dr):
            factors["Depth_Ratio"][code] = float(dr)

        iv = row["imbalance_vol"]
        if iv is not None and not np.isnan(iv):
            factors["VPIN_Proxy_neg"][code] = -float(iv)  # negative: low toxicity

        pi = row["price_impact"]
        if pi is not None and not np.isnan(pi):
            factors["Price_Impact_neg"][code] = -float(pi)  # negative: low impact = liquid

    return factors


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


def format_report(results):
    lines = [
        "# Flash Crash Prediction: VPIN + Orderbook Microstructure Factors",
        "",
        "Reference: QuantSeek - \"闪崩\"全解析 (VPIN + ML crash prediction)",
        "Data: A-share L2 orderbook (10-level bid/ask) aggregated to daily cross-section",
        "",
        "## Factors",
        "1. **OB_Imbalance**: (bid_vol - ask_vol) / total_vol (buying pressure)",
        "2. **Spread_neg**: -avg(bid-ask spread) (liquidity, negative = low spread = liquid)",
        "3. **Depth_Ratio**: bid_depth / ask_depth (supply-demand at orderbook level)",
        "4. **VPIN_Proxy_neg**: -std(imbalance) (flow toxicity proxy, negative = low toxicity)",
        "5. **Price_Impact_neg**: -|return|/sqrt(vol) (Kyle's lambda, negative = low impact)",
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
    best = sorted(results, key=lambda x: abs(x['ic_mean']), reverse=True)
    for i, r in enumerate(best):
        direction = "positive" if r['ic_mean'] > 0 else "negative"
        lines.append(f"{i+1}. **{r['name']}**: IC={r['ic_mean']:.4f} ({direction}), Sharpe={r['ls_sharpe']:.2f}")

    lines += [
        "",
        "## Notes",
        "- Full VPIN requires tick-level volume bucketing; we use snapshot-based proxy",
        "- Original paper achieves AUC 0.9+ for 15s/90s flash crash prediction (intraday)",
        "- Our daily aggregation tests whether microstructure signals predict next-day returns",
        "- A-share limit-up/down mechanism provides natural 'flash crash' boundaries",
        "- Orderbook imbalance is a well-known short-term alpha source in literature",
        "- These factors are most useful at intraday frequency, less so at daily",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    start, end = date(2025, 1, 2), date(2025, 12, 18)  # 1 year (L2 data is large)

    fwd_map = preload_fwd(start, end)

    # Get available L2 dates
    l2_dir = config.L2_OB_DIR
    l2_dates = [d for d in available_dates(l2_dir) if start <= d <= end]
    test_dates = [d for d in l2_dates if d in fwd_map]
    print(f"Test dates: {len(test_dates)} (L2 orderbook days with fwd returns)")

    # Compute factors day by day (L2 files are large)
    all_factors = {
        "OB_Imbalance": {},
        "Spread_neg": {},
        "Depth_Ratio": {},
        "VPIN_Proxy_neg": {},
        "Price_Impact_neg": {},
    }

    for i, d in enumerate(test_dates):
        if i % 50 == 0:
            print(f"Processing day {i+1}/{len(test_dates)}: {d}")
        day_factors = compute_daily_ob_factors(d)
        if day_factors is None:
            continue
        for fname in all_factors:
            if day_factors[fname]:
                all_factors[fname][d] = day_factors[fname]

    # Evaluate
    results = []
    for fname in ["OB_Imbalance", "Spread_neg", "Depth_Ratio",
                   "VPIN_Proxy_neg", "Price_Impact_neg"]:
        print(f"\nEvaluating: {fname}")
        r = evaluate(fname, all_factors[fname], fwd_map)
        results.append(r)
        print(f"  IC={r['ic_mean']:.4f}, IR={r['ir']:.2f}, LS Sharpe={r['ls_sharpe']:.2f}")

    report = format_report(results)
    print("\n" + report)

    path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"\nSaved: {path}")
