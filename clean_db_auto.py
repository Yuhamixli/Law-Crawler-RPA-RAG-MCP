"""
自动清理数据库中的数据
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.storage.database import DatabaseManager
from loguru import logger


def clean_database_auto():
    """自动清理数据库"""
    db = DatabaseManager()
    
    # 获取当前法规数量
    current_count = db.get_total_laws_count()
    logger.info(f"当前数据库中有 {current_count} 条法规")
    
    if current_count > 0:
        # 删除所有记录
        try:
            # 删除所有文档
            db.session.query(db.LawDocument).delete()
            # 删除所有元数据
            db.session.query(db.LawMetadata).delete()
            db.session.commit()
            logger.success("数据库已清理")
            
            # 确认清理结果
            new_count = db.get_total_laws_count()
            logger.info(f"清理后数据库中有 {new_count} 条法规")
        except Exception as e:
            db.session.rollback()
            logger.error(f"清理失败: {str(e)}")
    else:
        logger.info("数据库已经是空的")
    
    # 清理JSON文件
    json_dir = os.path.join('data', 'raw', 'json')
    if os.path.exists(json_dir):
        json_files = [f for f in os.listdir(json_dir) if f.endswith('.json') and f != 'mock']
        if json_files:
            logger.info(f"\n找到 {len(json_files)} 个JSON文件，正在清理...")
            for f in json_files:
                try:
                    os.remove(os.path.join(json_dir, f))
                except Exception as e:
                    logger.error(f"删除 {f} 失败: {str(e)}")
            logger.success(f"已清理 {len(json_files)} 个JSON文件")
        else:
            logger.info("没有需要清理的JSON文件")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    
    clean_database_auto() 