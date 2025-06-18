"""
国家法律法规数据库API爬虫
"""
import re
import json
import asyncio
from typing import Dict, Optional, List, Any
from urllib.parse import quote
import httpx
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.crawler.base_crawler import BaseCrawler
from config.config import RAW_DATA_DIR
import hashlib
from datetime import datetime


class NPCAPICrawler(BaseCrawler):
    """国家法律法规数据库API爬虫"""
    
    def __init__(self):
        super().__init__("npc_api")
        self.base_url = "https://flk.npc.gov.cn"
        self.search_api = f"{self.base_url}/api/search"
        self.detail_api = f"{self.base_url}/api/detail"
        
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """通过API搜索法律法规"""
        results = []
        
        # API参数 - 使用最小参数集避免500错误
        params = {
            "keyword": law_name,
            "page": 1,
            "size": 20
        }
        
        try:
            response = await self.fetch(self.search_api, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # 调试信息
                logger.debug(f"API响应: {json.dumps(data, ensure_ascii=False)[:500]}")
                
                if data.get("success") and data.get("result"):
                    items = data["result"].get("data", [])
                    
                    for item in items:
                        # 如果指定了编号，进行匹配
                        if law_number and law_number not in item.get("title", ""):
                            continue
                            
                        result = {
                            "id": item.get("id"),
                            "name": item.get("title"),
                            "number": self._extract_number_from_title(item.get("title", "")),
                            "law_type": item.get("type"),
                            "issuing_authority": item.get("office"),
                            "publish_date": item.get("publish"),
                            "effective_date": item.get("expiry"),
                            "status": item.get("status"),
                            "source_url": f"{self.base_url}{item.get('url', '').lstrip('.')}",
                            "summary": ""
                        }
                        results.append(result)
                        
                        logger.info(f"找到法规: {result['name']}")
                        
        except Exception as e:
            logger.error(f"搜索失败: {law_name}, 错误: {str(e)}")
            
        return results
        
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情"""
        # 尝试通过API获取详情
        params = {"id": law_id}
        
        try:
            # 首先尝试API
            response = await self.fetch(f"{self.detail_api}", params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and data.get("result"):
                    detail_data = data["result"]
                    
                    return {
                        "id": law_id,
                        "name": detail_data.get("title"),
                        "number": detail_data.get("number"),
                        "law_type": detail_data.get("type"),
                        "issuing_authority": detail_data.get("office"),
                        "publish_date": detail_data.get("publish"),
                        "effective_date": detail_data.get("expiry"),
                        "content": detail_data.get("content", ""),
                        "source_url": f"{self.base_url}/detail2.html?{law_id}",
                        "keywords": detail_data.get("keywords"),
                        "source": self.source_name
                    }
                    
        except Exception as e:
            logger.warning(f"API获取详情失败: {law_id}, 尝试网页爬取")
            
        # 如果API失败，尝试爬取网页
        return await self._get_detail_from_web(law_id)
        
    async def _get_detail_from_web(self, law_id: str) -> Dict[str, Any]:
        """从网页获取详情（备用方案）"""
        detail_url = f"{self.base_url}/detail2.html?{law_id}"
        
        try:
            # 获取网页
            response = await self.fetch(detail_url)
            
            # 由于内容是通过JavaScript加载的，我们需要分析JS请求
            # 或者使用其他方法获取内容
            
            # 这里简单返回基本信息
            return {
                "id": law_id,
                "source_url": detail_url,
                "source": self.source_name,
                "note": "详情需要JavaScript渲染"
            }
            
        except Exception as e:
            logger.error(f"网页获取详情失败: {law_id}, 错误: {str(e)}")
            
        return {}
        
    def _extract_number_from_title(self, title: str) -> str:
        """从标题中提取法规编号"""
        patterns = [
            r'第\d+号',
            r'〔\d+〕\d+号',
            r'（\d+年）',
            r'\[\d+\]\d+号'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group()
                
        return ""
        
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件（国家法律法规数据库通常不提供PDF下载）"""
        return False
        
    async def crawl_law(self, law_name: str, law_number: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """爬取单个法律法规"""
        # 搜索法规
        search_results = await self.search(law_name, law_number)
        
        if not search_results:
            logger.warning(f"未找到法规: {law_name}")
            return None
            
        # 获取第一个匹配结果
        result = search_results[0]
        
        # 尝试获取详情
        detail = await self.get_detail(result["id"])
        
        # 合并搜索结果和详情
        if detail:
            result.update(detail)
        
        # 生成唯一ID
        unique_id = hashlib.md5(f"{result['name']}_{result.get('number', '')}".encode()).hexdigest()[:16]
        result['law_id'] = unique_id
        
        # 保存到JSON文件
        json_file = f"{unique_id}_{result['name'][:30]}.json".replace("/", "_").replace("\\", "_")
        json_path = os.path.join(RAW_DATA_DIR, "json", json_file)
        
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            
        logger.info(f"法规爬取成功: {law_name}")
        return result 