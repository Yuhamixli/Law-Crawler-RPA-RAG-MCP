"""
数据库模型定义 - 三层架构设计
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, String, Text, DateTime, Date, Boolean, Integer, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel, Field
from enum import Enum

Base = declarative_base()

# ========== 元数据层 (Metadata Layer) ==========

class LawStatus(str, Enum):
    """法规状态枚举"""
    DRAFT = "draft"          # 草案
    EFFECTIVE = "effective"  # 有效
    AMENDED = "amended"      # 已修正
    REPEALED = "repealed"    # 已废止
    EXPIRED = "expired"      # 已失效

class LawMetadata(Base):
    """法律法规元数据模型"""
    __tablename__ = 'law_metadata'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    law_id = Column(String(100), unique=True, nullable=False, comment="法规唯一标识")
    name = Column(String(500), nullable=False, comment="法规名称")
    number = Column(String(200), comment="法规编号")
    law_type = Column(String(100), comment="法规类型")
    issuing_authority = Column(String(200), comment="发布机关")
    
    # 版本控制
    version_id = Column(String(50), comment="版本号")
    amend_id = Column(String(50), comment="修正案ID")
    parent_law_id = Column(String(100), comment="父法规ID（用于修正案）")
    
    # 时效性字段
    publish_date = Column(Date, comment="发布日期")
    valid_from = Column(Date, comment="生效开始日期")
    valid_to = Column(Date, comment="生效结束日期")
    status = Column(String(20), default=LawStatus.EFFECTIVE, comment="法规状态")
    
    # 来源信息
    source_url = Column(String(500), comment="来源URL")
    source = Column(String(100), comment="数据源")
    
    # 关键词和分类
    keywords = Column(Text, comment="关键词")
    category = Column(String(200), comment="法规分类")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    documents = relationship("LawDocument", back_populates="metadata")
    change_logs = relationship("LawChangeLog", back_populates="law")
    
    # 索引
    __table_args__ = (
        Index('idx_law_id', 'law_id'),
        Index('idx_name', 'name'),
        Index('idx_number', 'number'),
        Index('idx_valid_from_to', 'valid_from', 'valid_to'),
        Index('idx_status', 'status'),
        Index('idx_law_type', 'law_type'),
    )


# ========== 文档层 (Document Layer) ==========

class LawDocument(Base):
    """法规文档内容模型"""
    __tablename__ = 'law_documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    law_id = Column(String(100), ForeignKey('law_metadata.law_id'), nullable=False)
    
    # 文档内容
    content = Column(Text, comment="法规正文")
    content_html = Column(Text, comment="HTML格式内容")
    content_markdown = Column(Text, comment="Markdown格式内容")
    
    # 文档结构
    structure_json = Column(Text, comment="章节结构JSON")
    summary = Column(Text, comment="摘要")
    
    # 文件信息
    file_path = Column(String(500), comment="本地文件路径")
    file_type = Column(String(50), comment="文件类型")
    file_size = Column(Integer, comment="文件大小（字节）")
    file_hash = Column(String(100), comment="文件哈希值")
    
    # 爬取信息
    crawl_time = Column(DateTime, default=datetime.now)
    parse_time = Column(DateTime, comment="解析时间")
    
    # 关系
    metadata = relationship("LawMetadata", back_populates="documents")
    
    # 索引
    __table_args__ = (
        Index('idx_doc_law_id', 'law_id'),
    )


# ========== 向量层 (Vector Layer) - 预留接口 ==========

class LawVector(Base):
    """法规向量索引模型（预留）"""
    __tablename__ = 'law_vectors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    law_id = Column(String(100), nullable=False)
    chunk_id = Column(String(100), nullable=False, comment="文本块ID")
    
    # 向量信息
    chunk_text = Column(Text, comment="文本块内容")
    chunk_position = Column(Integer, comment="文本块位置")
    vector_model = Column(String(100), comment="向量模型名称")
    vector_dimension = Column(Integer, comment="向量维度")
    
    # 向量数据将存储在专门的向量数据库中
    vector_db_id = Column(String(100), comment="向量数据库中的ID")
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 索引
    __table_args__ = (
        Index('idx_vector_law_id', 'law_id'),
        Index('idx_chunk_id', 'chunk_id'),
    )


# ========== 变更历史 ==========

class LawChangeLog(Base):
    """法规变更历史记录"""
    __tablename__ = 'law_change_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    law_id = Column(String(100), ForeignKey('law_metadata.law_id'), nullable=False)
    
    change_type = Column(String(50), comment="变更类型：amend/repeal/expire")
    change_date = Column(Date, comment="变更日期")
    change_description = Column(Text, comment="变更说明")
    related_law_id = Column(String(100), comment="相关法规ID")
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    law = relationship("LawMetadata", back_populates="change_logs")


# ========== 爬取任务 ==========

class CrawlTask(Base):
    """爬取任务记录"""
    __tablename__ = 'crawl_tasks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    law_name = Column(String(500), nullable=False)
    law_number = Column(String(200))
    status = Column(String(50), default='pending')  # pending, processing, success, failed
    source = Column(String(100))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # 任务元数据
    priority = Column(Integer, default=0, comment="优先级")
    scheduled_at = Column(DateTime, comment="计划执行时间")
    started_at = Column(DateTime, comment="开始执行时间")
    completed_at = Column(DateTime, comment="完成时间")
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 索引
    __table_args__ = (
        Index('idx_task_status', 'status'),
        Index('idx_task_priority', 'priority'),
    )


# ========== Pydantic Schema ==========

class LawMetadataSchema(BaseModel):
    """法律法规元数据验证模型"""
    law_id: str
    name: str
    number: Optional[str] = None
    law_type: Optional[str] = None
    issuing_authority: Optional[str] = None
    version_id: Optional[str] = None
    amend_id: Optional[str] = None
    parent_law_id: Optional[str] = None
    publish_date: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    status: LawStatus = LawStatus.EFFECTIVE
    source_url: Optional[str] = None
    source: Optional[str] = None
    keywords: Optional[str] = None
    category: Optional[str] = None
    
    class Config:
        from_attributes = True


class LawDocumentSchema(BaseModel):
    """法规文档验证模型"""
    law_id: str
    content: Optional[str] = None
    content_html: Optional[str] = None
    content_markdown: Optional[str] = None
    structure_json: Optional[str] = None
    summary: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    
    class Config:
        from_attributes = True


class CrawlTaskSchema(BaseModel):
    """爬取任务数据验证模型"""
    law_name: str
    law_number: Optional[str] = None
    status: str = 'pending'
    source: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    priority: int = 0
    scheduled_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True 