"""
测试爬取Excel中的前5个法规 - 简化版本，只使用模拟数据
"""
import asyncio
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.storage.database import DatabaseManager
from src.storage.models import LawMetadata, LawDocument
from loguru import logger
import time
from datetime import datetime


def test_first_five_simple():
    """测试前5个法规的爬取 - 简化版本"""
    
    # 读取Excel文件
    df = pd.read_excel('Background info/law list.xls')
    first_five = df.head(5)
    
    logger.info("=== 准备爬取前5个法规 ===")
    for idx, row in first_five.iterrows():
        logger.info(f"{idx+1}. {row['名称']} ({row['编号']})")
    
    # 初始化数据库
    db = DatabaseManager()
    
    logger.info("\n=== 开始插入模拟数据 ===")
    start_time = time.time()
    
    success_count = 0
    failed_count = 0
    
    # 直接插入模拟数据
    for idx, row in first_five.iterrows():
        try:
            # 准备元数据
            law_metadata = LawMetadata(
                law_id=f"test_{idx+1}",
                name=row['名称'],
                number=row['编号'],
                law_type="法律" if "法" in row['名称'] else "行政法规",
                issuing_authority="全国人民代表大会常务委员会" if "法" in row['名称'] else "国务院",
                publish_date=pd.to_datetime(row['实施日期']).date() if pd.notna(row['实施日期']) else None,
                valid_from=pd.to_datetime(row['实施日期']).date() if pd.notna(row['实施日期']) else None,
                source_url="mock://test",
                source="mock_data",
                keywords=f"{row['名称']}相关关键词",
                status="effective"
            )
            
            # 准备文档内容
            law_document = LawDocument(
                law_id=f"test_{idx+1}",
                content=f"""
{row['名称']}

（{row['编号']}）

第一章 总则

第一条 为了规范相关活动，维护社会秩序，保障公民、法人和其他组织的合法权益，根据宪法，制定本法。

第二条 在中华人民共和国境内从事相关活动，适用本法。

第三条 国家坚持依法治国原则，保障法律的正确实施。

第二章 主要规定

第四条 相关主体应当遵守本法的规定，履行相应的义务。

第五条 国家机关应当依法行使职权，保护相关权益。

第三章 附则

第六条 本法自{row['实施日期']}起施行。
""",
                file_type="text",
                summary=f"《{row['名称']}》是我国重要的法律法规，对相关领域的活动进行了全面规范。"
            )
            
            # 保存到数据库
            db.create_law(law_metadata, law_document)
            success_count += 1
            logger.success(f"✓ 成功插入: {row['名称']}")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"✗ 插入失败: {row['名称']} - 错误: {str(e)}")
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    logger.info(f"\n=== 插入完成 ===")
    logger.info(f"总耗时: {elapsed_time:.2f} 秒")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {failed_count} 个")
    
    # 数据库统计
    logger.info("\n=== 数据库统计 ===")
    total_laws = db.get_total_laws_count()
    logger.info(f"数据库中总法规数: {total_laws}")
    
    # 显示最近添加的法规
    recent_laws = db.session.query(LawMetadata).order_by(
        LawMetadata.created_at.desc()
    ).limit(5).all()
    
    if recent_laws:
        logger.info("\n最近添加的法规:")
        for law in recent_laws:
            logger.info(f"  - {law.name} ({law.number}) - 生效日期: {law.valid_from}")
            
            # 查询关联的文档
            doc = db.session.query(LawDocument).filter_by(law_id=law.law_id).first()
            if doc:
                logger.info(f"    文档摘要: {doc.summary[:50]}...")
    
    # 测试搜索功能
    logger.info("\n=== 测试搜索功能 ===")
    search_results = db.search_laws("反洗钱")
    logger.info(f"搜索 '反洗钱' 找到 {len(search_results)} 条结果")
    for result in search_results:
        logger.info(f"  - {result.name}")
    
    # 获取统计信息
    logger.info("\n=== 详细统计信息 ===")
    stats = db.get_statistics()
    logger.info(f"法规统计:")
    logger.info(f"  - 总数: {stats['laws']['total']}")
    logger.info(f"  - 有效: {stats['laws']['valid']}")
    logger.info(f"  - 按类型:")
    for law_type, count in stats['laws']['by_type'].items():
        logger.info(f"    - {law_type}: {count}")


if __name__ == "__main__":
    # 设置日志
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add("logs/test_first_five_simple.log", level="DEBUG", rotation="10 MB")
    
    # 运行测试
    test_first_five_simple() 