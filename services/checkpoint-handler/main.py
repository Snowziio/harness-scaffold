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
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")


# ── GitHub API helpers ────────────────────────────────────────────────

def github_request(method: str, path: str, body: dict = None):
    if not GITHUB_PAT:
        raise RuntimeError("GITHUB_PAT 未配置")
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {GITHUB_PAT}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read()
        return json.loads(text) if text else {}


def merge_pr(repo: str, pr: str):
    github_request("PUT", f"/repos/{repo}/pulls/{pr}/merge", {
        "merge_method": "squash",
        "commit_title": f"Approved via Feishu (PR #{pr})",
    })
    print(f"[checkpoint] ✅ 合并 PR #{pr} in {repo}")


def reject_pr(repo: str, pr: str, reason: str = ""):
    comment = f"❌ **卡点2 · 质量门拒绝**\n\n{reason or '请修复后重新提交。'}"
    github_request("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": comment})
    print(f"[checkpoint] ❌ 拒绝 PR #{pr} in {repo}")


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


# ── 飞书卡片动作处理 ───────────────────────────────────────────────────

def do_card_action(data: lark.card.CardActionTrigger) -> None:
    try:
        value = data.event.action.value or {}
        action = value.get("action", "")
        repo = value.get("repo", "")
        pr = value.get("pr", "")
        sha = value.get("sha", "")
        customer = value.get("customer", "")
        reason = value.get("reason", "")

        print(f"[checkpoint] 收到动作: {action} | repo={repo} pr={pr} sha={sha}")

        if action == "merge_pr" and repo and pr:
            merge_pr(repo, pr)
        elif action == "reject_pr" and repo and pr:
            reject_pr(repo, pr, reason)
        elif action == "deploy_customer" and repo:
            trigger_deploy(repo, customer, sha)
        elif action == "reject_staging" and repo:
            reject_staging(repo, sha, reason)
        else:
            print(f"[checkpoint] 未知或参数不完整的动作: {action}")
    except Exception as e:
        print(f"[checkpoint] 处理失败: {e}")


# ── 健康检查 HTTP 服务（供 Docker healthcheck 使用）────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"checkpoint-handler"}')

    def log_message(self, *args):
        pass  # 静默访问日志


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
