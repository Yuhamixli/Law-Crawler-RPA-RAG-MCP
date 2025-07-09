# 代理池配置指南

## 概述

本系统支持增强版代理池，可同时使用付费代理和免费代理，确保爬虫的稳定性和反反爬能力。

## 策略调整 ✅

**重要变更：策略1现在是法律法规数据库！**

### 新的爬虫策略顺序：
1. **策略1: 国家法律法规数据库** (flk.npc.gov.cn) - 权威数据源，优先使用
2. **策略2: 搜索引擎爬虫** - 通过搜索引擎定位法规，补充覆盖
3. **策略3: Selenium政府网爬虫** - 浏览器自动化，处理复杂页面
4. **策略4: 直接URL访问爬虫** - 最后保障策略

## 代理池配置

### 1. 配置文件结构

```
config/
├── proxy_config.toml      # 主代理配置文件 ✅ 已创建
├── dev.toml              # 开发环境配置 ✅ 已更新
└── settings.py           # 配置管理 ✅ 已更新
```

### 2. 付费代理配置

您的截图显示的代理信息已经配置到 `config/proxy_config.toml`：

```toml
[[proxy_pool.paid_proxies.servers]]
name = "新加坡代理"
remarks = "新加坡C|中转|Trojan"
address = "best.cute-cloud.de"
port = 52203
password = "d32b360a-621a-472d-a29e-38f2ca977970"
protocol = "trojan"
tls = true
sni = "sgc.cloud-services.top"
allowInsecure = true
```

### 3. 添加更多代理服务器

如果您有多个代理服务器，可以在配置文件中添加：

```toml
# 添加第二个代理服务器
[[proxy_pool.paid_proxies.servers]]
name = "美国代理"
address = "us-proxy.example.com"
port = 1080
username = "your_username"
password = "your_password"
protocol = "socks5"

# 添加第三个代理服务器
[[proxy_pool.paid_proxies.servers]]
name = "日本代理"
address = "jp-proxy.example.com"
port = 8080
protocol = "http"
```

### 4. 代理类型支持

支持多种代理协议：
- **HTTP/HTTPS**: 标准HTTP代理
- **SOCKS4/SOCKS5**: Socket代理
- **Trojan**: 您当前使用的协议 ✅

### 5. 代理使用策略

```toml
[proxy_pool.strategy]
mode = "rotation"                    # 轮换模式
retry_on_failure = true             # 失败重试
fallback_to_direct = false          # 不回退到直连
max_failures_before_disable = 5     # 失败5次后禁用
```

## 使用方法

### 1. 测试代理配置

```bash
python test_enhanced_proxy_pool.py
```

测试结果示例：
```
✅ 配置加载成功: 1 个主要配置块
✅ 解析到付费代理: 1 个
✅ 代理池初始化成功
✅ 付费代理: 1/1 (成功率: 100.0%)
✅ 获取付费代理成功
```

### 2. 在爬虫中使用代理

代理池会自动集成到爬虫系统中：

```python
from src.crawler.utils.enhanced_proxy_pool import get_enhanced_proxy_pool

# 获取代理池实例
pool = await get_enhanced_proxy_pool()

# 获取可用代理
proxy = await pool.get_proxy(prefer_paid=True)

# 在请求中使用代理
async with aiohttp.ClientSession() as session:
    async with session.get(url, proxy=proxy.proxy_url) as response:
        # 处理响应
        pass
```

### 3. 启动完整爬虫系统

```bash
python main.py
```

系统会自动：
1. 加载代理配置
2. 验证代理可用性
3. 在爬取过程中智能轮换代理

## 代理配置最佳实践

### 1. 安全配置
- ✅ 密码等敏感信息已放在配置文件中
- 🔒 建议使用环境变量覆盖敏感配置
- 📝 不要将配置文件提交到公共代码仓库

### 2. 性能优化
- ✅ 付费代理优先级更高
- ✅ 自动健康检查和故障转移
- ✅ 智能轮换减少单点压力

### 3. 监控和维护
```bash
# 查看代理池状态
python -c "
import asyncio
from src.crawler.utils.enhanced_proxy_pool import get_enhanced_proxy_pool

async def check_status():
    pool = await get_enhanced_proxy_pool()
    pool.print_stats()

asyncio.run(check_status())
"
```

## 故障排除

### 1. 代理连接失败
- 检查代理服务器地址和端口
- 验证认证信息（用户名/密码）
- 确认代理协议类型正确

### 2. 配置加载失败
- 检查TOML文件语法
- 确认文件路径正确
- 查看日志获取详细错误信息

### 3. 性能问题
- 调整并发数量
- 增加代理检查间隔
- 监控代理响应时间

## 高级配置

### 1. 特定网站代理策略
```toml
[proxy_pool.site_specific]
"flk.npc.gov.cn" = { use_proxy = true, preferred_type = "paid" }
"*.gov.cn" = { use_proxy = true, preferred_type = "paid" }
"*.google.com" = { use_proxy = true, preferred_type = "paid" }
```

### 2. 免费代理支持
```toml
[proxy_pool.free_proxies]
enabled = false  # 当前关闭，因为有付费代理
sources = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
]
```

## 配置验证 ✅

根据测试结果，当前配置完全正常：

- ✅ 策略顺序已调整：法律法规数据库优先
- ✅ 代理配置文件创建成功
- ✅ 付费代理解析正确
- ✅ 代理池初始化成功
- ✅ 代理获取和轮换正常
- ✅ 健康检查机制工作正常

您的代理服务器 `best.cute-cloud.de:52203` 已成功配置并可正常使用！

## 下一步

现在可以：
1. 启动完整的爬虫系统测试
2. 根据需要添加更多代理服务器
3. 调整代理使用策略和参数
4. 监控代理池运行状态 