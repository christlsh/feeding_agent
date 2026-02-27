"""DingTalk notification with HMAC-SHA256 signing."""

import requests
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import config


def _sign_url(webhook_url: str) -> str:
    secret = config.DINGTALK_SECRET
    if not secret:
        return webhook_url
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{webhook_url}&timestamp={timestamp}&sign={sign}"


def send_dingtalk(title: str, text: str, is_at_all: bool = False):
    """Send a markdown message to DingTalk."""
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
        "at": {"atMobiles": [], "isAtAll": is_at_all},
    }
    signed_url = _sign_url(config.DINGTALK_WEBHOOK)
    resp = requests.post(url=signed_url, headers=headers, data=json.dumps(data))
    result = resp.json()
    if result.get("errcode") != 0:
        print(f"DingTalk send failed: {result}")
    return result
