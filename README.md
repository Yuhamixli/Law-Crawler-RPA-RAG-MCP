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

### 🚀 终极优化爬虫系统（NEW）
- **多层并行策略**: 搜索引擎→法规库→优化Selenium，智能分层处理
- **效率提升79-88%**: 平均耗时从24秒/法规降至3-5秒/法规
- **成功率提升**: 从68%提升到85%+
- **浏览器复用**: 避免重复启动Chrome，减少90%启动开销

### 💡 智能爬虫策略
- **搜索引擎爬虫**: DuckDuckGo+Bing双引擎，绕过反爬机制（1.4秒/法规）
- **优化版Selenium**: 批量处理、智能等待、会话复用
- **国家法律法规数据库**: 权威数据源，结构化采集
- **直接URL访问**: 最后保障策略

### 🛠️ 系统特性
- **本地缓存管理**: 分类存储法律文档，避免重复采集
- **Excel报告生成**: 自动生成包含完整信息的Excel报告
- **错误处理**: 完善的异常处理和重试机制
- **实时性能监控**: 详细的效率统计和策略分布

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行系统

#### 🚀 快速开始（推荐 - 终极优化版）
```bash
# 批量采集（终极优化版，默认模式）
python main.py

# 限制采集数量（推荐用于测试）
python main.py --limit 10

# 性能测试
python test_optimized_crawler.py
```

#### 📊 运行模式详解

**终极优化批量模式（默认）**
```bash
python main.py                    # 全部法规，终极优化
python main.py --limit 25         # 前25条，终极优化
```
- **特点**: 多层并行策略，效率提升79-88%
- **平均速度**: 3-5秒/法规（相比原版24秒/法规）
- **成功率**: 85%+

**原版兼容模式**
```bash
python main.py --legacy           # 使用原版方式
python main.py --legacy --limit 10
```
- **特点**: 逐个处理，保持向后兼容
- **适用**: 特殊调试或对比测试

**单法规搜索模式**
```bash
# 基本搜索
python main.py --law "电子招标投标办法"

# 详细模式（显示搜索过程）
python main.py --law "电子招标投标办法" -v

# 简写形式
python main.py -l "中华人民共和国民法典" -v
```

#### 命令行参数说明
- `--law, -l`: 指定要搜索的单个法规名称
- `--limit`: 限制批量采集数量，覆盖配置文件设置
- `--legacy`: 使用原版批量爬取模式（逐个处理）
- `--verbose, -v`: 详细模式，显示搜索过程和详细信息

### 3. 配置设置

主要配置文件：`config/dev.toml`

```toml
# 爬虫配置
[crawler]
max_concurrent = 5    # 最大并发数
rate_limit = 10      # 每分钟最大请求数
crawl_limit = 25     # 批量采集时的数量限制（0表示不限制）
timeout = 30         # 请求超时时间（秒）

# 数据库配置
[database]
url = "sqlite:///data/law_crawler_dev.db"
echo = true          # 是否打印SQL（开发环境）

# 日志配置
[log]
level = "DEBUG"      # 日志级别
serialize = true     # 结构化日志输出
```

## 输出文件

系统会在以下位置生成文件：

### 数据文件
- `data/raw/json/`: 简化的JSON数据
- `data/raw/detailed/`: 包含完整API响应的详细JSON
- `data/ledgers/`: Excel台账文件

### Excel台账字段
台账包含以下字段：
- 序号、目标法规、搜索关键词
- 法规名称、文号、发布日期、实施日期、失效日期
- 发布机关、法规级别、状态
- **来源渠道**（如"国家法律法规数据库"）
- 来源链接、采集时间、采集状态

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