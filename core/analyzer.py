"""Analyze articles and generate structured summaries."""

from dataclasses import dataclass, field
from core.parser import ParsedArticle
from core.classifier import Classification


@dataclass
class AnalysisResult:
    title: str = ""
    date: str = ""
    url: str = ""
    level: str = ""
    category: str = ""
    relevance: float = 0.0

    # Summary
    summary: str = ""
    core_idea: str = ""
    methodology: str = ""
    key_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    # Implementation potential
    implementable: bool = False
    implementation_notes: str = ""
    data_requirements: list[str] = field(default_factory=list)
    estimated_complexity: str = ""  # "simple", "moderate", "complex"

    # References
    paper_links: list[str] = field(default_factory=list)
    github_links: list[str] = field(default_factory=list)


def analyze(parsed: ParsedArticle, classification: Classification,
            date_str: str = "", url: str = "") -> AnalysisResult:
    """Generate a structured analysis of the article."""
    result = AnalysisResult(
        title=parsed.title,
        date=date_str,
        url=url,
        level=classification.level,
        category=classification.category,
        relevance=classification.relevance,
        paper_links=parsed.paper_links,
        github_links=parsed.github_links,
    )

    text = parsed.text
    if not text:
        result.summary = "No content available for analysis."
        return result

    # Extract summary from first ~500 chars
    paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 20]
    if paragraphs:
        # Use first few substantial paragraphs as summary
        summary_parts = []
        char_count = 0
        for p in paragraphs[:10]:
            if char_count > 800:
                break
            summary_parts.append(p)
            char_count += len(p)
        result.summary = "\n".join(summary_parts)

    # Extract core idea - look for key indicators
    idea_keywords = ["提出", "propose", "本文", "我们", "核心", "关键", "创新",
                     "方法", "framework", "模型", "model", "算法", "algorithm"]
    for p in paragraphs:
        if any(kw in p.lower() for kw in idea_keywords) and len(p) > 30:
            result.core_idea = p[:300]
            break

    # Extract methodology
    method_keywords = ["方法", "method", "步骤", "流程", "pipeline", "架构",
                       "实现", "implement", "训练", "train", "特征", "feature"]
    method_parts = []
    for p in paragraphs:
        if any(kw in p.lower() for kw in method_keywords) and len(p) > 30:
            method_parts.append(p[:200])
            if len(method_parts) >= 3:
                break
    result.methodology = "\n".join(method_parts)

    # Extract key findings
    finding_keywords = ["结果", "result", "发现", "实验表明", "表现", "performance",
                        "提升", "improve", "优于", "outperform", "夏普", "sharpe",
                        "IC", "收益", "return", "alpha"]
    for p in paragraphs:
        if any(kw in p.lower() for kw in finding_keywords) and len(p) > 20:
            result.key_findings.append(p[:200])
            if len(result.key_findings) >= 5:
                break

    # Determine implementation details
    if classification.level == "A":
        result.implementable = True
        result.estimated_complexity = _estimate_complexity(parsed, classification)
        result.data_requirements = _determine_data_needs(text, classification.category)
        result.implementation_notes = _generate_impl_notes(parsed, classification)
    elif classification.level == "B":
        result.implementable = False
        if classification.needs_gpu:
            result.implementation_notes = "Requires GPU for model training. Summary only."
        else:
            result.implementation_notes = "Theoretical/high-level content. Summary provided."

    return result


def _estimate_complexity(parsed: ParsedArticle, classification: Classification) -> str:
    has_code = len(parsed.code_blocks) > 0
    has_formulas = len(parsed.key_formulas) > 0

    if has_code and not has_formulas:
        return "simple"
    elif has_code and has_formulas:
        return "moderate"
    elif has_formulas and not has_code:
        return "moderate"
    else:
        return "complex"


def _determine_data_needs(text: str, category: str) -> list[str]:
    needs = []
    text_lower = text.lower()

    if any(kw in text_lower for kw in ["orderbook", "订单簿", "盘口", "买卖", "bid", "ask"]):
        needs.append("L2 orderbook")
    if any(kw in text_lower for kw in ["收益", "return", "预测", "predict"]):
        needs.append("forward returns")
    if any(kw in text_lower for kw in ["barra", "风险模型", "risk model", "因子载荷", "loading"]):
        needs.append("Barra risk model")
    if any(kw in text_lower for kw in ["成分", "权重", "index", "沪深300", "csi"]):
        needs.append("index weights")
    if any(kw in text_lower for kw in ["vwap", "执行", "滑点"]):
        needs.append("VWAP")
    if any(kw in text_lower for kw in ["涨跌停", "停牌", "limit"]):
        needs.append("limit status")

    if not needs:
        needs.append("forward returns")  # default for most strategies

    return needs


def _generate_impl_notes(parsed: ParsedArticle, classification: Classification) -> str:
    notes = []

    if parsed.github_links:
        notes.append(f"Reference code: {parsed.github_links[0]}")
    if parsed.paper_links:
        notes.append(f"Paper: {parsed.paper_links[0]}")
    if parsed.code_blocks:
        notes.append(f"Article contains {len(parsed.code_blocks)} code snippets")

    category_notes = {
        "factor_mining": "Implement as cross-sectional factor, evaluate with IC/IR and quintile returns",
        "portfolio_optimization": "Test with Barra risk model and index universe",
        "execution": "Evaluate against VWAP benchmark using L2 data",
        "market_microstructure": "Analyze using L2 orderbook features",
        "ml_strategy": "Implement simplified version without GPU requirements",
    }
    if classification.category in category_notes:
        notes.append(category_notes[classification.category])

    return "; ".join(notes)


def format_summary_markdown(result: AnalysisResult) -> str:
    """Format analysis result as a markdown summary file."""
    lines = [
        f"# {result.title}",
        "",
        f"- **Date**: {result.date}",
        f"- **URL**: {result.url}",
        f"- **Level**: {result.level} ({_level_desc(result.level)})",
        f"- **Category**: {result.category}",
        f"- **Relevance**: {result.relevance:.2f}",
        "",
    ]

    if result.summary:
        lines += ["## Summary", "", result.summary[:1500], ""]

    if result.core_idea:
        lines += ["## Core Idea", "", result.core_idea, ""]

    if result.methodology:
        lines += ["## Methodology", "", result.methodology, ""]

    if result.key_findings:
        lines += ["## Key Findings", ""]
        for f in result.key_findings:
            lines.append(f"- {f}")
        lines.append("")

    if result.implementable:
        lines += [
            "## Implementation",
            "",
            f"- **Complexity**: {result.estimated_complexity}",
            f"- **Data Required**: {', '.join(result.data_requirements)}",
            f"- **Notes**: {result.implementation_notes}",
            "",
        ]

    if result.paper_links:
        lines += ["## References", ""]
        for link in result.paper_links:
            lines.append(f"- {link}")
        lines.append("")

    if result.github_links:
        lines += ["## Code", ""]
        for link in result.github_links:
            lines.append(f"- {link}")
        lines.append("")

    return "\n".join(lines)


def format_dingtalk_message(result: AnalysisResult) -> str:
    """Format analysis result as a DingTalk markdown message."""
    level_emoji = {"A": "🔴", "B": "🟡", "C": "⚪"}
    emoji = level_emoji.get(result.level, "⚪")

    lines = [
        f"### {emoji} [{result.level}] {result.title}",
        "",
        f"> 日期: {result.date} | 类别: {result.category} | 相关度: {result.relevance:.0%}",
        "",
    ]

    if result.summary:
        # Truncate for DingTalk
        summary = result.summary[:400]
        if len(result.summary) > 400:
            summary += "..."
        lines += [summary, ""]

    if result.key_findings:
        lines += ["**关键发现:**", ""]
        for f in result.key_findings[:3]:
            lines.append(f"- {f[:100]}")
        lines.append("")

    if result.implementable:
        lines += [
            f"**可实现**: {result.estimated_complexity} | 数据: {', '.join(result.data_requirements)}",
            "",
        ]

    if result.url:
        lines.append(f"[原文链接]({result.url})")

    return "\n".join(lines)


def _level_desc(level: str) -> str:
    return {"A": "Implementable", "B": "Summary Only", "C": "Low Relevance"}.get(level, "Unknown")
