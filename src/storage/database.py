"""
数据库管理器
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.storage.models import Base, LawMetadata, LawDocument, LawChangeLog, CrawlTask
from config.config import DATABASE_CONFIG


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        # 创建数据库引擎
        self.engine = create_engine(
            DATABASE_CONFIG['url'],
            echo=DATABASE_CONFIG['echo'],
            pool_size=DATABASE_CONFIG['pool_size'],
            max_overflow=DATABASE_CONFIG['max_overflow']
        )
        
        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # 创建表
        self._create_tables()
        
        # 创建默认会话供外部使用
        self.session = self.get_session()
        
        # 导出模型类以便外部使用
        self.LawMetadata = LawMetadata
        self.LawDocument = LawDocument
        self.LawChangeLog = LawChangeLog
        self.CrawlTask = CrawlTask
        
    def _create_tables(self):
        """创建数据库表"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"创建数据库表失败: {str(e)}")
            raise
            
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
        
    def create_law(self, metadata: LawMetadata, document: Optional[LawDocument] = None) -> LawMetadata:
        """创建法律法规记录"""
        with self.get_session() as session:
            try:
                session.add(metadata)
                if document:
                    session.add(document)
                session.commit()
                session.refresh(metadata)
                return metadata
            except Exception as e:
                session.rollback()
                logger.error(f"创建法规记录失败: {str(e)}")
                raise
                
    def get_law_by_id(self, law_id: str) -> Optional[LawMetadata]:
        """根据法规ID获取法律法规"""
        with self.get_session() as session:
            return session.query(LawMetadata).filter(
                LawMetadata.law_id == law_id
            ).first()
            
    def get_law_by_name_and_number(self, name: str, number: Optional[str] = None) -> Optional[LawMetadata]:
        """根据名称和编号获取法律法规"""
        with self.get_session() as session:
            query = session.query(LawMetadata).filter(
                LawMetadata.name == name
            )
            if number:
                query = query.filter(LawMetadata.number == number)
            return query.first()
            
    def search_laws(self, keyword: str, law_type: Optional[str] = None, 
                   status: Optional[str] = None, limit: int = 50) -> List[LawMetadata]:
        """搜索法律法规"""
        with self.get_session() as session:
            query = session.query(LawMetadata)
            
            if keyword:
                query = query.filter(
                    (LawMetadata.name.contains(keyword)) |
                    (LawMetadata.keywords.contains(keyword))
                )
                
            if law_type:
                query = query.filter(LawMetadata.law_type == law_type)
                
            if status is not None:
                query = query.filter(LawMetadata.status == status)
                
            return query.limit(limit).all()
            
    def update_law(self, law_id: str, **kwargs) -> Optional[LawMetadata]:
        """更新法律法规信息"""
        with self.get_session() as session:
            law = session.query(LawMetadata).filter(
                LawMetadata.law_id == law_id
            ).first()
            
            if law:
                for key, value in kwargs.items():
                    if hasattr(law, key):
                        setattr(law, key, value)
                        
                law.updated_at = datetime.now()
                session.commit()
                session.refresh(law)
                
            return law
            
    def create_task(self, task: CrawlTask) -> CrawlTask:
        """创建爬取任务"""
        with self.get_session() as session:
            try:
                session.add(task)
                session.commit()
                session.refresh(task)
                return task
            except Exception as e:
                session.rollback()
                logger.error(f"创建任务失败: {str(e)}")
                raise
                
    def update_task(self, task: CrawlTask):
        """更新任务状态"""
        with self.get_session() as session:
            try:
                session.merge(task)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"更新任务失败: {str(e)}")
                raise
                
    def get_failed_tasks(self, limit: int = 100) -> List[CrawlTask]:
        """获取失败的任务"""
        with self.get_session() as session:
            return session.query(CrawlTask).filter(
                CrawlTask.status == 'failed'
            ).limit(limit).all()
            
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.get_session() as session:
            total_laws = session.query(func.count(LawMetadata.id)).scalar()
            valid_laws = session.query(func.count(LawMetadata.id)).filter(
                LawMetadata.status == 'effective'
            ).scalar()
            
            # 按类型统计
            type_stats = session.query(
                LawMetadata.law_type,
                func.count(LawMetadata.id)
            ).group_by(LawMetadata.law_type).all()
            
            # 任务统计
            total_tasks = session.query(func.count(CrawlTask.id)).scalar()
            success_tasks = session.query(func.count(CrawlTask.id)).filter(
                CrawlTask.status == 'success'
            ).scalar()
            failed_tasks = session.query(func.count(CrawlTask.id)).filter(
                CrawlTask.status == 'failed'
            ).scalar()
            
            return {
                "laws": {
                    "total": total_laws,
                    "valid": valid_laws,
                    "invalid": total_laws - valid_laws,
                    "by_type": dict(type_stats)
                },
                "tasks": {
                    "total": total_tasks,
                    "success": success_tasks,
                    "failed": failed_tasks,
                    "pending": total_tasks - success_tasks - failed_tasks
                }
            }
            
    def get_total_laws_count(self) -> int:
        """获取法规总数"""
        with self.get_session() as session:
            return session.query(LawMetadata).count()
            
    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'session'):
            self.session.close() 