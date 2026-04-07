"""
AI 失败分析脚本 - CI 失败时调用 Claude API 分析测试日志
用法: python scripts/analyze_failure.py <log_file>
输出: Markdown 格式的失败分析，写入 stdout
"""
import sys
import os
import json
import urllib.request


def call_claude(log_content: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ ANTHROPIC_API_KEY 未配置，跳过 AI 分析。\n\n请检查测试日志 artifact。"

    prompt = f"""你是一个 CI 失败分析助手。以下是测试失败的日志，请：
1. 用一句话说明失败原因
2. 列出具体失败的测试（如有）
3. 给出最可能的修复方向（1-3条）

格式要求：输出 Markdown，简洁，不超过 300 字。

---测试日志---
{log_content[:4000]}
---日志结束---"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]


def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_failure.py <log_file>", file=sys.stderr)
        sys.exit(1)

    log_file = sys.argv[1]
    try:
        with open(log_file, "r", errors="replace") as f:
            log_content = f.read()
    except FileNotFoundError:
        log_content = "(日志文件未找到)"

    analysis = call_claude(log_content)

    output = f"""## 🤖 AI 失败分析

{analysis}

---
*由 Claude AI 自动生成，仅供参考。完整日志见 Actions artifact。*"""

    print(output)


if __name__ == "__main__":
    main()
