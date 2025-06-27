#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版代理池管理系统
支持：
1. 付费代理配置 (Trojan, SOCKS5, HTTP等)
2. 免费代理自动获取
3. 代理健康检查和轮换
4. 多种代理协议支持
5. 配置文件热加载
"""

import asyncio
import aiohttp
import random
import time
import json
import toml
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from loguru import logger
from pathlib import Path
import threading
from dataclasses import dataclass, field
from enum import Enum


class ProxyProtocol(Enum):
    """代理协议枚举"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    TROJAN = "trojan"


class ProxyType(Enum):
    """代理类型枚举"""
    FREE = "free"
    PAID = "paid"


@dataclass
class EnhancedProxyInfo:
    """增强版代理信息类"""
    name: str
    address: str
    port: int
    protocol: ProxyProtocol
    proxy_type: ProxyType
    
    # 认证信息
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Trojan特有配置
    sni: Optional[str] = None
    tls: bool = False
    transport: str = "tcp"
    network: str = "tcp"
    flow: str = ""
    alpn: str = ""
    fingerprint: str = ""
    allowInsecure: bool = False
    
    # 统计信息
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    last_check: Optional[datetime] = None
    response_time: float = float('inf')
    is_alive: bool = True
    priority: int = 1
    
    # 元数据
    remarks: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """后初始化处理"""
        if isinstance(self.protocol, str):
            self.protocol = ProxyProtocol(self.protocol.lower())
        if isinstance(self.proxy_type, str):
            self.proxy_type = ProxyType(self.proxy_type.lower())
    
    @property
    def proxy_url(self) -> str:
        """获取代理URL"""
        if self.protocol == ProxyProtocol.TROJAN:
            # Trojan协议特殊处理
            return f"trojan://{self.password}@{self.address}:{self.port}"
        elif self.username and self.password:
            return f"{self.protocol.value}://{self.username}:{self.password}@{self.address}:{self.port}"
        else:
            return f"{self.protocol.value}://{self.address}:{self.port}"
    
    @property
    def proxy_dict(self) -> Dict[str, str]:
        """获取aiohttp格式的代理字典"""
        if self.protocol in [ProxyProtocol.HTTP, ProxyProtocol.HTTPS]:
            return {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        elif self.protocol in [ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5]:
            return {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
        else:
            # Trojan等特殊协议需要特殊处理
            return {
                'http': self.proxy_url,
                'https': self.proxy_url
            }
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def mark_success(self, response_time: float = None):
        """标记成功使用"""
        self.success_count += 1
        self.last_used = datetime.now()
        if response_time:
            self.response_time = min(self.response_time, response_time)
        self.is_alive = True
    
    def mark_failure(self):
        """标记失败使用"""
        self.failure_count += 1
        self.last_used = datetime.now()
        
        # 付费代理更宽容，免费代理更严格
        if self.proxy_type == ProxyType.PAID:
            # 付费代理：连续失败10次才标记为死亡
            if self.failure_count > 10 and self.success_rate < 0.2:
                self.is_alive = False
        else:
            # 免费代理：连续失败5次就标记为死亡
            if self.failure_count > 5 and self.success_rate < 0.3:
                self.is_alive = False
    
    def __str__(self):
        return f"{self.name} [{self.address}:{self.port}] (成功率: {self.success_rate:.1%}, 响应: {self.response_time:.2f}s)"


class ProxyConfigLoader:
    """代理配置加载器"""
    
    @staticmethod
    def load_from_toml(config_path: str) -> Dict[str, Any]:
        """从TOML文件加载代理配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"代理配置文件不存在: {config_path}")
            return {}
        
        try:
            config = toml.load(config_file)
            logger.info(f"加载代理配置: {config_path}")
            return config
        except Exception as e:
            logger.error(f"加载代理配置失败: {e}")
            return {}
    
    @staticmethod
    def parse_paid_proxies(config: Dict[str, Any]) -> List[EnhancedProxyInfo]:
        """解析付费代理配置"""
        proxies = []
        
        paid_config = config.get('proxy_pool', {}).get('paid_proxies', {})
        if not paid_config.get('enabled', False):
            return proxies
        
        servers = paid_config.get('servers', [])
        priority = paid_config.get('priority', 1)
        
        for server in servers:
            try:
                proxy = EnhancedProxyInfo(
                    name=server.get('name', 'Unknown'),
                    address=server['address'],
                    port=server['port'],
                    protocol=server.get('protocol', 'http'),
                    proxy_type=ProxyType.PAID,
                    username=server.get('username'),
                    password=server.get('password'),
                    sni=server.get('sni'),
                    tls=server.get('tls', False),
                    transport=server.get('transport', 'tcp'),
                    network=server.get('network', 'tcp'),
                    flow=server.get('flow', ''),
                    alpn=server.get('alpn', ''),
                    fingerprint=server.get('fingerprint', ''),
                    allowInsecure=server.get('allowInsecure', False),
                    priority=priority,
                    remarks=server.get('remarks', '')
                )
                proxies.append(proxy)
                logger.info(f"加载付费代理: {proxy.name}")
            except Exception as e:
                logger.error(f"解析付费代理配置失败: {e}")
        
        return proxies


class EnhancedProxyChecker:
    """增强版代理检查器"""
    
    def __init__(self):
        self.logger = logger
        self.test_urls = [
            "https://httpbin.org/ip",
            "https://ipinfo.io/json",
            "https://api.ipify.org?format=json"
        ]
    
    async def check_proxy(self, proxy: EnhancedProxyInfo, timeout: float = 10.0) -> bool:
        """检查单个代理可用性"""
        start_time = time.time()
        
        try:
            # 根据协议选择检查方式
            if proxy.protocol in [ProxyProtocol.HTTP, ProxyProtocol.HTTPS, 
                                ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5]:
                success = await self._check_http_proxy(proxy, timeout)
            elif proxy.protocol == ProxyProtocol.TROJAN:
                success = await self._check_trojan_proxy(proxy, timeout)
            else:
                logger.warning(f"不支持的代理协议: {proxy.protocol}")
                return False
            
            response_time = time.time() - start_time
            
            if success:
                proxy.mark_success(response_time)
                self.logger.debug(f"代理检查成功: {proxy.name} ({response_time:.2f}s)")
            else:
                proxy.mark_failure()
                self.logger.debug(f"代理检查失败: {proxy.name}")
            
            proxy.last_check = datetime.now()
            return success
            
        except Exception as e:
            proxy.mark_failure()
            proxy.last_check = datetime.now()
            self.logger.debug(f"代理检查异常: {proxy.name} - {e}")
            return False
    
    async def _check_http_proxy(self, proxy: EnhancedProxyInfo, timeout: float) -> bool:
        """检查HTTP/HTTPS/SOCKS代理"""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config
            ) as session:
                
                test_url = random.choice(self.test_urls)
                
                async with session.get(
                    test_url,
                    proxy=proxy.proxy_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        # 验证IP是否变化
                        return 'ip' in data or 'origin' in data
            
            return False
            
        except Exception:
            return False
    
    async def _check_trojan_proxy(self, proxy: EnhancedProxyInfo, timeout: float) -> bool:
        """检查Trojan代理 (需要特殊客户端)"""
        # Trojan代理检查比较复杂，这里简化处理
        # 实际应用中可能需要使用专门的Trojan客户端
        try:
            # 尝试建立连接
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.address, proxy.port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def batch_check_proxies(self, proxies: List[EnhancedProxyInfo], 
                                concurrent: int = 10) -> List[EnhancedProxyInfo]:
        """批量检查代理可用性"""
        semaphore = asyncio.Semaphore(concurrent)
        
        async def check_with_semaphore(proxy):
            async with semaphore:
                await self.check_proxy(proxy)
                return proxy
        
        tasks = [check_with_semaphore(proxy) for proxy in proxies]
        checked_proxies = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_proxies = [p for p in checked_proxies if isinstance(p, EnhancedProxyInfo) and p.is_alive]
        
        self.logger.info(f"代理检查完成: {len(valid_proxies)}/{len(proxies)} 可用")
        return valid_proxies


class EnhancedProxyPool:
    """增强版代理池 - 支持多地区IP轮换对抗WAF"""
    
    def __init__(self, config_path: str = "config/proxy_config.toml"):
        self.config_path = config_path
        self.config = {}
        self.state_file = "proxy_state.json"
        
        # 代理存储
        self.paid_proxies: List[EnhancedProxyInfo] = []
        self.free_proxies: List[EnhancedProxyInfo] = []
        self.all_proxies: List[EnhancedProxyInfo] = []
        
        # 轮换策略 - 从持久化状态加载
        self.current_paid_index = 0
        self.current_free_index = 0
        self.force_rotation_after_uses = 10  # 强制轮换频率
        self.uses_since_rotation = 0
        self.last_used_proxy = None
        self.rotation_count = 0
        
        # 加载持久化状态
        self._load_state()
        
        # WAF对抗策略
        self.waf_detection_keywords = [
            "Access Denied", "403 Forbidden", "blocked", "security", 
            "captcha", "验证码", "安全验证", "访问被拒绝"
        ]
        self.proxy_cooldown = {}  # 代理冷却时间
        self.cooldown_duration = 300  # 5分钟冷却
        
        # 健康检查
        self.checker = EnhancedProxyChecker()
        self.last_check_time = None
        self.check_interval = timedelta(minutes=30)
        
        self._lock = threading.Lock()
        logger.info("增强版代理池初始化完成")
        
    def _load_state(self):
        """加载持久化状态"""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.current_paid_index = state.get('current_paid_index', 0)
                    self.current_free_index = state.get('current_free_index', 0)
                    self.rotation_count = state.get('rotation_count', 0)
                    logger.debug(f"加载代理状态: paid_index={self.current_paid_index}, rotation_count={self.rotation_count}")
        except Exception as e:
            logger.warning(f"加载代理状态失败: {e}")
            
    def _save_state(self):
        """保存持久化状态"""
        try:
            state = {
                'current_paid_index': self.current_paid_index,
                'current_free_index': self.current_free_index,
                'rotation_count': self.rotation_count,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.debug(f"保存代理状态: {state}")
        except Exception as e:
            logger.warning(f"保存代理状态失败: {e}")
    
    async def initialize(self):
        """初始化代理池"""
        logger.info("初始化增强版代理池...")
        
        # 加载配置
        await self.load_config()
        
        # 加载付费代理
        await self.load_paid_proxies()
        
        # 检查代理可用性
        await self.check_all_proxies()
        
        logger.info(f"代理池初始化完成: 付费代理 {len(self.paid_proxies)}, 免费代理 {len(self.free_proxies)}")
    
    async def load_config(self):
        """加载配置文件"""
        self.config = ProxyConfigLoader.load_from_toml(self.config_path)
        
        pool_config = self.config.get('proxy_pool', {})
        self.rotation_enabled = pool_config.get('rotation_enabled', True)
        self.check_interval = pool_config.get('check_interval_minutes', 30)
    
    async def load_paid_proxies(self):
        """加载付费代理"""
        paid_proxies = ProxyConfigLoader.parse_paid_proxies(self.config)
        self.paid_proxies = paid_proxies
        logger.info(f"加载付费代理 {len(paid_proxies)} 个")
    
    async def check_all_proxies(self):
        """检查所有代理可用性"""
        all_proxies = self.paid_proxies + self.free_proxies
        if not all_proxies:
            return
        
        logger.info("开始检查代理可用性...")
        valid_proxies = await self.checker.batch_check_proxies(all_proxies)
        
        # 更新代理列表
        self.paid_proxies = [p for p in self.paid_proxies if p.is_alive]
        self.free_proxies = [p for p in self.free_proxies if p.is_alive]
        
        self.last_check_time = datetime.now()
    
    async def get_proxy(self, prefer_paid: bool = True, force_rotation: bool = False) -> Optional[EnhancedProxyInfo]:
        """
        获取代理 - 增强IP轮换策略
        
        Args:
            prefer_paid: 优先使用付费代理
            force_rotation: 强制轮换到下一个代理
        """
        with self._lock:
            # 检查是否需要刷新代理
            if self._should_refresh():
                await self.check_all_proxies()
            
            # 强制轮换检查
            if (force_rotation or 
                self.uses_since_rotation >= self.force_rotation_after_uses):
                logger.info("🔄 触发强制IP轮换")
                self.uses_since_rotation = 0
                return await self._get_next_rotation_proxy(prefer_paid)
            
            # 正常获取代理（优先使用可用的付费代理）
            if prefer_paid and self.paid_proxies:
                proxy = await self._get_best_paid_proxy()
                if proxy:
                    self.uses_since_rotation += 1
                    self.last_used_proxy = proxy
                    return proxy
            
            # 备选：使用免费代理
            if self.free_proxies:
                proxy = self._select_proxy_from_list(self.free_proxies)
                if proxy:
                    self.uses_since_rotation += 1
                    self.last_used_proxy = proxy
                    return proxy
            
            return None
    
    def _select_proxy_from_list(self, proxy_list: List[EnhancedProxyInfo]) -> Optional[EnhancedProxyInfo]:
        """从代理列表中选择代理"""
        if not proxy_list:
            return None
        
        # 过滤可用代理
        available_proxies = [p for p in proxy_list if p.is_alive]
        if not available_proxies:
            return None
        
        if self.rotation_enabled:
            # 轮换策略：按成功率和响应时间排序
            available_proxies.sort(key=lambda x: (-x.success_rate, x.response_time))
            self.current_proxy_index = (self.current_proxy_index + 1) % len(available_proxies)
            return available_proxies[self.current_proxy_index]
        else:
            # 随机策略
            return random.choice(available_proxies)
    
    def _should_refresh(self) -> bool:
        """判断是否需要刷新代理"""
        if not self.last_check_time:
            return True
        
        time_since_last_check = datetime.now() - self.last_check_time
        return time_since_last_check > timedelta(minutes=self.check_interval)
    
    async def mark_proxy_failed(self, proxy: EnhancedProxyInfo):
        """标记代理失败"""
        proxy.mark_failure()
        logger.debug(f"标记代理失败: {proxy.name}")
    
    async def mark_proxy_success(self, proxy: EnhancedProxyInfo, response_time: float = None):
        """标记代理成功"""
        proxy.mark_success(response_time)
        logger.debug(f"标记代理成功: {proxy.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取代理池统计信息"""
        paid_alive = len([p for p in self.paid_proxies if p.is_alive])
        free_alive = len([p for p in self.free_proxies if p.is_alive])
        
        return {
            "total_proxies": len(self.paid_proxies) + len(self.free_proxies),
            "paid_proxies": {
                "total": len(self.paid_proxies),
                "alive": paid_alive,
                "success_rate": sum(p.success_rate for p in self.paid_proxies) / len(self.paid_proxies) if self.paid_proxies else 0
            },
            "free_proxies": {
                "total": len(self.free_proxies),
                "alive": free_alive,
                "success_rate": sum(p.success_rate for p in self.free_proxies) / len(self.free_proxies) if self.free_proxies else 0
            },
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None
        }
    
    def print_stats(self):
        """打印代理池统计信息"""
        stats = self.get_stats()
        
        logger.info("=== 代理池统计 ===")
        logger.info(f"总代理数: {stats['total_proxies']}")
        logger.info(f"付费代理: {stats['paid_proxies']['alive']}/{stats['paid_proxies']['total']} (成功率: {stats['paid_proxies']['success_rate']:.1%})")
        logger.info(f"免费代理: {stats['free_proxies']['alive']}/{stats['free_proxies']['total']} (成功率: {stats['free_proxies']['success_rate']:.1%})")
        logger.info(f"上次检查: {stats['last_check']}")

    async def _get_next_rotation_proxy(self, prefer_paid: bool = True) -> Optional[EnhancedProxyInfo]:
        """获取下一个轮换代理"""
        if prefer_paid and self.paid_proxies:
            # 轮换到下一个付费代理
            available_proxies = [p for p in self.paid_proxies 
                               if p.is_alive and not self._is_in_cooldown(p)]
            
            if available_proxies:
                # 使用轮换索引选择代理，避免重复
                self.current_paid_index = (self.current_paid_index + 1) % len(available_proxies)
                proxy = available_proxies[self.current_paid_index]
                
                # 如果选中的代理与上次使用的相同，再试一次
                if proxy == self.last_used_proxy and len(available_proxies) > 1:
                    self.current_paid_index = (self.current_paid_index + 1) % len(available_proxies)
                    proxy = available_proxies[self.current_paid_index]
                
                # 更新轮换计数并保存状态
                self.rotation_count += 1
                self._save_state()
                
                logger.info(f"🌏 切换到 {proxy.name} [{proxy.address}] (第{self.rotation_count}次轮换)")
                return proxy
        
        # 备选：轮换免费代理
        if self.free_proxies:
            available_proxies = [p for p in self.free_proxies 
                               if p.is_alive and not self._is_in_cooldown(p)]
            if available_proxies:
                self.current_free_index = (self.current_free_index + 1) % len(available_proxies)
                self._save_state()
                return available_proxies[self.current_free_index]
        
        return None

    async def _get_best_paid_proxy(self) -> Optional[EnhancedProxyInfo]:
        """获取最佳付费代理"""
        available_proxies = [p for p in self.paid_proxies 
                           if p.is_alive and not self._is_in_cooldown(p)]
        
        if not available_proxies:
            return None
        
        # 优先选择成功率高、响应时间短的代理
        available_proxies.sort(key=lambda p: (
            -p.success_rate,  # 成功率高优先
            p.response_time,  # 响应时间短优先
            -p.priority       # 优先级高优先
        ))
        
        return available_proxies[0]

    def _select_by_region_priority(self, proxies: List[EnhancedProxyInfo]) -> EnhancedProxyInfo:
        """按地区优先级选择代理"""
        # 地区优先级（针对中国网站访问）
        region_priority = {
            '香港': 1, '台湾': 2, '日本': 3, 
            '马来西亚': 4, '加拿大': 5
        }
        
        # 按地区优先级排序
        sorted_proxies = sorted(proxies, key=lambda p: (
            region_priority.get(self._extract_region(p.name), 99),
            -p.success_rate,
            p.response_time
        ))
        
        return sorted_proxies[0]

    def _extract_region(self, proxy_name: str) -> str:
        """从代理名称提取地区"""
        for region in ['香港', '台湾', '日本', '马来西亚', '加拿大']:
            if region in proxy_name:
                return region
        return '未知'

    def _is_in_cooldown(self, proxy: EnhancedProxyInfo) -> bool:
        """检查代理是否在冷却期"""
        cooldown_key = f"{proxy.address}:{proxy.port}"
        if cooldown_key in self.proxy_cooldown:
            cooldown_until = self.proxy_cooldown[cooldown_key]
            if datetime.now() < cooldown_until:
                return True
            else:
                # 冷却期结束，移除记录
                del self.proxy_cooldown[cooldown_key]
        return False

    async def handle_waf_detection(self, proxy: EnhancedProxyInfo, response_text: str = ""):
        """
        处理WAF检测
        
        Args:
            proxy: 被检测到的代理
            response_text: 响应内容，用于检测WAF特征
        """
        # 检测WAF特征
        is_waf = any(keyword.lower() in response_text.lower() 
                    for keyword in self.waf_detection_keywords)
        
        if is_waf:
            logger.warning(f"🛡️ 检测到WAF阻断: {proxy.name} [{proxy.address}]")
            
            # 立即将该代理加入冷却期
            cooldown_key = f"{proxy.address}:{proxy.port}"
            self.proxy_cooldown[cooldown_key] = datetime.now() + timedelta(seconds=self.cooldown_duration)
            
            # 标记代理失败
            await self.mark_proxy_failed(proxy)
            
            # 强制轮换到下一个代理
            self.uses_since_rotation = self.force_rotation_after_uses
            
            logger.info(f"⏰ {proxy.name} 已冷却 {self.cooldown_duration//60} 分钟")

    async def get_proxy_for_waf_bypass(self) -> Optional[EnhancedProxyInfo]:
        """获取专门用于绕过WAF的代理"""
        # 强制轮换，避免使用最近的代理
        return await self.get_proxy(prefer_paid=True, force_rotation=True)


# 全局代理池实例
_global_proxy_pool: Optional[EnhancedProxyPool] = None


async def get_enhanced_proxy_pool(config_path: str = "config/proxy_config.toml") -> EnhancedProxyPool:
    """获取全局代理池实例"""
    global _global_proxy_pool
    
    if _global_proxy_pool is None:
        _global_proxy_pool = EnhancedProxyPool(config_path)
        await _global_proxy_pool.initialize()
    
    return _global_proxy_pool


async def test_enhanced_proxy_pool():
    """测试增强版代理池"""
    logger.info("测试增强版代理池...")
    
    pool = await get_enhanced_proxy_pool()
    pool.print_stats()
    
    # 获取几个代理进行测试
    for i in range(3):
        proxy = await pool.get_proxy()
        if proxy:
            logger.info(f"获取代理 {i+1}: {proxy}")
        else:
            logger.warning(f"无可用代理 {i+1}")


if __name__ == "__main__":
    asyncio.run(test_enhanced_proxy_pool()) 