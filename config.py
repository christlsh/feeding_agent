"""Central configuration for the feeding agent."""

# we-mp-rss service
WERSS_BASE_URL = "http://localhost:8001"
WERSS_API_PREFIX = "/api/v1/wx"
WERSS_USERNAME = "admin"
WERSS_PASSWORD = "admin@123"

# DingTalk notification
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=3ebb601f88770eea328f4f313790303101cc58f006782e77ca71510259f0102e"
DINGTALK_SECRET = "SEC231ce1c6e82ea7e3360bc702040936134bc90cd4d34c6e1a59a83a3a5da5e71c"

# Data paths (A-share)
DATA_ROOT = "/data/a_share/sihang"
L2_OB_DIR = f"{DATA_ROOT}/l2_ob_full_universe_with_info"
FWD_RET_DIR = f"{DATA_ROOT}/fwd_ret_with_open_intra"
BARRA_DIR = f"{DATA_ROOT}/GYCNE5_syn"
INDEX_WEIGHTS_DIR = f"{DATA_ROOT}/index_weights"
VWAP_PATH = f"{DATA_ROOT}/vwap_5m.parquet"
LIMIT_STATUS_DIR = f"{DATA_ROOT}/limit_status"
LIMIT_STATUS_5MIN_DIR = f"{DATA_ROOT}/limit_status_subsampled_5min"
SEC_INFO_DIR = f"{DATA_ROOT}/sec_info"
TRADE_DAYS_PATH = f"{DATA_ROOT}/all_trade_days.npy"

# Project paths
import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

# Python interpreter with polars
PYTHON = "/home/sihang/anaconda3/bin/python"
