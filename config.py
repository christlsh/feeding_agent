"""Central configuration for the feeding agent."""

import os

# we-mp-rss service
WERSS_BASE_URL = "http://localhost:8001"
WERSS_API_PREFIX = "/api/v1/wx"
WERSS_USERNAME = "admin"
WERSS_PASSWORD = "admin@123"

# DingTalk notification (webhook for outgoing push)
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=3ebb601f88770eea328f4f313790303101cc58f006782e77ca71510259f0102e"
DINGTALK_SECRET = "SEC231ce1c6e82ea7e3360bc702040936134bc90cd4d34c6e1a59a83a3a5da5e71c"

# DingTalk Stream Bot (bidirectional chat, set via env or fill in directly)
DINGTALK_APP_KEY = os.environ.get("DINGTALK_APP_KEY", "dingqzjtphfcqxcvozje")
DINGTALK_APP_SECRET = os.environ.get("DINGTALK_APP_SECRET", "xoWiaAncXotjFUzmRN0SRr_YmeWDIyiXX2818BHX93Sb8sWWJcowpE0chwLbwDUK")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8798729634:AAHAqqrRN1FtdZ6Xu49QbET3aQY0Ade8zgQ")

# Anthropic API (Claude) — third-party proxy
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://claudelike.online/api")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "cr_3050ca27e7cd779458bc8e0dcaad560b449d452b3c3e67c33a2a8499606d13be")

# XHS (Xiaohongshu)
XHS_COOKIE = os.environ.get("XHS_COOKIE", "acw_tc=0a00d1a617722597452506280e6b4dda234feecc1b8186ee187868d5a945a1;abRequestId=086f0244-ab20-50f4-acc5-abdc638db9a6;webBuild=5.13.0;xsecappid=xhs-pc-web;a1=19ca2e9a08f1vugn2gnwy06abmpain86gjmsprdgh30000251000;webId=027b2dd61a8cf52912452ddd52421aba;websectiga=f3d8eaee8a8c63016320d94a1bd00562d516a5417bc43a032a80cbf70f07d5c0;sec_poison_id=5971ca90-f7ae-4b11-8b47-ae3a5a05c685;gid=yjS0Jdj0fJkqyjS0Jdj08VFfYiyh7kIJkIEv6kx8K0D6UMq803IYKU888J2y8888Ji4SY02f;web_session=040069b02d7a895bad59dec1973b4b10c87abd")
XHS_SIGN_SERVER = os.environ.get("XHS_SIGN_SERVER", "http://localhost:5005/sign")

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
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

XHS_SUBSCRIPTIONS_FILE = os.path.join(PROJECT_ROOT, ".xhs_subscriptions.json")

# Python interpreter with polars
PYTHON = "/home/sihang/anaconda3/bin/python"
