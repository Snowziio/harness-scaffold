# [项目名称]

## 项目背景
[填写：这个项目解决什么问题，面向什么客户]

## 强制规则
- 先让 Harness 通过，再考虑代码优雅性
- 禁止修改 `harness/tests/` 目录下的任何文件
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

## 禁止行为
- 不允许修改 harness/tests/ 目录
- 不允许跳过失败的测试
- 不允许硬编码任何密钥或配置
