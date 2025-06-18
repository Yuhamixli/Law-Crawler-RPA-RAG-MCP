"""
国家法律法规数据库网页爬虫
"""
import re
import json
import asyncio
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import httpx
from loguru import logger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.crawler.base_crawler import BaseCrawler
from config.config import RAW_DATA_DIR
import hashlib
from datetime import datetime


class NPCWebCrawler(BaseCrawler):
    """国家法律法规数据库网页爬虫"""
    
    def __init__(self):
        super().__init__("npc_web")
        self.base_url = "https://flk.npc.gov.cn"
        self.detail_url = f"{self.base_url}/detail2.html"
        
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法律法规"""
        results = []
        
        # 构建搜索URL
        search_url = f"{self.base_url}/fl.html"
        
        try:
            # 获取法律列表页面
            response = await self.fetch(search_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有法律链接
            law_links = soup.find_all('p', onclick=re.compile(r"window\.open\('\.\/detail2\.html\?"))
            
            for link in law_links:
                title = link.get('title', '').strip()
                
                # 检查是否匹配搜索条件
                if law_name in title:
                    # 提取详情页ID
                    onclick = link.get('onclick', '')
                    match = re.search(r"detail2\.html\?([^']+)", onclick)
                    
                    if match:
                        detail_id = match.group(1)
                        
                        # 如果指定了编号，进行额外匹配
                        if law_number and law_number not in title:
                            continue
                            
                        result = {
                            "id": detail_id,
                            "name": title,
                            "number": self._extract_number_from_title(title),
                            "source_url": f"{self.detail_url}?{detail_id}",
                            "summary": ""
                        }
                        results.append(result)
                        
                        logger.info(f"找到匹配法规: {title}")
                        
            # 如果没有找到，尝试模糊搜索
            if not results:
                # 搜索所有包含关键词的法律
                for link in law_links:
                    title = link.get('title', '').strip()
                    
                    # 更宽松的匹配
                    if any(keyword in title for keyword in law_name.split()):
                        onclick = link.get('onclick', '')
                        match = re.search(r"detail2\.html\?([^']+)", onclick)
                        
                        if match:
                            detail_id = match.group(1)
                            result = {
                                "id": detail_id,
                                "name": title,
                                "number": self._extract_number_from_title(title),
                                "source_url": f"{self.detail_url}?{detail_id}",
                                "summary": ""
                            }
                            results.append(result)
                            
        except Exception as e:
            logger.error(f"搜索失败: {law_name}, 错误: {str(e)}")
            
        return results[:10]  # 返回前10个结果
        
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情"""
        detail_url = f"{self.detail_url}?{law_id}"
        
        try:
            response = await self.fetch(detail_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title_elem = soup.find('div', class_='title') or soup.find('h1') or soup.find('h2')
            title = title_elem.text.strip() if title_elem else ""
            
            # 提取正文内容
            content_elem = soup.find('div', class_='content') or soup.find('div', id='content')
            content = ""
            
            if content_elem:
                # 移除脚本和样式
                for script in content_elem(["script", "style"]):
                    script.decompose()
                content = content_elem.get_text(separator='\n', strip=True)
            else:
                # 尝试其他方式获取内容
                body_elem = soup.find('body')
                if body_elem:
                    content = body_elem.get_text(separator='\n', strip=True)
            
            # 提取元数据
            metadata = self._extract_metadata(soup, content)
            
            detail = {
                "id": law_id,
                "name": title or metadata.get("name", ""),
                "number": metadata.get("number"),
                "law_type": metadata.get("law_type"),
                "issuing_authority": metadata.get("issuing_authority"),
                "publish_date": metadata.get("publish_date"),
                "effective_date": metadata.get("effective_date"),
                "content": content,
                "source_url": detail_url,
                "keywords": metadata.get("keywords"),
                "source": self.source_name
            }
            
            return detail
            
        except Exception as e:
            logger.error(f"获取详情失败: {law_id}, 错误: {str(e)}")
            
        return {}
        
    def _extract_number_from_title(self, title: str) -> str:
        """从标题中提取法规编号"""
        # 尝试匹配常见的编号模式
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
        
    def _extract_metadata(self, soup: BeautifulSoup, content: str) -> Dict[str, Any]:
        """从页面提取元数据"""
        metadata = {}
        
        # 从内容中提取信息
        lines = content.split('\n')[:20]  # 只看前20行
        
        for line in lines:
            line = line.strip()
            
            # 提取发布机关
            if '发布' in line or '公布' in line:
                metadata['issuing_authority'] = line
                
            # 提取日期
            date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', line)
            if date_match:
                date_str = date_match.group(1)
                if '公布' in line or '发布' in line:
                    metadata['publish_date'] = self.parse_date(date_str)
                elif '施行' in line or '生效' in line:
                    metadata['effective_date'] = self.parse_date(date_str)
                    
            # 提取编号
            if '第' in line and '号' in line:
                metadata['number'] = line
                
        # 提取法规类型
        if content:
            metadata['law_type'] = self.extract_law_type(content[:200])
            
        return metadata
        
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件（如果有PDF版本）"""
        # 这个网站主要是HTML内容，通常不提供PDF下载
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
            # 生成唯一ID
            unique_id = hashlib.md5(f"{detail['name']}_{detail.get('number', '')}".encode()).hexdigest()[:16]
            detail['law_id'] = unique_id
            
            # 保存详情到JSON文件
            json_file = f"{unique_id}_{detail['name'][:30]}.json".replace("/", "_").replace("\\", "_")
            json_path = os.path.join(RAW_DATA_DIR, "json", json_file)
            
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(detail, f, ensure_ascii=False, indent=2, default=str)
                
            logger.info(f"法规爬取成功: {law_name}")
            return detail
            
        return None 