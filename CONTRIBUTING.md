# Contributing

感谢你愿意改进 Law Crawler RPA RAG MCP。这个项目希望成为可靠、克制、可审计的法律数据基础设施，因此贡献时请优先考虑准确性、可复现性和对公开数据源的尊重。

## 开发流程

1. Fork 仓库并创建分支：`feature/<short-name>` 或 `fix/<short-name>`。
2. 安装依赖：

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. 修改代码并补充测试。
4. 运行检查：

   ```bash
   pytest
   python -m compileall main.py src
   ```

5. 提交 Pull Request，并说明变更动机、验证方式和潜在风险。

## 贡献准则

- 对新采集策略，必须说明数据源、公开入口、robots.txt/服务条款注意点和限速建议。
- 对解析逻辑，优先增加小型可复现样例和单元测试。
- 对输出字段，避免破坏既有 JSON/Excel 字段；必要时在 PR 中明确迁移影响。
- 不提交真实业务数据、数据库文件、浏览器调试产物、Cookie、Token 或代理凭据。
- 不引入绕过登录、验证码、付费墙、访问控制或非公开接口的能力。

## Commit Message

推荐使用 Conventional Commits：

```text
feat: add state council gazette crawler
fix: normalize full-width date separators
docs: clarify crawler compliance guidance
test: cover date normalization edge cases
```

## 高价值任务

- 增加公开数据源策略。
- 完善 PDF/HTML 正文结构化解析。
- 建立法规版本、修订、废止关系模型。
- 为 RAG 检索增加可复现评估集。
- 将 MCP 服务从占位模块推进到可运行工具。

