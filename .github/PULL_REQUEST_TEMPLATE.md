## 关联 Spec
closes #

## 变更说明
（AI 自动填写）

## Harness 通过情况
- [ ] 所有单元测试通过
- [ ] 覆盖率 >= 80%
- [ ] Docker 构建成功

## 治理事件声明（如本 PR 涉及,勾选并填写;否则留空）

> 本节是 harness-guardrail CI 的强制检查点。未勾选声明却修改了
> `harness/tests/REQ-*/` 或 `acm-registry.yaml` 的 PR 会被 CI block。

- [ ] **无治理事件**(纯 impl PR,未动锁定测试与 registry)
- [ ] **shell-patched**(依赖升级/框架换版,AC 语义不变但测试外壳需改)
  - 影响的 REQ ID:`shell_patched: REQ-XXX-NNN`(每行一个)
  - 变更摘要:
- [ ] **supersedes**(本 REQ 取代历史 AC)
  - 被取代的 AC:`supersedes: [REQ-XXX-NNN#AC-M, ...]`
  - 理由:
- [ ] **retires**(专门的废弃 REQ,批量下线历史 AC)
  - 被废弃的 AC:`retires: [REQ-XXX-NNN#AC-M, ...]`
  - 理由:

## 人工检查项（卡点 2）
- [ ] 测试用例覆盖了 Spec 中的验收标准
- [ ] 无明显安全风险
- [ ] 治理事件声明(如有)与实际修改一致
