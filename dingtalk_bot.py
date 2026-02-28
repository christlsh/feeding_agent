"""
DingTalk Stream Bot — bidirectional chat interface for the feeding agent.

Usage:
  # Set credentials via env (recommended)
  export DINGTALK_APP_KEY=your_app_key
  export DINGTALK_APP_SECRET=your_app_secret
  python dingtalk_bot.py

  # Or fill DINGTALK_APP_KEY / DINGTALK_APP_SECRET directly in config.py

  # Daemon mode
  nohup python dingtalk_bot.py > logs/dingtalk_bot.log 2>&1 &

Prerequisites:
  1. Create Enterprise Internal App at https://open-dev.dingtalk.com
  2. Enable Robot capability with Stream Mode
  3. Add bot to your DingTalk group
"""

import sys
import os
import re
import json
import logging
import threading
import traceback
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

import dingtalk_stream
from dingtalk_stream import AckMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("dingtalk_bot")

# ── Lazy imports from run.py (avoid circular / heavy init at module level) ──


def _import_run():
    """Import run module lazily to avoid heavy startup cost."""
    import run
    return run


# ── Command handlers ─────────────────────────────────────────────


def handle_help() -> str:
    return (
        "### Feeding Agent 命令列表\n\n"
        "| 命令 | 说明 |\n"
        "|------|------|\n"
        "| **帮助** / **help** | 显示此帮助 |\n"
        "| **列表** / **list** | 列出已订阅公众号 |\n"
        "| **进度** / **状态** | 查看处理进度 |\n"
        "| **订阅** `<url>` | 订阅新公众号 |\n"
        "| **处理** `<name>` / **分析** `<name>` | 处理指定公众号文章 |\n"
        "| **结果** `<keyword>` | 搜索策略结果 |\n"
    )


def handle_list() -> str:
    run = _import_run()
    mps = run._list_all_mps()
    if not mps:
        return "当前没有已订阅的公众号。"

    lines = ["### 已订阅公众号\n"]
    for i, mp in enumerate(mps, 1):
        status = "Active" if mp["status"] == 1 else "Off"
        lines.append(f"{i}. **{mp['mp_name']}** ({status}) - {mp['created_at'][:10]}")
    return "\n".join(lines)


def handle_status() -> str:
    run = _import_run()
    mps = run._list_all_mps()

    # Count processed articles
    processed = run._load_processed()

    # Count result folders
    result_dirs = []
    if os.path.isdir(config.RESULTS_DIR):
        result_dirs = [
            d for d in os.listdir(config.RESULTS_DIR)
            if os.path.isdir(os.path.join(config.RESULTS_DIR, d))
        ]

    lines = [
        "### 系统状态\n",
        f"- 已订阅公众号: **{len(mps)}**",
        f"- 已处理文章数: **{len(processed)}**",
        f"- 结果文件夹数: **{len(result_dirs)}**",
    ]

    # Show recent results (last 5)
    if result_dirs:
        result_dirs.sort(reverse=True)
        lines.append("\n**最近处理:**")
        for d in result_dirs[:5]:
            lines.append(f"- {d}")

    return "\n".join(lines)


def handle_subscribe(url: str, reply_fn) -> str:
    """Subscribe a new account. Runs in background thread."""
    if not url.startswith("http"):
        return "请提供有效的微信文章链接，例如: 订阅 https://mp.weixin.qq.com/s/xxx"

    reply_fn("正在订阅，请稍候...")

    try:
        run = _import_run()
        args = Namespace(url=url, name="", process=False, days=7, no_dingtalk=True)
        result = run.cmd_subscribe(args)
        if result:
            return f"订阅成功! MP ID: `{result}`"
        else:
            return "订阅失败，请检查链接是否有效。"
    except Exception as e:
        log.error(f"Subscribe error: {e}\n{traceback.format_exc()}")
        return f"订阅出错: {e}"


def handle_process(name: str, reply_fn) -> str:
    """Process articles for a named account. Runs in background thread."""
    run = _import_run()
    mp = run._lookup_mp(name=name)
    if not mp:
        return f"未找到公众号: {name}\n请用 **列表** 查看已订阅的公众号。"

    reply_fn(f"正在处理 **{mp['mp_name']}** 的文章，请稍候...")

    try:
        results = run.cmd_process_mp(
            mp["id"], days_back=7, push_dingtalk=False,
            mp_name=mp["mp_name"], new_only=True,
        )
        if not results:
            return f"**{mp['mp_name']}**: 没有新文章需要处理。"

        lines = [f"**{mp['mp_name']}** 处理完成，共 {len(results)} 篇:\n"]
        for analysis, backtest in results:
            level_marker = {"A": "🔴", "B": "🟡", "C": "⚪"}.get(analysis.level, "⚪")
            line = f"- {level_marker} [{analysis.level}] {analysis.title}"
            if backtest and backtest.num_days > 0:
                line += f" (IC={backtest.ic_mean:.4f})"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        log.error(f"Process error: {e}\n{traceback.format_exc()}")
        return f"处理出错: {e}"


def handle_search(keyword: str) -> str:
    """Search result folders for a keyword."""
    if not os.path.isdir(config.RESULTS_DIR):
        return "暂无结果数据。"

    matches = []
    for dirname in sorted(os.listdir(config.RESULTS_DIR), reverse=True):
        dirpath = os.path.join(config.RESULTS_DIR, dirname)
        if not os.path.isdir(dirpath):
            continue
        if keyword.lower() in dirname.lower():
            # Check for summary/report
            has_summary = os.path.exists(os.path.join(dirpath, "summary.md"))
            has_report = os.path.exists(os.path.join(dirpath, "report.md"))
            tag = ""
            if has_report:
                tag = " [有回测]"
            elif has_summary:
                tag = " [有摘要]"
            matches.append(f"- {dirname}{tag}")

    if not matches:
        return f"未找到与 **{keyword}** 相关的结果。"

    header = f"### 搜索结果: {keyword}\n"
    # Cap at 10
    if len(matches) > 10:
        return header + "\n".join(matches[:10]) + f"\n\n...共 {len(matches)} 条"
    return header + "\n".join(matches)


# ── Command router ───────────────────────────────────────────────


def route_command(text: str, reply_fn):
    """
    Parse user text and route to the appropriate handler.
    Returns (response_text, is_async).
    is_async=True means the handler will call reply_fn itself when done.
    """
    text = text.strip()

    # Help
    if text in ("帮助", "help", "?", "？"):
        return handle_help(), False

    # List
    if text in ("列表", "list", "ls"):
        return handle_list(), False

    # Status
    if text in ("进度", "状态", "status"):
        return handle_status(), False

    # Subscribe: 订阅 <url>
    m = re.match(r"(?:订阅|subscribe)\s+(\S+)", text, re.IGNORECASE)
    if m:
        url = m.group(1)
        return handle_subscribe(url, reply_fn), True

    # Process: 处理/分析 <name>
    m = re.match(r"(?:处理|分析|process|analyze)\s+(.+)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        return handle_process(name, reply_fn), True

    # Search: 结果 <keyword>
    m = re.match(r"(?:结果|搜索|search|result)\s+(.+)", text, re.IGNORECASE)
    if m:
        keyword = m.group(1).strip()
        return handle_search(keyword), False

    # Unknown
    return "未识别的命令。发送 **帮助** 查看可用命令。", False


# ── DingTalk Stream handler ──────────────────────────────────────


class FeedingAgentHandler(dingtalk_stream.ChatbotHandler):
    """Handle incoming @mention messages from DingTalk group."""

    def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        text = (incoming.text.content or "").strip()
        sender = incoming.sender_nick or "unknown"
        webhook = incoming.session_webhook

        log.info(f"Message from {sender}: {text}")

        if not text:
            self.reply_text("发送 **帮助** 查看可用命令。", incoming)
            return AckMessage.STATUS_OK, "OK"

        def reply_fn(msg):
            """Send an intermediate reply via session webhook."""
            self._reply_via_webhook(webhook, msg)

        def run_async(handler_fn, *args):
            """Run a long operation in background, reply when done."""
            def _worker():
                try:
                    result = handler_fn(*args)
                    self._reply_via_webhook(webhook, result)
                except Exception as e:
                    log.error(f"Async handler error: {e}\n{traceback.format_exc()}")
                    self._reply_via_webhook(webhook, f"执行出错: {e}")
            t = threading.Thread(target=_worker, daemon=True)
            t.start()

        # Check if command is long-running
        text_lower = text.strip()
        is_long = any(text_lower.startswith(p) for p in
                       ("订阅", "subscribe", "处理", "分析", "process", "analyze"))

        if is_long:
            # For long-running commands, handle_subscribe/handle_process
            # call reply_fn for intermediate updates and return final result
            m_sub = re.match(r"(?:订阅|subscribe)\s+(\S+)", text, re.IGNORECASE)
            m_proc = re.match(r"(?:处理|分析|process|analyze)\s+(.+)", text, re.IGNORECASE)

            if m_sub:
                run_async(handle_subscribe, m_sub.group(1), reply_fn)
            elif m_proc:
                run_async(handle_process, m_proc.group(1).strip(), reply_fn)

            return AckMessage.STATUS_OK, "OK"
        else:
            response, _ = route_command(text, reply_fn)
            self.reply_text(response, incoming)
            return AckMessage.STATUS_OK, "OK"

    def _reply_via_webhook(self, webhook: str, text: str):
        """Reply to the group conversation via session webhook."""
        import requests
        try:
            resp = requests.post(webhook, json={
                "msgtype": "markdown",
                "markdown": {"title": "Feeding Agent", "text": text},
            }, timeout=10)
            if resp.status_code != 200:
                log.error(f"Webhook reply failed: {resp.status_code} {resp.text}")
        except Exception as e:
            log.error(f"Webhook reply error: {e}")


# ── Main ─────────────────────────────────────────────────────────


def main():
    app_key = config.DINGTALK_APP_KEY
    app_secret = config.DINGTALK_APP_SECRET

    if not app_key or not app_secret:
        print("ERROR: DINGTALK_APP_KEY and DINGTALK_APP_SECRET must be set.")
        print("Set them in config.py or via environment variables:")
        print("  export DINGTALK_APP_KEY=your_key")
        print("  export DINGTALK_APP_SECRET=your_secret")
        sys.exit(1)

    credential = dingtalk_stream.Credential(app_key, app_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC,
        FeedingAgentHandler(),
    )

    log.info("DingTalk bot starting (Stream mode)...")
    log.info(f"AppKey: {app_key[:6]}***")
    log.info(f"PID: {os.getpid()}")
    client.start_forever()


if __name__ == "__main__":
    main()
