"""
项目配置系统 - 基于 Pydantic Settings
"""
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import BaseSettings, Field, validator
from functools import lru_cache
import json


class CrawlerSettings(BaseSettings):
    """爬虫配置"""
    max_retries: int = Field(3, description="最大重试次数")
    retry_delay: float = Field(2.0, description="重试延迟（秒）")
    timeout: int = Field(30, description="请求超时（秒）")
    max_concurrent: int = Field(3, description="最大并发数")
    rate_limit: int = Field(5, description="每分钟最大请求数")
    user_agents: List[str] = Field(
        default=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Firefox/119.0"
        ],
        description="User-Agent列表"
    )
    default_headers: Dict[str, str] = Field(
        default={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        },
        description="默认请求头"
    )


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    url: str = Field("sqlite:///data/law_crawler.db", env="DATABASE_URL")
    echo: bool = Field(False, description="是否打印SQL语句")
    pool_size: int = Field(10, description="连接池大小")
    max_overflow: int = Field(20, description="最大溢出连接数")
    
    @validator("url")
    def validate_database_url(cls, v):
        """验证数据库URL"""
        if not v:
            raise ValueError("数据库URL不能为空")
        return v


class RedisSettings(BaseSettings):
    """Redis配置"""
    host: str = Field("localhost", env="REDIS_HOST")
    port: int = Field(6379, env="REDIS_PORT")
    db: int = Field(0, env="REDIS_DB")
    password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    
    @property
    def url(self) -> str:
        """生成Redis URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class LogSettings(BaseSettings):
    """日志配置"""
    level: str = Field("INFO", env="LOG_LEVEL")
    format: str = Field(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    rotation: str = Field("10 MB", description="日志轮转大小")
    retention: str = Field("7 days", description="日志保留时间")
    compression: str = Field("zip", description="日志压缩格式")
    serialize: bool = Field(False, description="是否序列化为JSON")
    
    @validator("level")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是: {', '.join(valid_levels)}")
        return v.upper()


class DataSourceSettings(BaseSettings):
    """数据源配置"""
    sources: Dict[str, Dict[str, any]] = Field(
        default={
            "national": {
                "name": "国家法律法规数据库",
                "base_url": "https://flk.npc.gov.cn",
                "priority": 1,
                "enabled": True
            },
            "gov_legal": {
                "name": "中国政府法制信息网",
                "base_url": "http://www.gov.cn/zhengce/",
                "priority": 2,
                "enabled": False
            }
        }
    )


class Settings(BaseSettings):
    """主配置类"""
    # 项目基本信息
    project_name: str = Field("法律法规爬虫系统", description="项目名称")
    version: str = Field("1.0.0", description="版本号")
    debug: bool = Field(False, env="DEBUG")
    
    # 路径配置
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    
    # 子配置
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    data_sources: DataSourceSettings = Field(default_factory=DataSourceSettings)
    
    # 法律类型映射
    law_type_mapping: Dict[str, str] = Field(
        default={
            "中华人民共和国主席令": "国家法律",
            "国务院令": "行政法规",
            "部令": "部门规章",
            "地方性法规": "地方性法规",
            "司法解释": "司法解释"
        }
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def to_json(self) -> str:
        """导出为JSON格式"""
        return json.dumps(self.dict(), indent=2, ensure_ascii=False, default=str)
    
    @classmethod
    def from_file(cls, config_file: str) -> "Settings":
        """从配置文件加载"""
        config_path = Path(config_file)
        if config_path.suffix == ".json":
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        elif config_path.suffix in [".yaml", ".yml"]:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls(**data)
        elif config_path.suffix == ".toml":
            import toml
            with open(config_path, "r", encoding="utf-8") as f:
                data = toml.load(f)
            return cls(**data)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出配置实例
settings = get_settings() 