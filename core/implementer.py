"""Lightweight factor/strategy backtesting framework using polars.

Designed for A-share market with constraints:
- T+1: can only sell next day
- No shorting
- Price limits (涨跌停)
"""

import polars as pl
import numpy as np
import os
from datetime import date
from dataclasses import dataclass, field
from typing import Optional, Callable

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.data_loader import (
    load_forward_returns, load_barra_loadings, load_barra_bret,
    load_limit_status, load_sec_info, get_trade_days_between, available_dates
)
import config


@dataclass
class BacktestResult:
    factor_name: str = ""
    period: str = ""
    num_days: int = 0
    num_stocks_avg: float = 0

    # IC stats
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ir: float = 0.0           # IC / std(IC)
    ic_positive_pct: float = 0.0

    # Quintile returns (Q1=lowest factor, Q5=highest)
    quintile_returns: dict = field(default_factory=dict)
    long_short_return: float = 0.0   # Q5 - Q1 annualized
    long_short_sharpe: float = 0.0

    # Turnover
    avg_turnover: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            f"## Backtest Report: {self.factor_name}",
            "",
            f"- **Period**: {self.period}",
            f"- **Trading Days**: {self.num_days}",
            f"- **Avg Stocks/Day**: {self.num_stocks_avg:.0f}",
            "",
            "### IC Analysis",
            f"- Mean IC: {self.ic_mean:.4f}",
            f"- IC Std: {self.ic_std:.4f}",
            f"- IR (IC/Std): {self.ir:.4f}",
            f"- IC > 0 Pct: {self.ic_positive_pct:.1%}",
            "",
            "### Quintile Returns (daily avg bps)",
        ]

        for q in sorted(self.quintile_returns.keys()):
            ret = self.quintile_returns[q]
            lines.append(f"- Q{q}: {ret*10000:.2f} bps")

        lines += [
            "",
            f"### Long-Short (Q5-Q1)",
            f"- Annualized Return: {self.long_short_return:.2%}",
            f"- Sharpe Ratio: {self.long_short_sharpe:.2f}",
            f"- Avg Daily Turnover: {self.avg_turnover:.1%}",
        ]

        return "\n".join(lines)


def compute_daily_factor_ic(
    factor_df: pl.DataFrame,
    fwd_ret_df: pl.DataFrame,
    factor_col: str = "factor",
    ret_col: str = "ret_T1d",
) -> float:
    """Compute rank IC between factor and forward return for one day."""
    # Join on stock code
    factor_codes = "code" if "code" in factor_df.columns else "symbol"
    fwd_codes = "code" if "code" in fwd_ret_df.columns else "symbol"

    # Get unique factor values per stock (use last of day if intraday)
    if "datetime" in factor_df.columns:
        factor_daily = factor_df.group_by(factor_codes).agg(
            pl.col(factor_col).last()
        )
    else:
        factor_daily = factor_df.select([factor_codes, factor_col])

    # Get daily forward return (use first bar of day = open-to-open style)
    if "time" in fwd_ret_df.columns:
        fwd_daily = fwd_ret_df.filter(
            pl.col("time") == fwd_ret_df["time"].min()
        ).select([fwd_codes, ret_col])
    else:
        fwd_daily = fwd_ret_df.select([fwd_codes, ret_col])

    # Rename to common key
    factor_daily = factor_daily.rename({factor_codes: "stock"})
    fwd_daily = fwd_daily.rename({fwd_codes: "stock"})

    # Join
    merged = factor_daily.join(fwd_daily, on="stock", how="inner")
    merged = merged.drop_nulls()

    if len(merged) < 30:
        return float("nan")

    # Rank IC (Spearman)
    factor_rank = merged[factor_col].rank().to_numpy().astype(float)
    ret_rank = merged[ret_col].rank().to_numpy().astype(float)

    n = len(factor_rank)
    mean_f = factor_rank.mean()
    mean_r = ret_rank.mean()
    cov = ((factor_rank - mean_f) * (ret_rank - mean_r)).sum()
    std_f = np.sqrt(((factor_rank - mean_f) ** 2).sum())
    std_r = np.sqrt(((ret_rank - mean_r) ** 2).sum())

    if std_f == 0 or std_r == 0:
        return float("nan")

    return float(cov / (std_f * std_r))


def compute_quintile_returns(
    factor_df: pl.DataFrame,
    fwd_ret_df: pl.DataFrame,
    factor_col: str = "factor",
    ret_col: str = "ret_T1d",
    n_groups: int = 5,
) -> dict[int, float]:
    """Compute average return by factor quintile for one day."""
    factor_codes = "code" if "code" in factor_df.columns else "symbol"
    fwd_codes = "code" if "code" in fwd_ret_df.columns else "symbol"

    # Daily aggregation
    if "datetime" in factor_df.columns:
        factor_daily = factor_df.group_by(factor_codes).agg(
            pl.col(factor_col).last()
        )
    else:
        factor_daily = factor_df.select([factor_codes, factor_col])

    if "time" in fwd_ret_df.columns:
        fwd_daily = fwd_ret_df.filter(
            pl.col("time") == fwd_ret_df["time"].min()
        ).select([fwd_codes, ret_col])
    else:
        fwd_daily = fwd_ret_df.select([fwd_codes, ret_col])

    factor_daily = factor_daily.rename({factor_codes: "stock"})
    fwd_daily = fwd_daily.rename({fwd_codes: "stock"})

    merged = factor_daily.join(fwd_daily, on="stock", how="inner").drop_nulls()

    if len(merged) < n_groups * 10:
        return {}

    # Assign quintiles
    merged = merged.with_columns(
        pl.col(factor_col).rank().alias("rank")
    )
    n = len(merged)
    merged = merged.with_columns(
        ((pl.col("rank") - 1) * n_groups / n).cast(pl.Int32).clip(0, n_groups - 1).alias("quintile")
    )

    result = {}
    for q in range(n_groups):
        group = merged.filter(pl.col("quintile") == q)
        if len(group) > 0:
            result[q + 1] = group[ret_col].mean()

    return result


def run_factor_backtest(
    factor_fn: Callable[[date], Optional[pl.DataFrame]],
    factor_col: str = "factor",
    start_date: date = date(2024, 1, 2),
    end_date: date = date(2025, 12, 29),
    ret_col: str = "ret_T1d",
    factor_name: str = "unnamed_factor",
) -> BacktestResult:
    """Run a full factor backtest over a date range.

    factor_fn: callable that takes a date and returns a DataFrame with columns [code/symbol, factor]
               or None if no data for that day.
    """
    fwd_ret_dates = available_dates(config.FWD_RET_DIR)
    test_dates = [d for d in fwd_ret_dates if start_date <= d <= end_date]

    if not test_dates:
        return BacktestResult(factor_name=factor_name, period=f"{start_date} to {end_date}")

    daily_ics = []
    daily_quintiles = []
    daily_counts = []
    prev_holdings = set()
    turnovers = []

    for d in test_dates:
        factor_df = factor_fn(d)
        if factor_df is None or len(factor_df) == 0:
            continue

        fwd_df = load_forward_returns(d)
        if fwd_df is None:
            continue

        # Compute IC
        ic = compute_daily_factor_ic(factor_df, fwd_df, factor_col, ret_col)
        if not np.isnan(ic):
            daily_ics.append(ic)

        # Compute quintile returns
        qr = compute_quintile_returns(factor_df, fwd_df, factor_col, ret_col)
        if qr:
            daily_quintiles.append(qr)
            daily_counts.append(len(factor_df))

        # Compute turnover (top quintile)
        if qr:
            code_col = "code" if "code" in factor_df.columns else "symbol"
            top_q = factor_df.sort(factor_col, descending=True).head(len(factor_df) // 5)
            current_holdings = set(top_q[code_col].to_list())
            if prev_holdings:
                overlap = len(current_holdings & prev_holdings)
                total = max(len(current_holdings), 1)
                turnovers.append(1 - overlap / total)
            prev_holdings = current_holdings

    # Aggregate results
    result = BacktestResult(
        factor_name=factor_name,
        period=f"{test_dates[0]} to {test_dates[-1]}",
        num_days=len(daily_ics),
        num_stocks_avg=np.mean(daily_counts) if daily_counts else 0,
    )

    if daily_ics:
        ics = np.array(daily_ics)
        result.ic_mean = float(np.nanmean(ics))
        result.ic_std = float(np.nanstd(ics))
        result.ir = result.ic_mean / result.ic_std if result.ic_std > 0 else 0
        result.ic_positive_pct = float(np.mean(ics > 0))

    if daily_quintiles:
        # Average quintile returns
        all_qs = set()
        for qr in daily_quintiles:
            all_qs.update(qr.keys())
        for q in sorted(all_qs):
            vals = [qr[q] for qr in daily_quintiles if q in qr]
            result.quintile_returns[q] = float(np.nanmean(vals))

        if 1 in result.quintile_returns and 5 in result.quintile_returns:
            ls_daily = result.quintile_returns[5] - result.quintile_returns[1]
            result.long_short_return = ls_daily * 242  # annualize
            ls_daily_series = np.array([
                (qr.get(5, 0) - qr.get(1, 0)) for qr in daily_quintiles
            ])
            ls_std = np.nanstd(ls_daily_series) * np.sqrt(242)
            result.long_short_sharpe = result.long_short_return / ls_std if ls_std > 0 else 0

    if turnovers:
        result.avg_turnover = float(np.mean(turnovers))

    return result
