"""
Telegram Bot — Claude Opus-powered AI agent for the feeding agent.

Usage:
  python telegram_bot.py

  # Daemon mode
  nohup python telegram_bot.py > logs/telegram_bot.log 2>&1 &

Prerequisites:
  1. Create bot via @BotFather on Telegram
  2. Set TELEGRAM_BOT_TOKEN in config.py or env
  3. Set ANTHROPIC_API_KEY in config.py or env
  4. pip install anthropic "python-telegram-bot[job-queue]"
"""

import sys
import os
import re
import json
import logging
import traceback
import subprocess
import requests
from argparse import Namespace
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("telegram_bot")


# ── Lazy imports from run.py ─────────────────────────────────────


def _import_run():
    import run
    return run


# ── Conversation memory ──────────────────────────────────────────

MAX_HISTORY = 50  # keep last N messages per chat

# chat_id -> list of {"role": "user"/"assistant", "content": ...}
_conversations: dict[int, list[dict]] = defaultdict(list)


def _add_message(chat_id: int, role: str, content: str):
    history = _conversations[chat_id]
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        _conversations[chat_id] = history[-MAX_HISTORY:]


def _get_history(chat_id: int) -> list[dict]:
    return list(_conversations[chat_id])


# ── Tool implementations ─────────────────────────────────────────


def tool_list_accounts() -> str:
    run = _import_run()
    mps = run._list_all_mps()
    if not mps:
        return "当前没有已订阅的公众号。"
    lines = []
    for i, mp in enumerate(mps, 1):
        status = "Active" if mp["status"] == 1 else "Off"
        lines.append(f"{i}. {mp['mp_name']} ({status}) - 订阅于 {mp['created_at'][:10]}")
    return "\n".join(lines)


def tool_get_status() -> str:
    run = _import_run()
    mps = run._list_all_mps()
    processed = run._load_processed()

    result_dirs = []
    if os.path.isdir(config.RESULTS_DIR):
        result_dirs = [
            d for d in os.listdir(config.RESULTS_DIR)
            if os.path.isdir(os.path.join(config.RESULTS_DIR, d))
        ]

    info = {
        "subscribed_accounts": len(mps),
        "processed_articles": len(processed),
        "result_folders": len(result_dirs),
    }

    if result_dirs:
        result_dirs.sort(reverse=True)
        info["recent_results"] = result_dirs[:8]

    return json.dumps(info, ensure_ascii=False)


def tool_subscribe_account(url: str) -> str:
    if not url.startswith("http"):
        return "错误: 请提供有效的微信文章链接，例如 https://mp.weixin.qq.com/s/xxx"
    try:
        run = _import_run()
        args = Namespace(url=url, name="", process=True, days=30, no_dingtalk=True)
        result = run.cmd_subscribe(args)
        if result:
            if isinstance(result, list):
                # process=True returns list of (analysis, backtest)
                lines = [f"订阅成功! 已自动处理最近30天文章，共 {len(result)} 篇:"]
                for analysis, backtest in result:
                    line = f"- [{analysis.level}] {analysis.title}"
                    if backtest and backtest.num_days > 0:
                        line += f" (IC={backtest.ic_mean:.4f})"
                    lines.append(line)
                return "\n".join(lines)
            return f"订阅成功! MP ID: {result} (无近30天新文章)"
        else:
            return "订阅失败，请检查链接是否有效。"
    except Exception as e:
        log.error(f"Subscribe error: {e}\n{traceback.format_exc()}")
        return f"订阅出错: {e}"


def tool_process_account(name: str) -> str:
    run = _import_run()
    mp = run._lookup_mp(name=name)
    if not mp:
        return f"未找到公众号: {name}。请使用 list_accounts 工具查看已订阅的公众号。"
    try:
        results = run.cmd_process_mp(
            mp["id"], days_back=7, push_dingtalk=False,
            mp_name=mp["mp_name"], new_only=True,
        )
        if not results:
            return f"{mp['mp_name']}: 没有新文章需要处理。"

        lines = [f"{mp['mp_name']} 处理完成，共 {len(results)} 篇:"]
        for analysis, backtest in results:
            line = f"- [{analysis.level}] {analysis.title}"
            if backtest and backtest.num_days > 0:
                line += f" (IC={backtest.ic_mean:.4f})"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        log.error(f"Process error: {e}\n{traceback.format_exc()}")
        return f"处理出错: {e}"


def tool_search_results(keyword: str) -> str:
    if not os.path.isdir(config.RESULTS_DIR):
        return "暂无结果数据。"

    matches = []
    for dirname in sorted(os.listdir(config.RESULTS_DIR), reverse=True):
        dirpath = os.path.join(config.RESULTS_DIR, dirname)
        if not os.path.isdir(dirpath):
            continue
        if keyword.lower() in dirname.lower():
            files = os.listdir(dirpath)
            has_summary = "summary.md" in files
            has_report = "report.md" in files
            has_strategy = any(f.endswith(".py") for f in files)
            tag_parts = []
            if has_summary:
                tag_parts.append("摘要")
            if has_report:
                tag_parts.append("回测")
            if has_strategy:
                tag_parts.append("策略代码")
            tag = f" [{', '.join(tag_parts)}]" if tag_parts else ""
            matches.append(f"- {dirname}{tag}")

    if not matches:
        return f"未找到与 '{keyword}' 相关的结果。"

    result = f"搜索 '{keyword}' 找到 {len(matches)} 条结果:\n"
    if len(matches) > 15:
        result += "\n".join(matches[:15]) + f"\n\n...共 {len(matches)} 条，仅显示前15条"
    else:
        result += "\n".join(matches)
    return result


def tool_read_summary(folder_name: str) -> str:
    path = os.path.join(config.RESULTS_DIR, folder_name, "summary.md")
    if not os.path.exists(path):
        if os.path.isdir(config.RESULTS_DIR):
            for d in os.listdir(config.RESULTS_DIR):
                if folder_name.lower() in d.lower():
                    candidate = os.path.join(config.RESULTS_DIR, d, "summary.md")
                    if os.path.exists(candidate):
                        path = candidate
                        break
    if not os.path.exists(path):
        return f"未找到 summary.md，文件夹: {folder_name}"
    content = open(path, "r", encoding="utf-8").read()
    if len(content) > 6000:
        content = content[:6000] + "\n\n...(内容过长已截断)"
    return content


def tool_read_report(folder_name: str) -> str:
    path = os.path.join(config.RESULTS_DIR, folder_name, "report.md")
    if not os.path.exists(path):
        if os.path.isdir(config.RESULTS_DIR):
            for d in os.listdir(config.RESULTS_DIR):
                if folder_name.lower() in d.lower():
                    candidate = os.path.join(config.RESULTS_DIR, d, "report.md")
                    if os.path.exists(candidate):
                        path = candidate
                        break
    if not os.path.exists(path):
        return f"未找到 report.md，文件夹: {folder_name}"
    content = open(path, "r", encoding="utf-8").read()
    if len(content) > 6000:
        content = content[:6000] + "\n\n...(内容过长已截断)"
    return content


def tool_read_strategy(folder_name: str) -> str:
    folder_path = os.path.join(config.RESULTS_DIR, folder_name)
    if not os.path.isdir(folder_path):
        if os.path.isdir(config.RESULTS_DIR):
            for d in os.listdir(config.RESULTS_DIR):
                if folder_name.lower() in d.lower():
                    candidate = os.path.join(config.RESULTS_DIR, d)
                    if os.path.isdir(candidate):
                        folder_path = candidate
                        break
    if not os.path.isdir(folder_path):
        return f"未找到文件夹: {folder_name}"

    py_files = [f for f in os.listdir(folder_path) if f.endswith(".py")]
    if not py_files:
        return f"文件夹 {folder_name} 中没有 .py 策略文件。"

    parts = []
    for f in py_files:
        content = open(os.path.join(folder_path, f), "r", encoding="utf-8").read()
        if len(content) > 4000:
            content = content[:4000] + "\n\n...(代码过长已截断)"
        parts.append(f"=== {f} ===\n{content}")
    return "\n\n".join(parts)


# ── New tools: read_file, list_files, view_logs, run_command ──────


def tool_read_file(file_path: str) -> str:
    """Read any file within the project directory."""
    # Resolve relative paths against project root
    if not os.path.isabs(file_path):
        file_path = os.path.join(config.PROJECT_ROOT, file_path)

    # Security: must be within project root or /data/a_share
    real_path = os.path.realpath(file_path)
    allowed_roots = [os.path.realpath(config.PROJECT_ROOT), "/data/a_share"]
    if not any(real_path.startswith(root) for root in allowed_roots):
        return f"安全限制: 只能读取项目目录或数据目录下的文件。"

    if not os.path.exists(real_path):
        return f"文件不存在: {file_path}"
    if os.path.isdir(real_path):
        return f"这是一个目录，请使用 list_files 工具查看内容。"

    try:
        content = open(real_path, "r", encoding="utf-8").read()
    except UnicodeDecodeError:
        return f"无法读取二进制文件: {file_path}"

    if len(content) > 8000:
        content = content[:8000] + f"\n\n...(文件过长已截断，共 {len(content)} 字符)"
    return content


def tool_list_files(directory: str) -> str:
    """List files in a directory."""
    if not os.path.isabs(directory):
        directory = os.path.join(config.PROJECT_ROOT, directory)

    real_path = os.path.realpath(directory)
    allowed_roots = [os.path.realpath(config.PROJECT_ROOT), "/data/a_share"]
    if not any(real_path.startswith(root) for root in allowed_roots):
        return f"安全限制: 只能查看项目目录或数据目录。"

    if not os.path.isdir(real_path):
        return f"目录不存在: {directory}"

    entries = []
    for name in sorted(os.listdir(real_path)):
        full = os.path.join(real_path, name)
        if os.path.isdir(full):
            entries.append(f"📁 {name}/")
        else:
            size = os.path.getsize(full)
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f}MB"
            entries.append(f"📄 {name} ({size_str})")

    if not entries:
        return f"空目录: {directory}"

    result = f"目录: {real_path}\n共 {len(entries)} 项:\n\n"
    if len(entries) > 50:
        result += "\n".join(entries[:50]) + f"\n\n...共 {len(entries)} 项，仅显示前50项"
    else:
        result += "\n".join(entries)
    return result


def tool_view_logs(log_file: str = "logs/telegram_bot.log", lines: int = 50) -> str:
    """Read recent log entries."""
    if not os.path.isabs(log_file):
        log_file = os.path.join(config.PROJECT_ROOT, log_file)

    real_path = os.path.realpath(log_file)
    if not real_path.startswith(os.path.realpath(config.PROJECT_ROOT)):
        return "安全限制: 只能查看项目目录下的日志。"

    if not os.path.exists(real_path):
        return f"日志文件不存在: {log_file}"

    try:
        with open(real_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return f"读取日志出错: {e}"

    lines = min(lines, 100)  # cap at 100
    recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
    content = "".join(recent)
    if len(content) > 6000:
        content = content[-6000:]
    return f"日志文件: {log_file} (最后 {len(recent)} 行)\n\n{content}"


def tool_run_command(command: str) -> str:
    """Run a shell command in the project directory."""
    # Block dangerous patterns
    dangerous = ["rm -rf", "mkfs", "dd if=", "> /dev/", "chmod 777", ":(){ :", "fork bomb"]
    cmd_lower = command.lower()
    for pattern in dangerous:
        if pattern in cmd_lower:
            return f"安全限制: 禁止执行危险命令。"

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=30,
            cwd=config.PROJECT_ROOT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[退出码: {result.returncode}]"
        if not output.strip():
            output = "(无输出)"
        if len(output) > 6000:
            output = output[:6000] + "\n\n...(输出过长已截断)"
        return output
    except subprocess.TimeoutExpired:
        return "命令执行超时 (30秒限制)"
    except Exception as e:
        return f"命令执行出错: {e}"


# ── XHS tools (consolidated to minimize API payload) ─────────────


def tool_xhs_manage(action: str, value: str = "") -> str:
    """Manage XHS subscriptions: subscribe_user, add_keyword, list, remove_user, remove_keyword."""
    from core.xhs_fetcher import (
        subscribe_user, unsubscribe_user, add_keyword, remove_keyword,
        list_subscriptions,
    )

    if action == "list":
        subs = list_subscriptions()
        users = subs.get("users", [])
        keywords = subs.get("keywords", [])
        if not users and not keywords:
            return "当前没有 XHS 订阅。"
        lines = []
        if users:
            lines.append("XHS 订阅用户:")
            for i, u in enumerate(users, 1):
                lines.append(f"  {i}. {u['nickname']} ({u['user_id'][:8]}...)")
        if keywords:
            lines.append("XHS 关注关键词:")
            for i, k in enumerate(keywords, 1):
                lines.append(f"  {i}. {k['keyword']}")
        return "\n".join(lines)

    elif action == "subscribe_user":
        if not value:
            return "请提供用户ID或主页URL"
        try:
            entry = subscribe_user(value)
            return f"已订阅 XHS 用户: {entry['nickname']} ({entry['user_id']})"
        except Exception as e:
            return f"订阅失败: {e}"

    elif action == "add_keyword":
        if not value:
            return "请提供关键词"
        entry = add_keyword(value)
        return f"已添加 XHS 关键词: {entry['keyword']}"

    elif action == "remove_user":
        if unsubscribe_user(value):
            return f"已取消订阅用户: {value}"
        return f"未找到用户: {value}"

    elif action == "remove_keyword":
        if remove_keyword(value):
            return f"已移除关键词: {value}"
        return f"未找到关键词: {value}"

    return f"未知操作: {action}"


def tool_xhs_process(action: str, keyword: str = "") -> str:
    """Process XHS notes: search by keyword or process all subscriptions."""
    from core.xhs_fetcher import search_notes, fetch_all_subscribed

    run = _import_run()

    if action == "search":
        if not keyword:
            return "请提供搜索关键词"
        try:
            articles = search_notes(keyword, max_notes=5)
            if not articles:
                return f"XHS 搜索 '{keyword}' 无结果。"
            processed = run._load_processed()
            articles = [a for a in articles if a.id not in processed]
            if not articles:
                return f"XHS 搜索 '{keyword}' 的结果都已处理过。"
            results = []
            for article in articles:
                result = run.process_article(article)
                run._mark_processed(article.id)
                results.append(result)
            lines = [f"XHS 搜索 '{keyword}' 处理了 {len(results)} 篇笔记:"]
            for r in results:
                a = r["analysis"]
                lines.append(f"- [{a.level}] {a.title}")
            return "\n".join(lines)
        except Exception as e:
            log.error(f"XHS search error: {e}\n{traceback.format_exc()}")
            return f"XHS 搜索出错: {e}"

    elif action == "process_all":
        try:
            articles = fetch_all_subscribed(days_back=7)
            processed = run._load_processed()
            articles = [a for a in articles if a.id not in processed]
            if not articles:
                return "没有新的 XHS 笔记需要处理。"
            results = []
            for article in articles:
                result = run.process_article(article)
                run._mark_processed(article.id)
                results.append(result)
            lines = [f"处理了 {len(results)} 篇 XHS 笔记:"]
            for r in results:
                a = r["analysis"]
                lines.append(f"- [{a.level}] {a.title}")
            return "\n".join(lines)
        except Exception as e:
            log.error(f"XHS process error: {e}\n{traceback.format_exc()}")
            return f"XHS 处理出错: {e}"

    return f"未知操作: {action}"


# ── Tool dispatch ─────────────────────────────────────────────────

TOOL_DISPATCH = {
    "list_accounts": lambda args: tool_list_accounts(),
    "get_status": lambda args: tool_get_status(),
    "subscribe_account": lambda args: tool_subscribe_account(args["url"]),
    "process_account": lambda args: tool_process_account(args["name"]),
    "search_results": lambda args: tool_search_results(args["keyword"]),
    "read_file": lambda args: tool_read_file(args["file_path"]),
    "run_command": lambda args: tool_run_command(args["command"]),
    "xhs_manage": lambda args: tool_xhs_manage(args["action"], args.get("value", "")),
    "xhs_process": lambda args: tool_xhs_process(args["action"], args.get("keyword", "")),
}


# ── Claude API ────────────────────────────────────────────────────

SYSTEM_PROMPT = "你是QFeeder Bot，量化研究AI助手。用中文回复。可管理公众号和小红书、分析文章、读文件、执行命令。深度分析IC/夏普。"

TOOLS = [
    {
        "name": "list_accounts",
        "description": "列出已订阅的微信公众号",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_status",
        "description": "获取系统状态(公众号数/文章数/最近结果)",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "subscribe_account",
        "description": "通过微信文章URL订阅新公众号",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "微信文章链接"}},
            "required": ["url"],
        },
    },
    {
        "name": "process_account",
        "description": "处理指定公众号的最新文章(模糊匹配名称)",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "公众号名称"}},
            "required": ["name"],
        },
    },
    {
        "name": "search_results",
        "description": "按关键词搜索已处理的文章结果",
        "input_schema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
            "required": ["keyword"],
        },
    },
    {
        "name": "read_file",
        "description": "读取文件内容。可读results下的summary.md/report.md/策略.py，也可读项目源码。路径相对于项目根目录或绝对路径。",
        "input_schema": {
            "type": "object",
            "properties": {"file_path": {"type": "string", "description": "文件路径，如 results/xxx/summary.md 或 core/analyzer.py"}},
            "required": ["file_path"],
        },
    },
    {
        "name": "run_command",
        "description": "在项目目录执行shell命令(ls/git/tail/python等)，30秒超时",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "shell命令"}},
            "required": ["command"],
        },
    },
    {
        "name": "xhs_manage",
        "description": "管理小红书订阅(subscribe_user/add_keyword/list/remove_user/remove_keyword)",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: subscribe_user/add_keyword/list/remove_user/remove_keyword"},
                "value": {"type": "string", "description": "用户ID/URL或关键词(list时可省略)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "xhs_process",
        "description": "处理小红书笔记(search搜索/process_all处理全部订阅)",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: search/process_all"},
                "keyword": {"type": "string", "description": "搜索关键词(search时必填)"},
            },
            "required": ["action"],
        },
    },
]

# Maximum tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 10


def _call_claude(chat_id: int, user_message: str) -> str:
    """Send message to Claude API with tools, handle tool calls, return final text."""
    import anthropic

    client_kwargs = {"api_key": config.ANTHROPIC_API_KEY}
    if config.ANTHROPIC_BASE_URL:
        client_kwargs["base_url"] = config.ANTHROPIC_BASE_URL
    client = anthropic.Anthropic(**client_kwargs)

    _add_message(chat_id, "user", user_message)
    messages = _get_history(chat_id)

    for round_idx in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Check if Claude wants to use tools
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No tool calls — extract text response
            text_parts = [b.text for b in response.content if b.type == "text"]
            assistant_text = "\n".join(text_parts) if text_parts else "（无回复）"
            _add_message(chat_id, "assistant", assistant_text)
            return assistant_text

        # Process tool calls: add assistant message, then tool results
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in tool_use_blocks:
            tool_name = block.name
            tool_input = block.input
            log.info(f"Tool call: {tool_name}({json.dumps(tool_input, ensure_ascii=False)})")

            if tool_name in TOOL_DISPATCH:
                try:
                    result = TOOL_DISPATCH[tool_name](tool_input)
                except Exception as e:
                    log.error(f"Tool error: {tool_name}: {e}\n{traceback.format_exc()}")
                    result = f"工具执行出错: {e}"
            else:
                result = f"未知工具: {tool_name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    # Exhausted rounds — return whatever we have
    text_parts = [b.text for b in response.content if b.type == "text"]
    assistant_text = "\n".join(text_parts) if text_parts else "处理完成。"
    _add_message(chat_id, "assistant", assistant_text)
    return assistant_text


# ── Keyword fallback (used when Claude API is unavailable) ────────


def _fallback_handle(text: str) -> str | None:
    """Simple keyword-based fallback. Returns response or None if unrecognized."""
    if text in ("帮助", "help", "?", "？", "/help"):
        return (
            "Feeding Agent 命令列表\n\n"
            "帮助 / help — 显示此帮助\n"
            "列表 / list — 列出已订阅公众号\n"
            "进度 / 状态 — 查看处理进度\n"
            "订阅 <url> — 订阅新公众号\n"
            "处理 <name> / 分析 <name> — 处理指定公众号文章\n"
            "结果 <keyword> — 搜索策略结果\n"
            "\n提示: 你也可以直接用自然语言提问！"
        )

    if text in ("列表", "list", "ls", "/list"):
        return tool_list_accounts()

    if text in ("进度", "状态", "status", "/status"):
        return tool_get_status()

    m = re.match(r"(?:订阅|subscribe|/subscribe)\s+(\S+)", text, re.IGNORECASE)
    if m:
        return tool_subscribe_account(m.group(1))

    m = re.match(r"(?:处理|分析|process|analyze|/process)\s+(.+)", text, re.IGNORECASE)
    if m:
        return tool_process_account(m.group(1).strip())

    m = re.match(r"(?:结果|搜索|search|result|/search)\s+(.+)", text, re.IGNORECASE)
    if m:
        return tool_search_results(m.group(1).strip())

    # XHS fallback commands
    if text in ("xhs列表", "xhs订阅", "小红书列表", "小红书订阅列表"):
        return tool_xhs_manage("list")

    m = re.match(r"(?:xhs订阅|小红书订阅)\s+(\S+)", text, re.IGNORECASE)
    if m:
        return tool_xhs_manage("subscribe_user", m.group(1))

    m = re.match(r"(?:xhs搜索|小红书搜索)\s+(.+)", text, re.IGNORECASE)
    if m:
        return tool_xhs_process("search", m.group(1).strip())

    return None


# ── Telegram handlers ────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _save_chat_id(update.effective_chat.id)
    await update.message.reply_text(
        "👋 QFeeder Bot 已就绪! (Claude Opus)\n\n"
        "我是你的量化研究助手，可以帮你：\n"
        "• 管理微信公众号订阅\n"
        "• 分析量化投资文章\n"
        "• 搜索和解读回测结果\n"
        "• 查看项目文件和日志\n"
        "• 执行命令和排查问题\n"
        "• 回答量化相关问题\n\n"
        "直接用自然语言跟我聊就行！"
    )


# Long-running tool names that need a "please wait" message
_LONG_RUNNING_KEYWORDS = {"订阅", "subscribe", "处理", "分析", "process", "analyze", "小红书", "xhs"}


def _is_long_running(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _LONG_RUNNING_KEYWORDS)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id

    log.info(f"Message from {update.effective_user.first_name}: {text}")

    # Track chat_id for health check notifications
    _save_chat_id(chat_id)

    if not text:
        return

    # Try Claude API first
    if config.ANTHROPIC_API_KEY:
        try:
            # Send "thinking" indicator for potentially long operations
            if _is_long_running(text):
                await update.message.reply_text("🔄 正在处理，请稍候...")

            response = _call_claude(chat_id, text)
            await _send_long_message(update, response)
            return
        except Exception as e:
            log.error(f"Claude API error: {e}\n{traceback.format_exc()}")
            # Fall through to keyword fallback

    # Fallback to keyword matching
    fallback_response = _fallback_handle(text)
    if fallback_response:
        await _send_long_message(update, fallback_response)
    else:
        await update.message.reply_text(
            "抱歉，我没有理解你的意思。\n"
            "发送 帮助 查看可用命令，或设置 ANTHROPIC_API_KEY 启用AI对话。"
        )


async def _send_long_message(update: Update, text: str):
    """Send a message, splitting if it exceeds Telegram's 4096 char limit."""
    MAX_LEN = 4000  # leave margin
    if len(text) <= MAX_LEN:
        await update.message.reply_text(text)
        return

    # Split into chunks
    chunks = []
    while text:
        if len(text) <= MAX_LEN:
            chunks.append(text)
            break
        # Try to split at a newline
        split_pos = text.rfind("\n", 0, MAX_LEN)
        if split_pos < MAX_LEN // 2:
            split_pos = MAX_LEN
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    for chunk in chunks:
        await update.message.reply_text(chunk)


# ── WeRSS health check ────────────────────────────────────────────

# Persistent set of chat_ids that have interacted with the bot
_active_chat_ids: set[int] = set()
CHAT_IDS_FILE = os.path.join(config.PROJECT_ROOT, ".telegram_chat_ids.json")


def _load_chat_ids():
    global _active_chat_ids
    if os.path.exists(CHAT_IDS_FILE):
        with open(CHAT_IDS_FILE, "r") as f:
            _active_chat_ids = set(json.load(f))


def _save_chat_id(chat_id: int):
    _active_chat_ids.add(chat_id)
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(sorted(_active_chat_ids), f)


def _check_werss_health() -> dict:
    """Check if we-mp-rss service is healthy and WeChat session is valid."""
    result = {"service_ok": False, "fetch_ok": False, "error": ""}

    try:
        from core.fetcher import _get_token, _auth_headers
        token = _get_token()
        if not token:
            result["error"] = "无法获取 we-mp-rss 认证 token"
            return result
        result["service_ok"] = True

        headers = _auth_headers()
        resp = requests.get(
            f"{config.WERSS_BASE_URL}{config.WERSS_API_PREFIX}/mps",
            params={"limit": 1}, headers=headers, timeout=10,
        )
        data = resp.json()
        mps = data.get("data", {}).get("list", [])
        if not mps:
            result["fetch_ok"] = True
            return result

        mp_id = mps[0]["id"]
        resp = requests.get(
            f"{config.WERSS_BASE_URL}{config.WERSS_API_PREFIX}/mps/update/{mp_id}",
            params={"start_page": 0, "end_page": 0},
            headers=headers, timeout=30,
        )
        update_data = resp.json()

        if update_data.get("code") != 0:
            err_msg = update_data.get("message", str(update_data))
            if any(kw in err_msg for kw in ("验证", "cookie", "登录", "过期", "expired", "login")):
                result["error"] = f"WeChat 登录可能已过期: {err_msg}"
            else:
                result["error"] = f"文章更新异常: {err_msg}"
            return result

        result["fetch_ok"] = True

    except requests.ConnectionError:
        result["error"] = "无法连接 we-mp-rss 服务 (连接失败)"
    except requests.Timeout:
        result["error"] = "we-mp-rss 服务响应超时"
    except Exception as e:
        result["error"] = f"健康检查出错: {e}"

    return result


_last_health_ok = True


async def _health_check_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: check we-mp-rss and XHS health, notify on Telegram if issues."""
    global _last_health_ok

    log.info("Running health check...")

    # --- WeRSS check ---
    health = _check_werss_health()
    werss_ok = health["service_ok"] and health["fetch_ok"]

    # --- XHS check ---
    xhs_ok = True
    xhs_error = ""
    if config.XHS_COOKIE:
        try:
            from core.xhs_fetcher import check_health as xhs_check_health
            xhs_health = xhs_check_health()
            xhs_ok = xhs_health["ok"]
            xhs_error = xhs_health.get("error", "")
        except Exception as e:
            xhs_ok = False
            xhs_error = str(e)

    all_ok = werss_ok and xhs_ok

    if all_ok:
        if not _last_health_ok:
            log.info("All services recovered")
            for chat_id in _active_chat_ids:
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="✅ 所有服务已恢复正常 (WeRSS + XHS)。",
                    )
                except Exception as e:
                    log.error(f"Failed to send recovery notice to {chat_id}: {e}")
        _last_health_ok = True
        log.info("Health check OK")
        return

    _last_health_ok = False

    # Build alert message
    alert_parts = ["⚠️ 服务健康检查异常\n"]

    if not werss_ok:
        alert_parts.append(
            f"WeRSS: {'✅' if health['service_ok'] else '❌'} 连接 / "
            f"{'✅' if health['fetch_ok'] else '❌'} 抓取"
        )
        if health["error"]:
            alert_parts.append(f"  → {health['error']}")
        alert_parts.append(f"  👉 检查: {config.WERSS_BASE_URL}")

    if not xhs_ok:
        alert_parts.append(f"XHS: ❌ {xhs_error}")
        if "cookie" in xhs_error.lower() or "expired" in xhs_error.lower():
            alert_parts.append("  👉 请更新 XHS_COOKIE 环境变量")

    alert = "\n".join(alert_parts)
    log.warning(f"Health issue: werss_ok={werss_ok}, xhs_ok={xhs_ok}")

    for chat_id in _active_chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=alert)
        except Exception as e:
            log.error(f"Failed to send health alert to {chat_id}: {e}")


# Check interval: every 6 hours (in seconds)
HEALTH_CHECK_INTERVAL = 6 * 3600


# ── Main ─────────────────────────────────────────────────────────


def main():
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN must be set.")
        print("Set it in config.py or via environment variable:")
        print("  export TELEGRAM_BOT_TOKEN=your_token")
        sys.exit(1)

    if not config.ANTHROPIC_API_KEY:
        log.warning("ANTHROPIC_API_KEY not set — running in keyword-only fallback mode.")
        log.warning("Set it in config.py or: export ANTHROPIC_API_KEY=sk-ant-...")

    log.info("Telegram bot starting (long polling)...")
    log.info(f"PID: {os.getpid()}")
    log.info(f"AI mode: {'Claude Sonnet agent' if config.ANTHROPIC_API_KEY else 'keyword fallback'}")

    # Load saved chat IDs for health check notifications
    _load_chat_ids()
    log.info(f"Loaded {len(_active_chat_ids)} saved chat IDs for notifications")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", lambda u, c: on_message(u, c)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # Schedule periodic WeRSS health check
    job_queue = app.job_queue
    job_queue.run_repeating(
        _health_check_job,
        interval=HEALTH_CHECK_INTERVAL,
        first=30,
        name="werss_health_check",
    )
    log.info(f"WeRSS health check scheduled: every {HEALTH_CHECK_INTERVAL // 3600}h")

    log.info("Bot ready, polling for messages...")
    app.run_polling()


if __name__ == "__main__":
    main()
