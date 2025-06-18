"""
检查爬取结果
"""
from src.storage.database import DatabaseManager
from src.storage.models import LawMetadata, LawDocument
from loguru import logger
import json
from pathlib import Path


def check_results():
    """检查爬取结果"""
    
    # 1. 检查数据库
    logger.info("=== 数据库检查 ===")
    db = DatabaseManager()
    
    # 获取统计信息
    stats = db.get_statistics()
    logger.info(f"法规总数: {stats['laws']['total']}")
    logger.info(f"有效法规: {stats['laws']['valid']}")
    
    # 获取所有法规
    with db.get_session() as session:
        laws = session.query(LawMetadata).all()
        
        logger.info(f"\n保存的法规列表:")
        for i, law in enumerate(laws, 1):
            logger.info(f"{i}. {law.name}")
            logger.info(f"   - ID: {law.law_id}")
            logger.info(f"   - 编号: {law.number}")
            logger.info(f"   - 类型: {law.law_type}")
            logger.info(f"   - 发布日期: {law.publish_date}")
            logger.info(f"   - 生效日期: {law.valid_from}")
            logger.info(f"   - 来源: {law.source}")
            
            # 检查是否有文档
            doc = session.query(LawDocument).filter_by(law_id=law.law_id).first()
            if doc:
                logger.info(f"   - 文档: 有 (内容长度: {len(doc.content) if doc.content else 0})")
            else:
                logger.info(f"   - 文档: 无")
                
    # 2. 检查文件系统
    logger.info(f"\n=== 文件系统检查 ===")
    
    json_dir = Path("data/raw/json")
    pdf_dir = Path("data/raw/pdf")
    
    # 查找JSON文件
    json_files = list(json_dir.glob("*.json"))
    logger.info(f"JSON文件数量: {len(json_files)}")
    
    for json_file in json_files[:5]:  # 只显示前5个
        logger.info(f"  - {json_file.name} ({json_file.stat().st_size} bytes)")
        
        # 读取并显示内容摘要
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"    名称: {data.get('name', 'N/A')}")
                logger.info(f"    来源: {data.get('source', 'N/A')}")
        except Exception as e:
            logger.error(f"    读取失败: {str(e)}")
            
    # 查找PDF文件
    pdf_files = list(pdf_dir.glob("*.pdf"))
    logger.info(f"\nPDF文件数量: {len(pdf_files)}")
    
    for pdf_file in pdf_files[:5]:
        logger.info(f"  - {pdf_file.name} ({pdf_file.stat().st_size} bytes)")


if __name__ == "__main__":
    check_results() 