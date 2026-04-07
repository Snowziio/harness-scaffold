"""
卡点响应处理器 - 飞书卡片按钮回调服务
接收飞书按钮点击事件，触发对应的 GitHub API 操作

部署: 运行在 ECS 8002 端口，Feishu 应用事件订阅 URL 指向此服务
"""
import os
import json
import hashlib
import hmac
import urllib.request
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Checkpoint Handler")

FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")


# ── GitHub API helpers ──────────────────────────────────────────────

def github_request(method: str, path: str, body: dict = None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {GITHUB_PAT}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read()) if resp.read() else {}


def merge_pr(repo: str, pr: str):
    """合并 PR"""
    github_request("PUT", f"/repos/{repo}/pulls/{pr}/merge", {
        "merge_method": "squash",
        "commit_title": f"Approved via Feishu (PR #{pr})",
    })


def reject_pr(repo: str, pr: str, reason: str = ""):
    """在 PR 上添加拒绝评论"""
    comment = f"❌ **卡点2 · 质量门拒绝**\n\n{reason or '请修复后重新提交。'}"
    github_request("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": comment})


def trigger_deploy(repo: str, customer: str, sha: str):
    """触发客户部署 workflow"""
    github_request("POST", f"/repos/{repo}/actions/workflows/deploy.yml/dispatches", {
        "ref": "main",
        "inputs": {"customer_name": customer, "image_tag": sha[:8]},
    })


def reject_staging(repo: str, sha: str, reason: str = ""):
    """打回 Staging，在 commit 上创建状态"""
    # 在最新 commit 创建 Issue 记录打回原因
    github_request("POST", f"/repos/{repo}/issues", {
        "title": f"[打回] Staging 验收未通过 ({sha[:8]})",
        "body": f"**打回原因**: {reason or '需人工说明'}\n\n**SHA**: `{sha}`\n\n请修复后重新部署 Staging。",
        "labels": ["staging-rejected"],
    })


# ── Feishu 验证 ─────────────────────────────────────────────────────

def verify_token(token: str) -> bool:
    if not FEISHU_VERIFICATION_TOKEN:
        return True  # 未配置时跳过验证（仅开发环境）
    return token == FEISHU_VERIFICATION_TOKEN


# ── 路由 ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "checkpoint-handler"}


@app.post("/feishu/callback")
async def feishu_callback(request: Request):
    body = await request.json()

    # 飞书 URL 验证握手
    if body.get("type") == "url_verification":
        challenge = body.get("challenge", "")
        return JSONResponse({"challenge": challenge})

    # 验证 token
    token = body.get("token", "")
    if not verify_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")

    # 处理卡片动作
    action_value = body.get("action", {}).get("value", {})
    action = action_value.get("action", "")
    repo = action_value.get("repo", "")
    pr = action_value.get("pr", "")
    sha = action_value.get("sha", "")
    customer = action_value.get("customer", "")
    reason = action_value.get("reason", "")

    if not GITHUB_PAT:
        return JSONResponse({"code": 0, "msg": "GITHUB_PAT 未配置，操作已记录但未执行"})

    try:
        if action == "merge_pr" and repo and pr:
            merge_pr(repo, pr)
            print(f"[checkpoint] 合并 PR #{pr} in {repo}")

        elif action == "reject_pr" and repo and pr:
            reject_pr(repo, pr, reason)
            print(f"[checkpoint] 拒绝 PR #{pr} in {repo}")

        elif action == "deploy_customer" and repo:
            trigger_deploy(repo, customer or "default", sha)
            print(f"[checkpoint] 触发部署 {repo} -> {customer}")

        elif action == "reject_staging" and repo:
            reject_staging(repo, sha, reason)
            print(f"[checkpoint] 打回 Staging {repo} @ {sha}")

        else:
            print(f"[checkpoint] 未知动作: {action}")

    except Exception as e:
        print(f"[checkpoint] 执行失败: {e}")
        return JSONResponse({"code": 1, "msg": str(e)})

    return JSONResponse({"code": 0})
