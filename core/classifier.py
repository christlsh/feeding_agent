"""Classify article relevance and determine processing strategy."""

from dataclasses import dataclass
from core.parser import ParsedArticle


@dataclass
class Classification:
    level: str          # "A" = implementable, "B" = summarize, "C" = low relevance
    relevance: float    # 0-1
    category: str       # e.g. "factor_mining", "portfolio_optimization", "news", "tool_review"
    reason: str
    needs_gpu: bool = False
    has_data: bool = False


# Keywords indicating quant-relevant content
QUANT_KEYWORDS_HIGH = [
    "因子", "alpha", "factor", "回测", "backtest", "策略", "strategy",
    "收益预测", "return prediction", "IC", "IR", "夏普", "sharpe",
    "组合优化", "portfolio", "风险模型", "risk model", "barra",
    "orderbook", "订单簿", "高频", "HFT", "做市", "market making",
    "动量", "momentum", "反转", "reversal", "价量", "price-volume",
    "截面", "cross-section", "时序", "time-series",
    "信号", "signal", "选股", "stock selection", "排序", "ranking",
    "分组收益", "quintile", "decile", "多空", "long-short",
    "执行", "execution", "VWAP", "TWAP", "滑点", "slippage",
]

QUANT_KEYWORDS_MED = [
    "机器学习", "deep learning", "深度学习", "神经网络", "neural",
    "强化学习", "reinforcement", "transformer", "attention",
    "图神经网络", "GNN", "graph neural",
    "NLP", "文本", "情绪", "sentiment", "事件驱动", "event-driven",
    "大模型", "LLM", "GPT", "量化", "quant",
    "金融", "finance", "市场", "market", "交易", "trading",
    "资产配置", "asset allocation", "对冲", "hedge",
]

GPU_KEYWORDS = [
    "GPU", "CUDA", "训练", "training", "fine-tune", "微调",
    "大模型", "LLM", "transformer", "bert", "预训练", "pre-train",
    "强化学习", "reinforcement learning", "RL", "PPO", "SAC", "DQN",
    "GNN", "图神经网络", "graph neural",
    "CNN", "RNN", "LSTM", "GRU",
]

LOW_RELEVANCE_KEYWORDS = [
    "交流群", "社群", "加群", "特惠", "优惠", "课程", "培训",
    "广告", "推广", "招聘", "求职",
]

# Categories based on content
CATEGORY_PATTERNS = {
    "factor_mining": ["因子", "alpha", "factor", "选股", "IC", "IR", "截面"],
    "portfolio_optimization": ["组合优化", "portfolio", "资产配置", "asset allocation", "风险模型"],
    "execution": ["执行", "execution", "VWAP", "TWAP", "滑点", "orderbook", "做市"],
    "ml_strategy": ["机器学习", "深度学习", "neural", "transformer", "强化学习"],
    "event_driven": ["事件驱动", "event", "新闻", "情绪", "sentiment", "NLP"],
    "market_microstructure": ["高频", "微观结构", "订单簿", "tick", "买卖价差"],
    "risk_management": ["风控", "风险管理", "VaR", "drawdown", "回撤"],
    "market_news": ["崩盘", "内幕", "监管", "诉讼", "IPO"],
    "tool_review": ["工具", "平台", "API", "软件", "框架", "开源"],
}


def classify(parsed: ParsedArticle) -> Classification:
    """Classify an article based on its parsed content."""
    text_lower = (parsed.title + " " + parsed.text[:3000]).lower()

    # Check for low relevance first
    for kw in LOW_RELEVANCE_KEYWORDS:
        if kw in text_lower:
            return Classification(
                level="C", relevance=0.1, category="advertisement",
                reason=f"Low relevance: matches '{kw}'"
            )

    # Count keyword matches
    high_matches = sum(1 for kw in QUANT_KEYWORDS_HIGH if kw.lower() in text_lower)
    med_matches = sum(1 for kw in QUANT_KEYWORDS_MED if kw.lower() in text_lower)
    gpu_matches = sum(1 for kw in GPU_KEYWORDS if kw.lower() in text_lower)

    relevance = min(1.0, (high_matches * 0.15 + med_matches * 0.08))
    needs_gpu = gpu_matches >= 3

    # Determine category
    category = "general"
    max_cat_score = 0
    for cat, keywords in CATEGORY_PATTERNS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > max_cat_score:
            max_cat_score = score
            category = cat

    # Has code or paper = more likely implementable
    has_code = len(parsed.code_blocks) > 0 or len(parsed.github_links) > 0
    has_paper = len(parsed.paper_links) > 0

    # Determine if we have relevant data
    data_relevant_categories = {"factor_mining", "portfolio_optimization", "execution",
                                "market_microstructure", "risk_management"}
    has_data = category in data_relevant_categories

    # Level assignment
    if relevance < 0.2:
        level = "C"
        reason = f"Low quant relevance (score={relevance:.2f})"
    elif needs_gpu and not has_code:
        level = "B"
        reason = f"Relevant (score={relevance:.2f}) but likely needs GPU training"
    elif has_data and (has_code or relevance >= 0.5):
        level = "A"
        reason = f"Implementable: {category}, relevance={relevance:.2f}, has_code={has_code}"
    elif relevance >= 0.3:
        level = "B"
        reason = f"Relevant but not directly implementable: {category}"
    else:
        level = "C"
        reason = f"Marginal relevance (score={relevance:.2f})"

    return Classification(
        level=level, relevance=relevance, category=category,
        reason=reason, needs_gpu=needs_gpu, has_data=has_data,
    )
