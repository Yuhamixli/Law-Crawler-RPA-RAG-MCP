"""
爬虫管理器
"""
import asyncio
import pandas as pd
from typing import List, Dict, Any, Optional
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from src.crawler.strategies.national_crawler import NationalLawCrawler
from src.storage.database import DatabaseManager
from src.storage.models import CrawlTask, LawMetadata
from config.config import CRAWLER_CONFIG


class CrawlerManager:
    """爬虫管理器"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.crawlers = {
            "national": NationalLawCrawler
        }
        self.semaphore = asyncio.Semaphore(CRAWLER_CONFIG['max_concurrent'])
        
    async def crawl_single_law(self, law_info: Dict[str, Any], source: str = "national") -> bool:
        """爬取单个法律法规"""
        async with self.semaphore:
            law_name = law_info.get("名称", "")
            law_number = law_info.get("编号", "")
            
            # 检查是否已存在
            existing = self.db_manager.get_law_by_name_and_number(law_name, law_number)
            if existing:
                logger.info(f"法规已存在，跳过: {law_name}")
                return True
                
            # 创建爬取任务
            task = CrawlTask(
                law_name=law_name,
                law_number=law_number,
                source=source,
                status="processing"
            )
            self.db_manager.create_task(task)
            
            try:
                # 选择爬虫
                crawler_class = self.crawlers.get(source)
                if not crawler_class:
                    raise ValueError(f"不支持的数据源: {source}")
                    
                # 执行爬取
                async with crawler_class() as crawler:
                    result = await crawler.crawl_law(law_name, law_number)
                    
                if result:
                    # 保存到数据库
                    law_regulation = LawRegulation(
                        name=result.get("name"),
                        number=result.get("number"),
                        law_type=result.get("law_type"),
                        issuing_authority=result.get("issuing_authority"),
                        publish_date=result.get("publish_date"),
                        effective_date=result.get("effective_date"),
                        content=result.get("content"),
                        source_url=result.get("source_url"),
                        file_path=result.get("file_path"),
                        keywords=result.get("keywords"),
                        source=result.get("source")
                    )
                    self.db_manager.create_law(law_regulation)
                    
                    # 更新任务状态
                    task.status = "success"
                    self.db_manager.update_task(task)
                    
                    logger.success(f"法规爬取并保存成功: {law_name}")
                    return True
                else:
                    task.status = "failed"
                    task.error_message = "未找到法规信息"
                    self.db_manager.update_task(task)
                    return False
                    
            except Exception as e:
                logger.error(f"爬取失败: {law_name}, 错误: {str(e)}")
                task.status = "failed"
                task.error_message = str(e)
                task.retry_count += 1
                self.db_manager.update_task(task)
                return False
                
    async def crawl_from_excel(self, excel_path: str, source: str = "national"):
        """从Excel文件批量爬取"""
        # 读取Excel文件
        df = pd.read_excel(excel_path)
        
        # 过滤掉空行
        df = df.dropna(subset=['名称'])
        
        total = len(df)
        logger.info(f"开始爬取，共 {total} 条法规")
        
        # 创建任务列表
        tasks = []
        for _, row in df.iterrows():
            law_info = row.to_dict()
            task = self.crawl_single_law(law_info, source)
            tasks.append(task)
            
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        failed_count = total - success_count
        
        logger.info(f"爬取完成: 成功 {success_count} 条，失败 {failed_count} 条")
        
        return {
            "total": total,
            "success": success_count,
            "failed": failed_count
        }
        
    async def retry_failed_tasks(self):
        """重试失败的任务"""
        failed_tasks = self.db_manager.get_failed_tasks()
        
        if not failed_tasks:
            logger.info("没有失败的任务需要重试")
            return
            
        logger.info(f"开始重试 {len(failed_tasks)} 个失败任务")
        
        for task in failed_tasks:
            if task.retry_count >= CRAWLER_CONFIG['max_retries']:
                logger.warning(f"任务重试次数已达上限，跳过: {task.law_name}")
                continue
                
            law_info = {
                "名称": task.law_name,
                "编号": task.law_number
            }
            
            await self.crawl_single_law(law_info, task.source or "national")
            
    def get_crawl_statistics(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        return self.db_manager.get_statistics() 