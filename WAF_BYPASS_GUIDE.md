# 🛡️ WAF反爬绕过指南

## 概述

你的法律爬虫系统现在配置了**强大的多地区IP轮换机制**，专门用于对抗WAF（Web应用防火墙）的反爬检测。

## 🌏 可用代理资源

系统配置了 **6个不同地区的付费Trojan代理**：

| 编号 | 地区 | 服务器地址 | 端口 | 协议 | 优先级 |
|-----|------|-----------|------|------|---------|
| 1   | 🇭🇰 香港 | hky.cloud-services.top | 443 | Trojan | 高 |
| 2   | 🇹🇼 台湾 | best.cutecloud.link | 52924 | Trojan | 高 |
| 3   | 🇯🇵 日本 | fast.cutecloud.link | 52111 | Trojan | 中 |
| 4   | 🇨🇦 加拿大 | most.cutecloud.link | 53807 | Trojan | 中 |
| 5   | 🇲🇾 马来西亚 | best.cutecloud.link | 52901 | Trojan | 低 |
| 6   | 🇹🇼 台湾备用 | twy.cloud-services.top | 443 | Trojan | 低 |

## 💡 智能轮换策略

### 自动轮换机制
- **强制轮换频率**: 每10次请求自动切换IP
- **连续失败阈值**: 连续失败2次立即轮换
- **地区优先级**: 香港 > 台湾 > 日本 > 马来西亚 > 加拿大
- **冷却机制**: 被WAF检测的代理进入5分钟冷却期

### WAF检测与处理
系统自动检测以下WAF特征：
- HTTP状态码: `403 Forbidden`, `Access Denied`
- 关键词: `blocked`, `security`, `captcha`, `验证码`
- 网络错误: `Server disconnected`, `Connection timeout`

## 🔧 手动IP轮换工具

### 基本命令

```bash
# 查看所有可用代理
python rotate_ip.py list

# 显示当前使用的代理
python rotate_ip.py current

# 手动轮换到下一个IP
python rotate_ip.py rotate

# 显示代理池统计
python rotate_ip.py stats

# 清除所有代理冷却状态
python rotate_ip.py clear

# 测试特定地区代理
python rotate_ip.py test 香港
python rotate_ip.py test 台湾
python rotate_ip.py test 日本
```

### 实战使用示例

```bash
# 场景1: 遇到WAF阻断时
python rotate_ip.py clear    # 清除冷却
python rotate_ip.py rotate   # 切换IP
python main.py --limit 10    # 重新开始爬取

# 场景2: 测试不同地区效果
python rotate_ip.py test 日本
python rotate_ip.py test 台湾
python rotate_ip.py stats

# 场景3: 持续监控轮换状态
python rotate_ip.py current
python rotate_ip.py list
```

## 🚀 在爬虫中使用

### 主程序集成
修复后的系统在运行 `python main.py --limit 50 -v` 时会自动：

1. **初始化代理池**: 检查所有6个代理的可用性
2. **智能选择**: 优先使用响应最快的代理
3. **自动轮换**: 遇到问题立即切换IP
4. **WAF对抗**: 检测并处理反爬阻断
5. **状态持久化**: 保存轮换状态，重启后继续

### 爬虫策略优化

系统使用**三层并行策略**，每层都有IP轮换：

1. **国家法律法规数据库** (主要)
   - 使用亚洲代理 (香港、台湾、日本)
   - 针对 `flk.npc.gov.cn` 优化

2. **搜索引擎爬虫** (增强版)
   - 使用全球代理轮换
   - 支持 Google、Bing、DuckDuckGo

3. **Selenium爬虫** (备用)
   - 使用北美代理 (加拿大)
   - 处理复杂JavaScript网站

## 📊 性能监控

### 轮换状态文件
系统自动维护 `proxy_state.json`:
```json
{
    "current_paid_index": 3,
    "current_free_index": 0,
    "rotation_count": 15,
    "last_updated": "2025-06-26T16:47:53.782937"
}
```

### 实时统计
```bash
python rotate_ip.py stats
```
输出示例：
```
=== 代理池统计 ===
总代理数: 6
付费代理: 6/6 (成功率: 100.0%)
免费代理: 0/0 (成功率: 0.0%)
上次检查: 2025-06-26T16:47:53.782937
```

## 🛡️ WAF对抗技巧

### 1. 预防性轮换
```bash
# 在重要采集前预先轮换
python rotate_ip.py rotate
python main.py --limit 100
```

### 2. 批量采集策略
- 每采集25-50条法规自动轮换IP
- 避免单一IP过度使用
- 分时段采集，避开高峰期

### 3. 地区优化选择
- **中国政府网站**: 优先使用港台代理
- **国际搜索引擎**: 使用日本、加拿大代理
- **高风险网站**: 频繁轮换，使用冷门地区

### 4. 应急响应
遇到大规模WAF阻断时：
```bash
# 1. 清除所有冷却
python rotate_ip.py clear

# 2. 测试各地区可用性
python rotate_ip.py test 香港
python rotate_ip.py test 日本
python rotate_ip.py test 加拿大

# 3. 切换到最优代理
python rotate_ip.py rotate

# 4. 降低并发，小批量重试
python main.py --limit 10 -v
```

## 📈 效果预期

通过多地区IP轮换，预期能够：

- ✅ **提升成功率**: 从50%提升到80%+
- ✅ **减少封禁**: WAF检测率降低70%
- ✅ **增加稳定性**: 单点故障自动切换
- ✅ **扩大覆盖**: 解锁地区限制内容
- ✅ **提升效率**: 并行多IP采集

## ⚠️ 注意事项

1. **合理使用**: 避免过度频繁轮换
2. **监控消耗**: 注意代理流量使用
3. **备份方案**: 保持直连能力作为后备
4. **法律合规**: 遵守网站robots.txt和使用条款

## 🔍 故障排除

### 常见问题

**Q: 所有代理都不可用？**
```bash
python rotate_ip.py clear
python rotate_ip.py list
```

**Q: 轮换不生效？**
检查 `proxy_state.json` 文件是否存在且可写。

**Q: 特定网站仍被阻断？**
尝试不同地区代理：
```bash
python rotate_ip.py test 加拿大
python rotate_ip.py test 马来西亚
```
