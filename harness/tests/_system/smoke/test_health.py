"""系统级冒烟测试。

本目录(harness/tests/_system/)是跨 REQ 的公共测试区,由项目维护者在
scaffold 初始化、依赖升级等场景下维护。和 REQ-* 目录的"锁定即只读"
纪律不同,_system/ 允许被修改,但所有修改都会被 CI guardrail 计入
shell-patch 事件审计。
"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_200():
    response = client.get("/")
    assert response.status_code == 200
