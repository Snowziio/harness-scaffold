# REQ 测试目录模板

这是创建新 REQ 测试目录时的复制源。Coordinator 在卡点 1b 通过(harness 锁定)时,
从这里复制为 `harness/tests/REQ-{PROJECT}-{NNN}/`,然后填入由 spec-to-harness
工作流生成的实际测试用例。

## 内部分层

- `unit/` — 纯函数、单类的快速测试,不依赖外部资源
- `integration/` — 跨模块、跨进程边界的契约测试
- `e2e/` — 端到端用户路径

## 历史只读纪律

REQ 目录一旦通过卡点 1b,**整目录冻结**:
- 不允许任何 PR 修改 `harness/tests/REQ-*/` 下任何文件
- 例外只有一种:`shell-patch` PR(依赖升级、框架换版导致测试外壳需调整,但 AC 语义不变),
  且必须在 PR body 显式声明 `shell_patched: <REQ-ID>` 并经 spec-reviewer 双签

## 过期 AC 处理

- **被取代**(supersedes):新 REQ 的 design.md 显式声明 → Coordinator 在卡点 1a 自动更新
  `acm-registry.yaml`,CI 在 collection 阶段 skip 老测试
- **被废弃**(retires):专门的"废弃 REQ"批量标记,本目录文件保留作审计
- **shell 调整**(shell_patched):见上方
