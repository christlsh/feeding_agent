"""Generate reports and save results to the repo."""

import os
from core.fetcher import Article
from core.analyzer import AnalysisResult, format_summary_markdown, format_dingtalk_message
from core.implementer import BacktestResult
from core.notifier import send_dingtalk
import config


def save_article_results(
    article: Article,
    analysis: AnalysisResult,
    backtest: BacktestResult = None,
    extra_files: dict[str, str] = None,
):
    """Save all results for an article to the results directory."""
    folder = os.path.join(config.RESULTS_DIR, article.folder_name)
    os.makedirs(folder, exist_ok=True)

    # Save summary
    summary_md = format_summary_markdown(analysis)
    with open(os.path.join(folder, "summary.md"), "w") as f:
        f.write(summary_md)

    # Save backtest report if available
    if backtest and backtest.num_days > 0:
        report_md = backtest.to_markdown()
        with open(os.path.join(folder, "report.md"), "w") as f:
            f.write(report_md)

    # Save extra files (e.g., strategy code, plots)
    if extra_files:
        for filename, content in extra_files.items():
            with open(os.path.join(folder, filename), "w") as f:
                f.write(content)

    print(f"  Results saved to: {folder}")
    return folder


def push_to_dingtalk(analysis: AnalysisResult, backtest: BacktestResult = None):
    """Push article analysis summary to DingTalk."""
    msg = format_dingtalk_message(analysis)

    if backtest and backtest.num_days > 0:
        msg += "\n\n---\n"
        msg += f"**回测结果**: IC={backtest.ic_mean:.4f}, IR={backtest.ir:.2f}, "
        msg += f"LS Sharpe={backtest.long_short_sharpe:.2f}"

    title = f"[{analysis.level}] {analysis.title[:30]}"
    result = send_dingtalk(title, msg)
    return result


def generate_batch_summary(results: list[tuple[AnalysisResult, BacktestResult]]) -> str:
    """Generate a batch summary for multiple articles."""
    lines = ["# Weekly Article Processing Summary", ""]

    level_counts = {"A": 0, "B": 0, "C": 0}
    for analysis, _ in results:
        level_counts[analysis.level] = level_counts.get(analysis.level, 0) + 1

    lines += [
        f"- **Total Articles**: {len(results)}",
        f"- **Level A (Implementable)**: {level_counts.get('A', 0)}",
        f"- **Level B (Summary)**: {level_counts.get('B', 0)}",
        f"- **Level C (Low Relevance)**: {level_counts.get('C', 0)}",
        "",
        "## Articles",
        "",
    ]

    for analysis, backtest in results:
        level_marker = {"A": "🔴", "B": "🟡", "C": "⚪"}.get(analysis.level, "⚪")
        line = f"- {level_marker} **[{analysis.level}]** {analysis.date} - {analysis.title}"
        if backtest and backtest.num_days > 0:
            line += f" (IC={backtest.ic_mean:.4f}, Sharpe={backtest.long_short_sharpe:.2f})"
        lines.append(line)

    return "\n".join(lines)
