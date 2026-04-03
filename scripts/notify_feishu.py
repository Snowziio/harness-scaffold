"""
飞书通知脚本 - 卡点事件通知
TODO: 接入飞书 Webhook 或函数计算 FC 后完善此脚本
"""
import argparse
import os
import json
import urllib.request

EVENTS = {
    "ci_passed":      "✅ CI 通过，等待合并",
    "ci_failed":      "❌ CI 失败，需要修复",
    "staging_ready":  "🚀 Staging 已就绪，等待验收",
    "deploy_done":    "✅ 客户环境已部署",
}


def send_feishu(webhook_url: str, text: str):
    payload = json.dumps({"msg_type": "text", "content": {"text": text}}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=EVENTS.keys())
    parser.add_argument("--repo", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--pr", default="")
    args = parser.parse_args()

    msg = EVENTS[args.event]
    if args.repo:
        msg += f"\nRepo: {args.repo}"
    if args.pr:
        msg += f"\nPR: #{args.pr}"
    if args.sha:
        msg += f"\nSHA: {args.sha[:8]}"

    webhook = os.environ.get("FEISHU_WEBHOOK", "")
    if webhook:
        send_feishu(webhook, msg)
    else:
        print(f"[notify_feishu] FEISHU_WEBHOOK 未配置，跳过发送")
        print(f"[notify_feishu] 消息内容: {msg}")


if __name__ == "__main__":
    main()
