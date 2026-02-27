"""Fetch WeChat article content directly via curl when we-mp-rss has no content."""

import subprocess
import re


def fetch_article_html(url: str) -> str:
    """Fetch a WeChat article's HTML using curl with browser-like headers."""
    cmd = [
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
        "-H", "Referer: https://mp.weixin.qq.com/",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout


def extract_text_from_html(html: str) -> str:
    """Extract readable text from WeChat article HTML."""
    # Remove script/style tags
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # Replace common block elements with newlines
    html = re.sub(r"<(?:br|p|div|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", html)
    # Decode HTML entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"')
    # Clean up whitespace
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def fetch_article_text(url: str) -> str:
    """Fetch and extract text from a WeChat article."""
    html = fetch_article_html(url)
    if not html or "环境异常" in html:
        return ""
    return extract_text_from_html(html)
