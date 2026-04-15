# [项目名称]

## 项目背景
[填写：这个项目解决什么问题，面向什么客户]

## 强制规则
- 先让 Harness 通过，再考虑代码优雅性
- 禁止修改 `harness/tests/REQ-*/` 目录下的任何文件(整目录只读)
- 禁止修改 `acm-registry.yaml`(由 Coordinator 或治理 PR 管理)
- 禁止注释掉或 skip 任何失败测试
- 所有外部 API 调用必须有对应的 mock 用于测试
- 所有配置项走环境变量，禁止硬编码

## 技术栈
- Python 3.11 + FastAPI
- 测试：pytest + httpx
- 容器：Docker + Docker Compose

## 本地开发
```bash
docker compose -f docker/docker-compose.yml up -d   # 启动开发环境
docker compose -f docker/docker-compose.test.yml up  # 运行测试
```

## Harness 通过标准（CI 必须全绿）
- pytest 全部通过
- 覆盖率 >= 80%
- docker build 成功
- harness-guardrail workflow 通过

## Harness 目录约定
- `harness/tests/REQ-*/{unit,integration,e2e}/` — 单条 REQ 的测试,**通过卡点 1b 后整目录只读**
- `harness/tests/_system/{smoke,compatibility,migration}/` — 跨 REQ 公共测试,项目维护者可改
- `harness/tests/.REQ-template/` — 创建新 REQ 目录时的复制源,不参与测试收集
- `acm-registry.yaml` — 所有 AC 的状态登记表,CI 据此决定 skip 哪些老测试

## 过期 AC 治理(新增 REQ 或依赖变更时必读)
- **supersedes**:新 REQ 取代老 AC → 在 design.md 声明,Coordinator 卡点 1a 自动更新 registry
- **retires**:功能整体废弃 → 走 `.github/ISSUE_TEMPLATE/retire-request.md`,专门发"废弃 REQ"
- **shell_patched**:依赖升级导致测试外壳需调整但 AC 语义不变 → PR body 显式声明 + spec-reviewer 双签

违反上述纪律的修改,会被 `harness-guardrail.yml` CI 检查直接 block。

## 禁止行为
- 不允许绕过 harness-guardrail(例如故意不在 PR body 写声明)
- 不允许在 impl PR 中顺手改老 REQ 的测试
- 不允许跳过失败的测试
- 不允许硬编码任何密钥或配置
