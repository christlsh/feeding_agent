"""Main entry point: process articles from a WeChat public account."""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from core.fetcher import fetch_articles, ensure_content, Article
from core.parser import parse_html
from core.classifier import classify
from core.analyzer import analyze, format_summary_markdown, format_dingtalk_message
from core.reporter import save_article_results, push_to_dingtalk, generate_batch_summary
from core.notifier import send_dingtalk


def process_article(article: Article) -> dict:
    """Process a single article through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"Processing: {article.title}")
    print(f"Date: {article.date_str}, URL: {article.url}")

    # Step 1: Ensure content
    article = ensure_content(article)

    # Step 2: Parse
    parsed = parse_html(article.content_html, title=article.title)
    print(f"  Parsed: {len(parsed.text)} chars, {len(parsed.code_blocks)} code blocks, "
          f"{len(parsed.paper_links)} papers, {len(parsed.github_links)} github links")

    # Step 3: Classify
    classification = classify(parsed)
    print(f"  Classification: Level={classification.level}, "
          f"Category={classification.category}, Relevance={classification.relevance:.2f}")
    print(f"  Reason: {classification.reason}")

    # Step 4: Analyze
    analysis = analyze(parsed, classification, date_str=article.date_str, url=article.url)

    # Step 5: Save results
    backtest = None
    extra_files = {}

    save_article_results(article, analysis, backtest, extra_files)

    return {
        "article": article,
        "parsed": parsed,
        "classification": classification,
        "analysis": analysis,
        "backtest": backtest,
    }


def process_mp(mp_id: str, days_back: int = 7, push_dingtalk: bool = True):
    """Process all recent articles from a public account."""
    print(f"Fetching articles for mp_id={mp_id}, last {days_back} days...")
    articles = fetch_articles(mp_id, limit=30, days_back=days_back)
    print(f"Found {len(articles)} articles")

    results = []
    for article in sorted(articles, key=lambda a: a.publish_time):
        result = process_article(article)
        analysis = result["analysis"]
        backtest = result["backtest"]
        results.append((analysis, backtest))

        # Push to DingTalk for Level A and B articles
        if push_dingtalk and analysis.level in ("A", "B"):
            print(f"  Pushing to DingTalk...")
            push_to_dingtalk(analysis, backtest)
            time.sleep(2)  # Rate limit

    # Generate batch summary
    if results:
        summary = generate_batch_summary(results)
        summary_path = os.path.join(config.RESULTS_DIR, "weekly_summary.md")
        with open(summary_path, "w") as f:
            f.write(summary)
        print(f"\nBatch summary saved to: {summary_path}")

        # Push batch summary to DingTalk
        if push_dingtalk:
            level_a = sum(1 for a, _ in results if a.level == "A")
            level_b = sum(1 for a, _ in results if a.level == "B")
            batch_msg = (
                f"### 📊 Weekly Article Summary\n\n"
                f"- Total: {len(results)} articles\n"
                f"- Level A (Implementable): {level_a}\n"
                f"- Level B (Summary): {level_b}\n"
            )
            send_dingtalk("Weekly Summary", batch_msg)

    return results


def main():
    parser = argparse.ArgumentParser(description="Feeding Agent - WeChat article analyzer")
    parser.add_argument("--mp-id", default="MP_WXS_3863007345", help="Public account MP ID")
    parser.add_argument("--days", type=int, default=7, help="Days back to fetch")
    parser.add_argument("--no-dingtalk", action="store_true", help="Skip DingTalk notifications")
    args = parser.parse_args()

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    process_mp(args.mp_id, days_back=args.days, push_dingtalk=not args.no_dingtalk)


if __name__ == "__main__":
    main()
