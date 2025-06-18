"""
法律法规爬虫主程序
"""
import asyncio
import argparse
from pathlib import Path
from loguru import logger
from src.crawler.crawler_manager import CrawlerManager
from config.config import LOG_CONFIG

# 配置日志
logger.add(
    "logs/crawler_{time}.log",
    format=LOG_CONFIG["format"],
    level=LOG_CONFIG["level"],
    rotation=LOG_CONFIG["rotation"],
    retention=LOG_CONFIG["retention"],
    compression=LOG_CONFIG["compression"]
)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="法律法规爬虫系统")
    parser.add_argument(
        "--action",
        choices=["crawl", "retry", "stats"],
        default="crawl",
        help="执行的操作"
    )
    parser.add_argument(
        "--excel",
        type=str,
        default="Background info/law list.xls",
        help="Excel文件路径"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="national",
        help="数据源"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以JSON格式输出结果"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径"
    )
    
    args = parser.parse_args()
    
    # 创建爬虫管理器
    manager = CrawlerManager()
    
    if args.action == "crawl":
        # 执行爬取
        excel_path = Path(args.excel)
        if not excel_path.exists():
            logger.error(f"Excel文件不存在: {excel_path}")
            return
            
        logger.info(f"开始从Excel文件爬取: {excel_path}")
        result = await manager.crawl_from_excel(str(excel_path), args.source)
        logger.info(f"爬取结果: {result}")
        
    elif args.action == "retry":
        # 重试失败任务
        logger.info("开始重试失败的任务")
        await manager.retry_failed_tasks()
        
    elif args.action == "stats":
        # 显示统计信息
        stats = manager.get_crawl_statistics()
        
        if args.json:
            # JSON格式输出
            import json
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            # 人类可读格式
            logger.info("爬取统计信息:")
            logger.info(f"法规总数: {stats['laws']['total']}")
            logger.info(f"有效法规: {stats['laws']['valid']}")
            logger.info(f"失效法规: {stats['laws']['invalid']}")
            logger.info("按类型统计:")
            for law_type, count in stats['laws']['by_type'].items():
                logger.info(f"  {law_type}: {count}")
            logger.info(f"任务总数: {stats['tasks']['total']}")
            logger.info(f"成功任务: {stats['tasks']['success']}")
            logger.info(f"失败任务: {stats['tasks']['failed']}")


if __name__ == "__main__":
    asyncio.run(main()) 