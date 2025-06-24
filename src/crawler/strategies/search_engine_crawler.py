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


class AntiDetectionManager:
    """反反爬检测管理器"""
    
    def __init__(self):
        self.logger = logger
        
        # IP池配置 (示例代理，实际使用时需要配置真实代理)
        self.proxy_pool = [
            # 免费代理示例 - 实际使用时需要替换为有效代理
            # {"http": "http://proxy1:port", "https": "https://proxy1:port"},
            # {"http": "http://proxy2:port", "https": "https://proxy2:port"},
        ]
        
        self.current_proxy_index = 0
        self.failed_proxies = set()
        
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
        
    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        return random.choice(self.user_agents)
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """获取下一个可用代理"""
        if not self.proxy_pool:
            return None
            
        available_proxies = [p for i, p in enumerate(self.proxy_pool) 
                           if i not in self.failed_proxies]
        
        if not available_proxies:
            # 重置失败代理列表
            self.failed_proxies.clear()
            available_proxies = self.proxy_pool
            
        if available_proxies:
            self.current_proxy_index = (self.current_proxy_index + 1) % len(available_proxies)
            return available_proxies[self.current_proxy_index]
        
        return None
    
    def mark_proxy_failed(self, proxy: Dict[str, str]):
        """标记代理失败"""
        if proxy in self.proxy_pool:
            index = self.proxy_pool.index(proxy)
            self.failed_proxies.add(index)
    
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


class SeleniumSearchEngine:
    """Selenium搜索引擎操作器"""
    
    def __init__(self, anti_detection: AntiDetectionManager):
        self.anti_detection = anti_detection
        self.logger = logger
        self.driver = None
        
    def setup_driver(self) -> webdriver.Chrome:
        """设置Chrome驱动 - 优化版"""
        try:
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
            
            # 代理配置
            proxy = self.anti_detection.get_next_proxy()
            if proxy and proxy.get('http'):
                proxy_address = proxy['http'].replace('http://', '')
                options.add_argument(f'--proxy-server={proxy_address}')
                self.logger.info(f"使用代理: {proxy_address}")
            
            # 创建驱动 - 使用更快的方式
            try:
                # 尝试使用系统已安装的ChromeDriver
                driver = webdriver.Chrome(options=options)
            except Exception:
                # 回退到自动下载
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            
            # 设置超时
            driver.set_page_load_timeout(10)  # 页面加载超时10秒
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
            self.driver = self.setup_driver()
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
    """增强版搜索引擎爬虫 - 包含完整反反爬机制"""
    
    def __init__(self):
        super().__init__("search_engine")
        self.logger = logger
        self.session = None
        
        # 初始化反检测管理器
        self.anti_detection = AntiDetectionManager()
        
        # 初始化Selenium搜索引擎
        self.selenium_engine = SeleniumSearchEngine(self.anti_detection)
        
        # IP池
        self.ip_pool: Optional[SmartIPPool] = None
        
        # 搜索引擎配置 - 启用部分搜索引擎并增加Selenium支持
        self.search_engines = [
            {
                "name": "Baidu_Selenium",
                "enabled": True,
                "priority": 1,
                "method": "selenium"
            },
            {
                "name": "Bing_Selenium", 
                "enabled": True,
                "priority": 2,
                "method": "selenium"
            },
            {
                "name": "Baidu",
                "enabled": True,
                "priority": 3,
                "api_url": "https://www.baidu.com/s",
                "method": "requests"
            },
            {
                "name": "DuckDuckGo",
                "enabled": True,
                "priority": 4,
                "api_url": "https://html.duckduckgo.com/html/",
                "method": "requests"
            }
        ]
        
        # 超时控制配置
        self.timeout_config = {
            'single_law_timeout': 30.0,  # 单个法规总超时时间
            'single_request_timeout': 15.0,  # 单个请求超时时间
            'selenium_timeout': 20.0,  # Selenium操作超时时间
            'selenium_search_timeout': 25.0,  # Selenium搜索超时时间
        }
        
        # 反反爬配置 - 极速优化版
        self.anti_detection = {
            "min_delay": 0.1,  # 最小延迟极速优化
            "max_delay": 0.5,  # 最大延迟极速优化
            "retry_delay": 2.0,  # 重试延迟极速优化
            "max_retries": 2,  # 减少重试次数
            "rotate_headers": True,  # 轮换请求头
            "use_proxy": False  # 暂不使用代理
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
    
    async def _ensure_ip_pool(self):
        """确保IP池存在"""
        if self.ip_pool is None:
            try:
                self.ip_pool = await get_ip_pool()
                self.logger.info("IP池初始化完成")
            except Exception as e:
                self.logger.warning(f"IP池初始化失败: {e}")
    
    async def _get_proxy_for_request(self):
        """获取用于请求的代理"""
        try:
            await self._ensure_ip_pool()
            if self.ip_pool:
                proxy = await self.ip_pool.get_proxy()
                if proxy:
                    self.logger.debug(f"使用代理: {proxy.ip}:{proxy.port}")
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
                if engine_name == 'Bing_Selenium':
                    results = await self.selenium_engine.search_with_selenium(query, 'bing')
                elif engine_name == 'Baidu_Selenium':
                    results = await self.selenium_engine.search_with_selenium(query, 'baidu')
                elif engine_name == 'DuckDuckGo':
                    results = await self._search_duckduckgo(query)
                
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
        
        # 1. 原始名称 + site:gov.cn
        queries.append(f'"{law_name}" site:gov.cn')
        
        # 2. 去掉括号内容
        clean_name = re.sub(r'[（(].*?[）)]', '', law_name).strip()
        if clean_name != law_name:
            queries.append(f'"{clean_name}" site:gov.cn')
        
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
    
    async def _search_duckduckgo(self, query: str) -> List[Dict[str, Any]]:
        """DuckDuckGo搜索"""
        try:
            # 添加随机延迟避免被识别为bot - 极速优化
            import asyncio
            import random
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # DuckDuckGo HTML搜索
            params = {
                'q': query,
                'kl': 'cn-zh',  # 中文地区
                'safe': 'moderate'
            }
            
            # 获取代理
            proxy = await self._get_proxy_for_request()
            
            async with self.session.get(
                'https://html.duckduckgo.com/html/',
                params=params,
                proxy=proxy
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_duckduckgo_results(html)
                elif response.status == 202:
                    self.logger.warning(f"DuckDuckGo反爬限制: HTTP 202 - 请求已接受但暂未处理")
                elif response.status == 403:
                    self.logger.warning(f"DuckDuckGo封锁访问: HTTP 403 - 禁止访问")
                else:
                    self.logger.warning(f"DuckDuckGo搜索失败: HTTP {response.status}")
                    
        except Exception as e:
            self.logger.warning(f"DuckDuckGo搜索异常: {e}")
        
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
            
            # 跳过明显不相关的页面
            if any(keyword in title for keyword in ['首页', '导航', '搜索', '登录', '注册']):
                self.logger.debug(f"跳过不相关页面: {title}")
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
            
            # 标题匹配加分
            if clean_law_name in title:
                score += 10
            
            # 关键词匹配
            keywords = self._extract_keywords(law_name)
            for keyword in keywords[:3]:
                if keyword.lower() in title:
                    score += 3
                if keyword.lower() in snippet:
                    score += 1
            
            # URL特征加分
            if 'gongbao' in url:  # 政府公报
                score += 5
            elif 'zhengce' in url:  # 政策文件
                score += 3
            elif 'content' in url:  # 内容页面
                score += 2
            
            # 优先选择HTML页面
            if any(path in url for path in ['content', 'zhengce', 'gongbao', 'flcaw']):
                score += 2
            
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
            
            # 2. 提取发布日期
            publish_patterns = [
                r'发布日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                r'颁布日期[：:](\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}年\d{1,2}月\d{1,2}日)发布',
                r'(\d{4}年\d{1,2}月\d{1,2}日)颁布',
                # 支持横线格式  
                r'发布日期[：:](\d{4}-\d{1,2}-\d{1,2})',
                r'颁布日期[：:](\d{4}-\d{1,2}-\d{1,2})',
                r'(\d{4}-\d{1,2}-\d{1,2})发布',
                r'(\d{4}-\d{1,2}-\d{1,2})颁布'
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
            
            # 3. 提取文号 - 增强版
            number_patterns = [
                # 完整的部门令格式
                r'(.*?部令第\d+号)',
                r'(.*?总局令第\d+号)',
                r'(.*?委员会令第\d+号)',
                r'(建设部令第\d+号)',
                r'(住房和城乡建设部令第\d+号)',
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
                matches = re.findall(pattern, content[:1000])
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
            
            # 4. 提取发布机关/颁布机关 - 增强版
            authority_patterns = [
                # 直接提及发布机关
                r'发布机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                r'颁布机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                r'制定机关[：:](.+?)(?:\s|发布日期|颁布日期|实施日期)',
                
                # 从具体描述中提取 - 改进版
                r'中华人民共和国(.*?部)(?:令|规章|办法)',
                r'(住房和城乡建设部)(?:令|规章|办法)',
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
                r'(交通运输部)',
                r'(工业和信息化部)'
            ]
            
            for pattern in authority_patterns:
                matches = re.findall(pattern, content[:1500], re.IGNORECASE)
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
    
    async def crawl_law(self, law_name: str, law_number: str = None) -> Optional[Dict[str, Any]]:
        """爬取单个法规 - 带超时控制和反反爬机制"""
        start_time = time.time()
        self.logger.info(f"搜索引擎爬取: {law_name}")
        
        try:
            # 1. 搜索获取候选结果 (带超时控制)
            search_task = self.search_law_via_engines(law_name)
            
            try:
                search_results = await asyncio.wait_for(
                    search_task, 
                    timeout=self.timeout_config['single_law_timeout']
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


def create_search_engine_crawler():
    """创建搜索引擎爬虫实例"""
    return SearchEngineCrawler() 