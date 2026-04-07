"""
飞书通知脚本 - 卡点事件通知
使用飞书自建应用 API 发送互动卡片消息到指定群
"""
import argparse
import os
import json
import urllib.request


# 卡片颜色主题
CARD_TEMPLATES = {
    "ci_passed":     "green",
    "ci_failed":     "red",
    "staging_ready": "blue",
    "deploy_done":   "green",
}

CARD_TITLES = {
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


def build_card(event: str, repo: str, pr: str, sha: str) -> dict:
    """构建飞书互动卡片"""
    body_lines = []
    if repo:
        body_lines.append(f"**仓库**: {repo}")
    if pr:
        pr_url = f"https://github.com/{repo}/pull/{pr}"
        body_lines.append(f"**PR**: [#{pr} 查看代码变更]({pr_url})")
    if sha:
        commit_url = f"https://github.com/{repo}/commit/{sha}"
        body_lines.append(f"**SHA**: [{sha[:8]}]({commit_url})")
    body_md = "\n".join(body_lines) if body_lines else "无附加信息"

    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": body_md},
        }
    ]

    # ci_passed：Review 链接 + 合并 / 拒绝 按钮
    if event == "ci_passed" and pr and repo:
        pr_url = f"https://github.com/{repo}/pull/{pr}"
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "Review 代码"},
                    "type": "default",
                    "multi_url": {
                        "url": pr_url,
                        "pc_url": pr_url,
                        "android_url": pr_url,
                        "ios_url": pr_url,
                    },
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "合并 PR"},
                    "type": "primary",
                    "value": {"action": "merge_pr", "repo": repo, "pr": pr},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "拒绝"},
                    "type": "danger",
                    "value": {"action": "reject_pr", "repo": repo, "pr": pr},
                },
            ],
        })

    # ci_failed：也附上 PR 链接供查看
    if event == "ci_failed" and pr and repo:
        pr_url = f"https://github.com/{repo}/pull/{pr}"
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看 PR 与 AI 分析"},
                    "type": "default",
                    "multi_url": {
                        "url": pr_url,
                        "pc_url": pr_url,
                        "android_url": pr_url,
                        "ios_url": pr_url,
                    },
                },
            ],
        })

    # staging_ready：发布到客户 / 打回 按钮
    if event == "staging_ready" and repo:
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "发布到客户环境"},
                    "type": "primary",
                    "value": {"action": "deploy_customer", "repo": repo, "sha": sha[:8] if sha else "", "customer": "default"},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "打回修改"},
                    "type": "danger",
                    "value": {"action": "reject_staging", "repo": repo, "sha": sha},
                },
            ],
        })

    return {
        "header": {
            "title": {"tag": "plain_text", "content": CARD_TITLES[event]},
            "template": CARD_TEMPLATES[event],
        },
        "elements": elements,
    }


def send_card(token: str, chat_id: str, card: dict):
    payload = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(card),
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
        raise RuntimeError(f"发送卡片失败: {data}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=CARD_TITLES.keys())
    parser.add_argument("--repo", default="")
    parser.add_argument("--sha", default="")
    parser.add_argument("--pr", default="")
    args = parser.parse_args()

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")

    if not all([app_id, app_secret, chat_id]):
        print("[notify_feishu] 环境变量未配置（FEISHU_APP_ID/APP_SECRET/CHAT_ID），跳过发送")
        print(f"[notify_feishu] 事件: {args.event}")
        return

    token = get_tenant_access_token(app_id, app_secret)
    card = build_card(args.event, args.repo, args.pr, args.sha)
    send_card(token, chat_id, card)
    print(f"[notify_feishu] 已发送卡片: {args.event}")


if __name__ == "__main__":
    main()
