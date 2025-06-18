"""
国家法律法规数据库爬虫
"""
import json
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.crawler.base_crawler import BaseCrawler
from config.config import DATA_SOURCES, RAW_DATA_DIR


class NationalLawCrawler(BaseCrawler):
    """国家法律法规数据库爬虫"""
    
    def __init__(self):
        super().__init__("national")
        self.base_url = DATA_SOURCES["national"]["base_url"]
        self.search_api = f"{self.base_url}/api/search"
        self.detail_api = f"{self.base_url}/api/detail"
        
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法律法规"""
        results = []
        
        # 构建搜索参数
        params = {
            "type": "title",
            "searchType": "title",
            "sortTr": "f_bbrq_s",
            "gbrqStart": "",
            "gbrqEnd": "",
            "sxrqStart": "",
            "sxrqEnd": "",
            "page": 1,
            "size": 10,
            "showDetailLink": "1",
            "checkFlag": "1",
            "keyword": law_name
        }
        
        try:
            # 发送搜索请求
            response = await self.fetch(self.search_api, params=params)
            data = response.json()
            
            if data.get("code") == 200 and data.get("result"):
                items = data["result"].get("data", [])
                
                for item in items:
                    # 如果指定了法规编号，进行匹配
                    if law_number and law_number not in item.get("subtitle", ""):
                        continue
                        
                    result = {
                        "id": item.get("id"),
                        "name": item.get("title"),
                        "number": item.get("subtitle"),
                        "publish_date": item.get("publish"),
                        "source_url": f"{self.base_url}/detail?sysId={item.get('id')}",
                        "summary": item.get("summary", "")
                    }
                    results.append(result)
                    
        except Exception as e:
            logger.error(f"搜索失败: {law_name}, 错误: {str(e)}")
            
        return results
        
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情"""
        params = {"sysId": law_id}
        
        try:
            response = await self.fetch(self.detail_api, params=params)
            data = response.json()
            
            if data.get("code") == 200 and data.get("result"):
                result = data["result"]
                
                # 提取详细信息
                detail = {
                    "id": law_id,
                    "name": result.get("title"),
                    "number": result.get("subtitle"),
                    "law_type": self.extract_law_type(result.get("subtitle", "")),
                    "issuing_authority": result.get("office"),
                    "publish_date": self.parse_date(result.get("publish")),
                    "effective_date": self.parse_date(result.get("expiry")),
                    "content": result.get("body", ""),
                    "source_url": f"{self.base_url}/detail?sysId={law_id}",
                    "keywords": result.get("keywords", ""),
                    "source": self.source_name
                }
                
                # 检查是否有PDF附件
                if result.get("attachment"):
                    detail["attachment_url"] = result["attachment"]
                    
                return detail
                
        except Exception as e:
            logger.error(f"获取详情失败: {law_id}, 错误: {str(e)}")
            
        return {}
        
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件"""
        try:
            response = await self.fetch(url)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存文件
            with open(save_path, 'wb') as f:
                f.write(response.content)
                
            logger.info(f"文件下载成功: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"文件下载失败: {url}, 错误: {str(e)}")
            return False
            
    async def crawl_law(self, law_name: str, law_number: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """爬取单个法律法规"""
        # 搜索法规
        search_results = await self.search(law_name, law_number)
        
        if not search_results:
            logger.warning(f"未找到法规: {law_name}")
            return None
            
        # 获取第一个匹配结果的详情
        law_id = search_results[0]["id"]
        detail = await self.get_detail(law_id)
        
        if detail:
            # 如果有附件，下载附件
            if detail.get("attachment_url"):
                file_name = f"{detail['number']}_{detail['name']}.pdf".replace("/", "_")
                save_path = os.path.join(RAW_DATA_DIR, "pdf", file_name)
                
                if await self.download_file(detail["attachment_url"], save_path):
                    detail["file_path"] = save_path
                    
            # 保存详情到JSON文件
            json_file = f"{detail['number']}_{detail['name']}.json".replace("/", "_")
            json_path = os.path.join(RAW_DATA_DIR, "json", json_file)
            
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(detail, f, ensure_ascii=False, indent=2, default=str)
                
            logger.info(f"法规爬取成功: {law_name}")
            return detail
            
        return None 