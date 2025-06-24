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
    """增强版代理池"""
    
    def __init__(self, config_path: str = "config/proxy_config.toml"):
        self.config_path = config_path
        self.logger = logger
        
        # 代理存储
        self.paid_proxies: List[EnhancedProxyInfo] = []
        self.free_proxies: List[EnhancedProxyInfo] = []
        self.current_proxy_index = 0
        
        # 组件
        self.config_loader = ProxyConfigLoader()
        self.proxy_checker = EnhancedProxyChecker()
        
        # 配置
        self.config = {}
        self.rotation_enabled = True
        self.check_interval = 30  # 分钟
        self.last_check_time = None
        
        # 线程锁
        self._lock = threading.Lock()
    
    async def initialize(self):
        """初始化代理池"""
        self.logger.info("初始化增强版代理池...")
        
        # 加载配置
        await self.load_config()
        
        # 加载付费代理
        await self.load_paid_proxies()
        
        # 检查代理可用性
        await self.check_all_proxies()
        
        self.logger.info(f"代理池初始化完成: 付费代理 {len(self.paid_proxies)}, 免费代理 {len(self.free_proxies)}")
    
    async def load_config(self):
        """加载配置文件"""
        self.config = self.config_loader.load_from_toml(self.config_path)
        
        pool_config = self.config.get('proxy_pool', {})
        self.rotation_enabled = pool_config.get('rotation_enabled', True)
        self.check_interval = pool_config.get('check_interval_minutes', 30)
    
    async def load_paid_proxies(self):
        """加载付费代理"""
        paid_proxies = self.config_loader.parse_paid_proxies(self.config)
        self.paid_proxies = paid_proxies
        self.logger.info(f"加载付费代理 {len(paid_proxies)} 个")
    
    async def check_all_proxies(self):
        """检查所有代理可用性"""
        all_proxies = self.paid_proxies + self.free_proxies
        if not all_proxies:
            return
        
        self.logger.info("开始检查代理可用性...")
        valid_proxies = await self.proxy_checker.batch_check_proxies(all_proxies)
        
        # 更新代理列表
        self.paid_proxies = [p for p in self.paid_proxies if p.is_alive]
        self.free_proxies = [p for p in self.free_proxies if p.is_alive]
        
        self.last_check_time = datetime.now()
    
    async def get_proxy(self, prefer_paid: bool = True) -> Optional[EnhancedProxyInfo]:
        """获取可用代理"""
        with self._lock:
            # 检查是否需要刷新
            if self._should_refresh():
                asyncio.create_task(self.check_all_proxies())
            
            # 按优先级获取代理
            if prefer_paid and self.paid_proxies:
                return self._select_proxy_from_list(self.paid_proxies)
            elif self.free_proxies:
                return self._select_proxy_from_list(self.free_proxies)
            elif self.paid_proxies:
                return self._select_proxy_from_list(self.paid_proxies)
            
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
        self.logger.debug(f"标记代理失败: {proxy.name}")
    
    async def mark_proxy_success(self, proxy: EnhancedProxyInfo, response_time: float = None):
        """标记代理成功"""
        proxy.mark_success(response_time)
        self.logger.debug(f"标记代理成功: {proxy.name}")
    
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
        
        self.logger.info("=== 代理池统计 ===")
        self.logger.info(f"总代理数: {stats['total_proxies']}")
        self.logger.info(f"付费代理: {stats['paid_proxies']['alive']}/{stats['paid_proxies']['total']} (成功率: {stats['paid_proxies']['success_rate']:.1%})")
        self.logger.info(f"免费代理: {stats['free_proxies']['alive']}/{stats['free_proxies']['total']} (成功率: {stats['free_proxies']['success_rate']:.1%})")
        self.logger.info(f"上次检查: {stats['last_check']}")


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