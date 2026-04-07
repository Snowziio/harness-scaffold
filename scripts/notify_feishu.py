"""
飞书通知脚本 - 卡点事件通知
使用飞书自建应用 API 发送消息到指定群
"""
import argparse
import os
import json
import urllib.request

EVENTS = {
    "ci_passed":     "✅ CI 通过，等待合并",
    "ci_failed":     "❌ CI 失败，需要修复",
    "staging_ready": "🚀 Staging 已就绪，等待验收",
    "deploy_done":   "✅ 客户环境已部署",
}


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def send_message(token: str, chat_id: str, text: str):
    payload = json.dumps({
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("code") != 0:
        raise RuntimeError(f"发送消息失败: {data}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=EVENTS.keys())
    parser.add_argument("--repo", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--pr", default="")
    args = parser.parse_args()

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")

    msg = EVENTS[args.event]
    if args.repo:
        msg += f"\nRepo: {args.repo}"
    if args.pr:
        msg += f"\nPR: #{args.pr}"
    if args.sha:
        msg += f"\nSHA: {args.sha[:8]}"

    if not all([app_id, app_secret, chat_id]):
        print("[notify_feishu] 环境变量未配置（FEISHU_APP_ID/APP_SECRET/CHAT_ID），跳过发送")
        print(f"[notify_feishu] 消息内容: {msg}")
        return

    token = get_tenant_access_token(app_id, app_secret)
    send_message(token, chat_id, msg)
    print(f"[notify_feishu] 已发送: {msg}")


if __name__ == "__main__":
    main()
