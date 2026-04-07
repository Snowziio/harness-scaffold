"""
卡点响应处理器 - 飞书 WebSocket 长连接方案
服务主动连接飞书，接收互动卡片按钮点击事件，触发对应 GitHub API 操作

优势：无需公网 URL、无需开放入站端口、迁移只需重启容器
"""
import os
import json
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]
GH_PAT = os.environ.get("GH_PAT", "")
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "")
# 逗号分隔的允许操作的仓库白名单，为空则不限制（新项目部署时记得配置）
ALLOWED_REPOS = set(filter(None, os.environ.get("ALLOWED_REPOS", "").split(",")))


# ── 飞书消息发送 ──────────────────────────────────────────────────────

def send_feishu_text(text: str) -> None:
    """向群发送纯文本消息（用于打回通知）"""
    if not FEISHU_CHAT_ID:
        print("[checkpoint] FEISHU_CHAT_ID 未配置，跳过飞书通知")
        return
    # 获取 tenant_access_token
    token_req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        method="POST",
    )
    token_req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(token_req, timeout=10) as r:
        token_data = json.loads(r.read())
    access_token = token_data.get("tenant_access_token", "")
    if not access_token:
        print(f"[checkpoint] 获取飞书 token 失败: {token_data}")
        return
    # 发送消息
    msg_req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=json.dumps({
            "receive_id": FEISHU_CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }).encode(),
        method="POST",
    )
    msg_req.add_header("Authorization", f"Bearer {access_token}")
    msg_req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(msg_req, timeout=10) as r:
        resp = json.loads(r.read())
    if resp.get("code", 0) != 0:
        print(f"[checkpoint] 飞书消息发送失败: {resp}")
    else:
        print("[checkpoint] 飞书打回通知已发送")


# ── GitHub API helpers ────────────────────────────────────────────────

def github_request(method: str, path: str, body: dict = None):
    if not GH_PAT:
        raise RuntimeError("GH_PAT 未配置")
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {GH_PAT}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read()
        return json.loads(text) if text else {}


def merge_pr(repo: str, pr: str):
    # 仓库白名单校验
    if ALLOWED_REPOS and repo not in ALLOWED_REPOS:
        print(f"[checkpoint] ⛔ 仓库 {repo} 不在白名单 {ALLOWED_REPOS}，拒绝合并")
        return

    # 幂等性：检查 PR 是否已合并或已关闭
    pr_data = github_request("GET", f"/repos/{repo}/pulls/{pr}")
    if pr_data.get("merged"):
        print(f"[checkpoint] PR #{pr} 已合并，跳过重复操作")
        return
    if pr_data.get("state") != "open":
        print(f"[checkpoint] PR #{pr} 状态为 {pr_data.get('state')}，无法合并")
        return

    # CI 检查状态校验：必须全部 completed 且结论成功
    head_sha = pr_data.get("head", {}).get("sha", "")
    if head_sha:
        checks = github_request("GET", f"/repos/{repo}/commits/{head_sha}/check-runs")
        runs = checks.get("check_runs", [])
        pending = [r["name"] for r in runs if r.get("status") != "completed"]
        if pending:
            print(f"[checkpoint] ⛔ CI 仍在运行，拒绝合并。未完成项: {pending}")
            return
        failed = [
            r["name"] for r in runs
            if r.get("conclusion") not in ("success", "skipped", "neutral")
        ]
        if failed:
            print(f"[checkpoint] ⛔ CI 未全部通过，拒绝合并。失败项: {failed}")
            return

    github_request("PUT", f"/repos/{repo}/pulls/{pr}/merge", {
        "merge_method": "squash",
        "commit_title": f"Approved via Feishu (PR #{pr})",
    })
    print(f"[checkpoint] ✅ 合并 PR #{pr} in {repo} head={head_sha[:8] if head_sha else '?'}")


def reject_pr(repo: str, pr: str, reason: str = ""):
    comment = f"❌ **卡点2 · 质量门拒绝**\n\n{reason or '请修复后重新提交。'}"
    github_request("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": comment})
    print(f"[checkpoint] ❌ 拒绝 PR #{pr} in {repo}")
    send_feishu_text(
        f"❌ PR #{pr} 已打回\n"
        f"仓库：{repo}\n"
        f"原因：{reason or '请修复后重新提交'}\n\n"
        f"修复后推送到同一分支，CI 将自动重新运行。"
    )


def trigger_deploy(repo: str, customer: str, sha: str):
    github_request("POST", f"/repos/{repo}/actions/workflows/deploy.yml/dispatches", {
        "ref": "main",
        "inputs": {"customer_name": customer or "default", "image_tag": sha[:8] if sha else "latest"},
    })
    print(f"[checkpoint] 🚀 触发部署 {repo} -> {customer}")


def reject_staging(repo: str, sha: str, reason: str = ""):
    github_request("POST", f"/repos/{repo}/issues", {
        "title": f"[打回] Staging 验收未通过 ({sha[:8] if sha else 'unknown'})",
        "body": f"**打回原因**: {reason or '需人工说明'}\n\n**SHA**: `{sha}`",
        "labels": ["staging-rejected"],
    })
    print(f"[checkpoint] 🔙 打回 Staging {repo} @ {sha}")
    send_feishu_text(
        f"🔙 Staging 验收打回\n"
        f"仓库：{repo}\n"
        f"SHA：{sha[:8] if sha else 'unknown'}\n"
        f"原因：{reason or '需人工说明'}\n\n"
        f"已在 GitHub 创建 Issue，请修复后重新部署 Staging。"
    )


# ── 飞书卡片动作处理 ───────────────────────────────────────────────────

def do_card_action(data: lark.card.CardActionHandler) -> None:
    """WebSocket 卡片回调入口，解析后转发给 _dispatch_action"""
    raw = data.action if hasattr(data, "action") else {}
    if hasattr(raw, "value"):
        value = raw.value or {}
    elif isinstance(raw, dict):
        value = raw.get("value", {})
    else:
        value = {}
    if isinstance(value, str):
        value = json.loads(value)
    act      = value.get("action", "")
    repo     = value.get("repo", "")
    pr       = value.get("pr", "")
    sha      = value.get("sha", "")
    customer = value.get("customer", "")
    reason   = value.get("reason", "")
    print(f"[checkpoint] WS 收到动作: {act} | repo={repo} pr={pr} sha={sha}")
    _dispatch_action(act, repo, pr, sha, customer, reason)


# ── 健康检查 HTTP 服务（供 Docker healthcheck 使用）────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"checkpoint-handler"}')

    def do_POST(self):
        """处理飞书卡片 HTTP 回调（消息卡片请求网址模式）"""
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        # 飞书 URL 验证（首次配置时的 challenge 握手）
        if body.get("type") == "url_verification":
            resp = json.dumps({"challenge": body.get("challenge", "")}).encode()
            self._json_response(resp)
            return

        # 卡片动作回调
        if body.get("type") == "card":
            action = body.get("action", {})
            value = action.get("value", {})
            if isinstance(value, str):
                value = json.loads(value)
            act     = value.get("action", "")
            repo    = value.get("repo", "")
            pr      = value.get("pr", "")
            sha     = value.get("sha", "")
            customer = value.get("customer", "")
            reason  = value.get("reason", "")
            print(f"[checkpoint] HTTP 收到动作: {act} | repo={repo} pr={pr} sha={sha}")
            # 飞书要求 3 秒内响应，业务逻辑放后台线程
            threading.Thread(
                target=_dispatch_action,
                args=(act, repo, pr, sha, customer, reason),
                daemon=True,
            ).start()

        self._json_response(b'{"StatusCode":0}')

    def _json_response(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 静默访问日志


def _dispatch_action(act: str, repo: str, pr: str, sha: str, customer: str, reason: str):
    """卡片动作统一分发（供 HTTP 和 WebSocket 两路复用）"""
    try:
        if act == "merge_pr" and repo and pr:
            merge_pr(repo, pr)
        elif act == "reject_pr" and repo and pr:
            reject_pr(repo, pr, reason)
        elif act == "deploy_customer" and repo:
            trigger_deploy(repo, customer, sha)
        elif act == "reject_staging" and repo:
            reject_staging(repo, sha, reason)
        else:
            print(f"[checkpoint] 未知或参数不完整的动作: {act}")
    except Exception as e:
        print(f"[checkpoint] 处理失败: {e}")


def start_health_server(port: int = 8002):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ── 主入口 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 后台启动健康检查服务
    threading.Thread(target=start_health_server, daemon=True).start()
    print("[checkpoint] 健康检查服务已启动 :8002")

    # 注册事件处理器
    dispatcher = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_card_action_trigger(do_card_action)
        .build()
    )

    # 启动飞书 WebSocket 长连接（阻塞）
    print(f"[checkpoint] 连接飞书 WebSocket, app_id={APP_ID}")
    ws_client = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=dispatcher,
        log_level=lark.LogLevel.INFO,
    )
    ws_client.start()
