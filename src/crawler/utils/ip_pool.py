#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能IP池管理系统
支持：
1. 免费代理自动获取
2. 代理健康检查
3. 智能轮换策略
4. 失败自动移除
5. 实时状态监控
"""

import asyncio
import aiohttp
import random
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from loguru import logger
import threading
from concurrent.futures import ThreadPoolExecutor


class ProxyInfo:
    """代理信息类"""
    
    def __init__(self, ip: str, port: int, proxy_type: str = "http", 
                 username: str = None, password: str = None):
        self.ip = ip
        self.port = port
        self.proxy_type = proxy_type.lower()
        self.username = username
        self.password = password
        
        # 统计信息
        self.success_count = 0
        self.failure_count = 0
        self.last_used = None
        self.last_check = None
        self.response_time = float('inf')
        self.is_alive = True
        
        # 创建时间
        self.created_at = datetime.now()
    
    @property
    def proxy_url(self) -> str:
        """获取代理URL"""
        if self.username and self.password:
            return f"{self.proxy_type}://{self.username}:{self.password}@{self.ip}:{self.port}"
        else:
            return f"{self.proxy_type}://{self.ip}:{self.port}"
    
    @property
    def proxy_dict(self) -> Dict[str, str]:
        """获取aiohttp格式的代理字典"""
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
        
        # 失败率过高时标记为死亡
        if self.failure_count > 5 and self.success_rate < 0.3:
            self.is_alive = False
    
    def __str__(self):
        return f"{self.ip}:{self.port} (成功率: {self.success_rate:.1%}, 响应: {self.response_time:.2f}s)"


class FreeProxyFetcher:
    """免费代理获取器"""
    
    def __init__(self):
        self.logger = logger
        
        # 免费代理API列表
        self.proxy_apis = [
            {
                "name": "ProxyList",
                "url": "https://www.proxy-list.download/api/v1/get?type=http",
                "parser": self._parse_proxylist_response
            },
            {
                "name": "FreeProxyList", 
                "url": "https://free-proxy-list.net/",
                "parser": self._parse_html_table
            },
            {
                "name": "ProxyScrape",
                "url": "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
                "parser": self._parse_proxyscrape_response
            }
        ]
    
    async def fetch_proxies(self, limit: int = 50) -> List[ProxyInfo]:
        """获取免费代理列表"""
        all_proxies = []
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for api_info in self.proxy_apis:
                try:
                    self.logger.info(f"从{api_info['name']}获取代理...")
                    proxies = await self._fetch_from_api(session, api_info)
                    all_proxies.extend(proxies)
                    self.logger.info(f"从{api_info['name']}获取到{len(proxies)}个代理")
                    
                    if len(all_proxies) >= limit:
                        break
                        
                except Exception as e:
                    self.logger.warning(f"从{api_info['name']}获取代理失败: {e}")
        
        # 去重并限制数量
        unique_proxies = self._deduplicate_proxies(all_proxies)
        return unique_proxies[:limit]
    
    async def _fetch_from_api(self, session: aiohttp.ClientSession, 
                            api_info: Dict) -> List[ProxyInfo]:
        """从单个API获取代理"""
        try:
            async with session.get(api_info["url"]) as response:
                if response.status == 200:
                    content = await response.text()
                    return api_info["parser"](content)
                else:
                    self.logger.warning(f"{api_info['name']} API返回状态码: {response.status}")
                    return []
        except Exception as e:
            self.logger.error(f"请求{api_info['name']} API失败: {e}")
            return []
    
    def _parse_proxylist_response(self, content: str) -> List[ProxyInfo]:
        """解析ProxyList API响应"""
        proxies = []
        try:
            for line in content.strip().split('\n'):
                if ':' in line:
                    ip, port = line.strip().split(':')
                    proxies.append(ProxyInfo(ip, int(port)))
        except Exception as e:
            self.logger.error(f"解析ProxyList响应失败: {e}")
        return proxies
    
    def _parse_proxyscrape_response(self, content: str) -> List[ProxyInfo]:
        """解析ProxyScrape API响应"""
        proxies = []
        try:
            for line in content.strip().split('\n'):
                if ':' in line:
                    ip, port = line.strip().split(':')
                    proxies.append(ProxyInfo(ip, int(port)))
        except Exception as e:
            self.logger.error(f"解析ProxyScrape响应失败: {e}")
        return proxies
    
    def _parse_html_table(self, content: str) -> List[ProxyInfo]:
        """解析HTML表格格式的代理列表"""
        proxies = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # 查找代理表格
            table = soup.find('table', {'id': 'proxylisttable'})
            if table:
                rows = table.find_all('tr')[1:]  # 跳过表头
                for row in rows[:20]:  # 只取前20个
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        if ip and port.isdigit():
                            proxies.append(ProxyInfo(ip, int(port)))
        except ImportError:
            self.logger.warning("需要安装BeautifulSoup4来解析HTML: pip install beautifulsoup4")
        except Exception as e:
            self.logger.error(f"解析HTML表格失败: {e}")
        return proxies
    
    def _deduplicate_proxies(self, proxies: List[ProxyInfo]) -> List[ProxyInfo]:
        """去重代理列表"""
        seen = set()
        unique_proxies = []
        for proxy in proxies:
            key = f"{proxy.ip}:{proxy.port}"
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)
        return unique_proxies


class ProxyChecker:
    """代理检查器"""
    
    def __init__(self):
        self.logger = logger
        
        # 测试URL列表
        self.test_urls = [
            "http://httpbin.org/ip",
            "https://api.ipify.org?format=json",
            "http://icanhazip.com/"
        ]
    
    async def check_proxy(self, proxy: ProxyInfo, timeout: float = 10.0) -> bool:
        """检查单个代理是否可用"""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                
                # 随机选择一个测试URL
                test_url = random.choice(self.test_urls)
                
                async with session.get(test_url, proxy=proxy.proxy_url) as response:
                    if response.status == 200:
                        response_time = time.time() - start_time
                        proxy.mark_success(response_time)
                        proxy.last_check = datetime.now()
                        self.logger.debug(f"代理检查成功: {proxy.ip}:{proxy.port} ({response_time:.2f}s)")
                        return True
                    else:
                        proxy.mark_failure()
                        return False
                        
        except Exception as e:
            proxy.mark_failure()
            self.logger.debug(f"代理检查失败: {proxy.ip}:{proxy.port} - {e}")
            return False
    
    async def batch_check_proxies(self, proxies: List[ProxyInfo], 
                                concurrent: int = 10) -> List[ProxyInfo]:
        """批量检查代理"""
        self.logger.info(f"开始批量检查{len(proxies)}个代理...")
        
        semaphore = asyncio.Semaphore(concurrent)
        
        async def check_with_semaphore(proxy):
            async with semaphore:
                return await self.check_proxy(proxy)
        
        # 并发检查所有代理
        tasks = [check_with_semaphore(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 筛选可用代理
        working_proxies = []
        for proxy, result in zip(proxies, results):
            if result is True and proxy.is_alive:
                working_proxies.append(proxy)
        
        self.logger.info(f"代理检查完成: {len(working_proxies)}/{len(proxies)} 可用")
        return working_proxies


class SmartIPPool:
    """智能IP池管理器"""
    
    def __init__(self, min_proxies: int = 5, max_proxies: int = 50):
        self.logger = logger
        self.min_proxies = min_proxies
        self.max_proxies = max_proxies
        
        # 代理池
        self.proxies: List[ProxyInfo] = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        
        # 组件
        self.fetcher = FreeProxyFetcher()
        self.checker = ProxyChecker()
        
        # 状态
        self.last_refresh = None
        self.refresh_interval = timedelta(hours=1)  # 1小时刷新一次
        
        # 统计
        self.total_requests = 0
        self.total_failures = 0
    
    async def initialize(self):
        """初始化IP池"""
        self.logger.info("初始化IP池...")
        await self.refresh_proxies()
    
    async def refresh_proxies(self):
        """刷新代理池"""
        async with self.lock:
            self.logger.info("开始刷新代理池...")
            
            # 获取新的代理
            new_proxies = await self.fetcher.fetch_proxies(self.max_proxies)
            
            if new_proxies:
                # 检查可用性
                working_proxies = await self.checker.batch_check_proxies(new_proxies)
                
                # 更新代理池
                self.proxies = working_proxies
                self.current_index = 0
                self.last_refresh = datetime.now()
                
                self.logger.success(f"代理池刷新完成: {len(self.proxies)}个可用代理")
            else:
                self.logger.warning("未能获取到新代理")
    
    async def get_proxy(self) -> Optional[ProxyInfo]:
        """获取下一个可用代理"""
        async with self.lock:
            # 检查是否需要刷新
            if self._should_refresh():
                await self.refresh_proxies()
            
            # 如果没有可用代理
            if not self.proxies:
                self.logger.warning("代理池为空")
                return None
            
            # 轮换获取代理
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            self.total_requests += 1
            return proxy
    
    async def mark_proxy_failed(self, proxy: ProxyInfo):
        """标记代理失败"""
        proxy.mark_failure()
        self.total_failures += 1
        
        # 如果代理失败过多，从池中移除
        if not proxy.is_alive:
            async with self.lock:
                try:
                    self.proxies.remove(proxy)
                    self.logger.info(f"移除失效代理: {proxy.ip}:{proxy.port}")
                    
                    # 如果代理数量过少，立即刷新
                    if len(self.proxies) < self.min_proxies:
                        self.logger.warning(f"代理数量不足({len(self.proxies)})，开始紧急刷新...")
                        await self.refresh_proxies()
                        
                except ValueError:
                    pass  # 代理已经被移除
    
    def _should_refresh(self) -> bool:
        """判断是否需要刷新代理池"""
        if not self.last_refresh:
            return True
        
        # 时间间隔刷新
        if datetime.now() - self.last_refresh > self.refresh_interval:
            return True
        
        # 代理数量不足刷新
        if len(self.proxies) < self.min_proxies:
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        working_count = len([p for p in self.proxies if p.is_alive])
        
        return {
            "total_proxies": len(self.proxies),
            "working_proxies": working_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "failure_rate": self.total_failures / self.total_requests if self.total_requests > 0 else 0.0,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "next_refresh": (self.last_refresh + self.refresh_interval).isoformat() if self.last_refresh else None
        }
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("📊 IP池统计信息")
        print("="*50)
        print(f"总代理数: {stats['total_proxies']}")
        print(f"可用代理: {stats['working_proxies']}")
        print(f"总请求数: {stats['total_requests']}")
        print(f"失败次数: {stats['total_failures']}")
        print(f"失败率: {stats['failure_rate']:.1%}")
        print(f"上次刷新: {stats['last_refresh']}")
        print(f"下次刷新: {stats['next_refresh']}")
        
        if self.proxies:
            print(f"\n🌐 当前代理列表:")
            for i, proxy in enumerate(self.proxies[:10], 1):  # 只显示前10个
                status = "✅" if proxy.is_alive else "❌"
                print(f"  {i}. {status} {proxy}")
        
        print("="*50)


# 全局IP池实例
_global_ip_pool: Optional[SmartIPPool] = None


async def get_ip_pool() -> SmartIPPool:
    """获取全局IP池实例"""
    global _global_ip_pool
    
    if _global_ip_pool is None:
        _global_ip_pool = SmartIPPool()
        await _global_ip_pool.initialize()
    
    return _global_ip_pool


async def test_ip_pool():
    """测试IP池功能"""
    print("🧪 IP池功能测试")
    
    # 创建IP池
    ip_pool = SmartIPPool(min_proxies=3, max_proxies=20)
    await ip_pool.initialize()
    
    # 显示统计
    ip_pool.print_stats()
    
    # 测试获取代理
    print("\n🔄 测试代理获取:")
    for i in range(5):
        proxy = await ip_pool.get_proxy()
        if proxy:
            print(f"  {i+1}. 获取代理: {proxy.ip}:{proxy.port}")
        else:
            print(f"  {i+1}. 无可用代理")
    
    print("\n✅ IP池测试完成")


if __name__ == "__main__":
    asyncio.run(test_ip_pool()) 