# 法律爬虫系统 (Law Crawler RPA RAG MCP)

一个基于Python的法律文档爬虫系统，支持批量采集法律条文、法规和司法解释，并生成结构化报告。

## 项目结构

```
Law-Crawler-RPA-RAG-MCP/
├── main.py                 # 主入口程序
├── src/                    # 源代码目录
│   ├── crawler/           # 爬虫模块
│   │   ├── strategies/    # 爬虫策略
│   │   │   ├── search_based_crawler.py  # 搜索API爬虫
│   │   │   └── law_matcher.py           # 法律匹配器
│   │   └── crawler_manager.py           # 爬虫管理器
│   ├── storage/           # 数据存储
│   ├── report/            # 报告生成
│   └── rag/               # RAG模块
├── config/                # 配置文件
├── data/                  # 数据目录 (已加入.gitignore)
├── logs/                  # 日志目录
└── tests/                 # 测试目录
```

## 核心功能

- **智能搜索爬虫**: 基于搜索API的法律采集，支持模糊匹配
- **本地缓存管理**: 分类存储法律文档，避免重复采集
- **Excel报告生成**: 自动生成包含完整信息的Excel报告
- **错误处理**: 完善的异常处理和重试机制

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置设置

编辑 `config/config.py` 中的配置参数：

```python
CRAWLER_CONFIG = {
    'max_concurrent': 5,      # 最大并发数
    'timeout': 30,           # 请求超时时间
    'retry_times': 3,        # 重试次数
    'delay': 1               # 请求间隔
}
```

### 3. 运行爬虫

```bash
python main.py
```

## 使用方法

### 批量采集法律

1. 准备Excel文件，包含法律名称列表
2. 运行主程序：`python main.py`
3. 系统将自动：
   - 搜索并匹配法律
   - 采集详细信息
   - 生成Excel报告

### 输出文件

- **JSON文件**: 按分类存储在 `data/` 目录
- **Excel报告**: 包含完整字段和超链接
- **日志文件**: 详细的执行日志

## 技术特点

- **模块化设计**: 清晰的架构分离
- **缓存机制**: 避免重复请求
- **错误恢复**: 自动重试和错误处理
- **数据完整性**: 包含所有必要字段

## 配置说明

### 爬虫配置

- `max_concurrent`: 控制并发数量
- `timeout`: 网络请求超时
- `retry_times`: 失败重试次数
- `delay`: 请求间隔时间

### 数据存储

- 本地JSON缓存
- 分类存储结构
- 自动文件命名

## 开发说明

### 项目架构

- **单一入口**: `main.py` 作为唯一入口点
- **策略模式**: 可扩展的爬虫策略
- **管理器模式**: 统一的爬虫管理

### 扩展开发

1. 在 `src/crawler/strategies/` 中添加新的爬虫策略
2. 继承 `BaseCrawler` 类
3. 实现必要的抽象方法
4. 在 `crawler_manager.py` 中注册新策略

台账包含以下信息：
- 法规名称、文号、发布机关
- 发布日期、生效日期、失效日期
- 当前状态（有效/已修正/已废止/已失效）
- 数据来源、爬取时间、更新时间

台账文件保存在 `data/ledgers/` 目录下。

## 项目结构

```
Law-Crawler-RPA-RAG-MCP/
├── src/                      # 源代码
│   ├── crawler/             # 爬虫模块
│   │   ├── base_crawler.py  # 基础爬虫类
│   │   ├── crawler_manager.py # 爬虫管理器
│   │   └── strategies/      # 不同数据源的爬虫实现
│   ├── parser/             # 文档解析模块
│   ├── storage/            # 数据存储模块
│   │   ├── database.py     # 数据库管理
│   │   └── models.py       # 数据模型
│   ├── report/             # 报告生成模块
│   │   └── ledger_generator.py # 台账生成器
│   ├── rag/               # RAG系统（开发中）
│   └── mcp/               # MCP服务（开发中）
├── data/                   # 数据目录
│   ├── raw/               # 原始爬取数据
│   ├── processed/         # 处理后的数据
│   ├── ledgers/           # 生成的台账文件
│   └── index/            # 索引文件
├── config/               # 配置文件
└── Background info/      # 背景资料和法规清单
```

## 数据源

目前支持的数据源：

1. **国家法律法规数据库** (https://flk.npc.gov.cn)
   - 国家级法律
   - 行政法规
   - 司法解释

计划支持的数据源：

2. **中国政府法制信息网**
3. **国务院公报数据库**
4. **地方人大和政府网站**

## 爬虫策略

- **礼貌爬取**：请求频率限制（≤5次/分钟）
- **智能重试**：指数退避策略
- **反爬应对**：随机User-Agent、请求头伪装
- **并发控制**：可配置的并发数限制

## 开发计划

### 第一阶段（当前）
- [x] 基础爬虫框架
- [x] 国家法律法规数据库爬虫
- [x] 数据存储和管理
- [ ] PDF文件解析
- [ ] 更多数据源支持

### 第二阶段
- [ ] RAG系统实现
- [ ] 向量索引构建
- [ ] 智能问答接口

### 第三阶段
- [ ] MCP服务开发
- [ ] Web界面
- [ ] API服务

## 注意事项

1. 请遵守各网站的使用条款和robots.txt
2. 合理控制爬取频率，避免对服务器造成压力
3. 仅用于学习和研究目的

## 技术栈说明

### 核心技术
- **Python**: 3.8+ (推荐3.10+)
- **异步框架**: asyncio + httpx
- **数据库**: SQLAlchemy 2.0 + PostgreSQL/SQLite
- **配置管理**: Pydantic Settings
- **日志**: Loguru + Python logging

### 数据处理
- **爬虫框架**: 自研异步爬虫 + Playwright (计划)
- **PDF解析**: PyPDF2 + pdfplumber
- **文本处理**: BeautifulSoup4 + lxml

### RAG技术栈（计划）
- **向量模型**: BGE-M3 / text-embedding-3
- **向量数据库**: Chroma / Milvus / Qdrant
- **LLM框架**: LangChain
- **本地模型**: ChatGLM / Qwen

## 数据流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   数据源    │────▶│    爬虫     │────▶│  清洗解析   │
│ (政府网站)  │     │ (异步并发)  │     │ (结构提取)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  向量索引   │◀────│  文档存储   │◀────│  元数据库   │
│ (Embedding) │     │(ElasticSearch)│    │(PostgreSQL) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │
       └────────────────────┴────────────────────┘
                            │
                            ▼
                    ┌─────────────┐
                    │  RAG 引擎   │
                    │ (LangChain) │
                    └─────────────┘
                            │
                    ┌───────┴───────┐
                    ▼               ▼
              ┌─────────┐    ┌─────────┐
              │MCP服务 │    │ Web API │
              └─────────┘    └─────────┘
```

## 开发规范

### Commit Message 约定
遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` Bug修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `perf:` 性能优化
- `test:` 测试相关
- `chore:` 构建/工具链相关

示例：
```
feat: 添加政府法制信息网爬虫支持
fix: 修复日期解析的时区问题
docs: 更新API文档
```

### 分支策略
- `main`: 稳定版本
- `develop`: 开发分支
- `feature/*`: 功能分支
- `hotfix/*`: 紧急修复

### 代码格式化
```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 代码格式化
black src/
isort src/

# 代码检查
flake8 src/
mypy src/
```

## Roadmap

### 第一阶段：数据采集（当前）
- [x] 基础爬虫框架
- [x] 国家法律法规数据库爬虫
- [x] 三层数据模型设计
- [x] 版本控制机制
- [ ] PDF文件解析器
- [ ] 政府法制信息网爬虫
- [ ] 地方法规爬虫
- [ ] 数据清洗管道

### 第二阶段：数据处理
- [ ] 法规文本结构化解析
- [ ] 章节条款提取
- [ ] 引用关系分析
- [ ] 时效性自动判断
- [ ] 增量更新机制

### 第三阶段：检索系统
- [ ] 文本向量化
- [ ] 向量数据库集成
- [ ] 混合检索实现
- [ ] 相似法规推荐

### 第四阶段：RAG系统
- [ ] LangChain集成
- [ ] Prompt工程
- [ ] 多轮对话支持
- [ ] 引用溯源

### 第五阶段：服务化
- [ ] RESTful API
- [ ] MCP协议实现
- [ ] Web界面
- [ ] 用户认证

## 贡献指南

我们欢迎所有形式的贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

### 如何贡献
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### Code of Conduct
本项目遵循 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。

## 贡献者

感谢所有为这个项目做出贡献的人！

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情 

## 许可证

MIT License - 详见 LICENSE 文件 