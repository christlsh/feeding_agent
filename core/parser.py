"""Parse article HTML into structured content."""

import re
from dataclasses import dataclass, field


@dataclass
class ParsedArticle:
    title: str = ""
    text: str = ""
    code_blocks: list[str] = field(default_factory=list)
    paper_links: list[str] = field(default_factory=list)
    github_links: list[str] = field(default_factory=list)
    key_formulas: list[str] = field(default_factory=list)
    images_count: int = 0


def parse_html(html: str, title: str = "") -> ParsedArticle:
    """Parse article HTML into structured content."""
    result = ParsedArticle(title=title)

    if not html:
        return result

    # Count images
    result.images_count = len(re.findall(r"<img[^>]+>", html, re.IGNORECASE))

    # Extract code blocks
    code_patterns = [
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>",
        r"<pre[^>]*>(.*?)</pre>",
    ]
    for pat in code_patterns:
        for match in re.finditer(pat, html, re.DOTALL):
            code = _strip_tags(match.group(1)).strip()
            if len(code) > 20:
                result.code_blocks.append(code)

    # Extract paper links (arxiv, openreview, etc.)
    url_pattern = r'href="([^"]*(?:arxiv|openreview|papers\.ssrn|doi\.org)[^"]*)"'
    result.paper_links = list(set(re.findall(url_pattern, html, re.IGNORECASE)))

    # Extract github links
    gh_pattern = r'href="(https?://github\.com/[^"]+)"'
    result.github_links = list(set(re.findall(gh_pattern, html, re.IGNORECASE)))

    # Extract formulas (LaTeX patterns)
    formula_patterns = [
        r"\$\$([^$]+)\$\$",
        r"\\\[(.+?)\\\]",
        r"\\\((.+?)\\\)",
    ]
    for pat in formula_patterns:
        for match in re.finditer(pat, html, re.DOTALL):
            formula = match.group(1).strip()
            if len(formula) > 5:
                result.key_formulas.append(formula)

    # Extract clean text
    result.text = _html_to_text(html)

    return result


def _strip_tags(html: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", "", html)


def _html_to_text(html: str) -> str:
    """Convert HTML to readable text."""
    # Remove script/style
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Block elements to newlines
    text = re.sub(r"<(?:br|p|div|h[1-6]|li|tr|section)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip tags
    text = _strip_tags(text)
    # Decode entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    # Clean whitespace
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    # Collapse consecutive empty-looking lines
    result = []
    for line in lines:
        if len(line) < 2 and result and len(result[-1]) < 2:
            continue
        result.append(line)
    return "\n".join(result)
