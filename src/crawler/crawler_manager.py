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
from src.storage.models import CrawlTask, LawMetadata, LawDocument
from src.report.ledger_generator import LedgerGenerator
from config.config import CRAWLER_CONFIG


class CrawlerManager:
    """爬虫管理器"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self.crawlers = {}
        self.semaphore = asyncio.Semaphore(CRAWLER_CONFIG['max_concurrent'])
        self.ledger_generator = LedgerGenerator(self.db_manager)
        
    def add_crawler(self, crawler):
        """添加爬虫"""
        self.crawlers[crawler.name] = crawler
        
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
                crawler = self.crawlers.get(source)
                if not crawler:
                    raise ValueError(f"不支持的数据源: {source}")
                    
                # 执行爬取
                result = await crawler.crawl_law(law_name, law_number)
                    
                if result:
                    # 保存到数据库
                    law_metadata = LawMetadata(
                        law_id=result.get("law_id"),
                        name=result.get("name"),
                        number=result.get("number"),
                        law_type=result.get("law_type"),
                        issuing_authority=result.get("issuing_authority"),
                        publish_date=result.get("publish_date"),
                        valid_from=result.get("effective_date"),
                        source_url=result.get("source_url"),
                        keywords=result.get("keywords"),
                        source=result.get("source")
                    )
                    
                    # 创建文档记录
                    law_document = None
                    if result.get("content"):
                        law_document = LawDocument(
                            law_id=result.get("law_id"),
                            content=result.get("content"),
                            file_path=result.get("file_path"),
                            file_type="json"
                        )
                    
                    self.db_manager.create_law(law_metadata, law_document)
                    
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
                
    async def crawl_from_excel(self, excel_path: str, source: str = "national", generate_ledger: bool = True):
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
        
        # 生成台账
        if generate_ledger and success_count > 0:
            try:
                logger.info("开始生成法律法规台账...")
                
                # 生成Excel格式台账
                excel_path = self.ledger_generator.generate_ledger(
                    output_format="excel",
                    filename=f"law_ledger_crawl_{source}"
                )
                logger.info(f"Excel台账已生成: {excel_path}")
                
                # 同时生成HTML格式方便查看
                html_path = self.ledger_generator.generate_ledger(
                    output_format="html",
                    filename=f"law_ledger_crawl_{source}"
                )
                logger.info(f"HTML台账已生成: {html_path}")
                
                # 生成汇总报告
                summary = self.ledger_generator.generate_summary_report()
                logger.info(f"汇总统计: {summary}")
                
            except Exception as e:
                logger.error(f"生成台账时出错: {str(e)}")
        
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
        
    async def crawl_laws(self, laws_to_crawl: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量爬取法规"""
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
                # 检查是否已存在
                existing = self.db_manager.get_law_by_name_and_number(
                    law_info['name'], 
                    law_info.get('number')
                )
                if existing:
                    logger.info(f"法规已存在，跳过: {law_info['name']}")
                    result['success'] = True
                    result['law_id'] = existing.law_id
                    result['source'] = 'existing'
                else:
                    # 尝试每个爬虫
                    for crawler_name, crawler in self.crawlers.items():
                        logger.info(f"使用 {crawler_name} 爬取: {law_info['name']}")
                        
                        try:
                            crawl_result = await crawler.crawl_law(
                                law_info['name'], 
                                law_info.get('number')
                            )
                            
                            if crawl_result:
                                # 保存到数据库
                                law_metadata = LawMetadata(
                                    law_id=crawl_result.get("law_id"),
                                    name=crawl_result.get("name"),
                                    number=crawl_result.get("number"),
                                    law_type=crawl_result.get("law_type"),
                                    issuing_authority=crawl_result.get("issuing_authority"),
                                    publish_date=crawl_result.get("publish_date"),
                                    valid_from=crawl_result.get("effective_date"),
                                    source_url=crawl_result.get("source_url"),
                                    keywords=crawl_result.get("keywords"),
                                    source=crawl_result.get("source")
                                )
                                
                                # 创建文档记录
                                law_document = None
                                if crawl_result.get("content"):
                                    law_document = LawDocument(
                                        law_id=crawl_result.get("law_id"),
                                        content=crawl_result.get("content"),
                                        file_path=crawl_result.get("file_path"),
                                        file_type="json"
                                    )
                                
                                self.db_manager.create_law(law_metadata, law_document)
                                
                                result['success'] = True
                                result['source'] = crawl_result.get('source', crawler_name)
                                result['law_id'] = crawl_result.get('law_id')
                                break
                                
                        except Exception as e:
                            logger.error(f"{crawler_name} 爬取失败: {str(e)}")
                            result['error'] = str(e)
                            
            except Exception as e:
                logger.error(f"处理法规 {law_info['name']} 时出错: {str(e)}")
                result['error'] = str(e)
                
            results.append(result)
            
        return results 