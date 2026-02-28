"""
Feeding Agent - WeChat public account article analyzer for quant investing.

Usage:
  # Subscribe a new account by article URL
  python run.py subscribe --url https://mp.weixin.qq.com/s/xxx

  # Process recent articles for one account (by name or MP ID)
  python run.py process --name QuantML --days 7
  python run.py process --mp-id MP_WXS_3863007345

  # Process ALL subscribed accounts
  python run.py process --all --days 7

  # List all subscribed accounts
  python run.py list

  # Subscribe + immediately process
  python run.py subscribe --url https://mp.weixin.qq.com/s/xxx --process --days 7

  # Daemon mode: auto-check every N minutes, only process new articles
  python run.py watch --interval 60
  python run.py watch --interval 30 --no-dingtalk

  # Disable DingTalk push
  python run.py process --name QuantML --no-dingtalk

  # XHS (Xiaohongshu) commands
  python run.py xhs-subscribe --user https://www.xiaohongshu.com/user/profile/xxx
  python run.py xhs-subscribe --keyword "量化交易"
  python run.py xhs-list
  python run.py xhs-process --days 7
  python run.py xhs-process --search "因子挖掘" --limit 10
"""

import sys
import os
import argparse
import time
import re
import json
import subprocess
import requests
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.fetcher import fetch_articles, ensure_content, Article, _get_token, _auth_headers
from core.parser import parse_html
from core.classifier import classify
from core.analyzer import analyze, format_summary_markdown, format_dingtalk_message
from core.reporter import save_article_results, push_to_dingtalk, generate_batch_summary
from core.notifier import send_dingtalk
from core.xhs_fetcher import (
    subscribe_user as xhs_subscribe_user,
    unsubscribe_user as xhs_unsubscribe_user,
    add_keyword as xhs_add_keyword,
    remove_keyword as xhs_remove_keyword,
    list_subscriptions as xhs_list_subscriptions,
    fetch_user_notes as xhs_fetch_user_notes,
    search_notes as xhs_search_notes,
    fetch_all_subscribed as xhs_fetch_all,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("feeding_agent")

# ── Processed article tracking ───────────────────────────────────

PROCESSED_DB = os.path.join(config.PROJECT_ROOT, ".processed.json")


def _load_processed() -> set:
    """Load set of already-processed article IDs."""
    if not os.path.exists(PROCESSED_DB):
        return set()
    with open(PROCESSED_DB, "r") as f:
        return set(json.load(f))


def _save_processed(processed: set):
    with open(PROCESSED_DB, "w") as f:
        json.dump(sorted(processed), f)


def _mark_processed(article_id: str):
    processed = _load_processed()
    processed.add(article_id)
    _save_processed(processed)


# ── Helpers ──────────────────────────────────────────────────────

def _api(method, path, **kwargs):
    """Call we-mp-rss API with auth."""
    headers = _auth_headers()
    url = f"{config.WERSS_BASE_URL}{config.WERSS_API_PREFIX}{path}"
    resp = getattr(requests, method)(url, headers=headers, **kwargs)
    return resp.json()


def _extract_account_info(article_url: str) -> dict:
    """Extract public account info from a WeChat article URL via curl."""
    cmd = [
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Referer: https://mp.weixin.qq.com/",
        article_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    html = result.stdout

    def _find(pattern):
        m = re.search(pattern, html)
        return m.group(1).strip() if m else ""

    name = _find(r'var\s+nickname\s*=\s*htmlDecode\("([^"]+)"\)')
    if not name:
        name = _find(r'nickname\s*=\s*"([^"]+)"')
    if not name:
        name = _find(r'rich_media_meta_nickname[^>]*>\s*(.+?)\s*<')

    biz = _find(r'__biz=([A-Za-z0-9=]+)')
    avatar = _find(r'var\s+hd_head_img\s*=\s*"([^"]+)"')

    return {"name": name, "biz": biz, "avatar": avatar, "url": article_url}


def _lookup_mp(name: str = None, mp_id: str = None) -> dict:
    """Find a subscribed account by name or MP ID. Returns dict with id, mp_name."""
    data = _api("get", "/mps", params={"limit": 100})
    mps = data.get("data", {}).get("list", [])
    for mp in mps:
        if mp_id and mp["id"] == mp_id:
            return mp
        if name and name.lower() in mp["mp_name"].lower():
            return mp
    return {}


def _list_all_mps() -> list[dict]:
    """List all subscribed accounts."""
    data = _api("get", "/mps", params={"limit": 100})
    return data.get("data", {}).get("list", [])


def _wait_for_articles(mp_id: str, timeout: int = 30):
    """Wait for background article fetching to finish."""
    for _ in range(timeout // 5):
        time.sleep(5)
        data = _api("get", "/articles", params={"mp_id": mp_id, "limit": 5})
        total = data.get("data", {}).get("total", 0)
        if total > 0:
            return total
    return 0


# ── Commands ─────────────────────────────────────────────────────

def cmd_subscribe(args):
    """Subscribe a new public account from an article URL."""
    print(f"Extracting account info from: {args.url}")
    info = _extract_account_info(args.url)

    if not info["biz"]:
        print("ERROR: Could not extract account biz ID from the article.")
        return None

    name = info["name"] or args.name or "Unknown"
    print(f"Account: {name} (biz={info['biz']})")

    # Check if already subscribed
    existing = _lookup_mp(name=name)
    if existing:
        print(f"Already subscribed: {existing['mp_name']} (id={existing['id']})")
        mp_id = existing["id"]
    else:
        # Add to we-mp-rss
        resp = _api("post", "/mps", json={
            "mp_name": name,
            "mp_id": info["biz"],
            "mp_cover": "",
            "avatar": info["avatar"] or "",
            "mp_intro": f"{name}",
        })
        if resp.get("code") != 0:
            print(f"ERROR: Failed to subscribe: {resp}")
            return None
        mp_id = resp["data"]["id"]
        print(f"Subscribed! MP ID: {mp_id}")

        # Wait for initial article fetch
        print("Waiting for articles to be fetched...")
        total = _wait_for_articles(mp_id)
        print(f"Initial fetch: {total} articles")

        # Trigger more pages
        time.sleep(3)
        _api("get", f"/mps/update/{mp_id}", params={"start_page": 0, "end_page": 3})
        print("Triggered extended article fetch (pages 0-3)...")
        time.sleep(15)

    # Show article count
    data = _api("get", "/articles", params={"mp_id": mp_id, "limit": 1})
    total = data.get("data", {}).get("total", 0)
    print(f"Total articles available: {total}")

    # Process if requested
    if args.process:
        return cmd_process_mp(mp_id, args.days, not args.no_dingtalk)

    return mp_id


def cmd_list(args):
    """List all subscribed accounts."""
    mps = _list_all_mps()
    if not mps:
        print("No subscribed accounts.")
        return

    print(f"{'ID':<25} {'Name':<20} {'Status':<8} {'Created'}")
    print("-" * 80)
    for mp in mps:
        print(f"{mp['id']:<25} {mp['mp_name']:<20} {'Active' if mp['status'] == 1 else 'Off':<8} {mp['created_at'][:10]}")


def cmd_process(args):
    """Process articles for one or all accounts."""
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    push = not args.no_dingtalk
    new_only = getattr(args, "new_only", False)

    if args.all:
        _process_all(args.days, push, new_only)
        return

    # Single account
    mp = None
    if args.mp_id:
        mp = _lookup_mp(mp_id=args.mp_id)
    elif args.name:
        mp = _lookup_mp(name=args.name)
    elif args.url:
        # Extract from article URL
        info = _extract_account_info(args.url)
        if info["name"]:
            mp = _lookup_mp(name=info["name"])

    if not mp:
        print("ERROR: Account not found. Use 'list' to see subscribed accounts, or 'subscribe' to add one.")
        return

    print(f"Processing: {mp['mp_name']} ({mp['id']})")
    cmd_process_mp(mp["id"], args.days, push, mp_name=mp["mp_name"])


def cmd_process_mp(mp_id: str, days_back: int, push_dingtalk: bool,
                   mp_name: str = "", new_only: bool = False) -> list:
    """Core processing logic for a single account."""
    log.info(f"Fetching articles for {mp_name or mp_id}, last {days_back} days...")
    articles = fetch_articles(mp_id, limit=30, days_back=days_back)
    log.info(f"Found {len(articles)} articles")

    # Filter to new-only if requested
    if new_only:
        processed = _load_processed()
        before = len(articles)
        articles = [a for a in articles if a.id not in processed]
        log.info(f"New articles: {len(articles)} (skipped {before - len(articles)} already processed)")

    if not articles:
        return []

    results = []
    for article in sorted(articles, key=lambda a: a.publish_time):
        result = process_article(article)
        analysis = result["analysis"]
        backtest = result["backtest"]
        results.append((analysis, backtest))
        _mark_processed(article.id)

        if push_dingtalk and analysis.level in ("A", "B"):
            log.info(f"  Pushing to DingTalk...")
            push_to_dingtalk(analysis, backtest)
            time.sleep(2)

    if results:
        summary = generate_batch_summary(results)
        summary_path = os.path.join(config.RESULTS_DIR,
                                    f"summary_{mp_name or mp_id}.md")
        with open(summary_path, "w") as f:
            f.write(summary)
        log.info(f"Summary saved: {summary_path}")

    return results


def process_article(article: Article) -> dict:
    """Process a single article through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"Processing: {article.title}")
    print(f"Date: {article.date_str}, URL: {article.url}")

    article = ensure_content(article)

    parsed = parse_html(article.content_html, title=article.title)
    print(f"  Parsed: {len(parsed.text)} chars, {len(parsed.code_blocks)} code blocks, "
          f"{len(parsed.paper_links)} papers, {len(parsed.github_links)} github links")

    classification = classify(parsed)
    print(f"  Classification: Level={classification.level}, "
          f"Category={classification.category}, Relevance={classification.relevance:.2f}")
    print(f"  Reason: {classification.reason}")

    analysis = analyze(parsed, classification, date_str=article.date_str, url=article.url)

    backtest = None
    save_article_results(article, analysis, backtest)

    return {
        "article": article,
        "parsed": parsed,
        "classification": classification,
        "analysis": analysis,
        "backtest": backtest,
    }


def _process_all(days_back: int, push_dingtalk: bool, new_only: bool = False):
    """Process all subscribed accounts."""
    mps = _list_all_mps()
    all_results = []
    for mp in mps:
        if mp["status"] != 1:
            continue
        log.info(f"Account: {mp['mp_name']}")
        results = cmd_process_mp(mp["id"], days_back, push_dingtalk,
                                 mp_name=mp["mp_name"], new_only=new_only)
        if results:
            all_results.extend(results)

    if all_results and push_dingtalk:
        summary = generate_batch_summary(all_results)
        summary_path = os.path.join(config.RESULTS_DIR, "weekly_summary.md")
        with open(summary_path, "w") as f:
            f.write(summary)
        level_a = sum(1 for a, _ in all_results if a.level == "A")
        level_b = sum(1 for a, _ in all_results if a.level == "B")
        send_dingtalk("Weekly Summary", (
            f"### 📊 Weekly Article Summary\n\n"
            f"- Accounts: {len(mps)}\n"
            f"- Total: {len(all_results)} articles\n"
            f"- Level A: {level_a} | Level B: {level_b}\n"
        ))

    return all_results


def cmd_watch(args):
    """Daemon mode: periodically check for new articles and process them."""
    interval = args.interval * 60  # convert minutes to seconds
    push = not args.no_dingtalk
    days_back = args.days

    log.info(f"Watch mode started: checking every {args.interval} min, "
             f"looking back {days_back} days, dingtalk={'on' if push else 'off'}")
    log.info(f"PID: {os.getpid()}")

    # First trigger article sync for all accounts
    _trigger_sync_all()

    while True:
        try:
            log.info("Checking for new articles...")
            os.makedirs(config.RESULTS_DIR, exist_ok=True)
            results = _process_all(days_back, push, new_only=True)
            if results:
                log.info(f"Processed {len(results)} new articles")
            else:
                log.info("No new articles")
        except Exception as e:
            log.error(f"Error during check: {e}")

        # Check XHS subscriptions
        try:
            xhs_subs = xhs_list_subscriptions()
            if xhs_subs.get("users") or xhs_subs.get("keywords"):
                log.info("Checking XHS subscriptions...")
                xhs_articles = xhs_fetch_all(days_back=days_back)
                if xhs_articles:
                    processed = _load_processed()
                    xhs_articles = [a for a in xhs_articles if a.id not in processed]
                    if xhs_articles:
                        log.info(f"Processing {len(xhs_articles)} new XHS notes...")
                        for article in sorted(xhs_articles, key=lambda a: a.publish_time):
                            try:
                                result = process_article(article)
                                _mark_processed(article.id)
                                if push and result["analysis"].level in ("A", "B"):
                                    push_to_dingtalk(result["analysis"], result["backtest"])
                                    time.sleep(2)
                            except Exception as e:
                                log.error(f"Error processing XHS note {article.title}: {e}")
                    else:
                        log.info("No new XHS notes")
        except Exception as e:
            log.error(f"Error during XHS check: {e}")

        # Periodically trigger article sync
        try:
            _trigger_sync_all()
        except Exception as e:
            log.error(f"Error triggering sync: {e}")

        log.info(f"Next check in {args.interval} min...")
        time.sleep(interval)


def _trigger_sync_all():
    """Trigger we-mp-rss to fetch latest articles for all accounts."""
    mps = _list_all_mps()
    for mp in mps:
        if mp["status"] != 1:
            continue
        try:
            _api("get", f"/mps/update/{mp['id']}", params={"start_page": 0, "end_page": 1})
        except Exception:
            pass  # rate-limited is fine


# ── XHS Commands ─────────────────────────────────────────────────


def cmd_xhs_subscribe(args):
    """Subscribe to an XHS user or add a search keyword."""
    if args.user:
        entry = xhs_subscribe_user(args.user, nickname=getattr(args, "nickname", "") or "")
        print(f"Subscribed to XHS user: {entry['nickname']} ({entry['user_id']})")
    elif args.keyword:
        entry = xhs_add_keyword(args.keyword)
        print(f"Added XHS keyword: {entry['keyword']}")
    else:
        print("ERROR: Provide --user <id_or_url> or --keyword <keyword>")


def cmd_xhs_list(args):
    """List XHS subscriptions."""
    subs = xhs_list_subscriptions()
    users = subs.get("users", [])
    keywords = subs.get("keywords", [])

    if not users and not keywords:
        print("No XHS subscriptions.")
        return

    if users:
        print("XHS Users:")
        for i, u in enumerate(users, 1):
            print(f"  {i}. {u['nickname']} - {u['url']} (since {u['added_at']})")

    if keywords:
        print("XHS Keywords:")
        for i, k in enumerate(keywords, 1):
            print(f"  {i}. {k['keyword']} (since {k['added_at']})")


def cmd_xhs_process(args):
    """Process XHS notes from subscriptions or search."""
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    push = not args.no_dingtalk
    new_only = getattr(args, "new_only", True)

    if args.search:
        log.info(f"Searching XHS for: {args.search}")
        articles = xhs_search_notes(args.search, max_notes=args.limit)
    elif args.user:
        log.info(f"Fetching notes for XHS user: {args.user}")
        articles = xhs_fetch_user_notes(args.user, max_notes=args.limit)
    else:
        log.info("Fetching all XHS subscriptions...")
        articles = xhs_fetch_all(days_back=args.days)

    if new_only:
        processed = _load_processed()
        before = len(articles)
        articles = [a for a in articles if a.id not in processed]
        log.info(f"New XHS notes: {len(articles)} (skipped {before - len(articles)})")

    if not articles:
        print("No new XHS notes to process.")
        return []

    results = []
    for article in sorted(articles, key=lambda a: a.publish_time):
        result = process_article(article)
        analysis = result["analysis"]
        backtest = result["backtest"]
        results.append((analysis, backtest))
        _mark_processed(article.id)

        if push and analysis.level in ("A", "B"):
            log.info("  Pushing to DingTalk...")
            push_to_dingtalk(analysis, backtest)
            time.sleep(2)

    if results:
        summary = generate_batch_summary(results)
        summary_path = os.path.join(config.RESULTS_DIR, "summary_xhs.md")
        with open(summary_path, "w") as f:
            f.write(summary)
        log.info(f"XHS summary saved: {summary_path}")

    return results


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Feeding Agent - WeChat quant article analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s subscribe --url https://mp.weixin.qq.com/s/xxx
  %(prog)s subscribe --url https://mp.weixin.qq.com/s/xxx --process --days 7
  %(prog)s process --name QuantML --days 7
  %(prog)s process --mp-id MP_WXS_3863007345
  %(prog)s process --all --days 7
  %(prog)s list
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # subscribe
    sub = subparsers.add_parser("subscribe", help="Subscribe a new public account")
    sub.add_argument("--url", required=True, help="WeChat article URL from the account")
    sub.add_argument("--name", default="", help="Override account name")
    sub.add_argument("--process", action="store_true", help="Also process recent articles")
    sub.add_argument("--days", type=int, default=7, help="Days back to fetch (with --process)")
    sub.add_argument("--no-dingtalk", action="store_true", help="Skip DingTalk push")

    # process
    proc = subparsers.add_parser("process", help="Process articles from subscribed accounts")
    group = proc.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Account name (fuzzy match)")
    group.add_argument("--mp-id", help="Account MP ID (exact)")
    group.add_argument("--url", help="Article URL (to identify account)")
    group.add_argument("--all", action="store_true", help="Process ALL subscribed accounts")
    proc.add_argument("--days", type=int, default=7, help="Days back to fetch")
    proc.add_argument("--new-only", action="store_true",
                      help="Skip already-processed articles")
    proc.add_argument("--no-dingtalk", action="store_true", help="Skip DingTalk push")

    # watch (daemon mode)
    watch = subparsers.add_parser("watch", help="Daemon: auto-check for new articles")
    watch.add_argument("--interval", type=int, default=60,
                       help="Check interval in minutes (default: 60)")
    watch.add_argument("--days", type=int, default=3,
                       help="Days back to look for articles (default: 3)")
    watch.add_argument("--no-dingtalk", action="store_true", help="Skip DingTalk push")

    # list
    subparsers.add_parser("list", help="List all subscribed accounts")

    # xhs-subscribe
    xhs_sub = subparsers.add_parser("xhs-subscribe", help="Subscribe to XHS user or keyword")
    xhs_sub_group = xhs_sub.add_mutually_exclusive_group(required=True)
    xhs_sub_group.add_argument("--user", help="XHS user ID or profile URL")
    xhs_sub_group.add_argument("--keyword", help="Search keyword to monitor")
    xhs_sub.add_argument("--nickname", default="", help="Nickname for the user")

    # xhs-list
    subparsers.add_parser("xhs-list", help="List XHS subscriptions")

    # xhs-process
    xhs_proc = subparsers.add_parser("xhs-process", help="Process XHS notes")
    xhs_proc_group = xhs_proc.add_mutually_exclusive_group()
    xhs_proc_group.add_argument("--search", help="Search keyword (one-off)")
    xhs_proc_group.add_argument("--user", help="Specific user ID")
    xhs_proc.add_argument("--days", type=int, default=7, help="Days back")
    xhs_proc.add_argument("--limit", type=int, default=20, help="Max notes to fetch")
    xhs_proc.add_argument("--new-only", action="store_true", default=True,
                          help="Skip already-processed notes")
    xhs_proc.add_argument("--no-dingtalk", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    if args.command == "subscribe":
        cmd_subscribe(args)
    elif args.command == "process":
        cmd_process(args)
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "xhs-subscribe":
        cmd_xhs_subscribe(args)
    elif args.command == "xhs-list":
        cmd_xhs_list(args)
    elif args.command == "xhs-process":
        cmd_xhs_process(args)


if __name__ == "__main__":
    main()
