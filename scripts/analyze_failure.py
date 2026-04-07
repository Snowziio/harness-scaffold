"""
AI 失败分析脚本 - CI 失败时调用 MiniMax API 分析测试日志
用法: python scripts/analyze_failure.py <log_file>
输出: Markdown 格式的失败分析，写入 stdout
"""
import sys
import os
import json
import urllib.request


def call_minimax(log_content: str) -> str:
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        return "⚠️ MINIMAX_API_KEY 未配置，跳过 AI 分析。\n\n请检查测试日志 artifact。"

    payload = json.dumps({
        "model": "MiniMax-M2.7",
        "messages": [
            {
                "role": "system",
                "content": "你是一个 CI 失败分析助手，擅长分析测试日志并给出简洁的修复建议。",
            },
            {
                "role": "user",
                "content": (
                    "以下是 CI 测试失败的日志，请：\n"
                    "1. 用一句话说明失败原因\n"
                    "2. 列出具体失败的测试（如有）\n"
                    "3. 给出最可能的修复方向（1-3条）\n\n"
                    "格式要求：输出 Markdown，简洁，不超过 300 字。\n\n"
                    f"---测试日志---\n{log_content[:4000]}\n---日志结束---"
                ),
            },
        ],
        "temperature": 0.3,
        "max_completion_tokens": 512,
    }).encode()

    req = urllib.request.Request(
        "https://api.minimax.io/v1/text/chatcompletion_v2",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    # 检查 API 层错误
    base = data.get("base_resp", {})
    if base.get("status_code", 0) != 0:
        raise RuntimeError(f"MiniMax API 错误: {base}")

    return data["choices"][0]["message"]["content"]


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

    analysis = call_minimax(log_content)

    print(f"""## 🤖 AI 失败分析

{analysis}

---
*由 MiniMax AI 自动生成，仅供参考。完整日志见 Actions artifact。*""")


if __name__ == "__main__":
    main()
