"""
基础爬虫类
"""
import time
import random
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from fake_useragent import UserAgent
from loguru import logger
import sys
sys.path.append('..')
from config.settings import settings


class BaseCrawler(ABC):
    """基础爬虫抽象类"""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.name = source_name  # 添加name属性以兼容CrawlerManager
        self.session = None
        self.ua = UserAgent()
        self.request_count = 0
        self.last_request_time = 0
        self.crawler_config = settings.crawler
        self.law_type_mapping = settings.law_type_mapping
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = httpx.AsyncClient(
            timeout=self.crawler_config.timeout,
            follow_redirects=True
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.aclose()
            
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = self.crawler_config.default_headers.copy() if hasattr(self.crawler_config, 'default_headers') else {}
        user_agents = self.crawler_config.user_agents if hasattr(self.crawler_config, 'user_agents') else []
        if user_agents:
            headers['User-Agent'] = random.choice(user_agents)
        return headers
        
    async def _rate_limit(self):
        """速率限制"""
        current_time = time.time()
        rate_limit = self.crawler_config.rate_limit if hasattr(self.crawler_config, 'rate_limit') else 5
        time_since_last_request = current_time - self.last_request_time
        
        # 确保请求间隔
        if time_since_last_request < 60 / rate_limit:
            sleep_time = 60 / rate_limit - time_since_last_request
            # 添加随机抖动
            sleep_time += random.uniform(0.5, 1.5)
            await asyncio.sleep(sleep_time)
            
        self.last_request_time = time.time()
        self.request_count += 1
        
    @retry(
        stop=stop_after_attempt(getattr(settings.crawler, 'max_retries', 3)),
        wait=wait_exponential(multiplier=getattr(settings.crawler, 'retry_delay', 2), max=60)
    )
    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        """发送HTTP请求"""
        await self._rate_limit()
        
        headers = kwargs.pop('headers', {})
        headers.update(self._get_headers())
        
        logger.info(f"Fetching: {url}")
        
        # 确保session存在
        if not self.session:
            self.session = httpx.AsyncClient(
                timeout=self.crawler_config.timeout,
                follow_redirects=True
            )
        
        try:
            response = await self.session.get(url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            raise
            
    @abstractmethod
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法律法规"""
        pass
        
    @abstractmethod
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情"""
        pass
        
    @abstractmethod
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件"""
        pass
        
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None
            
        # 尝试多种日期格式
        date_formats = [
            "%Y-%m-%d",
            "%Y年%m月%d日",
            "%Y.%m.%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
                
        logger.warning(f"无法解析日期: {date_str}")
        return None
        
    def extract_law_type(self, law_number: str) -> str:
        """从法规编号提取法规类型"""
        for key, value in self.law_type_mapping.items():
            if key in law_number:
                return value
                
        return "其他" 