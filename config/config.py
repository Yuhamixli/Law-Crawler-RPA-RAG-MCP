"""
项目配置文件
"""
import os
from pathlib import Path
from typing import Dict, List

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"

# 确保目录存在
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, INDEX_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 数据源配置
DATA_SOURCES = {
    "national": {
        "name": "国家法律法规数据库",
        "base_url": "https://flk.npc.gov.cn",
        "search_url": "https://flk.npc.gov.cn/api/detail",
        "priority": 1
    },
    "gov_legal": {
        "name": "中国政府法制信息网",
        "base_url": "http://www.gov.cn/zhengce/",
        "priority": 2
    },
    "state_council": {
        "name": "国务院公报",
        "base_url": "http://www.gov.cn/gongbao/",
        "priority": 2
    }
}

# 爬虫配置
CRAWLER_CONFIG = {
    "max_retries": 3,
    "retry_delay": 2,  # 秒
    "timeout": 30,  # 秒
    "max_concurrent": 3,  # 最大并发数
    "rate_limit": 5,  # 每分钟最大请求数
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
    ],
    "headers": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
}

# 数据库配置
DATABASE_CONFIG = {
    "url": os.getenv("DATABASE_URL", "sqlite:///data/law_crawler.db"),
    "echo": False,
    "pool_size": 10,
    "max_overflow": 20
}

# Redis配置
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DB", 0)),
    "password": os.getenv("REDIS_PASSWORD", None)
}

# RAG配置
RAG_CONFIG = {
    "embedding_model": "BAAI/bge-large-zh-v1.5",
    "vector_db": "chromadb",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 5
}

# 日志配置
LOG_CONFIG = {
    "level": "INFO",
    "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    "rotation": "10 MB",
    "retention": "7 days",
    "compression": "zip"
}

# 法律类型映射
LAW_TYPE_MAPPING = {
    "中华人民共和国主席令": "国家法律",
    "国务院令": "行政法规",
    "部令": "部门规章",
    "地方性法规": "地方性法规",
    "司法解释": "司法解释"
} 