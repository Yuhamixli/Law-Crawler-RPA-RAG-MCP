#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于搜索引擎的政府网法规爬虫 - 重构版
通过DuckDuckGo和Bing搜索 site:gov.cn 的法规文档
"""

import asyncio
import aiohttp
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, urljoin, urlparse, quote
from bs4 import BeautifulSoup
from loguru import logger
import random
import time

# 添加Selenium相关导入
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from ..base_crawler import BaseCrawler
from ..utils.ip_pool import get_ip_pool, SmartIPPool
from ..utils.enhanced_proxy_pool import get_enhanced_proxy_pool, EnhancedProxyPool
from ..utils.anti_detection_enhanced import get_anti_detection, EnhancedAntiDetection, ResponseAnalysisResult, AntiCrawlerLevel
from config.settings import get_settings


class AntiDetectionManager:
    """反反爬检测管理器"""
    
    def __init__(self):
        self.logger = logger
        
        # 现在使用真实的代理池
        self.enhanced_proxy_pool: Optional[EnhancedProxyPool] = None
        self.ip_pool: Optional[SmartIPPool] = None
        
        # User-Agent池
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ]
        
        # 请求延迟配置 - 极速优化版
        self.delay_config = {
            'min_delay': 0.5,  # 最小延迟大幅减少
            'max_delay': 1.5,  # 最大延迟大幅减少
            'retry_delay': 3.0,  # 重试延迟减少
            'timeout': 10.0,  # 请求超时减少
        }
        
        # 失败计数
        self.failure_counts = {}
    
    async def initialize_proxy_pools(self):
        """初始化代理池"""
        settings = get_settings()
        
        try:
            # 1. 优先使用enhanced_proxy_pool
            if settings.proxy_pool.enabled:
                self.enhanced_proxy_pool = await get_enhanced_proxy_pool()
                self.logger.success("Enhanced代理池初始化成功")
        except Exception as e:
            self.logger.warning(f"Enhanced代理池初始化失败: {e}")
        
        try:
            # 2. IP池作为备用
            if settings.ip_pool.enabled:
                from ..utils.ip_pool import get_ip_pool
                self.ip_pool = await get_ip_pool()
                self.logger.success("IP池初始化成功")
        except Exception as e:
            self.logger.warning(f"IP池初始化失败: {e}")
    
    def get_proxy(self):
        """获取代理 - 完全禁用，强制直连"""
        # 完全禁用代理，使用直连模式提高稳定性
        return None
        
        # # 原代理获取逻辑已禁用
        # try:
        #     # 优先使用Enhanced代理池
        #     if self.enhanced_proxy_pool:
        #         proxy_info = await self.enhanced_proxy_pool.get_proxy(prefer_paid=True)
        #         if proxy_info:
        #             self.logger.debug(f"使用Enhanced代理: {proxy_info.name}")
        #             return proxy_info.proxy_url
        # 
        #     # 备用IP池
        #     if self.ip_pool:
        #         proxy_info = await self.ip_pool.get_proxy()
        #         if proxy_info:
        #             self.logger.debug(f"使用IP池代理: {proxy_info.ip}:{proxy_info.port}")
        #             return proxy_info.proxy_url
        # 
        # except Exception as e:
        #     self.logger.debug(f"代理获取失败: {e}")
        # 
        # return None
    
    def mark_proxy_failed(self, proxy_url: str):
        """标记代理失败"""
        # 这里可以通知代理池某个代理失败了
        # 实现会比较复杂，暂时简化
        self.logger.debug(f"标记代理失败: {proxy_url}")
    
    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return random.choice(self.user_agents)
    
    async def smart_delay(self, operation_type: str = "default"):
        """智能延迟"""
        base_delay = random.uniform(self.delay_config['min_delay'], self.delay_config['max_delay'])
        
        # 根据操作类型调整延迟
        if operation_type == "search":
            base_delay *= 1.2  # 搜索操作稍长延迟
        elif operation_type == "retry":
            base_delay = self.delay_config['retry_delay']
            
        await asyncio.sleep(base_delay)
    
    def get_random_headers(self) -> Dict[str, str]:
        """生成随机请求头"""
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头 - get_random_headers的别名"""
        return self.get_random_headers()


class SeleniumSearchEngine:
    """Selenium搜索引擎操作器"""
    
    def __init__(self, anti_detection: AntiDetectionManager):
        self.anti_detection = anti_detection
        self.logger = logger
        self.driver = None
        
    async def setup_driver(self) -> webdriver.Chrome:
        """设置Chrome驱动 - 优化版"""
        try:
            # 导入本地ChromeDriver管理功能
            from ..utils.webdriver_manager import get_local_chromedriver_path
            
            options = Options()
            
            # 基础反检测配置
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 性能优化配置
            options.add_argument('--headless')  # 无头模式提升速度
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
            options.add_argument('--disable-javascript')  # 禁用JS提升速度
            options.add_argument('--no-first-run')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            
            # 随机窗口大小
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            options.add_argument(f'--window-size={width},{height}')
            
            # 随机User-Agent
            user_agent = self.anti_detection.get_random_user_agent()
            options.add_argument(f'--user-agent={user_agent}')
            
            # 禁用图片和媒体加载以提升速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.media_stream": 2,
                "profile.managed_default_content_settings.media_stream": 2
            }
            options.add_experimental_option("prefs", prefs)
            
            # 代理配置 - 使用新的代理池
            proxy_url = self.anti_detection.get_proxy()  # 修复：移除错误的await
            if proxy_url:
                # 解析代理URL
                if proxy_url.startswith('http://'):
                    proxy_address = proxy_url.replace('http://', '')
                elif proxy_url.startswith('https://'):
                    proxy_address = proxy_url.replace('https://', '')
                elif proxy_url.startswith('socks5://'):
                    proxy_address = proxy_url.replace('socks5://', '')
                    options.add_argument(f'--proxy-server=socks5://{proxy_address}')
                else:
                    proxy_address = proxy_url
                
                if not proxy_url.startswith('socks5://'):
                    options.add_argument(f'--proxy-server={proxy_address}')
                    
                self.logger.info(f"Selenium使用代理: {proxy_address}")
            
            # 使用本地缓存的ChromeDriver
            driver_path = get_local_chromedriver_path()
            if driver_path:
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                self.logger.info(f"使用本地缓存的ChromeDriver: {driver_path}")
            else:
                # 回退到默认方式
                driver = webdriver.Chrome(options=options)
                self.logger.info("使用系统PATH中的ChromeDriver")
            
            # 设置超时
            driver.set_page_load_timeout(10)
            driver.implicitly_wait(5)  # 隐式等待5秒
            
            # 执行反检测脚本
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("Selenium Chrome驱动初始化成功（快速模式）")
            return driver
            
        except Exception as e:
            self.logger.error(f"Selenium驱动初始化失败: {e}")
            return None
    
    async def search_with_selenium(self, query: str, engine: str = "baidu") -> List[Dict[str, Any]]:
        """使用Selenium进行搜索"""
        if not self.driver:
            self.driver = await self.setup_driver()
            if not self.driver:
                return []
        
        try:
            results = []
            
            if engine == "baidu":
                results = await self._search_baidu_selenium(query)
            elif engine == "bing":
                results = await self._search_bing_selenium(query)
            elif engine == "google":
                results = await self._search_google_selenium(query)
                
            return results
            
        except Exception as e:
            self.logger.error(f"Selenium搜索失败 ({engine}): {e}")
            return []
    
    async def _search_baidu_selenium(self, query: str) -> List[Dict[str, Any]]:
        """使用Selenium搜索百度"""
        try:
            search_url = f"https://www.baidu.com/s?wd={quote(query + ' site:gov.cn')}"
            self.logger.info(f"Selenium百度搜索: {search_url}")
            
            self.driver.get(search_url)
            
            # 等待搜索结果加载 - 极速优化
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 查找搜索结果
            results = []
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.result')
            
            self.logger.debug(f"找到 {len(result_elements)} 个搜索结果元素")
            
            for i, element in enumerate(result_elements[:3], 1):  # 只取前3个结果，提高速度
                try:
                    # 1. 首先尝试从mu属性获取真实URL（最可靠）
                    real_url = element.get_attribute('mu')
                    
                    # 2. 获取标题
                    title = ""
                    title_selectors = ['h3', 'h3 a', '.t', '.t a']
                    for title_sel in title_selectors:
                        try:
                            title_elem = element.find_element(By.CSS_SELECTOR, title_sel)
                            title = title_elem.text.strip()
                            if title:
                                break
                        except:
                            continue
                    
                    # 3. 如果没有mu属性，尝试从链接获取
                    if not real_url:
                        try:
                            link_elem = element.find_element(By.CSS_SELECTOR, 'h3 a, .t a')
                            link_url = link_elem.get_attribute('href')
                            
                            # 处理百度重定向URL
                            if link_url and 'baidu.com/link?' in link_url:
                                try:
                                    # 尝试从百度链接中提取真实URL
                                    import urllib.parse
                                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link_url).query)
                                    if 'url' in parsed:
                                        real_url = parsed['url'][0]
                                    else:
                                        real_url = link_url  # 保留百度链接作为备用
                                except:
                                    real_url = link_url
                            else:
                                real_url = link_url
                        except:
                            continue
                    
                    # 4. 提取描述
                    description = ""
                    desc_selectors = [
                        '.c-abstract', 
                        '.c-span9', 
                        '.summary-text_560AW',
                        'span[class*="summary"]',
                        'span[class*="abstract"]',
                        '.content-gap_3jlQr'
                    ]
                    for desc_sel in desc_selectors:
                        try:
                            desc_elem = element.find_element(By.CSS_SELECTOR, desc_sel)
                            description = desc_elem.text.strip()
                            if description:
                                break
                        except:
                            continue
                    
                    # 5. 验证是否是有效的政府网结果
                    if real_url and title:
                        # 检查URL或标题中是否包含gov.cn
                        if 'gov.cn' in real_url or 'gov.cn' in title.lower():
                            results.append({
                                'title': title,
                                'url': real_url,
                                'snippet': description,
                                'source': 'Baidu_Selenium',
                                'rank': i
                            })
                            self.logger.debug(f"找到有效结果 {i}: {title} -> {real_url[:100]}...")
                        else:
                            self.logger.debug(f"跳过非政府网结果 {i}: {title}")
                    else:
                        self.logger.debug(f"跳过无效结果 {i}: title={bool(title)}, url={bool(real_url)}")
                        
                except Exception as e:
                    self.logger.debug(f"解析结果元素 {i} 时出错: {e}")
                    continue
            
            self.logger.info(f"Selenium百度找到 {len(results)} 个有效政府网结果")
            return results
            
        except Exception as e:
            self.logger.error(f"Selenium百度搜索失败: {e}")
            return []
    
    async def _search_bing_selenium(self, query: str) -> List[Dict[str, Any]]:
        """使用Selenium搜索Bing"""
        try:
            search_url = f"https://www.bing.com/search?q={quote(query + ' site:gov.cn')}"
            self.logger.info(f"Selenium Bing搜索: {search_url}")
            
            self.driver.get(search_url)
            
            # 等待搜索结果加载 - 极速优化
            await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # 查找Bing搜索结果
            results = []
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, '.b_algo, li.b_algo')
            
            for element in result_elements[:3]:  # 只取前3个结果，提高速度
                try:
                    # 提取标题和链接
                    title_elem = element.find_element(By.CSS_SELECTOR, 'h2 a, .b_title a')
                    title = title_elem.text.strip()
                    url = title_elem.get_attribute('href')
                    
                    # 提取描述
                    description = ""
                    try:
                        desc_elem = element.find_element(By.CSS_SELECTOR, '.b_caption p, .b_snippet')
                        description = desc_elem.text.strip()
                    except:
                        pass
                    
                    if 'gov.cn' in url:
                        results.append({
                            'title': title,
                            'url': url,
                            'snippet': description,
                            'source': 'Bing_Selenium'
                        })
                        
                except Exception as e:
                    continue
            
            self.logger.info(f"Selenium Bing找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"Selenium Bing搜索失败: {e}")
            return []
    
    def close(self):
        """关闭驱动"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Selenium驱动已关闭")
            except:
                pass
            self.driver = None


class SearchEngineCrawler(BaseCrawler):
    """搜索引擎爬虫 - 增强WAF对抗版本"""
    
    def __init__(self, **config):
        super().__init__(source_name="搜索引擎爬虫")
        self.name = "搜索引擎爬虫"
        # 添加logger属性，防止AttributeError
        self.logger = logger
        
        self.search_engines = [
            "https://www.google.com/search?q=",
            "https://www.bing.com/search?q=",
            "https://duckduckgo.com/?q="
        ]
        
        # WAF对抗配置
        self.max_waf_retries = 3
        self.waf_retry_delay = 5  # 秒
        self.proxy_rotation_threshold = 2  # 连续失败2次就轮换IP
        self.consecutive_failures = 0
        
        # 初始化代理池
        self.enhanced_proxy_pool = None
        self.ip_pool = None
        self.current_proxy = None
        self._initialized = False
        
        self.logger.info(f"🔍 {self.name} 初始化完成 - 增强WAF对抗")
        
        # 初始化反检测管理器
        self.anti_detection = AntiDetectionManager()
        
        # 初始化Selenium搜索引擎
        self.selenium_engine = SeleniumSearchEngine(self.anti_detection)
        
        # 初始化标志
        self.initialized = False
        
        # IP池
        self.ip_pool: Optional[SmartIPPool] = None
        
        # 搜索引擎配置 - 优化策略顺序，优先使用直连
        self.search_engines = [
            {
                "name": "DuckDuckGo",
                "enabled": True,
                "priority": 1,  # 最高优先级：快速HTTP搜索
                "api_url": "https://html.duckduckgo.com/html/",
                "method": "requests",
                "use_proxy": False  # 优先直连
            },
            {
                "name": "Bing",
                "enabled": True,
                "priority": 2,  # 次优先级：Bing HTTP搜索
                "api_url": "https://www.bing.com/search",
                "method": "requests",
                "use_proxy": False  # 优先直连
            },
            {
                "name": "Baidu_Selenium",
                "enabled": False,  # 暂时禁用Selenium，太慢
                "priority": 3,  # 备用策略：Selenium百度
                "method": "selenium"
            },
            {
                "name": "Bing_Selenium", 
                "enabled": False,  # 暂时禁用Selenium，太慢
                "priority": 4,  # 备用策略：Selenium Bing
                "method": "selenium"
            }
        ]
        
        # 超时控制配置 - 大幅优化超时时间
        self.timeout_config = {
            'single_law_timeout': 15.0,  # 单个法规总超时时间
            'single_request_timeout': 8.0,  # 单个请求超时时间
            'selenium_timeout': 10.0,  # Selenium操作超时时间
            'selenium_search_timeout': 12.0,  # Selenium搜索超时时间
        }
        
        # 反反爬配置 - 极速优化
        self.anti_detection_config = {
            "min_delay": 0.1,  # 最小延迟极速优化
            "max_delay": 0.3,  # 最大延迟极速优化
            "retry_delay": 1.0,  # 重试延迟极速优化
            "max_retries": 1,  # 减少重试次数
            "rotate_headers": True,  # 轮换请求头
            "use_proxy": False  # 优先直连，代理作为备用
        }
        
        # 请求头 - 模拟更真实的浏览器行为
        self.headers = self._get_random_headers()
    
    def _get_random_headers(self) -> Dict[str, str]:
        """获取随机的浏览器头信息，避免被识别"""
        import random
        
        # 多种真实的User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def _ensure_session(self):
        """确保aiohttp会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=timeout,
                connector=connector
            )
    
    async def _ensure_initialized(self):
        """确保爬虫已初始化 - 按需初始化代理池"""
        if not self.initialized:
            # 不立即初始化代理池，等到需要时再初始化
            self.initialized = True
    
    async def _lazy_init_proxy_pools(self):
        """延迟初始化代理池 - 只在直连失败时调用"""
        if self.enhanced_proxy_pool is None and self.ip_pool is None:
            await self.anti_detection.initialize_proxy_pools()
            # 将初始化后的代理池引用赋值给当前实例
            self.enhanced_proxy_pool = self.anti_detection.enhanced_proxy_pool
    
    async def _ensure_ip_pool(self):
        """确保IP池存在 - 优化版，减少检查数量"""
        if self.ip_pool is None:
            try:
                # 只在真正需要时才初始化IP池，并限制检查数量
                from ..utils.ip_pool import get_ip_pool
                self.ip_pool = await get_ip_pool(max_check=10)  # 只检查10个代理，提高速度
                self.logger.info("IP池初始化完成（快速模式）")
            except Exception as e:
                self.logger.warning(f"IP池初始化失败: {e}")
    
    async def _get_proxy_for_request(self, force_proxy: bool = False):
        """获取用于请求的代理 - 优化版"""
        # 如果不强制使用代理，先返回None（直连）
        if not force_proxy:
            return None
        
        await self._ensure_initialized()
        
        # 延迟初始化代理池
        await self._lazy_init_proxy_pools()
        
        # 优先使用enhanced_proxy_pool
        proxy_url = await self.anti_detection.get_proxy()
        if proxy_url:
            return proxy_url
        
        # 备用IP池（快速模式）
        try:
            await self._ensure_ip_pool()
            if self.ip_pool:
                proxy = await self.ip_pool.get_proxy()
                if proxy:
                    self.logger.debug(f"使用IP池代理: {proxy.ip}:{proxy.port}")
                    return proxy.proxy_url
        except Exception as e:
            self.logger.debug(f"获取代理失败: {e}")
        return None
    
    async def search_law_via_engines(self, law_name: str) -> List[Dict[str, Any]]:
        """通过搜索引擎查找法规"""
        await self._ensure_session()
        
        # 构建搜索查询
        search_queries = self._build_search_queries(law_name)
        
        all_results = []
        
        # 按优先级尝试搜索引擎
        search_engines = sorted(
            [engine for engine in self.search_engines if engine['enabled']], 
            key=lambda x: x['priority']
        )
        
        for query in search_queries:
            self.logger.info(f"搜索引擎查询: {query}")
            
            for engine in search_engines:
                engine_name = engine['name']
                self.logger.debug(f"尝试{engine_name}搜索...")
                
                results = []
                if engine_name == 'DuckDuckGo':
                    results = await self._search_duckduckgo(query)
                elif engine_name == 'Bing':
                    results = await self._search_bing(query)
                elif engine_name == 'Baidu_Selenium':
                    results = await self.selenium_engine.search_with_selenium(query, 'baidu')
                elif engine_name == 'Bing_Selenium':
                    results = await self.selenium_engine.search_with_selenium(query, 'bing')
                
                if results:
                    self.logger.success(f"{engine_name}搜索成功，找到{len(results)}个结果")
                    all_results.extend(results)
                    break  # 找到结果就停止当前查询
                else:
                    self.logger.debug(f"{engine_name}搜索无结果")
            
            if all_results:
                break  # 找到结果就停止所有查询
        
        # 过滤和排序结果
        filtered_results = self._filter_and_rank_results(all_results, law_name)
        return filtered_results[:5]  # 返回前5个最相关的结果
    
    def _build_search_queries(self, law_name: str) -> List[str]:
        """构建搜索查询列表"""
        queries = []
        
        # 1. 优先：去掉括号内容（更容易找到结果）
        clean_name = re.sub(r'[（(].*?[）)]', '', law_name).strip()
        if clean_name != law_name:
            queries.append(f'"{clean_name}" site:gov.cn')
        
        # 2. 原始名称 + site:gov.cn
        queries.append(f'"{law_name}" site:gov.cn')
        
        # 3. 不使用引号的搜索（有时引号会限制结果）
        queries.append(f'{law_name} site:gov.cn')
        
        # 4. 添加"办法"、"规定"等后缀变体
        base_name = re.sub(r'(办法|规定|条例|实施细则|管理办法|暂行办法|试行办法)$', '', clean_name).strip()
        if base_name != clean_name:
            for suffix in ['办法', '管理办法', '规定']:
                variant = f'{base_name}{suffix}'
                if variant != law_name:
                    queries.append(f'"{variant}" site:gov.cn')
        
        # 5. 提取关键词搜索
        keywords = self._extract_keywords(law_name)
        if len(keywords) >= 2:
            keyword_query = ' '.join(keywords[:3]) + ' site:gov.cn'
            queries.append(keyword_query)
        
        # 6. 特定于政府网站的搜索
        queries.append(f'{law_name} site:www.gov.cn')
        queries.append(f'{law_name} 住建部 site:gov.cn')
        
        return queries
    
    def _extract_keywords(self, law_name: str) -> List[str]:
        """提取法规名称的关键词"""
        # 移除常见后缀
        clean_name = re.sub(r'[（(].*?[）)]', '', law_name)
        clean_name = re.sub(r'(办法|规定|条例|实施细则|管理办法|暂行办法|试行办法)$', '', clean_name)
        
        # 分词 - 简单的中文分词
        keywords = []
        
        # 提取重要词汇
        important_patterns = [
            r'(食品|药品|医疗|建筑|工程|交通|环境|质量|安全|标准|计量|特种设备)',
            r'(招标|投标|采购|监督|管理|审查|验收|检测|认证)',
            r'(企业|公司|机构|单位|行业|领域)',
            r'(国家|中华人民共和国|部门|政府)'
        ]
        
        for pattern in important_patterns:
            matches = re.findall(pattern, clean_name)
            keywords.extend(matches)
        
        # 如果关键词太少，按字符分组
        if len(keywords) < 2:
            # 3-4字符的词组
            for i in range(0, len(clean_name)-2):
                word = clean_name[i:i+3]
                if len(word) == 3 and word not in keywords:
                    keywords.append(word)
        
        return keywords[:5]  # 返回前5个关键词
    
    async def _search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """DuckDuckGo搜索 - 仅直连模式"""
        self.logger.debug("尝试DuckDuckGo直连搜索...")
        
        try:
            # 仅使用直连模式
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers=self.anti_detection.get_headers()
            ) as session:
                params = {
                    'q': query,
                    'format': 'json',
                    'no_redirect': '1',
                    'no_html': '1',
                    'skip_disambig': '1'
                }
                
                url = "https://api.duckduckgo.com"
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        # 解析即时答案
                        if data.get('AbstractURL'):
                            results.append({
                                'title': data.get('AbstractText', ''),
                                'url': data.get('AbstractURL', ''),
                                'snippet': data.get('AbstractText', '')
                            })
                        
                        # 解析相关主题
                        for topic in data.get('RelatedTopics', []):
                            if isinstance(topic, dict) and topic.get('FirstURL'):
                                results.append({
                                    'title': topic.get('Text', ''),
                                    'url': topic.get('FirstURL', ''),
                                    'snippet': topic.get('Text', '')
                                })
                        
                        if results:
                            self.logger.success(f"DuckDuckGo直连成功，找到{len(results)}个结果")
                            return results[:max_results]
                    
                    self.logger.debug(f"DuckDuckGo API响应状态: {response.status}")
                    
        except Exception as e:
            self.logger.debug(f"DuckDuckGo直连异常: {e}")
        
        # 直连失败，不再尝试代理搜索
        self.logger.debug("DuckDuckGo搜索失败，跳过代理模式")
        return []
    
    async def _search_bing(self, query: str, max_results: int = 10) -> List[Dict[str, str]]:
        """Bing搜索 - 仅直连模式"""
        self.logger.debug("尝试Bing直连搜索...")
        
        try:
            # 仅使用直连模式
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers=self.anti_detection.get_headers()
            ) as session:
                params = {
                    'q': query,
                    'count': max_results,
                    'offset': 0,
                    'mkt': 'zh-CN'
                }
                
                url = "https://www.bing.com/search"
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        html = await response.text()
                        results = self._parse_bing_results(html)
                        
                        if results:
                            self.logger.success(f"Bing直连成功，找到{len(results)}个结果")
                            return results[:max_results]
                    
                    self.logger.debug(f"Bing响应状态: {response.status}")
                    
        except Exception as e:
            self.logger.debug(f"Bing直连异常: {e}")
        
        # 直连失败，不再尝试代理搜索
        self.logger.debug("Bing搜索失败，跳过代理模式")
        return []
    
    # Google搜索已移除 - 在国内访问不稳定

    def _parse_duckduckgo_results(self, html: str) -> List[Dict[str, Any]]:
        """解析DuckDuckGo搜索结果"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # DuckDuckGo结果选择器
            result_items = soup.find_all('div', class_='result')
            
            for item in result_items:
                try:
                    # 提取标题
                    title_elem = item.find('a', class_='result__a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    href = title_elem.get('href', '')
                    
                    # 处理DuckDuckGo重定向URL
                    real_url = self._extract_real_url_from_duckduckgo(href)
                    
                    # 确保是gov.cn域名
                    if 'gov.cn' not in real_url:
                        continue
                    
                    # 提取摘要
                    snippet_elem = item.find('a', class_='result__snippet')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append({
                        'title': title,
                        'url': real_url,
                        'snippet': snippet,
                        'source': 'DuckDuckGo'
                    })
                    
                except Exception as e:
                    self.logger.debug(f"解析DuckDuckGo结果项失败: {e}")
                    continue
            
            self.logger.debug(f"DuckDuckGo找到 {len(results)} 个结果项")
            
        except Exception as e:
            self.logger.error(f"解析DuckDuckGo结果失败: {e}")
        
        return results
    
    def _extract_real_url_from_duckduckgo(self, duckduckgo_url: str) -> str:
        """从DuckDuckGo重定向URL中提取真实URL"""
        try:
            # DuckDuckGo的重定向URL格式:
            # //duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.gov.cn%2F...&rut=...
            
            if 'duckduckgo.com/l/' in duckduckgo_url:
                # 提取uddg参数
                import urllib.parse
                
                # 确保URL有协议
                if duckduckgo_url.startswith('//'):
                    duckduckgo_url = 'https:' + duckduckgo_url
                
                parsed = urllib.parse.urlparse(duckduckgo_url)
                query_params = urllib.parse.parse_qs(parsed.query)
                
                if 'uddg' in query_params:
                    # 解码真实URL
                    real_url = urllib.parse.unquote(query_params['uddg'][0])
                    return real_url
            
            # 如果不是重定向URL，直接返回
            return duckduckgo_url
            
        except Exception as e:
            self.logger.debug(f"解析DuckDuckGo重定向URL失败: {duckduckgo_url} - {e}")
            return duckduckgo_url
    
    def _parse_google_results(self, html: str) -> List[Dict[str, Any]]:
        """解析Google搜索结果"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Google结果选择器
            result_items = soup.find_all('div', class_='g')
            
            for item in result_items:
                try:
                    # 提取标题和链接
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue
                    
                    link_elem = title_elem.find_parent('a')
                    if not link_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    # 调试：记录所有找到的链接
                    self.logger.debug(f"Google发现链接: {title[:50]}... -> {href}")
                    
                    # 确保是gov.cn域名
                    if 'gov.cn' not in href:
                        self.logger.debug(f"跳过非gov.cn链接: {href}")
                        continue
                    
                    # 提取描述
                    desc_elem = item.find('span', class_='aCOpRe')
                    if not desc_elem:
                        desc_elem = item.find('div', class_='VwiC3b')
                    
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # 过滤PDF和其他不合适的文件
                    if self._should_skip_url(href, title):
                        continue
                    
                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': description,
                        'source': 'Google'
                    })
                    
                except Exception as e:
                    self.logger.debug(f"解析Google结果项失败: {e}")
                    continue
            
            self.logger.debug(f"Google找到 {len(results)} 个结果项")
            
        except Exception as e:
            self.logger.warning(f"解析Google结果失败: {e}")
        
        return results
    
    def _should_skip_url(self, url: str, title: str) -> bool:
        """判断是否应该跳过这个URL"""
        url_lower = url.lower()
        title_lower = title.lower()
        
        # 跳过PDF文件
        if url_lower.endswith('.pdf') or 'pdf' in url_lower:
            return True
        
        # 跳过下载链接和附件
        if any(keyword in url_lower for keyword in ['download', 'attachment', 'file', '.doc', '.docx']):
            return True
        
        # 跳过明显不相关的页面
        if any(keyword in title_lower for keyword in ['首页', '导航', '搜索', '登录', '注册']):
            return True
        
        return False
    
    def _parse_bing_results(self, html: str) -> List[Dict[str, Any]]:
        """解析Bing搜索结果"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 多种Bing结果选择器
            result_selectors = [
                'li.b_algo',           # 标准结果
                'div.b_algo',          # 备用选择器
                'li[class*="algo"]',   # 模糊匹配
                'div[class*="algo"]'   # 模糊匹配
            ]
            
            result_items = []
            for selector in result_selectors:
                items = soup.select(selector)
                if items:
                    result_items = items
                    self.logger.debug(f"使用Bing选择器: {selector}, 找到 {len(items)} 个结果")
                    break
            
            if not result_items:
                # 如果没找到标准结果，尝试查找所有链接
                all_links = soup.find_all('a', href=True)
                gov_links = [link for link in all_links if 'gov.cn' in link.get('href', '')]
                self.logger.debug(f"备用方案：找到 {len(gov_links)} 个gov.cn链接")
                
                for link in gov_links[:5]:  # 只取前5个
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    if title and len(title) > 10:  # 过滤掉太短的标题
                        results.append({
                            'title': title,
                            'url': href,
                            'snippet': '',
                            'source': 'Bing'
                        })
            else:
                for item in result_items:
                    try:
                        # 提取标题和链接
                        title_elem = item.find('h2') or item.find('h3') or item.find('a')
                        if not title_elem:
                            continue
                        
                        link_elem = title_elem.find('a') if title_elem.name != 'a' else title_elem
                        if not link_elem:
                            continue
                        
                        title = link_elem.get_text(strip=True)
                        href = link_elem.get('href', '')
                        
                        # 调试：记录所有找到的链接
                        self.logger.debug(f"Bing发现链接: {title[:50]}... -> {href}")
                        
                        # 确保是gov.cn域名
                        if 'gov.cn' not in href:
                            self.logger.debug(f"跳过非gov.cn链接: {href}")
                            continue
                        
                        # 提取摘要
                        snippet_elem = item.find('div', class_='b_caption') or item.find('p')
                        snippet = ""
                        if snippet_elem:
                            snippet = snippet_elem.get_text(strip=True)
                        
                        results.append({
                            'title': title,
                            'url': href,
                            'snippet': snippet,
                            'source': 'Bing'
                        })
                        
                    except Exception as e:
                        self.logger.debug(f"解析Bing结果项失败: {e}")
                        continue
            
            self.logger.debug(f"Bing找到 {len(results)} 个结果项")
            
        except Exception as e:
            self.logger.error(f"解析Bing结果失败: {e}")
        
        return results
    
    def _parse_baidu_results(self, html: str) -> List[Dict[str, Any]]:
        """解析百度搜索结果"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 百度结果选择器 - 多种可能的选择器
            selectors = [
                'div.result',  # 标准结果
                'div[class*="result"]',  # 包含result的class
                'div.c-container',  # 新版百度
                'div[tpl]'  # 有tpl属性的div
            ]
            
            result_items = []
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    result_items = items
                    break
            
            for item in result_items:
                try:
                    # 提取标题和链接 - 多种可能的选择器
                    title_elem = (
                        item.find('h3') or 
                        item.find('a', class_='t') or
                        item.find('a', attrs={'data-click': True}) or
                        item.find('a')
                    )
                    
                    if not title_elem:
                        continue
                    
                    # 如果title_elem是a标签，直接使用；否则查找其中的a标签
                    if title_elem.name == 'a':
                        link_elem = title_elem
                        title = title_elem.get_text(strip=True)
                    else:
                        link_elem = title_elem.find('a')
                        title = title_elem.get_text(strip=True)
                    
                    if not link_elem:
                        continue
                    
                    href = link_elem.get('href', '')
                    
                    # 处理百度重定向链接
                    if 'baidu.com/link?' in href:
                        # 尝试提取真实URL
                        import urllib.parse
                        try:
                            parsed = urllib.parse.urlparse(href)
                            params = urllib.parse.parse_qs(parsed.query)
                            if 'url' in params:
                                href = urllib.parse.unquote(params['url'][0])
                        except:
                            pass
                    
                    # 确保是gov.cn域名
                    if 'gov.cn' not in href:
                        continue
                    
                    # 提取描述
                    desc_elem = (
                        item.find('div', class_='c-abstract') or
                        item.find('div', class_='c-span9') or
                        item.find('span', class_='content-right_8Zs40')
                    )
                    
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # 过滤不合适的链接
                    if self._should_skip_url(href, title):
                        continue
                    
                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': description,
                        'source': 'Baidu'
                    })
                    
                except Exception as e:
                    self.logger.debug(f"解析百度结果项失败: {e}")
                    continue
            
            self.logger.debug(f"百度找到 {len(results)} 个结果项")
            
        except Exception as e:
            self.logger.error(f"解析百度结果失败: {e}")
        
        return results
    
    def _parse_sogou_results(self, html: str) -> List[Dict[str, Any]]:
        """解析搜狗搜索结果"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 搜狗结果选择器
            result_items = soup.find_all('div', class_='vrwrap')
            
            for item in result_items:
                try:
                    # 提取标题和链接
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue
                    
                    link_elem = title_elem.find('a')
                    if not link_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    # 确保是gov.cn域名
                    if 'gov.cn' not in href:
                        continue
                    
                    # 提取描述
                    desc_elem = item.find('div', class_='str_info')
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # 过滤不合适的链接
                    if self._should_skip_url(href, title):
                        continue
                    
                    results.append({
                        'title': title,
                        'url': href,
                        'snippet': description,
                        'source': 'Sogou'
                    })
                    
                except Exception as e:
                    self.logger.debug(f"解析搜狗结果项失败: {e}")
                    continue
            
            self.logger.debug(f"搜狗找到 {len(results)} 个结果项")
            
        except Exception as e:
            self.logger.error(f"解析搜狗结果失败: {e}")
        
        return results
    
    def _filter_and_rank_results(self, results: List[Dict[str, Any]], law_name: str) -> List[Dict[str, Any]]:
        """过滤和排序搜索结果"""
        if not results:
            return []
        
        # 先过滤掉不合适的链接
        filtered_results = []
        for result in results:
            url = result.get('url', '').lower()
            title = result.get('title', '').lower()
            
            # 跳过PDF文件
            if url.endswith('.pdf') or 'pdf' in url:
                self.logger.debug(f"跳过PDF链接: {url}")
                continue
            
            # 跳过下载链接和附件
            if any(keyword in url for keyword in ['download', 'attachment', 'file', '.doc', '.docx']):
                self.logger.debug(f"跳过下载链接: {url}")
                continue
            
            # 跳过明显不相关的页面 - 但要确保不误杀正确的法规
            irrelevant_keywords = [
                '首页', '导航', '搜索', '登录', '注册', '目录', '索引'
            ]
            
            # 对于"清单"类页面，需要更精确的判断
            if any(keyword in title for keyword in irrelevant_keywords):
                self.logger.debug(f"跳过不相关页面: {title}")
                continue
            
            # 特殊处理：如果是"检查事项清单"等明显不是法规本身的页面
            if ('检查事项' in title or '涉企检查' in title or '工作清单' in title or '责任清单' in title) and \
               not any(core_word in title for core_word in ['招标投标管理办法', '施工招标投标']):
                self.logger.debug(f"跳过检查清单页面: {title}")
                continue
            
            filtered_results.append(result)
        
        # 计算相关性分数
        scored_results = []
        clean_law_name = re.sub(r'[（(].*?[）)]', '', law_name).lower()
        
        for result in filtered_results:
            score = 0
            title = result['title'].lower()
            snippet = result['snippet'].lower()
            url = result['url'].lower()
            
            # 标题匹配加分 - 更精确的匹配
            title_clean = re.sub(r'[（(].*?[）)]', '', title).strip()
            
            # 完全匹配（去掉括号后）
            if clean_law_name == title_clean:
                score += 25
            # 高度匹配（目标在标题中）
            elif clean_law_name in title:
                score += 20
            # 标题在目标中（可能是简称）
            elif title_clean in clean_law_name and len(title_clean) > 6:
                score += 15
            
            # 关键词匹配 - 提取更多关键词进行匹配
            keywords = self._extract_keywords(law_name)
            title_keyword_matches = 0
            for keyword in keywords[:5]:  # 检查前5个关键词
                if keyword.lower() in title:
                    title_keyword_matches += 1
                    score += 2
                if keyword.lower() in snippet:
                    score += 1
            
            # 关键词匹配度奖励
            if title_keyword_matches >= 3:
                score += 5  # 多个关键词匹配奖励
            
            # 特殊奖励：如果标题包含法规的核心名称（去掉修订年份）
            core_name = re.sub(r'[（(].*?[）)]', '', law_name).replace('中华人民共和国', '').strip()
            if core_name and len(core_name) > 4 and core_name in title:
                score += 8
            
            # URL权威性加分 - 优先中央政府网站
            if 'www.gov.cn' in url:  # 中国政府网（中央）
                score += 15
            elif 'gov.cn' in url and not any(city in url for city in ['yueyang', 'beijing', 'shanghai', 'guangzhou', 'shenzhen']):
                score += 10  # 其他gov.cn但非地方政府
            elif 'gov.cn' in url:  # 地方政府网站
                score += 5
            
            # URL特征加分
            if 'gongbao' in url:  # 政府公报
                score += 8
            elif 'zhengce' in url:  # 政策文件
                score += 6
            elif 'content' in url:  # 内容页面
                score += 4
            
            # 优先选择HTML页面
            if any(path in url for path in ['content', 'zhengce', 'gongbao', 'flcaw']):
                score += 3
            
            # 包含年份信息
            if re.search(r'20\d{2}', title + snippet):
                score += 1
            
            scored_results.append({
                **result,
                'relevance_score': score
            })
        
        # 按分数排序
        scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 去重 - 根据URL
        seen_urls = set()
        unique_results = []
        for result in scored_results:
            url_key = result['url'].split('?')[0]  # 去掉查询参数
            if url_key not in seen_urls:
                seen_urls.add(url_key)
                unique_results.append(result)
        
        return unique_results
    
    async def get_law_detail_from_url(self, url: str) -> Dict[str, Any]:
        """从URL获取法规详细信息"""
        await self._ensure_session()
        
        try:
            # 检查是否是PDF文件
            if url.lower().endswith('.pdf'):
                self.logger.warning(f"跳过PDF文件: {url}")
                return {}
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    # 检查Content-Type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/pdf' in content_type:
                        self.logger.warning(f"跳过PDF内容: {url}")
                        return {}
                    
                    # 尝试获取文本内容，处理编码问题
                    try:
                        html = await response.text()
                    except UnicodeDecodeError:
                        # 如果UTF-8解码失败，尝试其他编码
                        try:
                            content = await response.read()
                            # 尝试常见的中文编码
                            for encoding in ['gb2312', 'gbk', 'gb18030', 'utf-8', 'latin1']:
                                try:
                                    html = content.decode(encoding)
                                    self.logger.debug(f"使用编码 {encoding} 成功解码: {url}")
                                    break
                                except:
                                    continue
                            else:
                                self.logger.warning(f"无法解码页面内容: {url}")
                                return {}
                        except Exception as decode_error:
                            self.logger.warning(f"解码失败: {url} - {decode_error}")
                            return {}
                    
                    return self._extract_law_details_from_html(html, url)
                else:
                    self.logger.warning(f"获取详情页面失败: {url} - HTTP {response.status}")
                    
        except Exception as e:
            self.logger.error(f"获取详情页面异常: {url} - {e}")
        
        return {}
    
    def _extract_law_details_from_html(self, html: str, url: str) -> Dict[str, Any]:
        """从HTML提取法规详细信息"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取完整内容
            content_selectors = [
                'div.pages_content',
                'div.TRS_Editor',
                'div.content',
                'div.article_content',
                'div.main_content'
            ]
            
            content = ""
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    content = content_div.get_text(strip=True)
                    break
            
            # 如果没找到专门的内容区域，获取body文本
            if not content:
                body = soup.find('body')
                content = body.get_text(strip=True) if body else ""
            
            # 基础信息
            result = {
                'content': content[:5000],  # 限制内容长度
                'source_url': url,
                'publish_date': '',
                'valid_from': '',
                'valid_to': '',
                'office': '',
                'issuing_authority': '',
                'document_number': '',
                'law_level': '部门规章',
                'status': '有效'
            }
            
            # 正则提取关键信息 - 确保re模块在局部作用域可用
            import re
            
            # 1. 提取实施日期/施行日期 - 优先级最高
            # 首先检查是否有"自发布之日起施行"的情况
            if re.search(r'本办法自发布之日起施行|自发布之日起施行', content, re.IGNORECASE):
                self.logger.debug("发现'自发布之日起施行'，实施日期将设为发布日期")
                result['implement_from_publish'] = True
            else:
                # 正常提取实施日期
                implement_patterns = [
                    r'本办法自(\d{4}年\d{1,2}月\d{1,2}日)起施行',
                    r'本规定自(\d{4}年\d{1,2}月\d{1,2}日)起施行',
                    r'本条例自(\d{4}年\d{1,2}月\d{1,2}日)起施行',
                    r'自(\d{4}年\d{1,2}月\d{1,2}日)起施行',
                    r'实施日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                    r'施行日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                    r'生效日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                    # 支持横线格式
                    r'本办法自(\d{4}-\d{1,2}-\d{1,2})起施行',
                    r'本规定自(\d{4}-\d{1,2}-\d{1,2})起施行', 
                    r'本条例自(\d{4}-\d{1,2}-\d{1,2})起施行',
                    r'自(\d{4}-\d{1,2}-\d{1,2})起施行'
                ]
                
                for pattern in implement_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        result['valid_from'] = matches[0]
                        self.logger.debug(f"提取到实施日期: {matches[0]}")
                        break
            
            # 2. 提取发布日期 - 增强版，处理复杂的修正情况
            # 首先尝试提取复杂的发布和修正信息
            # 修改正则表达式以捕获所有修正信息
            complex_publish_pattern = r'（(\d{4}年\d{1,2}月\d{1,2}日).*?(第\d+号)发布.*?根据.*?(\d{4}年\d{1,2}月\d{1,2}日).*?(第\d+号).*?修正.*?根据.*?(\d{4}年\d{1,2}月\d{1,2}日).*?(第\d+号).*?修正'
            complex_matches = re.findall(complex_publish_pattern, content[:2000], re.DOTALL)
            
            # 如果没有找到多次修正，尝试单次修正
            if not complex_matches:
                simple_revision_pattern = r'（(\d{4}年\d{1,2}月\d{1,2}日).*?(第\d+号)发布.*?根据(\d{4}年\d{1,2}月\d{1,2}日).*?(第\d+号).*?修正'
                simple_matches = re.findall(simple_revision_pattern, content[:2000], re.DOTALL)
                if simple_matches:
                    # 转换为复杂匹配格式（添加空的第二次修正）
                    original_date, original_number, revision_date, revision_number = simple_matches[-1]
                    complex_matches = [(original_date, original_number, revision_date, revision_number, '', '')]
            
            if complex_matches:
                # 处理复杂情况：有原始发布日期和修正日期
                match = complex_matches[-1]  # 取最后一个匹配
                if len(match) == 6:  # 多次修正
                    original_date, original_number, first_revision_date, first_revision_number, latest_date, latest_number = match
                    result['publish_date'] = original_date
                    result['document_number'] = original_number
                    result['latest_revision_date'] = latest_date if latest_date else first_revision_date
                    result['latest_revision_number'] = latest_number if latest_number else first_revision_number
                    self.logger.debug(f"提取到复杂发布信息 - 原始: {original_date} {original_number}, 最新修正: {result['latest_revision_date']} {result['latest_revision_number']}")
                else:  # 单次修正
                    original_date, original_number, latest_date, latest_number = match[:4]
                    result['publish_date'] = original_date
                    result['document_number'] = original_number
                    result['latest_revision_date'] = latest_date
                    result['latest_revision_number'] = latest_number
                    self.logger.debug(f"提取到发布信息 - 原始: {original_date} {original_number}, 修正: {latest_date} {latest_number}")
            else:
                # 常规发布日期提取
                publish_patterns = [
                    r'发布日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                    r'颁布日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                    r'(\d{4}年\d{1,2}月\d{1,2}日)发布',
                    r'(\d{4}年\d{1,2}月\d{1,2}日)颁布',
                    # 支持横线格式  
                    r'发布日期[：:](\d{4}-\d{1,2}-\d{1,2})',
                    r'颁布日期[：:](\d{4}-\d{1,2}-\d{1,2})',
                    r'(\d{4}-\d{1,2}-\d{1,2})发布',
                    r'(\d{4}-\d{1,2}-\d{1,2})颁布',
                    # 从法规开头的复杂描述中提取原始发布日期
                    r'（(\d{4}年\d{1,2}月\d{1,2}日).*?发布',
                    r'（(\d{4}年\d{1,2}月\d{1,2}日).*?令.*?发布'
                ]
                
                for pattern in publish_patterns:
                    matches = re.findall(pattern, content[:1500], re.IGNORECASE)
                    if matches:
                        result['publish_date'] = matches[0]
                        self.logger.debug(f"提取到发布日期: {matches[0]}")
                        break
                
                # 如果没有专门的发布日期，从前部分找一般日期
                if not result['publish_date']:
                    general_date_patterns = [
                        r'(\d{4}年\d{1,2}月\d{1,2}日)',
                        r'(\d{4}-\d{1,2}-\d{1,2})',
                        r'(\d{4}\.\d{1,2}\.\d{1,2})'
                    ]
                    
                    for pattern in general_date_patterns:
                        matches = re.findall(pattern, content[:1000])
                        if matches:
                            result['publish_date'] = matches[0]
                            break
            
            # 3. 提取文号 - 增强版，处理复杂的部门令格式
            # 如果在复杂发布信息中已经提取到文号，跳过这一步
            if not result.get('document_number'):
                number_patterns = [
                    # 完整的部门令格式 - 增强版
                    r'(中华人民共和国.*?部令第\d+号)',
                    r'(住房和城乡建设部令第\d+号)',
                    r'(建设部令第\d+号)',
                    r'(.*?部令第\d+号)',
                    r'(.*?总局令第\d+号)',
                    r'(.*?委员会令第\d+号)',
                    # 从复杂描述中提取最新的文号
                    r'根据.*?(第\d+号).*?修正',
                    r'根据.*?令(第\d+号)',
                    # 标准格式
                    r'第(\d+)号令',
                    r'令第(\d+)号',
                    r'第(\d+)号',
                    r'(\d{4}年第\d+号)',
                    r'令.*?第?(\d+)号',
                    # 其他格式
                    r'文号[：:](.+?)\s',
                    r'文件编号[：:](.+?)\s'
                ]
                
                for pattern in number_patterns:
                    matches = re.findall(pattern, content[:1500])
                    if matches:
                        doc_num = matches[0]
                        # 如果已经是完整格式，直接使用
                        if '令' in doc_num or '号' in doc_num:
                            result['document_number'] = doc_num
                        elif doc_num.isdigit():
                            result['document_number'] = f"第{doc_num}号"
                        else:
                            result['document_number'] = doc_num
                        self.logger.debug(f"提取到文号: {result['document_number']}")
                        break
            
            # 4. 提取发布机关/颁布机关 - 增强版，处理复杂修正情况
            authority_patterns = [
                # 直接提及发布机关
                r'发布机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                r'颁布机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                r'制定机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                
                # 从复杂的发布描述中提取原始和最新发布机关
                r'（\d{4}年\d{1,2}月\d{1,2}日(中华人民共和国.*?部)令第\d+号发布',
                r'根据\d{4}年\d{1,2}月\d{1,2}日(中华人民共和国.*?部)令第\d+号',
                
                # 从具体描述中提取 - 改进版
                r'中华人民共和国(.*?部)(?:令|规章|办法)',
                r'(住房和城乡建设部)(?:令|规章|办法)',
                r'(建设部)(?:令|规章|办法)',
                r'(交通运输部)(?:令|规章|办法)',
                r'(工业和信息化部)(?:令|规章|办法)',
                r'(国家市场监督管理总局)(?:令|规章|办法)',
                r'(国家.*?局)令',
                r'(.*?部)令',
                r'(国务院.*?)令',
                r'(.*?委员会)令',
                r'(.*?总局)令',
                r'(.*?监督管理局)令',
                
                # 从废止信息中提取
                r'原(国家.*?局)令',
                r'原(.*?部)令',
                r'原(.*?总局)令',
                
                # 特殊情况
                r'(国家质量监督检验检疫总局)',
                r'(市场监督管理总局)',
                r'(住房和城乡建设部)',
                r'(建设部)',
                r'(交通运输部)',
                r'(工业和信息化部)'
            ]
            
            for pattern in authority_patterns:
                matches = re.findall(pattern, content[:2000], re.IGNORECASE)
                if matches:
                    authority = matches[0].strip()
                    # 清理常见后缀和前缀
                    authority = re.sub(r'(令|第.*?号|发布|颁布)$', '', authority).strip()
                    authority = re.sub(r'^(首页|公开|政策|规章库|下载|文字版|图片版|>)+', '', authority).strip()
                    # 清理导航文本和多余信息
                    authority = re.sub(r'.*?>(.*?)(?:规章|办法|令|下载|版|首页)', r'\1', authority).strip()
                    # 提取核心部门名称
                    if '中华人民共和国' in authority:
                        authority = re.sub(r'.*中华人民共和国(.*)', r'\1', authority).strip()
                    
                    # 特殊处理：建设部 -> 住房和城乡建设部（历史变更）
                    if authority == '建设部':
                        authority = '住房和城乡建设部'
                        result['historical_authority'] = '建设部'
                    
                    if len(authority) > 2:  # 避免提取到过短的文本
                        result['issuing_authority'] = authority
                        result['office'] = authority  # 同时设置office字段
                        self.logger.debug(f"提取到发布机关: {authority}")
                        break
            
            # 5. 提取废止信息中的额外细节
            revoke_pattern = r'(\d{4}年\d{1,2}月\d{1,2}日)(.*?)(第\d+号)(.*?)同时废止'
            revoke_matches = re.findall(revoke_pattern, content)
            if revoke_matches:
                revoke_date, revoke_authority, revoke_number, revoke_doc = revoke_matches[0]
                # 如果还没找到发布机关，从废止信息中提取
                if not result['issuing_authority'] and revoke_authority:
                    cleaned_authority = re.sub(r'(原|发布的|令)', '', revoke_authority).strip()
                    if len(cleaned_authority) > 2:
                        result['issuing_authority'] = cleaned_authority
                        result['office'] = cleaned_authority
            
            # 6. 处理"自发布之日起施行"的情况
            if result.get('implement_from_publish') and result.get('publish_date'):
                result['valid_from'] = result['publish_date']
                self.logger.debug(f"设置实施日期为发布日期: {result['publish_date']}")
            
            # 7. 智能推断法规级别
            authority = result.get('issuing_authority', '')
            if '国务院' in authority:
                result['law_level'] = '行政法规'
            elif any(keyword in authority for keyword in ['部', '委员会', '总局', '局']):
                result['law_level'] = '部门规章'
            else:
                result['law_level'] = '部门规章'  # 默认
            
            return result
            
        except Exception as e:
            self.logger.error(f"提取法规详情失败: {e}")
            return {}
    
    async def crawl_law(self, law_name: str, law_number: str = None, strict_mode: bool = False, force_selenium: bool = False) -> Optional[Dict[str, Any]]:
        """爬取单个法规 - 带超时控制和反反爬机制
        
        Args:
            law_name: 法规名称
            law_number: 法规编号（可选）
            strict_mode: 严格模式，True时仅使用HTTP搜索，禁用自动切换
            force_selenium: 强制使用Selenium搜索（策略3专用）
        """
        start_time = time.time()
        
        if strict_mode:
            self.logger.info(f"搜索引擎严格模式爬取: {law_name} (仅HTTP搜索)")
        elif force_selenium:
            self.logger.info(f"搜索引擎Selenium模式爬取: {law_name} (仅Selenium搜索)")
        else:
            self.logger.info(f"搜索引擎智能模式爬取: {law_name}")
        
        try:
            # 根据模式选择搜索方法
            if force_selenium:
                # 策略3：强制使用Selenium搜索，但简化处理避免超时
                if not hasattr(self, 'selenium_engine') or not self.selenium_engine:
                    self.selenium_engine = SeleniumSearchEngine(self.anti_detection)
                search_task = self.selenium_engine.search_with_selenium(law_name, engine="baidu")
            elif strict_mode:
                # 策略2：严格模式，仅HTTP搜索
                search_task = self.search_law_via_engines(law_name)
            else:
                # 智能模式：HTTP + 可能的Selenium补充
                search_task = self.search_law_via_engines(law_name)
            
            # 1. 搜索获取候选结果 (带超时控制)
            
            try:
                if force_selenium:
                    # Selenium搜索直接返回结果，设置较短超时避免卡住
                    search_results = await asyncio.wait_for(search_task, timeout=20)
                    # 转换Selenium结果格式为统一格式
                    if search_results:
                        search_results = self._filter_and_rank_results(search_results, law_name)
                else:
                    search_results = await asyncio.wait_for(
                        search_task, 
                        timeout=min(self.timeout_config['single_law_timeout'] + 10, 60)  # 增加10秒缓冲，最大60秒
                    )
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                self.logger.warning(f"搜索引擎爬取超时 ({elapsed:.1f}s > {self.timeout_config['single_law_timeout']}s): {law_name}")
                return None
            
            if not search_results:
                elapsed = time.time() - start_time
                self.logger.warning(f"搜索引擎未找到结果 (耗时 {elapsed:.1f}s): {law_name}")
                return None
            
            # 2. 检查剩余时间
            elapsed = time.time() - start_time
            remaining_time = self.timeout_config['single_law_timeout'] - elapsed
            
            if remaining_time <= 2:  # 剩余时间不足2秒
                self.logger.warning(f"剩余时间不足，返回基本信息: {law_name}")
                best_result = search_results[0]
                return {
                    'success': True,
                    'name': best_result['title'],
                    'title': best_result['title'],
                    'target_name': law_name,
                    'search_keyword': law_name,
                    'crawl_time': datetime.now().isoformat(),
                    'source': '搜索引擎(政府网)',
                    'source_url': best_result['url'],
                    'crawler_strategy': 'search_engine',
                    'search_engine': best_result.get('source', 'unknown'),
                    'timeout_limited': True,
                    'elapsed_time': elapsed
                }
            
            # 3. 获取最佳匹配的详细信息 (带剩余时间限制)
            best_result = search_results[0]
            
            try:
                detail_task = self.get_law_detail_from_url(best_result['url'])
                # 获取详细信息，考虑剩余时间，但保证最小时间
                remaining_time = max(15, self.timeout_config['single_law_timeout'] - elapsed)  # 最少15秒
                detail_info = await asyncio.wait_for(detail_task, timeout=remaining_time)
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                self.logger.warning(f"详细信息获取超时 (总耗时 {elapsed:.1f}s): {law_name}")
                return {
                    'success': True,
                    'name': best_result['title'],
                    'title': best_result['title'],
                    'target_name': law_name,
                    'search_keyword': law_name,
                    'crawl_time': datetime.now().isoformat(),
                    'source': '搜索引擎(政府网)',
                    'source_url': best_result['url'],
                    'crawler_strategy': 'search_engine',
                    'search_engine': best_result.get('source', 'unknown'),
                    'detail_timeout': True,
                    'elapsed_time': elapsed
                }
            
            if not detail_info:
                elapsed = time.time() - start_time
                self.logger.warning(f"无法获取详细信息 (耗时 {elapsed:.1f}s): {law_name}")
                return None
            
            # 4. 整合结果
            elapsed = time.time() - start_time
            result = {
                'success': True,
                'name': best_result['title'],
                'title': best_result['title'],
                'target_name': law_name,
                'search_keyword': law_name,
                'crawl_time': datetime.now().isoformat(),
                'source': '搜索引擎(政府网)',
                'source_url': best_result['url'],
                'crawler_strategy': 'search_engine',
                'search_engine': best_result.get('source', 'unknown'),
                'search_rank': 1,
                'elapsed_time': elapsed,
                **detail_info
            }
            
            self.logger.success(f"搜索引擎爬取成功 (耗时 {elapsed:.1f}s): {law_name}")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"搜索引擎爬取失败 (耗时 {elapsed:.1f}s): {law_name} - {e}")
            return None
        finally:
            # 保持会话打开以便复用
            pass
    
    async def close(self):
        """关闭会话和Selenium驱动"""
        # 关闭Selenium驱动
        if hasattr(self, 'selenium_engine') and self.selenium_engine:
            try:
                self.selenium_engine.close()
                self.logger.debug("Selenium搜索引擎已关闭")
            except Exception as e:
                self.logger.warning(f"关闭Selenium搜索引擎时出错: {e}")
        
        # 关闭HTTP会话
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                self.session = None
                self.logger.debug("搜索引擎爬虫会话已关闭")
            except Exception as e:
                self.logger.warning(f"关闭搜索引擎爬虫会话时出错: {e}")
                self.session = None
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            try:
                # 直接设置为None，避免在析构时进行复杂的异步操作
                self.session = None
            except:
                pass

    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法规 - 实现抽象方法"""
        return await self.search_law_via_engines(law_name)
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法规详情 - 实现抽象方法"""
        return await self.get_law_detail_from_url(law_id)
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件 - 实现抽象方法"""
        try:
            await self._ensure_session()
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    return True
            return False
        except Exception as e:
            self.logger.error(f"下载文件失败: {e}")
            return False

    async def _search_with_waf_protection(self, query: str, max_retries: int = 3) -> List[Dict]:
        """
        带WAF保护的搜索
        
        Args:
            query: 搜索关键词
            max_retries: 最大重试次数
        """
        results = []
        
        for attempt in range(max_retries):
            try:
                # 检查是否需要轮换IP
                if (attempt > 0 or 
                    self.consecutive_failures >= self.proxy_rotation_threshold):
                    
                    logger.info(f"🔄 第{attempt+1}次尝试，轮换IP中...")
                    await self._rotate_proxy_for_waf()
                
                # 执行搜索
                search_results = await self._execute_protected_search(query)
                
                if search_results:
                    results.extend(search_results)
                    self.consecutive_failures = 0  # 重置失败计数
                    logger.info(f"✅ 搜索成功，获得 {len(search_results)} 个结果")
                    break
                else:
                    self.consecutive_failures += 1
                    logger.warning(f"⚠️ 搜索无结果，连续失败 {self.consecutive_failures} 次")
                
            except Exception as e:
                self.consecutive_failures += 1
                error_msg = str(e)
                
                # 检测WAF阻断
                is_waf_blocked = any(keyword in error_msg.lower() for keyword in [
                    '403', 'forbidden', 'access denied', 'blocked', 
                    'captcha', 'security check', '验证码', '安全验证'
                ])
                
                if is_waf_blocked:
                    logger.warning(f"🛡️ 检测到WAF阻断: {error_msg}")
                    
                    # 处理WAF检测
                    if self.current_proxy and self.enhanced_proxy_pool:
                        await self.enhanced_proxy_pool.handle_waf_detection(
                            self.current_proxy, error_msg
                        )
                    
                    # 等待后重试
                    await asyncio.sleep(self.waf_retry_delay)
                else:
                    logger.error(f"❌ 搜索异常: {error_msg}")
                
                if attempt == max_retries - 1:
                    logger.error(f"💥 搜索完全失败，已重试 {max_retries} 次")
        
        return results

    async def _rotate_proxy_for_waf(self):
        """为WAF对抗轮换代理"""
        try:
            if self.enhanced_proxy_pool:
                # 获取专门用于绕过WAF的代理
                new_proxy = await self.enhanced_proxy_pool.get_proxy_for_waf_bypass()
                if new_proxy:
                    old_proxy_name = self.current_proxy.name if self.current_proxy else "无"
                    self.current_proxy = new_proxy
                    logger.info(f"🌍 IP轮换: {old_proxy_name} → {new_proxy.name}")
                    
                    # 短暂延迟，避免请求过于频繁
                    await asyncio.sleep(random.uniform(2, 5))
                else:
                    logger.warning("⚠️ 无可用代理进行轮换")
            else:
                logger.warning("⚠️ 代理池未初始化，无法轮换")
                
        except Exception as e:
            logger.error(f"❌ 代理轮换失败: {e}")

    async def _execute_protected_search(self, query: str) -> List[Dict]:
        """执行受保护的搜索"""
        results = []
        
        for search_engine in self.search_engines:
            try:
                logger.info(f"🔍 使用 {search_engine} 搜索: {query}")
                
                # 构建搜索URL
                search_url = f"{search_engine}{query}"
                
                # 使用当前代理发起请求
                response = await self._make_protected_request(search_url)
                
                if response:
                    # 检测响应是否包含WAF特征
                    if await self._detect_waf_response(response):
                        logger.warning(f"🛡️ {search_engine} 响应包含WAF特征")
                        continue
                    
                    # 解析搜索结果
                    engine_results = await self._parse_search_results(response, search_engine)
                    results.extend(engine_results)
                    
                    logger.info(f"✅ {search_engine} 返回 {len(engine_results)} 个结果")
                
            except Exception as e:
                logger.error(f"❌ {search_engine} 搜索失败: {e}")
                continue
        
        return results

    async def _make_protected_request(self, url: str, timeout: int = 30) -> str:
        """发起受保护的请求"""
        # 构建请求headers
        headers = self._get_stealth_headers()
        
        # 获取代理配置
        proxy_dict = None
        if self.current_proxy:
            proxy_dict = self.current_proxy.proxy_dict
        
        # 发起请求
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=headers
        ) as session:
            
            async with session.get(url, proxy=proxy_dict.get('http') if proxy_dict else None) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    raise Exception(f"HTTP {response.status}: {await response.text()}")

    async def _detect_waf_response(self, response_text: str) -> bool:
        """检测响应是否包含WAF特征"""
        waf_indicators = [
            'cloudflare', 'access denied', '403 forbidden',
            'security check', 'captcha', 'blocked',
            '验证码', '安全验证', '访问被拒绝', '防火墙'
        ]
        
        response_lower = response_text.lower()
        return any(indicator in response_lower for indicator in waf_indicators)

    def _get_stealth_headers(self) -> Dict[str, str]:
        """获取隐秘性请求头"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }

    def initialize_proxy_pools(self):
        """初始化代理池 - 完全禁用，使用直连模式"""
        self.logger.info("🚀 搜索引擎爬虫使用直连模式，跳过代理池初始化")
        self._initialized = True
        return
        
        # # 原代理池初始化逻辑已禁用
        # if self._initialized:
        #     return
        # 
        # try:
        #     # Enhanced代理池
        #     settings = get_settings()
        #     if settings.proxy_pool.enabled:
        #         try:
        #             self.enhanced_proxy_pool = await get_enhanced_proxy_pool()
        #             self.logger.success("Enhanced代理池初始化成功")
        #         except Exception as e:
        #             self.logger.warning(f"Enhanced代理池初始化失败: {e}")
        # 
        #     # IP池
        #     if settings.ip_pool.enabled:
        #         try:
        #             self.ip_pool = await get_ip_pool()
        #             self.logger.success("IP池初始化成功")
        #         except Exception as e:
        #             self.logger.warning(f"IP池初始化失败: {e}")
        # 
        #     self._initialized = True
        # 
        # except Exception as e:
        #     self.logger.error(f"代理池初始化异常: {e}")
        #     self._initialized = True


def create_search_engine_crawler():
    """创建搜索引擎爬虫实例"""
    return SearchEngineCrawler() 