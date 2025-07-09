#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置管理模块 - 使用Pydantic Settings优雅处理多环境配置
配置优先级：环境变量 > dev.toml > 默认值
"""
from typing import Dict, List, Optional
from pathlib import Path
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import json
import toml


class CrawlerSettings(BaseSettings):
    """爬虫配置"""
    max_retries: int = Field(3, description="最大重试次数")
    retry_delay: float = Field(2.0, description="重试延迟（秒）")
    timeout: int = Field(30, description="请求超时（秒）")
    max_concurrent: int = Field(3, description="最大并发数")
    rate_limit: int = Field(5, description="每分钟最大请求数")
    crawl_limit: int = Field(0, description="本次爬取数量限制，0表示不限制")
    
    # 友好爬虫策略配置
    friendly_crawling: bool = Field(True, description="启用友好爬虫策略")
    request_interval: float = Field(1.0, description="请求间隔（秒）- 友好爬虫策略")
    respect_robots_txt: bool = Field(True, description="遵守robots.txt")
    max_requests_per_minute: int = Field(60, description="每分钟最大请求数")
    
    user_agents: List[str] = Field(
        default=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ],
        description="User-Agent列表"
    )


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    url: str = Field("sqlite:///data/law_crawler.db", description="数据库连接URL")
    echo: bool = Field(False, description="是否打印SQL语句")
    pool_size: int = Field(10, description="连接池大小")
    max_overflow: int = Field(20, description="最大溢出连接数")
    
    @validator("url")
    def validate_database_url(cls, v):
        """验证数据库URL"""
        if not v:
            raise ValueError("数据库URL不能为空")
        return v


class LogSettings(BaseSettings):
    """日志配置"""
    level: str = Field("INFO", description="日志级别")
    serialize: bool = Field(False, description="是否序列化为JSON格式")
    
    @validator("level")
    def validate_log_level(cls, v):
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"日志级别必须是: {', '.join(valid_levels)}")
        return v.upper()


class DataSourceSettings(BaseSettings):
    """数据源配置"""
    national_name: str = Field("国家法律法规数据库", description="国家数据库名称")
    national_base_url: str = Field("https://flk.npc.gov.cn", description="国家数据库URL")
    national_enabled: bool = Field(True, description="是否启用国家数据库")
    
    gov_legal_name: str = Field("中国政府网", description="政府网名称")
    gov_legal_base_url: str = Field("http://www.gov.cn/zhengce/", description="政府网URL")
    gov_legal_enabled: bool = Field(True, description="是否启用政府网")


class ProxyPoolSettings(BaseSettings):
    """代理池配置"""
    enabled: bool = Field(True, description="是否启用代理池")
    config_file: str = Field("config/proxy_config.toml", description="代理池配置文件路径")
    debug_mode: bool = Field(False, description="调试模式")
    rotation_enabled: bool = Field(True, description="是否启用代理轮换")
    check_interval_minutes: int = Field(30, description="代理检查间隔(分钟)")
    max_retries: int = Field(3, description="最大重试次数")
    timeout_seconds: int = Field(10, description="代理连接超时")


class IPPoolSettings(BaseSettings):
    """IP池配置 (传统配置，保持兼容性)"""
    enabled: bool = Field(True, description="是否启用IP池")
    min_proxies: int = Field(5, description="最小代理数量")
    max_proxies: int = Field(50, description="最大代理数量")
    refresh_interval_hours: int = Field(1, description="刷新间隔(小时)")
    check_timeout: int = Field(10, description="代理检查超时(秒)")
    use_free_proxies: bool = Field(True, description="是否使用免费代理")


class Settings(BaseSettings):
    """主配置类 - 支持环境变量和配置文件覆盖"""
    
    # 项目基本信息
    project_name: str = Field("法律法规爬虫系统", description="项目名称")
    version: str = Field("1.0.0", description="版本号")
    debug: bool = Field(False, description="调试模式")
    
    # 子配置
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    data_sources: DataSourceSettings = Field(default_factory=DataSourceSettings)
    proxy_pool: ProxyPoolSettings = Field(default_factory=ProxyPoolSettings)
    ip_pool: IPPoolSettings = Field(default_factory=IPPoolSettings)
    
    # 法律类型映射
    law_type_mapping: Dict[str, str] = Field(
        default={
            "中华人民共和国主席令": "法律",
            "国务院令": "行政法规",
            "部令": "部门规章",
            "地方性法规": "地方性法规",
            "司法解释": "司法解释"
        }
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # 支持嵌套配置，如 CRAWLER__CRAWL_LIMIT=40
        case_sensitive=False,
        extra="ignore"
    )
    
    @classmethod
    def load_from_toml(cls, toml_path: str = "config/dev.toml") -> "Settings":
        """从TOML文件加载配置"""
        config_file = Path(toml_path)
        
        if not config_file.exists():
            print(f"配置文件 {toml_path} 不存在，使用默认配置")
            return cls()
        
        try:
            toml_data = toml.load(config_file)
            print(f"从 {toml_path} 加载配置")
            
            # 展平嵌套配置，Pydantic会自动处理
            flat_config = {}
            
            # 处理爬虫配置
            if 'crawler' in toml_data:
                for key, value in toml_data['crawler'].items():
                    flat_config[f'crawler__{key}'] = value
            
            # 处理数据库配置
            if 'database' in toml_data:
                for key, value in toml_data['database'].items():
                    flat_config[f'database__{key}'] = value
            
            # 处理日志配置
            if 'log' in toml_data:
                for key, value in toml_data['log'].items():
                    flat_config[f'log__{key}'] = value
            
            # 处理数据源配置
            if 'data_sources' in toml_data:
                ds = toml_data['data_sources']
                if 'national' in ds:
                    for key, value in ds['national'].items():
                        flat_config[f'data_sources__national_{key}'] = value
                if 'gov_legal' in ds:
                    for key, value in ds['gov_legal'].items():
                        flat_config[f'data_sources__gov_legal_{key}'] = value
            
            # 处理代理池配置
            if 'proxy_pool' in toml_data:
                for key, value in toml_data['proxy_pool'].items():
                    flat_config[f'proxy_pool__{key}'] = value
            
            # 处理IP池配置
            if 'ip_pool' in toml_data:
                for key, value in toml_data['ip_pool'].items():
                    flat_config[f'ip_pool__{key}'] = value
            
            # 处理顶级配置
            for key in ['project_name', 'version', 'debug']:
                if key in toml_data:
                    flat_config[key] = toml_data[key]
            
            # 处理default节（兼容旧配置）
            if 'default' in toml_data:
                for key, value in toml_data['default'].items():
                    flat_config[key] = value
            
            return cls(**flat_config)
            
        except Exception as e:
            print(f"加载配置文件失败: {e}，使用默认配置")
            return cls()
    
    def to_json(self) -> str:
        """导出为JSON格式"""
        return json.dumps(self.model_dump(), indent=2, ensure_ascii=False, default=str)
    
    def show_config(self):
        """显示当前配置"""
        print("=== 当前配置 ===")
        print(f"项目: {self.project_name} v{self.version}")
        print(f"调试模式: {self.debug}")
        print(f"爬取限制: {self.crawler.crawl_limit} ({'无限制' if self.crawler.crawl_limit == 0 else '条'})")
        print(f"数据库: {self.database.url}")
        print(f"日志级别: {self.log.level}")
        print(f"数据源: {self.data_sources.national_name}, {self.data_sources.gov_legal_name}")


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例 - 自动加载dev.toml"""
    return Settings.load_from_toml()


# 导出配置实例
settings = get_settings() 