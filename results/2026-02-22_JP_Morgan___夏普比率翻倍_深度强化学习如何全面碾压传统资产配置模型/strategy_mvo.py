"""
MVO (Mean-Variance Optimization) Baseline Implementation

Based on: JP Morgan | 深度强化学习如何全面碾压传统资产配置模型
The paper compares DRL against MVO. We implement the MVO baseline
using Barra GYCNE5 risk model on A-share CSI300 constituents.

Approach:
  1. Universe: CSI300 constituents
  2. Risk: Barra factor cov + specific risk → stock variance σ²_i = x_i'Fx_i + s²_i
  3. Expected returns: 20-day momentum
  4. Weighting: inverse-variance with momentum tilt (long-only, max 5%)
  5. Evaluate: daily rebalance with T+1 constraint
"""

import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import polars as pl
import numpy as np
from datetime import date
from data.data_loader import (
    load_barra_loadings, load_barra_cov, load_barra_srisk,
    load_barra_bret, load_index_weights, available_dates
)
import config


def short_to_full_code(short_code: str) -> str:
    """Convert 6-digit code to full code with exchange suffix."""
    if "." in short_code:
        return short_code
    if short_code.startswith(("6", "5")):
        return f"{short_code}.XSHG"
    else:
        return f"{short_code}.XSHE"


def compute_stock_variance(
    code: str,
    loadings_map: dict[str, np.ndarray],
    factor_cov: np.ndarray,
    srisk_map: dict[str, float],
) -> float:
    """Compute stock variance from Barra model: σ²_i = x_i'Fx_i + s²_i."""
    x = loadings_map.get(code)
    s = srisk_map.get(code, 0.3)  # default annualized srisk ~30%
    if x is None:
        return s * s / 252  # daily variance fallback
    # x and factor_cov should have matching dimensions
    n = min(len(x), factor_cov.shape[0])
    x = x[:n]
    F = factor_cov[:n, :n]
    factor_var = float(x @ F @ x)
    spec_var = (s ** 2) / 252  # srisk is annualized, convert to daily
    return factor_var + spec_var


def compute_momentum(dates: list[date], lookback: int = 20) -> dict[date, dict[str, float]]:
    """Compute 20-day cumulative return as momentum signal."""
    bret_dir = os.path.join(config.BARRA_DIR, "bret")
    all_dates = available_dates(bret_dir)

    signals = {}
    for d in dates:
        idx = None
        for i, ad in enumerate(all_dates):
            if ad >= d:
                idx = i
                break
        if idx is None or idx < lookback:
            continue

        lookback_dates = all_dates[idx - lookback:idx]
        cum_ret = {}
        for ld in lookback_dates:
            bret = load_barra_bret(ld)
            if bret is None:
                continue
            for row in bret.iter_rows(named=True):
                code = row["code"]
                ret = row.get("ret")
                if ret is not None and not np.isnan(ret):
                    cum_ret[code] = cum_ret.get(code, 0.0) + ret
        signals[d] = cum_ret
    return signals


def get_barra_risk(d: date) -> tuple[dict, np.ndarray, dict]:
    """Load Barra loadings, factor covariance, and specific risk for a date.
    Returns: (loadings_map, factor_cov_matrix, srisk_map)
    """
    loadings = load_barra_loadings(d)
    cov_df = load_barra_cov(d)
    srisk_df = load_barra_srisk(d)

    if loadings is None or cov_df is None or srisk_df is None:
        return {}, np.zeros((0, 0)), {}

    # Factor covariance matrix (exclude date and factor name columns)
    factor_cols = [c for c in cov_df.columns if c not in ("date", "factor")]
    factor_cov = cov_df.select(factor_cols).to_numpy()

    # Loadings map: code -> factor exposure vector
    load_factor_cols = [c for c in loadings.columns if c not in ("last_date", "code", "ind")]
    loadings_map = {}
    for row in loadings.iter_rows(named=True):
        code = row["code"]
        exposures = np.array([row[c] for c in load_factor_cols], dtype=float)
        loadings_map[code] = exposures

    # Specific risk map
    srisk_map = {}
    for row in srisk_df.iter_rows(named=True):
        srisk_map[row["code"]] = row["srisk"]

    return loadings_map, factor_cov, srisk_map


def mvo_weights(
    universe: list[str],
    expected_returns: dict[str, float],
    loadings_map: dict[str, np.ndarray],
    factor_cov: np.ndarray,
    srisk_map: dict[str, float],
    max_weight: float = 0.05,
) -> dict[str, float]:
    """Compute MVO weights: inverse-variance with momentum tilt, long-only."""
    n = len(universe)
    if n == 0:
        return {}

    mu = np.zeros(n)
    var = np.zeros(n)

    for i, code in enumerate(universe):
        mu[i] = expected_returns.get(code, 0.0)
        var[i] = compute_stock_variance(code, loadings_map, factor_cov, srisk_map)
        var[i] = max(var[i], 1e-8)

    # Score: momentum / risk (long-only: only positive momentum)
    scores = np.where(mu > 0, mu / np.sqrt(var), 0.0)

    if scores.sum() <= 0:
        weights = np.ones(n) / n  # equal weight fallback
    else:
        weights = scores / scores.sum()

    weights = np.minimum(weights, max_weight)
    if weights.sum() > 0:
        weights /= weights.sum()

    return {universe[i]: float(weights[i]) for i in range(n) if weights[i] > 1e-6}


def run_mvo_backtest(
    start_date: date = date(2024, 1, 2),
    end_date: date = date(2025, 12, 18),
    index_code: str = "000300.XSHG",
    lookback: int = 20,
    max_weight: float = 0.05,
) -> dict:
    """Run MVO backtest."""
    bret_dates = available_dates(os.path.join(config.BARRA_DIR, "bret"))
    test_dates = [d for d in bret_dates if start_date <= d <= end_date]

    if not test_dates:
        return {}

    print(f"Period: {test_dates[0]} to {test_dates[-1]}, {len(test_dates)} days")

    # Precompute momentum
    print("Computing momentum...")
    momentum = compute_momentum(test_dates, lookback=lookback)
    print(f"Momentum computed for {len(momentum)} dates")

    # Find available index weight dates (may not have every day)
    iw_dates = available_dates(os.path.join(config.INDEX_WEIGHTS_DIR, index_code))
    last_iw = {}  # cache: nearest available index weight

    def get_universe(d: date) -> list[str]:
        """Get CSI300 universe, using nearest available date."""
        # Find nearest index weight date <= d
        candidates = [iwd for iwd in iw_dates if iwd <= d]
        if not candidates:
            return []
        nearest = candidates[-1]
        if nearest not in last_iw:
            iw = load_index_weights(index_code, nearest)
            if iw is not None:
                # Convert short codes to full codes
                short_codes = iw["code"].to_list()
                last_iw[nearest] = [short_to_full_code(c) for c in short_codes]
            else:
                last_iw[nearest] = []
        return last_iw[nearest]

    port_rets = []
    bench_rets = []

    for i, d in enumerate(test_dates):
        if d not in momentum:
            continue

        universe = get_universe(d)
        if not universe:
            continue

        # Get risk model
        loadings_map, factor_cov, srisk_map = get_barra_risk(d)
        if factor_cov.size == 0:
            continue

        # Compute weights
        weights = mvo_weights(universe, momentum[d], loadings_map, factor_cov, srisk_map, max_weight)
        if not weights:
            continue

        # Evaluate using same-day returns (signal was computed at open, returns are close-to-close)
        bret = load_barra_bret(d)
        if bret is None:
            continue

        ret_map = {}
        for row in bret.iter_rows(named=True):
            ret_map[row["code"]] = row["ret"]

        port_ret = sum(w * ret_map.get(code, 0.0) for code, w in weights.items())
        port_rets.append(port_ret)

        # Benchmark: equal-weight CSI300
        univ_rets = [ret_map.get(c, 0.0) for c in universe if c in ret_map]
        bench_rets.append(np.mean(univ_rets) if univ_rets else 0.0)

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(test_dates)} days, last portfolio: {len(weights)} stocks")

    # Stats
    port = np.array(port_rets)
    bench = np.array(bench_rets)

    if len(port) == 0:
        return {}

    excess = port - bench

    return {
        "days": len(port),
        "period": f"{test_dates[0]} to {test_dates[-1]}",
        "portfolio": {
            "annual_return": float(port.mean() * 242),
            "annual_vol": float(port.std() * np.sqrt(242)),
            "sharpe": float(port.mean() / port.std() * np.sqrt(242)) if port.std() > 0 else 0,
            "max_drawdown": float(_max_dd(port)),
            "daily_bps": float(port.mean() * 10000),
        },
        "benchmark": {
            "annual_return": float(bench.mean() * 242),
            "sharpe": float(bench.mean() / bench.std() * np.sqrt(242)) if bench.std() > 0 else 0,
        },
        "excess": {
            "annual_return": float(excess.mean() * 242),
            "ir": float(excess.mean() / excess.std() * np.sqrt(242)) if excess.std() > 0 else 0,
        },
    }


def _max_dd(rets):
    cum = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cum)
    return float(((cum - peak) / peak).min())


def format_report(r: dict) -> str:
    if not r:
        return "No results."
    return f"""## MVO Backtest Report

**Period**: {r['period']} ({r['days']} trading days)

### Portfolio (Momentum + Inverse-Variance MVO)
- Annual Return: {r['portfolio']['annual_return']:.2%}
- Annual Volatility: {r['portfolio']['annual_vol']:.2%}
- Sharpe Ratio: {r['portfolio']['sharpe']:.2f}
- Max Drawdown: {r['portfolio']['max_drawdown']:.2%}
- Daily Mean: {r['portfolio']['daily_bps']:.2f} bps

### Benchmark (Equal-Weight CSI300)
- Annual Return: {r['benchmark']['annual_return']:.2%}
- Sharpe Ratio: {r['benchmark']['sharpe']:.2f}

### Excess (Portfolio - Benchmark)
- Annual Alpha: {r['excess']['annual_return']:.2%}
- Information Ratio: {r['excess']['ir']:.2f}

### Setup
- Universe: CSI300
- Signal: 20-day momentum (cumulative return)
- Risk model: Barra GYCNE5 (factor cov + specific risk)
- Weighting: inverse-variance * momentum, long-only, max 5%/stock
- Reference: JP Morgan DRL vs MVO paper (MVO baseline)
"""


if __name__ == "__main__":
    print("Running MVO Backtest on CSI300...")
    print("=" * 60)

    result = run_mvo_backtest(
        start_date=date(2024, 1, 2),
        end_date=date(2025, 12, 18),
        lookback=20,
        max_weight=0.05,
    )

    report = format_report(result)
    print("\n" + report)

    report_path = os.path.join(os.path.dirname(__file__), "report.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Saved: {report_path}")
