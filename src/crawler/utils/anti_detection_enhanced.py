#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强反爬检测机制
包含：
1. 实时反爬检测
2. 响应内容分析
3. 自动代理切换
4. 请求频率动态调整
5. 异常行为检测
"""

import asyncio
import aiohttp
import re
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
from dataclasses import dataclass, field
from enum import Enum


class AntiCrawlerLevel(Enum):
    """反爬级别枚举"""
    NONE = "none"           # 无反爬
    LOW = "low"             # 低级反爬 
    MEDIUM = "medium"       # 中级反爬
    HIGH = "high"           # 高级反爬
    EXTREME = "extreme"     # 极高反爬


class ResponseAnalysisResult(Enum):
    """响应分析结果"""
    NORMAL = "normal"               # 正常响应
    BLOCKED = "blocked"             # 被阻止
    CAPTCHA = "captcha"             # 验证码
    RATE_LIMITED = "rate_limited"   # 频率限制
    WAF_DETECTED = "waf_detected"   # WAF检测
    IP_BANNED = "ip_banned"         # IP封禁
    CLOUDFLARE = "cloudflare"       # Cloudflare保护


@dataclass
class DetectionMetrics:
    """检测指标"""
    total_requests: int = 0
    blocked_requests: int = 0
    captcha_requests: int = 0
    rate_limited_requests: int = 0
    successful_requests: int = 0
    
    last_blocked_time: Optional[datetime] = None
    consecutive_blocks: int = 0
    avg_response_time: float = 0.0
    
    # 各网站的检测统计
    site_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    @property
    def block_rate(self) -> float:
        """阻止率"""
        if self.total_requests == 0:
            return 0.0
        return (self.blocked_requests + self.captcha_requests + self.rate_limited_requests) / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class EnhancedAntiDetection:
    """增强反爬检测器"""
    
    def __init__(self):
        self.logger = logger
        self.metrics = DetectionMetrics()
        
        # 检测规则
        self.detection_rules = self._load_detection_rules()
        
        # 动态延迟配置
        self.base_delay = 1.0
        self.max_delay = 30.0
        self.delay_multiplier = 1.5
        
        # 代理切换阈值
        self.proxy_switch_threshold = 3  # 连续失败3次切换代理
        self.ip_ban_threshold = 5        # 连续失败5次认为IP被封
        
        # 状态跟踪
        self.current_anti_level = AntiCrawlerLevel.NONE
        self.last_analysis_time = datetime.now()
        
    def _load_detection_rules(self) -> Dict[str, Any]:
        """加载检测规则"""
        return {
            # HTTP状态码检测
            "status_codes": {
                "blocked": [403, 429, 503, 520, 521, 522, 523, 524],
                "rate_limited": [429, 503],
                "captcha": [403, 503],
                "ip_banned": [403, 451]
            },
            
            # 响应内容关键词检测
            "content_patterns": {
                "blocked": [
                    r"access\s+denied", r"访问被拒绝", r"禁止访问",
                    r"blocked", r"封禁", r"拦截",
                    r"security\s+check", r"安全检查"
                ],
                "captcha": [
                    r"captcha", r"验证码", r"人机验证",
                    r"prove\s+you\s+are\s+human", r"请验证您是人类",
                    r"robot\s+check", r"机器人检测"
                ],
                "rate_limited": [
                    r"rate\s+limit", r"频率限制", r"请求过于频繁",
                    r"too\s+many\s+requests", r"访问过于频繁",
                    r"slow\s+down", r"请稍后再试"
                ],
                "waf": [
                    r"web\s+application\s+firewall", r"waf",
                    r"安全防护", r"网站防火墙",
                    r"security\s+service", r"安全服务"
                ],
                "cloudflare": [
                    r"cloudflare", r"cf-ray", r"ray\s+id",
                    r"checking\s+your\s+browser", r"正在检查您的浏览器"
                ]
            },
            
            # 响应头检测
            "header_patterns": {
                "cloudflare": ["cf-ray", "cf-cache-status", "__cfduid"],
                "waf": ["x-waf-event", "x-security-check"],
                "rate_limit": ["x-ratelimit-remaining", "retry-after"]
            },
            
            # 响应时间异常检测
            "response_time": {
                "suspicious_fast": 0.1,    # 异常快速响应可能是错误页面
                "suspicious_slow": 30.0,   # 异常慢速响应可能是防护措施
                "normal_range": (0.5, 10.0)
            }
        }
    
    async def analyze_response(
        self, 
        response: aiohttp.ClientResponse, 
        content: str, 
        url: str,
        response_time: float
    ) -> Tuple[ResponseAnalysisResult, AntiCrawlerLevel]:
        """
        分析响应内容，检测反爬情况
        
        Args:
            response: HTTP响应对象
            content: 响应内容
            url: 请求URL
            response_time: 响应时间
            
        Returns:
            (检测结果, 反爬级别)
        """
        site = self._extract_site(url)
        
        # 更新统计
        self.metrics.total_requests += 1
        self._update_site_stats(site, "total")
        
        # 1. HTTP状态码检测
        status_result = self._check_status_code(response.status)
        if status_result != ResponseAnalysisResult.NORMAL:
            self._handle_detection(site, status_result)
            return status_result, self._calculate_anti_level()
        
        # 2. 响应头检测
        header_result = self._check_response_headers(response.headers)
        if header_result != ResponseAnalysisResult.NORMAL:
            self._handle_detection(site, header_result)
            return header_result, self._calculate_anti_level()
        
        # 3. 响应内容检测
        content_result = self._check_response_content(content)
        if content_result != ResponseAnalysisResult.NORMAL:
            self._handle_detection(site, content_result)
            return content_result, self._calculate_anti_level()
        
        # 4. 响应时间检测
        time_result = self._check_response_time(response_time, len(content))
        if time_result != ResponseAnalysisResult.NORMAL:
            self._handle_detection(site, time_result)
            return time_result, self._calculate_anti_level()
        
        # 5. 成功响应处理
        self.metrics.successful_requests += 1
        self.metrics.consecutive_blocks = 0
        self._update_site_stats(site, "success")
        
        return ResponseAnalysisResult.NORMAL, self._calculate_anti_level()
    
    def _check_status_code(self, status_code: int) -> ResponseAnalysisResult:
        """检查HTTP状态码"""
        rules = self.detection_rules["status_codes"]
        
        if status_code in rules["rate_limited"]:
            return ResponseAnalysisResult.RATE_LIMITED
        elif status_code in rules["captcha"]:
            return ResponseAnalysisResult.CAPTCHA
        elif status_code in rules["blocked"]:
            if status_code == 403:
                return ResponseAnalysisResult.IP_BANNED
            else:
                return ResponseAnalysisResult.BLOCKED
        
        return ResponseAnalysisResult.NORMAL
    
    def _check_response_headers(self, headers: Dict[str, str]) -> ResponseAnalysisResult:
        """检查响应头"""
        header_rules = self.detection_rules["header_patterns"]
        
        # 检查Cloudflare
        if any(header in headers for header in header_rules["cloudflare"]):
            return ResponseAnalysisResult.CLOUDFLARE
        
        # 检查WAF
        if any(header in headers for header in header_rules["waf"]):
            return ResponseAnalysisResult.WAF_DETECTED
        
        # 检查频率限制
        if any(header in headers for header in header_rules["rate_limit"]):
            return ResponseAnalysisResult.RATE_LIMITED
        
        return ResponseAnalysisResult.NORMAL
    
    def _check_response_content(self, content: str) -> ResponseAnalysisResult:
        """检查响应内容"""
        if not content:
            return ResponseAnalysisResult.NORMAL
        
        content_lower = content.lower()
        patterns = self.detection_rules["content_patterns"]
        
        # 按优先级检查
        for result_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    if result_type == "blocked":
                        return ResponseAnalysisResult.BLOCKED
                    elif result_type == "captcha":
                        return ResponseAnalysisResult.CAPTCHA
                    elif result_type == "rate_limited":
                        return ResponseAnalysisResult.RATE_LIMITED
                    elif result_type == "waf":
                        return ResponseAnalysisResult.WAF_DETECTED
                    elif result_type == "cloudflare":
                        return ResponseAnalysisResult.CLOUDFLARE
        
        # 检查是否是空白或错误页面
        if len(content.strip()) < 100:
            self.logger.debug(f"检测到疑似空白响应，内容长度: {len(content)}")
            return ResponseAnalysisResult.BLOCKED
        
        return ResponseAnalysisResult.NORMAL
    
    def _check_response_time(self, response_time: float, content_length: int) -> ResponseAnalysisResult:
        """检查响应时间异常"""
        time_rules = self.detection_rules["response_time"]
        
        # 异常快速响应（可能是错误页面）
        if response_time < time_rules["suspicious_fast"] and content_length < 1000:
            self.logger.debug(f"检测到异常快速响应: {response_time:.3f}s, 内容长度: {content_length}")
            return ResponseAnalysisResult.BLOCKED
        
        # 异常慢速响应（可能是防护措施）
        if response_time > time_rules["suspicious_slow"]:
            self.logger.debug(f"检测到异常慢速响应: {response_time:.3f}s")
            return ResponseAnalysisResult.RATE_LIMITED
        
        return ResponseAnalysisResult.NORMAL
    
    def _handle_detection(self, site: str, result: ResponseAnalysisResult):
        """处理检测到的反爬情况"""
        self.metrics.consecutive_blocks += 1
        self.metrics.last_blocked_time = datetime.now()
        
        # 更新统计
        if result == ResponseAnalysisResult.BLOCKED:
            self.metrics.blocked_requests += 1
            self._update_site_stats(site, "blocked")
        elif result == ResponseAnalysisResult.CAPTCHA:
            self.metrics.captcha_requests += 1
            self._update_site_stats(site, "captcha")
        elif result == ResponseAnalysisResult.RATE_LIMITED:
            self.metrics.rate_limited_requests += 1
            self._update_site_stats(site, "rate_limited")
        
        self.logger.warning(f"检测到反爬 - {site}: {result.value} (连续失败: {self.metrics.consecutive_blocks})")
    
    def _calculate_anti_level(self) -> AntiCrawlerLevel:
        """计算当前反爬级别"""
        block_rate = self.metrics.block_rate
        consecutive_blocks = self.metrics.consecutive_blocks
        
        if consecutive_blocks >= 10 or block_rate > 0.8:
            level = AntiCrawlerLevel.EXTREME
        elif consecutive_blocks >= 5 or block_rate > 0.5:
            level = AntiCrawlerLevel.HIGH
        elif consecutive_blocks >= 3 or block_rate > 0.3:
            level = AntiCrawlerLevel.MEDIUM
        elif consecutive_blocks >= 1 or block_rate > 0.1:
            level = AntiCrawlerLevel.LOW
        else:
            level = AntiCrawlerLevel.NONE
        
        if level != self.current_anti_level:
            self.logger.info(f"反爬级别变化: {self.current_anti_level.value} → {level.value}")
            self.current_anti_level = level
        
        return level
    
    def get_adaptive_delay(self, operation_type: str = "default") -> float:
        """获取自适应延迟时间"""
        base = self.base_delay
        
        # 根据反爬级别调整
        if self.current_anti_level == AntiCrawlerLevel.EXTREME:
            base *= 10
        elif self.current_anti_level == AntiCrawlerLevel.HIGH:
            base *= 5
        elif self.current_anti_level == AntiCrawlerLevel.MEDIUM:
            base *= 3
        elif self.current_anti_level == AntiCrawlerLevel.LOW:
            base *= 2
        
        # 根据操作类型调整
        if operation_type == "search":
            base *= 1.5
        elif operation_type == "retry":
            base *= 2.0
        elif operation_type == "detail":
            base *= 1.2
        
        # 添加随机性
        delay = base * random.uniform(0.8, 1.5)
        
        # 限制最大延迟
        return min(delay, self.max_delay)
    
    def should_switch_proxy(self) -> bool:
        """判断是否应该切换代理"""
        return (
            self.metrics.consecutive_blocks >= self.proxy_switch_threshold or
            self.current_anti_level in [AntiCrawlerLevel.HIGH, AntiCrawlerLevel.EXTREME]
        )
    
    def should_ban_ip(self) -> bool:
        """判断是否应该认为IP被封禁"""
        return (
            self.metrics.consecutive_blocks >= self.ip_ban_threshold or
            self.current_anti_level == AntiCrawlerLevel.EXTREME
        )
    
    def _extract_site(self, url: str) -> str:
        """提取网站域名"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return "unknown"
    
    def _update_site_stats(self, site: str, stat_type: str):
        """更新网站统计"""
        if site not in self.metrics.site_stats:
            self.metrics.site_stats[site] = {
                "total": 0, "success": 0, "blocked": 0, 
                "captcha": 0, "rate_limited": 0
            }
        
        self.metrics.site_stats[site][stat_type] += 1
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """获取检测摘要"""
        return {
            "current_level": self.current_anti_level.value,
            "total_requests": self.metrics.total_requests,
            "success_rate": f"{self.metrics.success_rate:.1%}",
            "block_rate": f"{self.metrics.block_rate:.1%}",
            "consecutive_blocks": self.metrics.consecutive_blocks,
            "last_blocked": self.metrics.last_blocked_time.isoformat() if self.metrics.last_blocked_time else None,
            "adaptive_delay": f"{self.get_adaptive_delay():.1f}s",
            "should_switch_proxy": self.should_switch_proxy(),
            "site_stats": dict(self.metrics.site_stats)
        }
    
    def print_detection_report(self):
        """打印检测报告"""
        summary = self.get_detection_summary()
        
        self.logger.info("=" * 60)
        self.logger.info("🛡️  反爬检测报告")
        self.logger.info("=" * 60)
        self.logger.info(f"当前反爬级别: {summary['current_level'].upper()}")
        self.logger.info(f"总请求数: {summary['total_requests']}")
        self.logger.info(f"成功率: {summary['success_rate']}")
        self.logger.info(f"阻止率: {summary['block_rate']}")
        self.logger.info(f"连续失败: {summary['consecutive_blocks']}")
        self.logger.info(f"建议延迟: {summary['adaptive_delay']}")
        self.logger.info(f"建议切换代理: {'是' if summary['should_switch_proxy'] else '否'}")
        
        if summary['site_stats']:
            self.logger.info("\n📊 各网站统计:")
            for site, stats in summary['site_stats'].items():
                success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
                self.logger.info(f"  {site}: 成功率 {success_rate:.1%} ({stats['success']}/{stats['total']})")
        
        self.logger.info("=" * 60)


# 全局检测器实例
_global_detector: Optional[EnhancedAntiDetection] = None


def get_anti_detection() -> EnhancedAntiDetection:
    """获取全局反爬检测器实例"""
    global _global_detector
    if _global_detector is None:
        _global_detector = EnhancedAntiDetection()
    return _global_detector


async def test_anti_detection():
    """测试反爬检测功能"""
    detector = get_anti_detection()
    
    # 模拟正常响应
    class MockResponse:
        def __init__(self, status, headers):
            self.status = status
            self.headers = headers
    
    # 测试正常响应
    normal_response = MockResponse(200, {})
    normal_content = "<html><head><title>正常页面</title></head><body>大量正常内容...</body></html>" * 10
    
    result, level = await detector.analyze_response(
        normal_response, normal_content, "https://example.com/test", 2.5
    )
    
    print(f"正常响应检测: {result.value}, 级别: {level.value}")
    
    # 测试403响应
    blocked_response = MockResponse(403, {})
    blocked_content = "Access Denied - Your IP has been blocked"
    
    result, level = await detector.analyze_response(
        blocked_response, blocked_content, "https://example.com/test", 0.1
    )
    
    print(f"403响应检测: {result.value}, 级别: {level.value}")
    
    # 打印报告
    detector.print_detection_report()


if __name__ == "__main__":
    asyncio.run(test_anti_detection()) 