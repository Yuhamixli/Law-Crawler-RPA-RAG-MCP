# CLI and MCP Design

项目最终应该提供三层使用入口，让不同用户都能方便使用同一份中国法律法规数据库。

## User Personas

- 研究者：希望快速搜索、导出台账、查看法规来源。
- 开发者：希望用 Python API 或 JSON 数据集构建自己的应用。
- 智能体：希望通过 MCP 工具搜索法规、读取详情、查看更新。
- 维护者：希望定期自动更新数据并审查变更报告。

## CLI Direction

当前入口是 `python main.py`。后续建议演进为更稳定的子命令：

```bash
law-crawler crawl --law "固定资产投资项目节能审查办法" --strategy 5
law-crawler crawl --input laws.xlsx --limit 100
law-crawler urls list
law-crawler urls validate
law-crawler update --since 2026-01-01
law-crawler export --format jsonl
law-crawler serve-mcp
```

短期内保留 `main.py` 兼容入口，同时逐步把逻辑迁移到 `src/cli.py` 和可测试服务层。

## MCP Tool Direction

MCP 层不应该直接写爬虫细节，而应该调用稳定的核心服务。建议工具：

| Tool | Purpose |
| --- | --- |
| `search_laws` | 按关键词搜索法规 |
| `get_law_detail` | 按法规 ID 或名称读取详情 |
| `list_law_updates` | 查看最近自动更新结果 |
| `crawl_law` | 触发单法规采集 |
| `export_ledger` | 导出 Excel 或 JSON 台账 |

## Core Service Boundary

建议新增 `src/service/`，沉淀 CLI、MCP、Web 都可复用的能力：

```text
src/service/
├── crawl_service.py        # 单法规/批量采集
├── catalog_service.py      # 已知URL、数据源、法规目录
├── export_service.py       # JSON/Excel/JSONL导出
├── update_service.py       # 增量更新与变更报告
└── search_service.py       # 本地索引检索
```

这样 MCP 和 CLI 都只是薄薄的接口层，不会复制业务逻辑。

## Data Product Direction

高星开源项目不只要代码，还要稳定数据产品：

- `data/releases/laws.jsonl`：法规主数据。
- `data/releases/law_documents.jsonl`：正文与结构化条款。
- `data/releases/change_log.jsonl`：每次更新的新增、修订、废止。
- GitHub Releases：发布版本化数据快照。
- Actions artifacts：保存每次自动更新的临时结果。

## Implementation Order

1. 把 `main.py` 拆成 `src/cli.py` + service 层。
2. 把 `config/known_urls.toml` 做成可验证目录，提供 `urls list/validate`。
3. 建立 JSONL 数据快照格式。
4. 引入 MCP server，先实现只读工具 `search_laws` 和 `get_law_detail`。
5. 接入增量更新和定期发布。

