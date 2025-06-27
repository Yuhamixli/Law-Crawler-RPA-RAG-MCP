#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
爬虫管理器
负责协调不同的爬虫策略，优化效率
"""

import asyncio
import pandas as pd
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import sys
import os
import aiohttp
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.crawler.strategies.search_based_crawler import SearchBasedCrawler
from src.crawler.strategies.selenium_gov_crawler import SeleniumGovCrawler
from src.crawler.strategies.search_engine_crawler import SearchEngineCrawler
from src.crawler.strategies.selenium_search_crawler import SeleniumSearchCrawler
from src.crawler.strategies.direct_url_crawler import DirectUrlCrawler
from src.crawler.strategies.optimized_selenium_crawler import OptimizedSeleniumCrawler

from config.settings import settings


class CacheManager:
    """缓存管理器 - 参考example project"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分类目录
        self.categories = {
            "法律": "laws",
            "行政法规": "regulations", 
            "部门规章": "departmental_rules",
            "地方性法规": "local_regulations",
            "司法解释": "judicial_interpretations",
            "其他": "others"
        }
        
        for category_name, category_dir in self.categories.items():
            category_path = self.cache_dir / category_dir
            category_path.mkdir(exist_ok=True)
        
    def _get_cache_key(self, data: str) -> str:
        """生成缓存键"""
        return hashlib.sha1(data.encode()).hexdigest()
        
    def get(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"读取缓存失败: {e}")
        return None
        
    def set(self, key: str, data: Dict):
        """设置缓存"""
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入缓存失败: {e}")
            
    def write_law(self, law_data: Dict):
        """写入法律文件到分类目录 - 参考example project"""
        try:
            # 确定分类
            category = self._determine_category(law_data.get('name', ''))
            category_dir = self.categories.get(category, 'others')
            
            # 生成文件名
            law_name = law_data.get('name', 'unknown')
            safe_name = self._sanitize_filename(law_name)
            file_path = self.cache_dir / category_dir / f"{safe_name}.json"
            
            # 确保包含所有必要字段
            enriched_data = {
                "law_id": law_data.get("law_id"),
                "name": law_data.get("name"),
                "number": law_data.get("number"),
                "law_type": law_data.get("law_type"),
                "issuing_authority": law_data.get("issuing_authority"),
                
                # 时间字段
                "publish_date": law_data.get("publish_date"),  # 发布日期
                "valid_from": law_data.get("valid_from"),      # 实施日期
                "valid_to": law_data.get("valid_to"),          # 失效日期
                "crawl_time": law_data.get("crawl_time"),      # 爬取日期
                
                # 来源信息
                "source_url": law_data.get("source_url"),      # 实际网页URL
                "source": law_data.get("source"),              # 数据源
                
                # 内容
                "content": law_data.get("content"),
                "keywords": law_data.get("keywords"),
                "category": category,
                
                # 元数据
                "status": law_data.get("status", "effective"),
                "version": law_data.get("version", "1.0")
            }
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(enriched_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"法律文件已保存到: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"写入法律文件失败: {e}")
            return None
            
    def _determine_category(self, law_name: str) -> str:
        """根据法律名称确定分类"""
        if not law_name:
            return "其他"
            
        # 法律分类规则
        if any(keyword in law_name for keyword in ["法", "法典"]):
            return "法律"
        elif any(keyword in law_name for keyword in ["条例", "规定", "办法"]):
            if any(keyword in law_name for keyword in ["国务院", "政府"]):
                return "行政法规"
            else:
                return "部门规章"
        elif any(keyword in law_name for keyword in ["解释", "司法解释"]):
            return "司法解释"
        elif any(keyword in law_name for keyword in ["省", "市", "自治区", "地方"]):
            return "地方性法规"
        else:
            return "其他"
            
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename


class CrawlerManager:
    """
    爬虫管理器 - 双数据源策略
    
    数据源优先级：
    1. 国家法律法规数据库 (flk.npc.gov.cn) - SearchBasedCrawler [法律法规数据库]
    2. 搜索引擎爬虫 (SearchEngineCrawler) - 通过搜索引擎定位法规
    
    特性：
    - 法律法规数据库优先，确保权威性
    - 搜索引擎补充，提高覆盖率
    - 台账字段完整提取
    """
    
    def __init__(self):
        self.logger = logger
        # 延迟初始化爬虫，实现浏览器复用
        self._search_crawler = None
        self._selenium_crawler = None
        self._optimized_selenium_crawler = None
        self._search_engine_crawler = None
        self._selenium_search_crawler = None
        self._direct_url_crawler = None
        self.cache = CacheManager()
        self.semaphore = asyncio.Semaphore(settings.crawler.max_concurrent)
    
    def _get_search_crawler(self):
        """获取搜索爬虫实例"""
        if self._search_crawler is None:
            self._search_crawler = SearchBasedCrawler()
        return self._search_crawler
    
    def _get_selenium_crawler(self):
        """获取Selenium爬虫实例（复用浏览器）"""
        if self._selenium_crawler is None:
            self._selenium_crawler = SeleniumGovCrawler()
            # 预先初始化浏览器
            self._selenium_crawler.setup_driver()
        return self._selenium_crawler
    
    def _get_search_engine_crawler(self):
        """获取搜索引擎爬虫实例"""
        if self._search_engine_crawler is None:
            self._search_engine_crawler = SearchEngineCrawler()
        return self._search_engine_crawler
    
    def _get_selenium_search_crawler(self):
        """获取Selenium搜索引擎爬虫实例"""
        if self._selenium_search_crawler is None:
            self._selenium_search_crawler = SeleniumSearchCrawler(settings)
        return self._selenium_search_crawler
    
    def _get_direct_url_crawler(self):
        """获取直接URL爬虫实例"""
        if self._direct_url_crawler is None:
            self._direct_url_crawler = DirectUrlCrawler()
        return self._direct_url_crawler
    
    def _get_optimized_selenium_crawler(self):
        """获取优化版Selenium爬虫实例"""
        if self._optimized_selenium_crawler is None:
            self._optimized_selenium_crawler = OptimizedSeleniumCrawler()
        return self._optimized_selenium_crawler
    
    async def fetch(self, url: str, params: Dict = None, headers: Dict = None) -> aiohttp.ClientResponse:
        """通用HTTP请求方法"""
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            }
            
        timeout = aiohttp.ClientTimeout(total=settings.crawler.timeout)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                if params:
                    async with session.get(url, params=params, headers=headers) as response:
                        return response
                else:
                    async with session.get(url, headers=headers) as response:
                        return response
            except Exception as e:
                logger.error(f"HTTP请求失败: {url}, 错误: {e}")
                raise
        
    async def crawl_law(self, law_name: str, law_number: str = None, strategy: int = None) -> Dict[str, Any]:
        """
        爬取单个法规
        strategy: 指定策略 (1-5)，None表示使用默认多层策略
            1 - 国家法律法规数据库（权威数据源）
            2 - HTTP搜索引擎（快速搜索，先直连后代理）
            3 - Selenium搜索引擎（浏览器搜索引擎）
            4 - Selenium政府网（针对政府网优化）
            5 - 直接URL访问（最后保障）
        """
        self.logger.info(f"开始爬取法规: {law_name}")
        
        if strategy:
            # 单一策略模式
            self.logger.info(f"使用指定策略 {strategy}")
            return await self._crawl_with_single_strategy(law_name, law_number, strategy)
        else:
            # 默认多层策略模式
            return await self._crawl_with_multi_strategy(law_name, law_number)
    
    async def _crawl_with_single_strategy(self, law_name: str, law_number: str, strategy: int) -> Dict[str, Any]:
        """使用指定的单一策略爬取"""
        try:
            # 导入配置检查
            from config.settings import settings
            enable_selenium_search = getattr(settings.crawler, 'enable_selenium_search', True)
            enable_optimized_selenium = getattr(settings.crawler, 'enable_optimized_selenium', True)
            
            if strategy == 1:
                # 策略1: 国家法律法规数据库
                self.logger.info("使用策略1: 国家法律法规数据库（权威数据源）")
                search_crawler = self._get_search_crawler()
                result = await search_crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"国家法律法规数据库成功: {law_name}")
                    result['crawler_strategy'] = 'search_based'
                    return result
                    
            elif strategy == 2:
                # 策略2: HTTP搜索引擎
                self.logger.info("使用策略2: HTTP搜索引擎（快速直连）")
                search_engine_crawler = self._get_search_engine_crawler()
                result = await search_engine_crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"HTTP搜索引擎成功: {law_name}")
                    result['crawler_strategy'] = 'search_engine'
                    return result
                    
            elif strategy == 3:
                # 策略3: Selenium搜索引擎 - 检查是否启用
                if not enable_selenium_search:
                    self.logger.warning(f"Selenium搜索引擎策略已禁用，跳过: {law_name}")
                    return self._create_failed_result(law_name, "Selenium搜索引擎策略已禁用")
                    
                self.logger.info("使用策略3: Selenium搜索引擎（浏览器搜索）")
                selenium_search_crawler = self._get_selenium_search_crawler()
                result = await selenium_search_crawler.crawl(law_name, law_number=law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"Selenium搜索引擎成功: {law_name}")
                    result['crawler_strategy'] = 'selenium_search'
                    return result
                    
            elif strategy == 4:
                # 策略4: Selenium政府网 - 检查是否启用
                if not enable_optimized_selenium:
                    self.logger.warning(f"Selenium政府网策略已禁用，跳过: {law_name}")
                    return self._create_failed_result(law_name, "Selenium政府网策略已禁用")
                    
                self.logger.info("使用策略4: Selenium政府网爬虫")
                selenium_crawler = self._get_selenium_crawler()
                result = await selenium_crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"Selenium政府网爬虫成功: {law_name}")
                    result['crawler_strategy'] = 'selenium_gov'
                    return result
                    
            elif strategy == 5:
                # 策略5: 直接URL访问
                self.logger.info("使用策略5: 直接URL访问爬虫")
                direct_url_crawler = self._get_direct_url_crawler()
                result = await direct_url_crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"直接URL访问成功: {law_name}")
                    result['crawler_strategy'] = 'direct_url'
                    return result
            
            # 策略失败
            self.logger.error(f"指定策略 {strategy} 失败: {law_name}")
            return self._create_failed_result(law_name, f"策略 {strategy} 失败")
            
        except Exception as e:
            self.logger.error(f"策略 {strategy} 执行异常: {e}")
            return self._create_failed_result(law_name, f"策略 {strategy} 执行异常: {e}")

    async def _crawl_with_multi_strategy(self, law_name: str, law_number: str) -> Dict[str, Any]:
        """使用默认多层策略爬取"""
        # 导入配置检查
        from config.settings import settings
        enable_selenium_search = getattr(settings.crawler, 'enable_selenium_search', True)
        enable_optimized_selenium = getattr(settings.crawler, 'enable_optimized_selenium', True)
        
        # 策略1: 国家法律法规数据库爬虫（优先级最高）
        # 优势：数据权威，结构化好，官方数据源
        try:
            self.logger.info("尝试策略1: 国家法律法规数据库（权威数据源）")
            search_crawler = self._get_search_crawler()
            result = await search_crawler.crawl_law(law_name, law_number)
            
            if result and result.get('success'):
                self.logger.success(f"国家法律法规数据库成功: {law_name}")
                result['crawler_strategy'] = 'search_based'
                return result
            else:
                self.logger.warning(f"国家法律法规数据库无结果: {law_name}")
        except Exception as e:
            self.logger.warning(f"国家法律法规数据库失败: {e}")
        
        # 策略2: 快速HTTP搜索引擎爬虫（先直连，失败后用代理）
        # 优势：速度快，绕过反爬机制，不依赖浏览器
        try:
            self.logger.info("尝试策略2: 快速HTTP搜索引擎（先直连后代理）")
            search_engine_crawler = self._get_search_engine_crawler()
            result = await search_engine_crawler.crawl_law(law_name, law_number)
            
            if result and result.get('success'):
                self.logger.success(f"HTTP搜索引擎成功: {law_name}")
                result['crawler_strategy'] = 'search_engine'
                return result
            else:
                self.logger.warning(f"HTTP搜索引擎无结果: {law_name}")
        except Exception as e:
            self.logger.warning(f"HTTP搜索引擎失败: {e}")
        
        # 策略3: Selenium搜索引擎爬虫（浏览器搜索引擎）- 检查是否启用
        if enable_selenium_search:
            try:
                self.logger.info("尝试策略3: Selenium搜索引擎（浏览器搜索）")
                selenium_search_crawler = self._get_selenium_search_crawler()
                result = await selenium_search_crawler.crawl(law_name, law_number=law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"Selenium搜索引擎成功: {law_name}")
                    result['crawler_strategy'] = 'selenium_search'
                    return result
                else:
                    self.logger.warning(f"Selenium搜索引擎无结果: {law_name}")
            except Exception as e:
                self.logger.warning(f"Selenium搜索引擎失败: {e}")
        else:
            self.logger.info("⚡ 跳过Selenium搜索引擎策略 - 已禁用以提高性能")
        
        # 策略4: Selenium政府网爬虫 - 检查是否启用
        if enable_optimized_selenium:
            try:
                self.logger.info("尝试策略4: Selenium政府网爬虫")
                selenium_crawler = self._get_selenium_crawler()
                result = await selenium_crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    self.logger.success(f"Selenium政府网爬虫成功: {law_name}")
                    result['crawler_strategy'] = 'selenium_gov'
                    return result
                else:
                    self.logger.warning(f"Selenium政府网爬虫无结果: {law_name}")
            except Exception as e:
                self.logger.warning(f"Selenium政府网爬虫失败: {e}")
        else:
            self.logger.info("⚡ 跳过Selenium政府网策略 - 已禁用以提高性能")
        
        # 策略5: 直接URL访问爬虫（最后保障）
        # 优势：直接访问已知的政府网链接，绕过搜索限制
        try:
            self.logger.info("尝试策略5: 直接URL访问爬虫")
            direct_url_crawler = self._get_direct_url_crawler()
            result = await direct_url_crawler.crawl_law(law_name, law_number)
            
            if result and result.get('success'):
                self.logger.success(f"直接URL访问成功: {law_name}")
                result['crawler_strategy'] = 'direct_url'
                return result
            else:
                self.logger.warning(f"直接URL访问无结果: {law_name}")
        except Exception as e:
            self.logger.warning(f"直接URL访问失败: {e}")
        
        # 所有策略都失败
        self.logger.error(f"所有爬取策略都失败: {law_name}")
        return self._create_failed_result(law_name, "所有爬取策略都失败")
    
    async def crawl_laws_batch(self, law_list: List[Dict[str, str]], limit: int = None, strategy: int = None) -> List[Dict[str, Any]]:
        """
        批量爬取法规 - 终极优化版本
        实现多策略并行，浏览器复用，显著提高效率
        strategy: 指定策略 (1-5)，None表示使用默认多层策略
        """
        if limit:
            law_list = law_list[:limit]
        
        total_count = len(law_list)
        
        if strategy:
            self.logger.info(f"开始批量爬取 {total_count} 个法规（单一策略 {strategy} 模式）")
            return await self._crawl_laws_batch_single_strategy(law_list, strategy)
        else:
            self.logger.info(f"开始批量爬取 {total_count} 个法规（终极优化模式）")
            return await self._crawl_laws_batch_multi_strategy(law_list)
    
    async def _crawl_laws_batch_single_strategy(self, law_list: List[Dict[str, str]], strategy: int) -> List[Dict[str, Any]]:
        """使用单一策略批量爬取"""
        total_count = len(law_list)
        law_names = [law_info.get('名称', law_info.get('name', '')) for law_info in law_list]
        
        strategy_names = {
            1: "国家法律法规数据库",
            2: "HTTP搜索引擎",
            3: "Selenium搜索引擎",
            4: "Selenium政府网",
            5: "直接URL访问"
        }
        
        self.logger.info(f"使用单一策略: {strategy} - {strategy_names.get(strategy, '未知策略')}")
        
        start_time = time.time()
        results = []
        
        # 并行处理所有法规
        tasks = []
        for law_name in law_names:
            tasks.append(self._crawl_with_single_strategy(law_name, None, strategy))
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for law_info, result in zip(law_list, batch_results):
            law_name = law_info.get('名称', law_info.get('name', ''))
            
            if isinstance(result, Exception):
                self.logger.warning(f"策略 {strategy} 异常: {law_name} - {result}")
                results.append(self._create_failed_result(law_name, f"策略 {strategy} 异常: {result}"))
            elif result and result.get('success'):
                results.append(result)
                success_count += 1
                self.logger.success(f"策略 {strategy} 成功: {law_name}")
            else:
                results.append(self._create_failed_result(law_name, f"策略 {strategy} 失败"))
                self.logger.warning(f"策略 {strategy} 失败: {law_name}")
        
        total_time = time.time() - start_time
        success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
        avg_time_per_law = total_time / total_count if total_count > 0 else 0
        
        self.logger.success(f"🎉 单一策略批量爬取完成！")
        self.logger.info(f"📊 策略: {strategy} - {strategy_names.get(strategy, '未知')}")
        self.logger.info(f"📊 总数: {total_count}, 成功: {success_count}, 成功率: {success_rate:.1f}%")
        self.logger.info(f"⏱️ 总用时: {total_time:.1f}秒, 平均: {avg_time_per_law:.2f}秒/法规")
        
        return results
    
    async def _crawl_laws_batch_multi_strategy(self, law_list: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """使用默认多层策略批量爬取"""
        from config.settings import settings
        
        total_count = len(law_list)
        
        # 提取法规名称列表
        law_names = [law_info.get('名称', law_info.get('name', '')) for law_info in law_list]
        
        start_time = time.time()
        
        # 策略1: 国家法律法规数据库批量爬取（优先级最高）
        search_based_results = {}
        try:
            self.logger.info(f"[PHASE1] 阶段1: 国家法律法规数据库批量爬取（权威数据源）- 总数: {total_count}")
            search_crawler = self._get_search_crawler()
            
            search_tasks = []
            for i, law_name in enumerate(law_names, 1):
                self.logger.info(f"[{i}/{total_count}] 准备爬取: {law_name}")
                search_tasks.append(search_crawler.crawl_law(law_name))
            
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            for i, (law_name, result) in enumerate(zip(law_names, search_results), 1):
                if isinstance(result, Exception):
                    self.logger.warning(f"[{i}/{total_count}] 法规库异常: {law_name} - {result}")
                elif result and result.get('success'):
                    search_based_results[law_name] = result
                    self.logger.success(f"[{i}/{total_count}] [DB] 法规库成功: {law_name}")
                else:
                    self.logger.warning(f"[{i}/{total_count}] 法规库失败: {law_name}")
            
            search_success_rate = len(search_based_results) / len(law_names) * 100
            self.logger.info(f"法规库阶段完成: {len(search_based_results)}/{len(law_names)} 成功 ({search_success_rate:.1f}%)")
            
        except Exception as e:
            self.logger.error(f"法规库批量爬取失败: {e}")
        
        # 策略2: 快速HTTP搜索引擎批量爬取（先直连，失败后用代理）
        remaining_laws = [name for name in law_names if name not in search_based_results]
        search_engine_results = {}
        
        if remaining_laws:
            try:
                self.logger.info(f"[PHASE2] 阶段2: 快速HTTP搜索引擎批量爬取 ({len(remaining_laws)}个剩余)")
                search_engine_crawler = self._get_search_engine_crawler()
                
                search_tasks = []
                for i, law_name in enumerate(remaining_laws, 1):
                    remaining_index = len(search_based_results) + i
                    self.logger.info(f"[{remaining_index}/{total_count}] 搜索引擎准备: {law_name}")
                    search_tasks.append(search_engine_crawler.crawl_law(law_name))
                
                search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                for i, (law_name, result) in enumerate(zip(remaining_laws, search_results), 1):
                    remaining_index = len(search_based_results) + i
                    if isinstance(result, Exception):
                        self.logger.warning(f"[{remaining_index}/{total_count}] HTTP搜索引擎异常: {law_name} - {result}")
                    elif result and result.get('success'):
                        search_engine_results[law_name] = result
                        self.logger.success(f"[{remaining_index}/{total_count}] [SE] HTTP搜索引擎成功: {law_name}")
                    else:
                        self.logger.warning(f"[{remaining_index}/{total_count}] HTTP搜索引擎失败: {law_name}")
                
                search_engine_success_rate = len(search_engine_results) / len(remaining_laws) * 100 if remaining_laws else 0
                self.logger.info(f"HTTP搜索引擎阶段完成: {len(search_engine_results)}/{len(remaining_laws)} 成功 ({search_engine_success_rate:.1f}%)")
                
            except Exception as e:
                self.logger.error(f"HTTP搜索引擎批量爬取失败: {e}")
        
        # [OPTIMIZE] 性能优化：完全跳过失效的Selenium策略
        selenium_search_results = {}
        selenium_results = {}
        
        # 检查是否启用Selenium策略
        enable_selenium_search = getattr(settings.crawler, 'enable_selenium_search', True)
        enable_optimized_selenium = getattr(settings.crawler, 'enable_optimized_selenium', True)
        
        # 强制禁用Selenium策略以避免Chrome崩溃
        enable_selenium_search = False
        enable_optimized_selenium = False
        
        remaining_laws_2 = [name for name in law_names if name not in search_based_results and name not in search_engine_results]
        
        if remaining_laws_2 and enable_selenium_search:
            try:
                self.logger.info(f"🌐 阶段3: Selenium搜索引擎批量爬取 ({len(remaining_laws_2)}个剩余)")
                selenium_search_crawler = self._get_selenium_search_crawler()
                
                search_tasks = []
                for law_name in remaining_laws_2:
                    search_tasks.append(selenium_search_crawler.crawl(law_name))
                
                search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                for law_name, result in zip(remaining_laws_2, search_results):
                    if isinstance(result, Exception):
                        self.logger.warning(f"Selenium搜索引擎异常: {law_name} - {result}")
                    elif result and result.get('success'):
                        selenium_search_results[law_name] = result
                        self.logger.success(f"🔍 Selenium搜索引擎成功: {law_name}")
                
                selenium_search_success_rate = len(selenium_search_results) / len(remaining_laws_2) * 100 if remaining_laws_2 else 0
                self.logger.info(f"Selenium搜索引擎阶段完成: {len(selenium_search_results)}/{len(remaining_laws_2)} 成功 ({selenium_search_success_rate:.1f}%)")
                
            except Exception as e:
                self.logger.error(f"Selenium搜索引擎批量爬取失败: {e}")
        else:
            if remaining_laws_2 and not enable_selenium_search:
                self.logger.info(f"[SKIP] 跳过Selenium搜索引擎策略 - 已禁用以提高性能")
        
        # 策略4: 优化版Selenium政府网批量爬取（最难的法规）
        final_remaining_laws = [name for name in law_names if name not in search_based_results and name not in search_engine_results and name not in selenium_search_results]
        
        if final_remaining_laws and enable_optimized_selenium:
            try:
                self.logger.info(f"🔧 阶段4: 优化版Selenium政府网批量爬取 ({len(final_remaining_laws)}个困难法规)")
                optimized_selenium_crawler = self._get_optimized_selenium_crawler()
                
                # 使用优化版Selenium的批量处理方法
                selenium_batch_results = await optimized_selenium_crawler.crawl_laws_batch(final_remaining_laws)
                
                for result in selenium_batch_results:
                    if result and result.get('success'):
                        law_name = result.get('target_name', result.get('name', ''))
                        selenium_results[law_name] = result
                        self.logger.success(f"⚡ 优化Selenium成功: {law_name}")
                
                selenium_success_rate = len(selenium_results) / len(final_remaining_laws) * 100 if final_remaining_laws else 0
                self.logger.info(f"Selenium政府网阶段完成: {len(selenium_results)}/{len(final_remaining_laws)} 成功 ({selenium_success_rate:.1f}%)")
                
            except Exception as e:
                self.logger.error(f"优化Selenium批量爬取失败: {e}")
        else:
            if final_remaining_laws and not enable_optimized_selenium:
                self.logger.info(f"[SKIP] 跳过优化版Selenium策略 - 已禁用以提高性能")

        # 合并所有结果
        results = []
        success_count = 0
        
        for law_info in law_list:
            law_name = law_info.get('名称', law_info.get('name', ''))
            
            if law_name in search_based_results:
                result = search_based_results[law_name]
                result['crawler_strategy'] = 'search_based'
                results.append(result)
                success_count += 1
            elif law_name in search_engine_results:
                result = search_engine_results[law_name]
                result['crawler_strategy'] = 'search_engine'
                results.append(result)
                success_count += 1
            elif law_name in selenium_search_results:
                result = selenium_search_results[law_name]
                result['crawler_strategy'] = 'selenium_search'
                results.append(result)
                success_count += 1
            elif law_name in selenium_results:
                result = selenium_results[law_name]
                result['crawler_strategy'] = 'optimized_selenium'
                results.append(result)
                success_count += 1
            else:
                results.append(self._create_failed_result(law_name, "所有批量策略都失败"))
        
        total_time = time.time() - start_time
        success_rate = (success_count / total_count) * 100
        avg_time_per_law = total_time / total_count
        
        self.logger.success(f"[COMPLETED] 批量爬取完成！")
        self.logger.info(f"[STATS] 总数: {total_count}, 成功: {success_count}, 成功率: {success_rate:.1f}%")
        self.logger.info(f"[TIME] 总用时: {total_time:.1f}秒, 平均: {avg_time_per_law:.2f}秒/法规")
        self.logger.info(f"[STRATEGY] 策略分布: 搜索引擎({len(search_engine_results)}), 法规库({len(search_based_results)}), Selenium({len(selenium_results)})")
        
        return results
    
    async def async_cleanup(self):
        """异步清理资源"""
        try:
            if self._selenium_crawler:
                self._selenium_crawler.close_driver()
                self.logger.info("Selenium浏览器已关闭")
            if self._optimized_selenium_crawler:
                self._optimized_selenium_crawler.close_session()
                self.logger.info("优化版Selenium浏览器已关闭")
            if self._search_engine_crawler:
                try:
                    await self._search_engine_crawler.close()
                    self.logger.info("搜索引擎爬虫连接已关闭")
                except Exception as close_error:
                    self.logger.warning(f"关闭搜索引擎爬虫连接失败: {close_error}")
        except Exception as e:
            self.logger.warning(f"异步清理资源时出错: {e}")
            
    def cleanup(self):
        """清理资源"""
        try:
            if self._selenium_crawler:
                self._selenium_crawler.close_driver()
                self.logger.info("Selenium浏览器已关闭")
            if self._optimized_selenium_crawler:
                self._optimized_selenium_crawler.close_session()
                self.logger.info("优化版Selenium浏览器已关闭")
            if self._search_engine_crawler:
                # 同步调用异步关闭
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环正在运行，创建任务
                        loop.create_task(self._search_engine_crawler.close())
                    else:
                        # 如果事件循环未运行，直接执行
                        loop.run_until_complete(self._search_engine_crawler.close())
                    self.logger.info("搜索引擎爬虫连接已关闭")
                except Exception as close_error:
                    self.logger.warning(f"关闭搜索引擎爬虫连接失败: {close_error}")
        except Exception as e:
            self.logger.warning(f"清理资源时出错: {e}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup()
    
    def _create_failed_result(self, law_name: str, error_message: str) -> Dict[str, Any]:
        """创建失败结果的标准格式"""
        from datetime import datetime
        return {
            'success': False,
            'name': law_name,
            'title': law_name,
            'number': '',
            'document_number': '',
            'publish_date': '',
            'valid_from': '',
            'valid_to': '',
            'office': '',
            'issuing_authority': '',
            'level': '',
            'law_level': '',
            'status': '',
            'source_url': '',
            'content': '',
            'target_name': law_name,
            'search_keyword': law_name,
            'crawl_time': datetime.now().isoformat(),
            'source': 'failed',
            'error': error_message,
            'crawler_strategy': 'failed'
        }


def create_crawler_manager():
    """创建爬虫管理器实例"""
    return CrawlerManager()
        
 