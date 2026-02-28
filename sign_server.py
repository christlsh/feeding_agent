"""
XHS Sign Server — generates x-s/x-t signatures for Xiaohongshu API.

Uses Playwright + stealth to run XHS's signing JavaScript in a headless browser.

Usage:
  python sign_server.py
  # Runs on http://0.0.0.0:5005

  # Daemon mode
  nohup python sign_server.py > logs/sign_server.log 2>&1 &

Endpoints:
  POST /sign  — generate x-s/x-t for a request
  GET  /a1    — get current browser a1 cookie
  GET  /      — health check
"""

import time
import logging
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sign_server")

app = Flask(__name__)
A1 = ""
_context_page = None


def _start_browser():
    """Launch headless Chromium, navigate to XHS, extract a1 cookie."""
    global A1, _context_page

    log.info("Starting Playwright browser...")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Apply stealth to avoid detection
    Stealth().apply_stealth_sync(page)

    log.info("Navigating to xiaohongshu.com...")
    page.goto("https://www.xiaohongshu.com")
    time.sleep(5)
    page.reload()
    time.sleep(3)

    # Extract a1 cookie
    cookies = context.cookies()
    for cookie in cookies:
        if cookie["name"] == "a1":
            A1 = cookie["value"]
            log.info(f"Got browser a1 cookie: {A1[:8]}...")

    _context_page = page
    log.info("Browser ready for signing")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "a1": A1[:8] + "..." if A1 else ""})


@app.route("/sign", methods=["POST"])
def handle_sign():
    try:
        data = request.json
        uri = data.get("uri", "")
        payload = data.get("data", None)
        a1 = data.get("a1", "")
        web_session = data.get("web_session", "")

        encrypt_params = _context_page.evaluate(
            "([url, data]) => window._webmsxyw(url, data)",
            [uri, payload],
        )

        return jsonify({
            "x-s": encrypt_params.get("X-s", ""),
            "x-t": str(encrypt_params.get("X-t", "")),
        })
    except Exception as e:
        log.error(f"Sign error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/a1", methods=["GET"])
def get_a1():
    return jsonify({"a1": A1})


if __name__ == "__main__":
    _start_browser()
    log.info("Sign server starting on port 5005...")
    # threaded=False: Playwright page objects are not thread-safe
    app.run(host="0.0.0.0", port=5005, threaded=False)
