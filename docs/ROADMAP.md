# Roadmap

目标是把 Law Crawler RPA RAG MCP 做成 GitHub 上最好的开源中国法律法规数据库基础设施：公开、可追溯、可复现、方便人和智能体共同使用。

## North Star

- 覆盖公开中国法律法规、行政法规、部门规章、司法解释和重要地方性法规。
- 保留每条法规的来源链接、版本、修订历史、效力状态和采集时间。
- 提供 CLI、Python API、MCP 工具和可部署的数据更新流水线。
- 支持定期自动更新，并输出可审计的变更报告。

## Phases

### Phase 1: Reliable Seeds and CLI

- 将已知法规 URL 从代码迁移到 `config/known_urls.toml`。
- 提供 `--list-known-urls` 查看直接 URL 种子。
- 建立小规模定时更新烟测，持续验证采集链路。
- 将运行产物作为 artifact 保存，避免污染源码仓库。

### Phase 2: Source Adapters

- 重新适配国家法律法规数据库当前前端接口。
- 增加中国政府网、公报、部委站点和地方公开法规入口。
- 为每个数据源建立离线 fixture 和解析单测。
- 输出统一字段：法规名称、文号、机关、层级、发布时间、实施时间、效力状态、正文、来源。

### Phase 3: Open Law Database

- 引入稳定的数据目录格式，例如 JSONL 或 SQLite release artifact。
- 建立增量更新：发现新增、修改、废止和来源变更。
- 生成机器可读 changelog。
- 通过 GitHub Releases 发布数据快照。

### Phase 4: Retrieval and RAG

- 法规正文条款级切片。
- 建立 BM25 + 向量混合检索。
- 支持引用溯源和答案证据链。
- 提供面向研究者和开发者的评估集。

### Phase 5: MCP and Services

- MCP 工具：`search_laws`、`get_law_detail`、`list_updates`、`export_ledger`。
- CLI 子命令：`crawl`、`update`、`search`、`export`、`serve-mcp`。
- 可选 Web/API 服务，用于任务调度、人工复核和数据下载。

CLI 与 MCP 的详细设计见 [MCP_CLI_DESIGN.md](MCP_CLI_DESIGN.md)。

## Design Principles

- Public sources only：只采集公开来源，不绕过登录、验证码、付费墙或访问控制。
- Traceable by default：任何数据都必须能追溯到原始 URL 和采集时间。
- Small reliable core：优先把少数权威来源跑稳，再扩展覆盖面。
- Human review friendly：所有自动更新都应输出人能看懂的变更报告。
- Agent ready：CLI、Python API 和 MCP 使用同一套核心服务。
