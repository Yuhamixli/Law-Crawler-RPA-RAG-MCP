"""
测试爬取脚本 - 先爬取少量数据
"""
import asyncio
import pandas as pd
from pathlib import Path
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.crawler.strategies.fallback_crawler import FallbackCrawler
from src.storage.database import DatabaseManager
from src.storage.models import LawMetadata, LawDocument, LawStatus
from loguru import logger
import hashlib
from datetime import datetime

# 配置日志
logger.add("logs/test_crawl.log", rotation="10 MB")


async def test_single_law():
    """测试爬取单个法律"""
    logger.info("开始测试爬取单个法律...")
    
    async with FallbackCrawler() as crawler:
        # 测试搜索功能
        results = await crawler.search("中华人民共和国反洗钱法")
        
        if results:
            logger.info(f"搜索到 {len(results)} 条结果")
            for result in results:
                logger.info(f"- {result['name']} ({result['number']})")
            
            # 获取第一个结果的详情
            first_result = results[0]
            detail = await crawler.get_detail(first_result['id'])
            
            if detail:
                logger.info(f"成功获取详情: {detail['name']}")
                logger.info(f"  - 编号: {detail['number']}")
                logger.info(f"  - 类型: {detail['law_type']}")
                logger.info(f"  - 发布日期: {detail['publish_date']}")
                logger.info(f"  - 内容长度: {len(detail.get('content', ''))}")
                return detail
            else:
                logger.error("获取详情失败")
        else:
            logger.warning("未搜索到结果")
    
    return None


async def test_batch_crawl():
    """测试批量爬取"""
    logger.info("开始测试批量爬取...")
    
    # 读取Excel文件的前5条
    excel_path = "Background info/law list.xls"
    df = pd.read_excel(excel_path).dropna(subset=['名称']).head(5)
    
    logger.info(f"准备爬取 {len(df)} 条法规:")
    for _, row in df.iterrows():
        logger.info(f"  - {row['名称']} ({row.get('编号', 'N/A')})")
    
    # 初始化数据库
    db_manager = DatabaseManager()
    
    # 爬取每条法规
    success_count = 0
    async with FallbackCrawler() as crawler:
        for _, row in df.iterrows():
            law_name = row['名称']
            law_number = row.get('编号', '')
            
            try:
                logger.info(f"\n正在爬取: {law_name}")
                
                # 检查是否已存在
                existing = db_manager.get_law_by_name_and_number(law_name, law_number)
                if existing:
                    logger.info(f"法规已存在，跳过: {law_name}")
                    continue
                
                # 爬取法规
                result = await crawler.crawl_law(law_name, law_number)
                
                if result:
                    # 生成法规ID
                    law_id = hashlib.md5(f"{law_name}_{law_number}".encode()).hexdigest()[:16]
                    
                    # 创建元数据
                    # 转换日期字符串为date对象
                    publish_date = result.get("publish_date")
                    effective_date = result.get("effective_date")
                    
                    if publish_date and isinstance(publish_date, str):
                        try:
                            publish_date = datetime.strptime(publish_date, "%Y-%m-%d").date()
                        except:
                            publish_date = None
                            
                    if effective_date and isinstance(effective_date, str):
                        try:
                            effective_date = datetime.strptime(effective_date, "%Y-%m-%d").date()
                        except:
                            effective_date = None
                    
                    metadata = LawMetadata(
                        law_id=law_id,
                        name=result.get("name"),
                        number=result.get("number"),
                        law_type=result.get("law_type"),
                        issuing_authority=result.get("issuing_authority"),
                        publish_date=publish_date,
                        valid_from=effective_date,
                        status=LawStatus.EFFECTIVE,
                        source_url=result.get("source_url"),
                        source=result.get("source"),
                        keywords=result.get("keywords")
                    )
                    
                    # 创建文档
                    document = None
                    if result.get("content"):
                        document = LawDocument(
                            law_id=law_id,
                            content=result.get("content"),
                            summary=result.get("summary"),
                            file_path=result.get("file_path"),
                            file_type="html" if not result.get("file_path") else "pdf"
                        )
                    
                    # 保存到数据库
                    db_manager.create_law(metadata, document)
                    success_count += 1
                    logger.success(f"成功爬取并保存: {law_name}")
                else:
                    logger.warning(f"未能爬取到数据: {law_name}")
                    
            except Exception as e:
                logger.error(f"爬取失败: {law_name}, 错误: {str(e)}")
            
            # 延迟一下，避免太快
            await asyncio.sleep(2)
    
    logger.info(f"\n爬取完成! 成功: {success_count}/{len(df)}")
    
    # 显示统计
    stats = db_manager.get_statistics()
    logger.info(f"数据库统计:")
    logger.info(f"  - 法规总数: {stats['laws']['total']}")
    logger.info(f"  - 有效法规: {stats['laws']['valid']}")


async def main():
    """主函数"""
    print("=== 法律法规爬虫测试 ===\n")
    
    # 创建必要的目录
    Path("logs").mkdir(exist_ok=True)
    Path("data/raw/json").mkdir(parents=True, exist_ok=True)
    Path("data/raw/pdf").mkdir(parents=True, exist_ok=True)
    
    # 选择测试模式
    print("请选择测试模式:")
    print("1. 测试单个法律爬取")
    print("2. 测试批量爬取（前5条）")
    print("3. 退出")
    
    choice = input("\n请输入选择 (1-3): ")
    
    if choice == "1":
        await test_single_law()
    elif choice == "2":
        await test_batch_crawl()
    else:
        print("退出测试")


if __name__ == "__main__":
    asyncio.run(main()) 