"""
XHS Sign Server — signatures + browser-based page scraping.

Uses Playwright + stealth to run XHS's signing JavaScript in a headless browser.
Scrapes XHS via browser API interception to bypass API restrictions (300011).

Working endpoints:
  POST /sign        — generate x-s/x-t signatures
  POST /search      — search notes by keyword (intercepts search API)
  POST /user_notes  — scrape user profile (nickname + note IDs)
  GET  /a1          — get current browser a1 cookie
  GET  /            — health check

Note: Individual note detail fetching is not available due to XHS API 300011
restriction. Search results provide title, user, images, and interaction counts.

Usage:
  python sign_server.py
  nohup python sign_server.py > logs/sign_server.log 2>&1 &
"""

import sys
import os
import re
import json
import time
import logging
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sign_server")

app = Flask(__name__)
A1 = ""
_sign_page = None      # stays on XHS homepage for signing
_scrape_page = None     # navigates freely for scraping
_browser_context = None

# Regex to extract raw __INITIAL_STATE__ JSON from page HTML
_STATE_RE = re.compile(
    r'window\.__INITIAL_STATE__\s*=\s*(.+?)\s*;?\s*</script>',
    re.DOTALL,
)


def _parse_cookie_string(cookie_str: str) -> list[dict]:
    """Parse cookie string into Playwright cookie format."""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".xiaohongshu.com",
            "path": "/",
        })
    return cookies


def _extract_initial_state(page) -> dict | None:
    """Extract raw __INITIAL_STATE__ JSON from page HTML."""
    html = page.content()
    m = _STATE_RE.search(html)
    if not m:
        return None
    json_str = m.group(1)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # XHS SSR uses JS-specific values — replace with null
        fixed = re.sub(r'\bundefined\b', 'null', json_str)
        fixed = re.sub(r'\bNaN\b', 'null', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


def _start_browser():
    """Launch headless Chromium with two pages: signing + scraping."""
    global A1, _sign_page, _scrape_page, _browser_context

    log.info("Starting Playwright browser...")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context()

    # Inject user cookies BEFORE creating pages
    user_cookie = config.XHS_COOKIE
    if user_cookie:
        log.info("Injecting user cookies into browser...")
        parsed = _parse_cookie_string(user_cookie)
        context.add_cookies(parsed)
        for c in parsed:
            if c["name"] == "a1":
                A1 = c["value"]
                log.info(f"User a1 cookie: {A1[:16]}...")

    # Page 1: signing (stays on XHS homepage)
    sign_page = context.new_page()
    Stealth().apply_stealth_sync(sign_page)
    log.info("Navigating sign page to xiaohongshu.com...")
    sign_page.goto("https://www.xiaohongshu.com")
    time.sleep(3)
    sign_page.reload()
    time.sleep(3)

    # Page 2: scraping (navigates freely)
    scrape_page = context.new_page()
    Stealth().apply_stealth_sync(scrape_page)

    # Verify a1 cookie
    for cookie in context.cookies():
        if cookie["name"] == "a1":
            A1 = cookie["value"]
            log.info(f"Browser a1 cookie: {A1[:16]}...")

    _sign_page = sign_page
    _scrape_page = scrape_page
    _browser_context = context
    log.info("Browser ready (sign page + scrape page)")


def _reset_scrape_page():
    """Close and recreate the scrape page for a clean state."""
    global _scrape_page
    try:
        _scrape_page.close()
    except Exception:
        pass
    _scrape_page = _browser_context.new_page()
    Stealth().apply_stealth_sync(_scrape_page)


# ── Core endpoints ───────────────────────────────────────────────


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "a1": A1[:8] + "..." if A1 else ""})


@app.route("/sign", methods=["POST"])
def handle_sign():
    try:
        data = request.json
        uri = data.get("uri", "")
        payload = data.get("data", None)

        encrypt_params = _sign_page.evaluate(
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


# ── Search endpoint ──────────────────────────────────────────────


@app.route("/search", methods=["POST"])
def handle_search():
    """Search XHS notes by keyword. Intercepts the search API for rich data.

    Returns note_card data: title, user, images, interact_info, type.
    """
    try:
        keyword = request.json.get("keyword", "")
        sort = request.json.get("sort", "general")  # general, time_descending, popularity_descending
        if not keyword:
            return jsonify({"error": "keyword required"}), 400

        from urllib.parse import quote
        url = (f"https://www.xiaohongshu.com/search_result"
               f"?keyword={quote(keyword)}&source=web_search_result_note")
        log.info(f"Searching: {keyword}")

        # Intercept search API response for rich data
        captured_results = {}

        def handle_response(response):
            try:
                req_url = response.url
                if "/api/sns/web/v1/search/notes" in req_url and response.status == 200:
                    data = response.json()
                    items = data.get("data", {}).get("items", [])
                    if items:
                        captured_results["items"] = items
                        captured_results["has_more"] = data.get("data", {}).get("has_more", False)
                        log.info(f"Captured search API: {len(items)} items")
            except Exception:
                pass

        # Recreate scrape page for clean state
        _reset_scrape_page()

        _scrape_page.on("response", handle_response)
        try:
            _scrape_page.goto(url, wait_until="networkidle", timeout=20000)
            time.sleep(2)
        finally:
            _scrape_page.remove_listener("response", handle_response)

        # Build response from captured API data
        if captured_results.get("items"):
            notes = []
            for item in captured_results["items"]:
                card = item.get("note_card", {})
                nid = item.get("id", "") or card.get("note_id", "")
                if not nid:
                    continue
                user = card.get("user", {})
                notes.append({
                    "note_id": nid,
                    "title": card.get("title", "") or card.get("display_title", ""),
                    "display_title": card.get("display_title", ""),
                    "desc": card.get("desc", ""),
                    "type": card.get("type", "normal"),
                    "time": card.get("time", 0) or card.get("last_update_time", 0),
                    "user": {
                        "user_id": user.get("user_id", ""),
                        "nickname": user.get("nickname", ""),
                    },
                    "tag_list": [{"name": t.get("name", "")}
                                 for t in card.get("tag_list", []) if t.get("name")],
                    "image_list": [{"url": img.get("url_default", "") or
                                    (img.get("info_list", [{}])[0].get("url", "")
                                     if img.get("info_list") else "")}
                                   for img in card.get("image_list", [])],
                    "interact_info": {
                        "liked_count": card.get("interact_info", {}).get("liked_count", "0"),
                        "collected_count": card.get("interact_info", {}).get("collected_count", "0"),
                        "comment_count": card.get("interact_info", {}).get("comment_count", "0"),
                    },
                })
            log.info(f"Search '{keyword}': {len(notes)} notes")
            return jsonify({"source": "api", "notes": notes,
                           "has_more": captured_results.get("has_more", False)})

        # Fallback: DOM links
        notes = _scrape_page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/explore/"]');
            const seen = new Set();
            const notes = [];
            links.forEach(a => {
                const m = a.href.match(/\\/explore\\/([a-f0-9]+)/);
                if (m && !seen.has(m[1])) {
                    seen.add(m[1]);
                    const title = a.querySelector(
                        '.title, .note-title, h3, p, span'
                    )?.textContent || "";
                    notes.push({
                        note_id: m[1],
                        title: title.trim(),
                        type: "normal",
                    });
                }
            });
            return notes;
        }""")

        log.info(f"Search '{keyword}': {len(notes)} notes (DOM fallback)")
        return jsonify({"source": "dom", "notes": notes})
    except Exception as e:
        log.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500


# ── User profile endpoint ────────────────────────────────────────


@app.route("/user_notes", methods=["POST"])
def handle_user_notes():
    """Get a user's profile info and note IDs from their profile page."""
    try:
        user_id = request.json.get("user_id", "")
        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        log.info(f"Scraping user profile: {user_id}")

        # Intercept any API responses with note data
        captured_notes = []
        captured_info = {}

        def handle_response(response):
            try:
                req_url = response.url
                if "/api/" in req_url and response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" not in ct:
                        return
                    data = response.json()
                    inner = data.get("data", {})
                    # Check for note lists
                    if isinstance(inner.get("notes"), list) and inner["notes"]:
                        for note in inner["notes"]:
                            captured_notes.append(note)
                        log.info(f"Captured {len(inner['notes'])} notes from API")
                    # Check for user info (but not /user/me which is the logged-in user)
                    if "/user/me" not in req_url and (inner.get("basic_info") or inner.get("nickname")):
                        captured_info.update(inner)
            except Exception:
                pass

        _scrape_page.on("response", handle_response)
        try:
            _scrape_page.goto(url, wait_until="networkidle", timeout=20000)
            time.sleep(2)
        finally:
            _scrape_page.remove_listener("response", handle_response)

        # Debug: check what the page looks like
        debug_info = _scrape_page.evaluate("""() => ({
            url: window.location.href,
            title: document.title,
            exploreLinks: document.querySelectorAll('a[href*="/explore/"]').length,
            bodyLen: document.body?.innerText?.length || 0,
        })""")
        log.info(f"User page debug: url={debug_info['url'][:60]}, "
                 f"links={debug_info['exploreLinks']}, bodyLen={debug_info['bodyLen']}")

        nickname = ""
        desc = ""

        # User info from __INITIAL_STATE__ (SSR data)
        state = _extract_initial_state(_scrape_page)
        if state:
            user_state = state.get("user", {})
            info = user_state.get("userPageData", user_state.get("userInfo", {}))
            basic = info.get("basicInfo", info)
            nickname = basic.get("nickname", "") or basic.get("nickName", "")
            desc = basic.get("desc", "")

        # Override with API-captured info if it's for the right user
        if captured_info:
            bi = captured_info.get("basic_info", captured_info)
            api_nickname = bi.get("nickname", "")
            if api_nickname and api_nickname != nickname:
                # Only use if it looks like the target user
                pass
            elif api_nickname:
                nickname = api_nickname
                desc = bi.get("desc", desc)

        # DOM fallback for nickname
        if not nickname:
            nickname = _scrape_page.evaluate("""() => {
                const el = document.querySelector(
                    '.user-name, .nickname, .user-nickname');
                return el ? el.textContent.trim() : "";
            }""") or ""

        # Build notes list
        notes = []
        if captured_notes:
            for note in captured_notes:
                nid = note.get("note_id", "")
                if not nid:
                    continue
                user_info = note.get("user", {})
                notes.append({
                    "note_id": nid,
                    "title": note.get("title", "") or note.get("display_title", ""),
                    "display_title": note.get("display_title", ""),
                    "desc": note.get("desc", ""),
                    "type": note.get("type", "normal"),
                    "time": note.get("time", 0) or note.get("last_update_time", 0),
                    "user": {
                        "user_id": user_info.get("user_id", user_id),
                        "nickname": user_info.get("nickname", nickname),
                    },
                    "interact_info": {
                        "liked_count": note.get("interact_info", {}).get("liked_count", "0"),
                        "collected_count": note.get("interact_info", {}).get("collected_count", "0"),
                        "comment_count": note.get("interact_info", {}).get("comment_count", "0"),
                    },
                })

        # Fallback: DOM note IDs (no titles)
        if not notes:
            notes = _scrape_page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/explore/"]');
                const seen = new Set();
                const notes = [];
                links.forEach(a => {
                    const m = a.href.match(/\\/explore\\/([a-f0-9]+)/);
                    if (m && !seen.has(m[1])) {
                        seen.add(m[1]);
                        // Try to get title from the note card
                        const card = a.closest('.note-item, [class*="note"]');
                        const titleEl = card?.querySelector(
                            '.title, .footer .name, span');
                        notes.push({
                            note_id: m[1],
                            title: titleEl?.textContent?.trim() || "",
                            type: "normal",
                        });
                    }
                });
                return notes;
            }""")

        log.info(f"User {user_id}: {nickname or '?'}, {len(notes)} notes")
        return jsonify({
            "nickname": nickname,
            "user_id": user_id,
            "desc": desc,
            "notes": notes,
        })
    except Exception as e:
        log.error(f"User notes error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    _start_browser()
    log.info("Sign server starting on port 5005...")
    # threaded=False: Playwright page objects are not thread-safe
    app.run(host="0.0.0.0", port=5005, threaded=False)
