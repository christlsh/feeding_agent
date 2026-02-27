"""Fetch articles from we-mp-rss API."""

import requests
import re
from datetime import datetime, timedelta
from typing import Optional
import config
from utils.wx_fetcher import fetch_article_html, extract_text_from_html


class Article:
    def __init__(self, id: str, title: str, url: str, publish_time: int,
                 content_html: str = "", mp_name: str = "", mp_id: str = ""):
        self.id = id
        self.title = title
        self.url = url
        self.publish_time = publish_time
        self.publish_date = datetime.fromtimestamp(publish_time)
        self.content_html = content_html
        self.content_text = ""
        self.mp_name = mp_name
        self.mp_id = mp_id

    @property
    def date_str(self) -> str:
        return self.publish_date.strftime("%Y-%m-%d")

    @property
    def safe_title(self) -> str:
        """Sanitized title for filesystem use."""
        t = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', self.title)
        return t[:60].strip("_")

    @property
    def folder_name(self) -> str:
        return f"{self.date_str}_{self.safe_title}"

    def __repr__(self):
        return f"Article({self.date_str}, {self.title[:40]})"


def _get_token() -> str:
    resp = requests.post(
        f"{config.WERSS_BASE_URL}{config.WERSS_API_PREFIX}/auth/login",
        data={"username": config.WERSS_USERNAME, "password": config.WERSS_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    data = resp.json()
    return data["data"]["access_token"]


def _auth_headers() -> dict:
    token = _get_token()
    return {"Authorization": f"Bearer {token}"}


def fetch_articles(mp_id: str, limit: int = 20, days_back: int = 7) -> list[Article]:
    """Fetch recent articles for a public account from we-mp-rss."""
    headers = _auth_headers()
    resp = requests.get(
        f"{config.WERSS_BASE_URL}{config.WERSS_API_PREFIX}/articles",
        params={"mp_id": mp_id, "limit": limit, "has_content": "true"},
        headers=headers,
    )
    data = resp.json()
    articles_data = data.get("data", {}).get("list", [])

    cutoff = datetime.now() - timedelta(days=days_back)
    cutoff_ts = int(cutoff.timestamp())

    articles = []
    for a in articles_data:
        if a["publish_time"] < cutoff_ts:
            continue
        art = Article(
            id=a["id"],
            title=a.get("title", ""),
            url=a.get("url", ""),
            publish_time=a["publish_time"],
            content_html=a.get("content", "") or "",
            mp_name=a.get("mp_name", ""),
            mp_id=a.get("mp_id", mp_id),
        )
        articles.append(art)

    return articles


def ensure_content(article: Article) -> Article:
    """If article has no content from API, fetch directly from WeChat."""
    if article.content_html and len(article.content_html) > 100:
        return article
    if not article.url:
        return article
    print(f"  Fetching content from WeChat: {article.title[:40]}...")
    html = fetch_article_html(article.url)
    if html and "环境异常" not in html:
        # Extract the article body from the full page
        match = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*(?:<script|<div class="ct_mpda_wrp")',
                          html, re.DOTALL)
        if match:
            article.content_html = match.group(1)
        else:
            article.content_html = html
    return article
