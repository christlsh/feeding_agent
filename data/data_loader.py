"""Unified data loading interface using polars."""

import polars as pl
import numpy as np
import os
from datetime import date, datetime
from typing import Optional
import config


def get_trade_days() -> list[date]:
    """Load all trading days."""
    days = np.load(config.TRADE_DAYS_PATH, allow_pickle=True)
    return [d if isinstance(d, date) else d.date() for d in days]


def get_trade_days_between(start: date, end: date) -> list[date]:
    """Get trading days in a date range."""
    all_days = get_trade_days()
    return [d for d in all_days if start <= d <= end]


def load_l2_orderbook(trade_date: date) -> Optional[pl.DataFrame]:
    """Load L2 orderbook data for a trading day."""
    path = os.path.join(config.L2_OB_DIR, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_forward_returns(trade_date: date) -> Optional[pl.DataFrame]:
    """Load forward return data for a trading day.
    Columns: code, datetime, date, time, ret, ret_T1min..ret_T5d
    """
    path = os.path.join(config.FWD_RET_DIR, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_barra_loadings(trade_date: date) -> Optional[pl.DataFrame]:
    """Load Barra factor loadings for a trading day."""
    path = os.path.join(config.BARRA_DIR, "loadings", f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_barra_factor_returns(trade_date: date) -> Optional[pl.DataFrame]:
    """Load Barra factor returns for a trading day."""
    path = os.path.join(config.BARRA_DIR, "factor_rets", f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_barra_cov(trade_date: date) -> Optional[pl.DataFrame]:
    """Load Barra factor covariance matrix for a trading day."""
    path = os.path.join(config.BARRA_DIR, "cov", f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_barra_srisk(trade_date: date) -> Optional[pl.DataFrame]:
    """Load Barra specific risk for a trading day."""
    path = os.path.join(config.BARRA_DIR, "srisk", f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_barra_bret(trade_date: date) -> Optional[pl.DataFrame]:
    """Load Barra benchmark returns (ret vs bret) for a trading day."""
    path = os.path.join(config.BARRA_DIR, "bret", f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_index_weights(index_code: str, trade_date: date) -> Optional[pl.DataFrame]:
    """Load index constituent weights.
    index_code: e.g. '000300.XSHG' (CSI300), '000905.XSHG' (CSI500), '000852.XSHG' (CSI1000)
    """
    path = os.path.join(config.INDEX_WEIGHTS_DIR, index_code, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_vwap() -> pl.DataFrame:
    """Load VWAP 5min data. Columns: code, vwap_1, datetime, vwap_2, vwap_5, date."""
    return pl.read_parquet(config.VWAP_PATH)


def load_limit_status(trade_date: date, subsampled_5min: bool = False) -> Optional[pl.DataFrame]:
    """Load limit status data. Columns: datetime, symbol, limit_status, paused."""
    base_dir = config.LIMIT_STATUS_5MIN_DIR if subsampled_5min else config.LIMIT_STATUS_DIR
    path = os.path.join(base_dir, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def load_sec_info(trade_date: date) -> Optional[pl.DataFrame]:
    """Load security info. Columns: date, code, high_limit, low_limit, paused."""
    path = os.path.join(config.SEC_INFO_DIR, f"{trade_date}.parquet")
    if not os.path.exists(path):
        return None
    return pl.read_parquet(path)


def available_dates(directory: str) -> list[date]:
    """List available trading dates from a parquet directory."""
    dates = []
    for f in os.listdir(directory):
        if f.endswith(".parquet"):
            try:
                d = date.fromisoformat(f.replace(".parquet", ""))
                dates.append(d)
            except ValueError:
                continue
    return sorted(dates)
