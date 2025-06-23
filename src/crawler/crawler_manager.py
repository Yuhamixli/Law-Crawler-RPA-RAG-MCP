"""
爬虫管理器 - 整合版本
参考example project的单一入口模式
支持多数据源优先级爬取，内置缓存管理
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
    """爬虫管理器"""
    
    def __init__(self):
        pass
        self.cache = CacheManager()
        self.semaphore = asyncio.Semaphore(settings.crawler.max_concurrent)
        self._init_crawlers()
        
    def _init_crawlers(self):
        """初始化爬虫策略 - 双数据源优先级策略"""
        
        # 按优先级排序：flk.npc.gov.cn -> www.gov.cn
        # 启用双数据源策略确保数据完整性
        self.crawlers = [
            ("search_api", SearchBasedCrawler()),  # 优先：全国人大法律法规数据库
        ]
        
        # 初始化政府网爬虫 - 优先使用Selenium版本
        try:
            from .strategies.selenium_gov_crawler import SeleniumGovCrawler
            gov_crawler = SeleniumGovCrawler()
            self.crawlers.append(("selenium_gov_web", gov_crawler))
            logger.info("使用Selenium政府网爬虫")
        except Exception as selenium_error:
            logger.warning(f"Selenium爬虫初始化失败，回退到普通爬虫: {selenium_error}")
            from .strategies.gov_web_crawler import GovWebCrawler
            gov_crawler = GovWebCrawler()
            self.crawlers.append(("gov_web", gov_crawler))
            logger.info("使用普通政府网爬虫")
        
        logger.info(f"初始化爬虫策略: {[name for name, _ in self.crawlers]}")
        logger.info("已启用双数据源策略，确保数据完整性")
        
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
        
    def add_crawler(self, crawler):
        """添加爬虫（保留兼容性）"""
        self.crawlers.append((crawler.name, crawler))
        
    async def crawl_law(self, law_name: str, law_number: str = None, use_cache: bool = False) -> Optional[Dict]:
        """单一入口：爬取单个法律（禁用缓存以确保数据时效性）"""
        # 缓存已禁用 - 避免法律法规失效但缓存中依然存在的情况
        # cache_key = self.cache._get_cache_key(f"{law_name}_{law_number}")
        
        # 1. 不使用缓存，直接从数据源获取最新数据
        # if use_cache:
        #     cached_result = self.cache.get(cache_key)
        #     if cached_result:
        #         logger.info(f"从缓存获取: {law_name}")
        #         return cached_result
            
        # 2. 暂时禁用数据库检查，直接爬取真实数据源
        # existing = self.db_manager.get_law_by_name_and_number(law_name, law_number)
        # if existing:
        #     logger.info(f"从数据库获取: {law_name}")
        #     result = {
        #         "law_id": existing.law_id,
        #         "name": existing.name,
        #         "number": existing.number,
        #         "source": "database",
        #         "success": True,
        #         "source_url": existing.source_url,
        #         "publish_date": existing.publish_date.isoformat() if existing.publish_date else None,
        #         "valid_from": existing.valid_from.isoformat() if existing.valid_from else None,
        #         "valid_to": existing.valid_to.isoformat() if existing.valid_to else None,
        #         "crawl_time": datetime.now().isoformat()
        #     }
        #     # 保存到分类目录
        #     self.cache.write_law(result)
        #     return result
            
        # 3. 按优先级尝试不同数据源
        for crawler_name, crawler in self.crawlers:
            try:
                logger.info(f"使用 {crawler_name} 爬取: {law_name}")
                
                result = await crawler.crawl_law(law_name, law_number)
                
                if result and result.get('success'):
                    # 添加来源信息
                    result['source'] = crawler_name
                    result['crawl_time'] = datetime.now().isoformat()
                    
                    # 确保包含完整的时间信息
                    if not result.get('publish_date'):
                        result['publish_date'] = None
                    if not result.get('valid_from'):
                        result['valid_from'] = None
                    if not result.get('valid_to'):
                        result['valid_to'] = None
                        
                    # 确保包含实际URL
                    if not result.get('source_url'):
                        result['source_url'] = None
                    
                    # 缓存已禁用 - 确保每次都获取最新数据
                    # self.cache.set(cache_key, result)
                    
                    # 不保存到分类目录 - 避免使用过期数据
                    # self.cache.write_law(result)
                    
                    # 暂时禁用数据库保存
    
                    
                    logger.success(f"成功爬取: {law_name} (来源: {crawler_name})")
                    return result
                    
            except Exception as e:
                logger.warning(f"{crawler_name} 爬取失败: {law_name}, 错误: {e}")
                continue
                
        logger.error(f"所有数据源都失败: {law_name}")
        return None
        

        
    async def crawl_laws(self, laws_to_crawl: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量爬取法规 - 使用单一入口模式"""
        results = []
        
        for law_info in laws_to_crawl:
            result = {
                'name': law_info['name'],
                'success': False,
                'error': None,
                'source': None,
                'law_id': None
            }
            
            try:
                # 使用单一入口爬取
                crawl_result = await self.crawl_law(
                    law_info['name'], 
                    law_info.get('number')
                )
                
                if crawl_result:
                    result['success'] = True
                    result['source'] = crawl_result.get('source')
                    result['law_id'] = crawl_result.get('law_id')
                else:
                    result['error'] = '所有数据源都失败'
                        
            except Exception as e:
                logger.error(f"处理法规 {law_info['name']} 时出错: {str(e)}")
                result['error'] = str(e)
                
            results.append(result)
            
        return results
        
    async def crawl_from_excel(self, excel_path: str, generate_ledger: bool = True):
        """从Excel文件批量爬取 - 参考example project的批量处理"""
        # 读取Excel文件
        df = pd.read_excel(excel_path)
        
        # 过滤掉空行
        df = df.dropna(subset=['名称'])
        
        total = len(df)
        logger.info(f"开始爬取，共 {total} 条法规")
        
        # 创建任务列表
        tasks = []
        for _, row in df.iterrows():
            law_info = {
                'name': row['名称'],
                'number': row.get('编号', '')
            }
            task = self.crawl_law(law_info['name'], law_info['number'])
            tasks.append(task)
            
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r and r.get('success'))
        failed_count = total - success_count
        
        logger.info(f"爬取完成: 成功 {success_count} 条，失败 {failed_count} 条")
        
        # 台账生成已移至main.py中统一处理
        
        return {
            "total": total,
            "success": success_count,
            "failed": failed_count
        }
        
 