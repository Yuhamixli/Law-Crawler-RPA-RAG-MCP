"""
测试爬取Excel中的前5个法规
"""
import asyncio
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crawler.crawler_manager import CrawlerManager
from src.storage.database import DatabaseManager
from src.crawler.strategies.multi_source_crawler import MultiSourceCrawler
from loguru import logger
import time


async def test_first_five():
    """测试前5个法规的爬取"""
    
    # 读取Excel文件
    df = pd.read_excel('Background info/law list.xls')
    first_five = df.head(5)
    
    logger.info("=== 准备爬取前5个法规 ===")
    for idx, row in first_five.iterrows():
        logger.info(f"{idx+1}. {row['名称']} ({row['编号']})")
    
    # 初始化数据库
    db = DatabaseManager()
    
    # 初始化爬虫管理器
    manager = CrawlerManager(db)
    
    # 添加多源爬虫
    multi_crawler = MultiSourceCrawler()
    manager.add_crawler(multi_crawler)
    
    # 准备爬取任务
    laws_to_crawl = []
    for idx, row in first_five.iterrows():
        laws_to_crawl.append({
            'name': row['名称'],
            'number': row['编号'],
            'implementation_date': str(row['实施日期']) if pd.notna(row['实施日期']) else None
        })
    
    logger.info("\n=== 开始爬取 ===")
    start_time = time.time()
    
    # 执行爬取
    results = await manager.crawl_laws(laws_to_crawl)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    failed_count = sum(1 for r in results if not r['success'])
    
    logger.info(f"\n=== 爬取完成 ===")
    logger.info(f"总耗时: {elapsed_time:.2f} 秒")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {failed_count} 个")
    
    # 显示详细结果
    logger.info("\n=== 详细结果 ===")
    for i, result in enumerate(results):
        law = laws_to_crawl[i]
        if result['success']:
            logger.success(f"✓ {law['name']} - 数据源: {result.get('source', 'unknown')}")
            if result.get('law_id'):
                # 查询数据库中的详细信息
                law_metadata = db.get_law_by_id(result['law_id'])
                if law_metadata:
                    logger.info(f"  - 类型: {law_metadata.law_type}")
                    logger.info(f"  - 发布机关: {law_metadata.issuing_authority}")
                    logger.info(f"  - 生效日期: {law_metadata.effective_date}")
                    if law_metadata.documents:
                        logger.info(f"  - 文档数: {len(law_metadata.documents)}")
        else:
            logger.error(f"✗ {law['name']} - 错误: {result.get('error', '未知错误')}")
    
    # 检查数据文件
    logger.info("\n=== 数据文件检查 ===")
    json_dir = os.path.join('data', 'raw', 'json')
    if os.path.exists(json_dir):
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
        logger.info(f"JSON文件数: {len(json_files)}")
        for f in json_files[:5]:  # 只显示前5个
            logger.info(f"  - {f}")
    
    # 数据库统计
    logger.info("\n=== 数据库统计 ===")
    total_laws = db.get_total_laws_count()
    logger.info(f"数据库中总法规数: {total_laws}")
    
    # 显示最近添加的法规
    recent_laws = db.session.query(db.LawMetadata).order_by(
        db.LawMetadata.created_at.desc()
    ).limit(5).all()
    
    if recent_laws:
        logger.info("\n最近添加的法规:")
        for law in recent_laws:
            logger.info(f"  - {law.name} ({law.law_number}) - {law.created_at}")


if __name__ == "__main__":
    # 设置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add("logs/test_first_five.log", level="DEBUG", rotation="10 MB")
    
    # 运行测试
    asyncio.run(test_first_five()) 