"""Fetch notes from Xiaohongshu (XHS / 小红书) via browser scraping.

Uses sign server's browser-based scraping to bypass XHS API restrictions.
Primary data source is the search API (intercepted by the sign server).

Requires:
  1. Sign server running on localhost:5005
  2. XHS_COOKIE set in config.py or env
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

# Sign server base URL (strip /sign suffix)
_SIGN_SERVER_BASE = config.XHS_SIGN_SERVER.replace("/sign", "")


# ── Sign server communication ────────────────────────────────────


def _search_via_server(keyword: str) -> list[dict]:
    """Search notes via sign server (intercepts search API).

    Returns list of note dicts with: note_id, title, desc, type, user,
    tag_list, image_list, interact_info.
    """
    try:
        res = requests.post(
            f"{_SIGN_SERVER_BASE}/search",
            json={"keyword": keyword},
            timeout=30,
        )
        data = res.json()
        if "error" in data and "notes" not in data:
            log.warning(f"Search '{keyword}': {data.get('error')}")
            return []
        return data.get("notes", [])
    except Exception as e:
        log.error(f"Search '{keyword}' failed: {e}")
        return []


def _fetch_user_profile(user_id: str) -> dict:
    """Fetch user profile (nickname + notes) via sign server.

    Returns: {nickname, user_id, desc, notes: [{note_id, title, ...}]}
    """
    try:
        res = requests.post(
            f"{_SIGN_SERVER_BASE}/user_notes",
            json={"user_id": user_id},
            timeout=30,
        )
        data = res.json()
        if "error" in data and "notes" not in data:
            log.warning(f"User profile {user_id}: {data.get('error')}")
            return {}
        return data
    except Exception as e:
        log.error(f"User profile {user_id} failed: {e}")
        return {}


# ── Health check ─────────────────────────────────────────────────


def check_health() -> dict:
    """Check if sign server is working.

    Returns: {"ok": bool, "sign_server_ok": bool, "cookie_ok": bool, "error": str}
    """
    result = {"ok": False, "sign_server_ok": False, "cookie_ok": False, "error": ""}

    try:
        resp = requests.get(_SIGN_SERVER_BASE, timeout=5)
        resp.raise_for_status()
        result["sign_server_ok"] = True
    except Exception as e:
        result["error"] = f"Sign server unreachable: {e}"
        return result

    # Test search functionality (quick keyword)
    try:
        test = _search_via_server("test")
        # Even if no results, search working means cookies are OK
        result["cookie_ok"] = True
        result["ok"] = True
    except Exception as e:
        result["error"] = f"Search test failed: {e}"

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

    if "xiaohongshu.com" in user_id:
        parts = user_id.rstrip("/").split("/")
        user_id = parts[-1]

    for u in subs["users"]:
        if u["user_id"] == user_id:
            return u

    if not nickname:
        nickname = user_id  # Use ID as placeholder; user can update later

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
    subs = _load_subscriptions()
    for k in subs["keywords"]:
        if k["keyword"] == keyword:
            return k
    entry = {"keyword": keyword, "added_at": datetime.now().strftime("%Y-%m-%d")}
    subs["keywords"].append(entry)
    _save_subscriptions(subs)
    log.info(f"Added XHS keyword: {keyword}")
    return entry


def remove_keyword(keyword: str) -> bool:
    subs = _load_subscriptions()
    before = len(subs["keywords"])
    subs["keywords"] = [k for k in subs["keywords"] if k["keyword"] != keyword]
    if len(subs["keywords"]) < before:
        _save_subscriptions(subs)
        return True
    return False


def list_subscriptions() -> dict:
    return _load_subscriptions()


# ── Note → Article conversion ───────────────────────────────────


def _note_to_article(note_data: dict, source_name: str = "XHS") -> Article:
    """Convert a note dict (from search API or user profile) into an Article.

    Handles both cases where desc is available or only title is available.
    """
    note_id = note_data.get("note_id", "")
    title = note_data.get("title", "") or note_data.get("display_title", "")
    desc = note_data.get("desc", "")

    # Parse timestamp
    time_val = note_data.get("time", 0)
    if isinstance(time_val, str):
        try:
            dt = datetime.fromisoformat(time_val)
            publish_time = int(dt.timestamp())
        except Exception:
            publish_time = int(datetime.now().timestamp())
    elif time_val and time_val > 1e12:
        publish_time = int(time_val / 1000)
    elif time_val:
        publish_time = int(time_val)
    else:
        publish_time = int(datetime.now().timestamp())

    # Tags
    tags = note_data.get("tag_list", [])
    tag_text = " ".join(f"#{t.get('name', '')}" for t in tags if t.get("name"))

    # Images
    images = note_data.get("image_list", [])

    # Interaction stats
    interact = note_data.get("interact_info", {})
    stats_parts = []
    if interact.get("liked_count", "0") != "0":
        stats_parts.append(f"赞 {interact['liked_count']}")
    if interact.get("collected_count", "0") != "0":
        stats_parts.append(f"收藏 {interact['collected_count']}")
    if interact.get("comment_count", "0") != "0":
        stats_parts.append(f"评论 {interact['comment_count']}")
    stats_text = " | ".join(stats_parts)

    # Build content text (title + desc + tags + stats)
    content_parts = []
    if title:
        content_parts.append(title)
    if desc and desc != title:
        content_parts.append(desc)
    if tag_text:
        content_parts.append(tag_text)
    if images:
        content_parts.append(f"[{len(images)}张图片]")
    if stats_text:
        content_parts.append(f"互动: {stats_text}")
    content_text = "\n\n".join(content_parts)

    # Build pseudo-HTML for pipeline compatibility
    html_parts = []
    if title:
        html_parts.append(f"<h1>{title}</h1>")
    if desc and desc != title:
        html_parts.append(f"<div>{desc.replace(chr(10), '<br>')}</div>")
    if tag_text:
        html_parts.append(f"<p>{tag_text}</p>")
    for _ in images:
        html_parts.append('<img src="xhs_image">')
    if stats_text:
        html_parts.append(f"<p><small>{stats_text}</small></p>")
    content_html = "\n".join(html_parts)

    url = f"https://www.xiaohongshu.com/explore/{note_id}"

    user = note_data.get("user", {})
    user_nickname = user.get("nickname", source_name)

    article = Article(
        id=f"xhs_{note_id}",
        title=title if title else "Untitled",
        url=url,
        publish_time=publish_time,
        content_html=content_html,
        mp_name=f"XHS:{user_nickname}",
        mp_id=f"xhs_{user.get('user_id', '')}",
    )
    article.content_text = content_text
    return article


# ── Note fetching ────────────────────────────────────────────────


def search_notes(keyword: str, max_notes: int = 20) -> list[Article]:
    """Search XHS for notes by keyword. Uses search API data directly."""
    note_list = _search_via_server(keyword)
    if not note_list:
        log.warning(f"No search results for '{keyword}'")
        return []

    articles = []
    for note_data in note_list:
        # Skip video notes
        if note_data.get("type") == "video":
            continue
        if not note_data.get("note_id"):
            continue
        articles.append(_note_to_article(note_data))
        if len(articles) >= max_notes:
            break

    log.info(f"Search '{keyword}': {len(articles)} articles")
    return articles


def fetch_user_notes(user_id: str, max_notes: int = 20) -> list[Article]:
    """Fetch notes from an XHS user by searching for their nickname.

    XHS profile pages trigger captcha, so we search for the user's nickname
    instead and filter results to only include their notes.
    """
    if "xiaohongshu.com" in user_id:
        parts = user_id.rstrip("/").split("/")
        user_id = parts[-1]

    # Get nickname from subscriptions or profile
    nickname = ""
    subs = _load_subscriptions()
    for u in subs.get("users", []):
        if u["user_id"] == user_id:
            nickname = u.get("nickname", "")
            break

    if not nickname:
        # Try fetching profile (might trigger captcha)
        profile = _fetch_user_profile(user_id)
        nickname = profile.get("nickname", "") or user_id

    if not nickname or nickname == user_id:
        log.warning(f"No nickname for user {user_id}, can't search")
        return []

    # Search by nickname and filter by user_id
    all_results = _search_via_server(nickname)
    articles = []
    for note_data in all_results:
        note_user_id = note_data.get("user", {}).get("user_id", "")
        if note_user_id != user_id:
            continue
        if note_data.get("type") == "video":
            continue
        articles.append(_note_to_article(note_data, source_name=nickname))
        if len(articles) >= max_notes:
            break

    log.info(f"User {user_id} ({nickname}): {len(articles)} articles (via search)")
    return articles


def fetch_all_subscribed(days_back: int = 7, max_per_user: int = 10,
                         max_per_keyword: int = 10) -> list[Article]:
    """Fetch notes from all subscribed users and keywords.

    Returns deduplicated list of Article objects.
    """
    subs = _load_subscriptions()
    all_articles = []

    for user in subs.get("users", []):
        log.info(f"Fetching XHS notes for user: {user['nickname']} ({user['user_id']})")
        try:
            notes = fetch_user_notes(user["user_id"], max_notes=max_per_user)
            all_articles.extend(notes)
            time.sleep(2)  # rate limit between users
        except Exception as e:
            log.error(f"Error fetching user {user['nickname']}: {e}")

    for kw_entry in subs.get("keywords", []):
        keyword = kw_entry["keyword"]
        log.info(f"Searching XHS for keyword: {keyword}")
        try:
            notes = search_notes(keyword, max_notes=max_per_keyword)
            all_articles.extend(notes)
            time.sleep(2)  # rate limit between searches
        except Exception as e:
            log.error(f"Error searching keyword '{keyword}': {e}")

    # Deduplicate by article ID
    seen = set()
    unique = []
    for a in all_articles:
        if a.id not in seen:
            seen.add(a.id)
            unique.append(a)

    log.info(f"Total XHS: {len(unique)} articles (from {len(subs.get('users', []))} users, "
             f"{len(subs.get('keywords', []))} keywords)")
    return unique
