---
name: 废弃需求(Retire REQ)
about: 申请下线一组历史 AC(功能整体废弃,无替代者)
title: "[RETIRE] "
labels: retirement
---

## 被废弃的 AC 清单

每行一条,格式 `REQ-XXX-NNN#AC-M`:

```
REQ-PROJ-003#AC-1
REQ-PROJ-003#AC-2
```

## 废弃理由

(说明为什么这组 AC 不再需要。典型理由:功能下线、客户流失、产品方向调整)

## 影响分析

- 是否有下游依赖?(列出可能被波及的功能)
- 是否有数据迁移需要?
- 生效时间点:

## 后续动作

- [ ] 本 issue 被产品/技术负责人批准后,创建一个专门的"废弃 REQ":
  `REQ-RETIRE-NNN`,走完整 Coordinator 流程至 SPEC_LOCKED
- [ ] SPEC_LOCKED 时 Coordinator 自动把上述 AC 在 `acm-registry.yaml`
  标记为 `retired`,CI 不再运行对应测试(测试代码保留作审计)
- [ ] 若有 impl 侧清理(删除 dead code、下线端点),作为独立的清理 PR
  提交(不走 harness 改动,因 harness 文件仍保留)
