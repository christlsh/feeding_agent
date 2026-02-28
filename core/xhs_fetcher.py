"""Fetch notes from Xiaohongshu (XHS / 小红书) via xhs package.

Requires:
  1. pip install xhs
  2. Sign server running on localhost:5005 (Playwright-based)
  3. XHS_COOKIE env variable set (from browser)
"""

import json
import os
import logging
import time
import requests
from datetime import datetime, timedelta

import config
from core.fetcher import Article

log = logging.getLogger("feeding_agent.xhs")


# ── Sign function ────────────────────────────────────────────────


def _sign(uri, data=None, a1="", web_session=""):
    """Call the local sign server to get x-s/x-t signatures."""
    res = requests.post(
        config.XHS_SIGN_SERVER,
        json={"uri": uri, "data": data, "a1": a1, "web_session": web_session},
        timeout=10,
    )
    signs = res.json()
    return {"x-s": signs["x-s"], "x-t": signs["x-t"]}


# ── Client management ───────────────────────────────────────────

_client = None


def get_client():
    """Get or create a singleton XhsClient instance."""
    global _client
    if _client is None:
        from xhs import XhsClient
        cookie = config.XHS_COOKIE
        if not cookie:
            raise RuntimeError("XHS_COOKIE not set. Set via env or config.py.")
        _client = XhsClient(cookie=cookie, sign=_sign)
    return _client


def reset_client():
    """Reset the client (e.g., after cookie update)."""
    global _client
    _client = None


# ── Health check ─────────────────────────────────────────────────


def check_health() -> dict:
    """Check if XHS cookie and sign server are working.

    Returns: {"ok": bool, "sign_server_ok": bool, "cookie_ok": bool, "error": str}
    """
    result = {"ok": False, "sign_server_ok": False, "cookie_ok": False, "error": ""}

    # 1. Check sign server
    try:
        # Try the sign server root endpoint
        base_url = config.XHS_SIGN_SERVER.replace("/sign", "")
        requests.get(base_url, timeout=5)
        result["sign_server_ok"] = True
    except Exception as e:
        result["error"] = f"Sign server unreachable: {e}"
        return result

    # 2. Check cookie by trying a simple API call
    try:
        client = get_client()
        client.get_self_info()
        result["cookie_ok"] = True
        result["ok"] = True
    except Exception as e:
        err_str = str(e)
        if any(kw in err_str.lower() for kw in ("login", "cookie", "sign", "expired", "未登录")):
            result["error"] = f"XHS cookie expired or invalid: {err_str}"
        else:
            result["error"] = f"XHS API error: {err_str}"

    return result


# ── Subscription management ─────────────────────────────────────


def _load_subscriptions() -> dict:
    """Load XHS subscriptions from local JSON file."""
    path = config.XHS_SUBSCRIPTIONS_FILE
    if not os.path.exists(path):
        return {"users": [], "keywords": []}
    with open(path, "r") as f:
        return json.load(f)


def _save_subscriptions(subs: dict):
    with open(config.XHS_SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def subscribe_user(user_id: str, nickname: str = "") -> dict:
    """Add an XHS user to subscriptions.

    user_id can be a raw ID or full profile URL like:
    https://www.xiaohongshu.com/user/profile/5f3e2a...
    """
    subs = _load_subscriptions()

    # Normalize: extract user_id from URL if needed
    if "xiaohongshu.com" in user_id:
        parts = user_id.rstrip("/").split("/")
        user_id = parts[-1]

    # Check duplicate
    for u in subs["users"]:
        if u["user_id"] == user_id:
            return u  # already subscribed

    # Fetch nickname if not provided
    if not nickname:
        try:
            client = get_client()
            info = client.get_user_info(user_id)
            nickname = info.get("nickname", user_id)
        except Exception:
            nickname = user_id

    entry = {
        "user_id": user_id,
        "nickname": nickname,
        "url": f"https://www.xiaohongshu.com/user/profile/{user_id}",
        "added_at": datetime.now().strftime("%Y-%m-%d"),
    }
    subs["users"].append(entry)
    _save_subscriptions(subs)
    log.info(f"Subscribed to XHS user: {nickname} ({user_id})")
    return entry


def unsubscribe_user(user_id: str) -> bool:
    """Remove an XHS user subscription."""
    if "xiaohongshu.com" in user_id:
        parts = user_id.rstrip("/").split("/")
        user_id = parts[-1]

    subs = _load_subscriptions()
    before = len(subs["users"])
    subs["users"] = [u for u in subs["users"] if u["user_id"] != user_id]
    if len(subs["users"]) < before:
        _save_subscriptions(subs)
        return True
    return False


def add_keyword(keyword: str) -> dict:
    """Add a search keyword to monitor."""
    subs = _load_subscriptions()
    for k in subs["keywords"]:
        if k["keyword"] == keyword:
            return k  # already exists
    entry = {"keyword": keyword, "added_at": datetime.now().strftime("%Y-%m-%d")}
    subs["keywords"].append(entry)
    _save_subscriptions(subs)
    log.info(f"Added XHS keyword: {keyword}")
    return entry


def remove_keyword(keyword: str) -> bool:
    """Remove a keyword subscription."""
    subs = _load_subscriptions()
    before = len(subs["keywords"])
    subs["keywords"] = [k for k in subs["keywords"] if k["keyword"] != keyword]
    if len(subs["keywords"]) < before:
        _save_subscriptions(subs)
        return True
    return False


def list_subscriptions() -> dict:
    """Return all XHS subscriptions."""
    return _load_subscriptions()


# ── Note → Article conversion ───────────────────────────────────


def _note_to_article(note_detail: dict, source_name: str = "XHS") -> Article:
    """Convert an XHS note detail dict into an Article object.

    Constructs lightweight HTML from the note's text/tags so the existing
    parse_html() pipeline works unchanged.
    """
    note_id = note_detail.get("note_id", "")
    title = note_detail.get("title", "") or note_detail.get("display_title", "")
    desc = note_detail.get("desc", "")

    # Parse timestamp (XHS uses ms timestamps or ISO strings)
    time_val = note_detail.get("time", 0)
    if isinstance(time_val, str):
        try:
            dt = datetime.fromisoformat(time_val)
            publish_time = int(dt.timestamp())
        except Exception:
            publish_time = int(datetime.now().timestamp())
    elif time_val and time_val > 1e12:
        publish_time = int(time_val / 1000)  # ms -> s
    elif time_val:
        publish_time = int(time_val)
    else:
        publish_time = int(datetime.now().timestamp())

    # Tags
    tags = note_detail.get("tag_list", [])
    tag_text = " ".join(f"#{t.get('name', '')}" for t in tags if t.get("name"))

    # Image count
    images = note_detail.get("image_list", [])

    # Build pseudo-HTML for pipeline compatibility
    content_parts = []
    if title:
        content_parts.append(f"<h1>{title}</h1>")
    if desc:
        html_desc = desc.replace("\n", "<br>\n")
        content_parts.append(f"<div>{html_desc}</div>")
    if tag_text:
        content_parts.append(f"<p>{tag_text}</p>")
    for _ in images:
        content_parts.append('<img src="xhs_image">')

    content_html = "\n".join(content_parts)
    url = f"https://www.xiaohongshu.com/explore/{note_id}"

    # User info
    user = note_detail.get("user", {})
    user_nickname = user.get("nickname", source_name)

    article = Article(
        id=f"xhs_{note_id}",
        title=title if title else (desc[:50] if desc else "Untitled"),
        url=url,
        publish_time=publish_time,
        content_html=content_html,
        mp_name=f"XHS:{user_nickname}",
        mp_id=f"xhs_{user.get('user_id', '')}",
    )
    article.content_text = desc  # Store raw text directly
    return article


# ── Note fetching ────────────────────────────────────────────────


def fetch_user_notes(user_id: str, max_notes: int = 20) -> list[Article]:
    """Fetch recent image-only notes from an XHS user."""
    if "xiaohongshu.com" in user_id:
        parts = user_id.rstrip("/").split("/")
        user_id = parts[-1]

    client = get_client()
    articles = []
    cursor = ""

    while len(articles) < max_notes:
        try:
            data = client.get_user_notes(user_id=user_id, cursor=cursor)
        except Exception as e:
            log.error(f"Error fetching notes for user {user_id}: {e}")
            break

        notes = data.get("notes", [])
        if not notes:
            break

        for note in notes:
            # Filter: image-only (type == "normal"), skip video
            if note.get("type") != "normal":
                continue
            note_id = note.get("note_id", "")
            if not note_id:
                continue

            try:
                detail = client.get_note_by_id(note_id)
                time.sleep(1)  # rate limiting
            except Exception as e:
                log.warning(f"Error fetching note detail {note_id}: {e}")
                continue

            articles.append(_note_to_article(detail))
            if len(articles) >= max_notes:
                break

        if not data.get("has_more"):
            break
        cursor = data.get("cursor", "")

    log.info(f"Fetched {len(articles)} image notes for user {user_id}")
    return articles


def search_notes(keyword: str, max_notes: int = 20) -> list[Article]:
    """Search XHS for image-only notes by keyword."""
    from xhs import SearchNoteType, SearchSortType

    client = get_client()
    articles = []
    page = 1

    while len(articles) < max_notes:
        try:
            data = client.get_note_by_keyword(
                keyword=keyword,
                note_type=SearchNoteType.IMAGE,
                sort=SearchSortType.LATEST,
                page=page,
                page_size=20,
            )
        except Exception as e:
            log.error(f"Error searching XHS for '{keyword}': {e}")
            break

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            note_card = item.get("note_card", {})
            if note_card.get("type") != "normal":
                continue
            note_id = item.get("id", "")
            if not note_id:
                continue

            try:
                detail = client.get_note_by_id(note_id)
                time.sleep(1)  # rate limiting
            except Exception as e:
                log.warning(f"Error fetching note detail {note_id}: {e}")
                continue

            articles.append(_note_to_article(detail))
            if len(articles) >= max_notes:
                break

        if not data.get("has_more"):
            break
        page += 1

    log.info(f"Search '{keyword}': found {len(articles)} image notes")
    return articles


def fetch_all_subscribed(days_back: int = 7, max_per_user: int = 10,
                         max_per_keyword: int = 10) -> list[Article]:
    """Fetch notes from all subscribed users and keywords.

    Returns deduplicated list of Article objects, filtered by days_back.
    """
    subs = _load_subscriptions()
    all_articles = []
    cutoff = datetime.now() - timedelta(days=days_back)
    cutoff_ts = int(cutoff.timestamp())

    for user in subs.get("users", []):
        log.info(f"Fetching XHS notes for user: {user['nickname']} ({user['user_id']})")
        try:
            notes = fetch_user_notes(user["user_id"], max_notes=max_per_user)
            for note in notes:
                if note.publish_time >= cutoff_ts:
                    all_articles.append(note)
        except Exception as e:
            log.error(f"Error fetching user {user['nickname']}: {e}")

    for kw_entry in subs.get("keywords", []):
        keyword = kw_entry["keyword"]
        log.info(f"Searching XHS for keyword: {keyword}")
        try:
            notes = search_notes(keyword, max_notes=max_per_keyword)
            for note in notes:
                if note.publish_time >= cutoff_ts:
                    all_articles.append(note)
        except Exception as e:
            log.error(f"Error searching keyword '{keyword}': {e}")

    # Deduplicate by article ID
    seen = set()
    unique = []
    for a in all_articles:
        if a.id not in seen:
            seen.add(a.id)
            unique.append(a)

    log.info(f"Total XHS notes fetched: {len(unique)} (from {len(subs.get('users', []))} users, "
             f"{len(subs.get('keywords', []))} keywords)")
    return unique
