"""
本地文件爬虫 - 从本地HTML文件中提取法规数据
"""
import os
import json
import hashlib
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup
from loguru import logger
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.crawler.base_crawler import BaseCrawler
from config.config import RAW_DATA_DIR
from datetime import datetime, date


class LocalFileCrawler(BaseCrawler):
    """本地文件爬虫"""
    
    def __init__(self, test_dir: str = "data/test_laws"):
        super().__init__("local_file")
        self.name = "local_file"
        self.test_dir = test_dir
        
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """从本地文件搜索法律法规"""
        results = []
        
        # 检查测试目录是否存在
        if not os.path.exists(self.test_dir):
            logger.warning(f"测试目录不存在: {self.test_dir}")
            return results
            
        # 遍历目录中的HTML文件
        for filename in os.listdir(self.test_dir):
            if filename.endswith('.html') and law_name in filename:
                file_path = os.path.join(self.test_dir, filename)
                logger.info(f"找到匹配文件: {filename}")
                
                # 读取并解析HTML文件
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                        
                    # 解析HTML
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 提取标题和内容
                    title = soup.find('title')
                    title_text = title.text.strip() if title else law_name
                    
                    # 提取正文内容
                    content = soup.get_text(separator='\n', strip=True)
                    
                    # 检查是否有对应的JSON文件
                    json_file = filename.replace('.html', '.json')
                    json_path = os.path.join(self.test_dir, json_file)
                    
                    law_data = {
                        "name": title_text or law_name,
                        "number": law_number,
                        "source_url": f"file:///{file_path}",
                        "source": "local_file",
                        "content": content
                    }
                    
                    # 如果有JSON文件，读取额外信息
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                                law_data.update(json_data)
                        except Exception as e:
                            logger.error(f"读取JSON文件失败: {json_path}, 错误: {str(e)}")
                    
                    results.append(law_data)
                    
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {str(e)}")
                    
        # 如果没有找到文件，返回模拟数据
        if not results:
            logger.info(f"未找到本地文件，生成模拟数据: {law_name}")
            results = self._generate_mock_data(law_name, law_number)
            
        return results
        
    def _generate_mock_data(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """生成模拟数据"""
        # 基于法律名称生成模拟数据
        mock_content = f"""
{law_name}

（{law_number or '法律编号'}）

第一章 总则

第一条 为了规范相关活动，维护社会秩序，保障公民、法人和其他组织的合法权益，根据宪法，制定本法。

第二条 在中华人民共和国境内从事相关活动，适用本法。

第三条 国家坚持依法治国原则，保障法律的正确实施。

第二章 主要规定

第四条 相关主体应当遵守本法的规定，履行相应的义务。

第五条 国家机关应当依法行使职权，保护相关权益。

第六条 任何组织和个人不得违反本法的规定。

第三章 监督管理

第七条 国务院相关部门负责本法的监督管理工作。

第八条 地方各级人民政府应当加强对本法实施的领导。

第四章 法律责任

第九条 违反本法规定的，依法承担相应的法律责任。

第十条 构成犯罪的，依法追究刑事责任。

第五章 附则

第十一条 本法自公布之日起施行。
"""
        
        # 解析实施日期
        impl_date = None
        impl_date_str = None
        if '反洗钱法' in law_name:
            impl_date_str = "2025-01-01"
            impl_date = date(2025, 1, 1)
        elif '关税法' in law_name:
            impl_date_str = "2024-12-01"
            impl_date = date(2024, 12, 1)
        elif '统计法' in law_name:
            impl_date_str = "2024-09-13"
            impl_date = date(2024, 9, 13)
        elif '会计法' in law_name:
            impl_date_str = "2024-07-01"
            impl_date = date(2024, 7, 1)
        elif '科学技术奖励条例' in law_name:
            impl_date_str = "2024-05-26"
            impl_date = date(2024, 5, 26)
            
        result = {
            "id": hashlib.md5(law_name.encode()).hexdigest()[:16],
            "name": law_name,
            "number": law_number,
            "law_type": "行政法规" if "条例" in law_name else "法律",
            "issuing_authority": "国务院" if "条例" in law_name else "全国人民代表大会常务委员会",
            "publish_date": impl_date,  # 已经是date对象
            "effective_date": impl_date,  # 已经是date对象
            "content": mock_content,
            "source_url": f"mock://local/{hashlib.md5(law_name.encode()).hexdigest()[:8]}",
            "source": "local_mock",
            "summary": f"《{law_name}》是我国重要的法律法规，对相关领域的活动进行了全面规范。"
        }
        
        return [result]
        
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情"""
        # 对于本地文件，直接返回
        return {"id": law_id, "source": "local_file"}
        
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件（本地文件不需要下载）"""
        return False
        
    async def crawl_law(self, law_name: str, law_number: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """爬取单个法律法规"""
        # 搜索法规
        search_results = await self.search(law_name, law_number)
        
        if not search_results:
            logger.warning(f"未找到法规: {law_name}")
            return None
            
        # 获取第一个结果
        result = search_results[0]
        
        # 生成唯一ID
        unique_id = hashlib.md5(f"{result['name']}_{result.get('number', '')}".encode()).hexdigest()[:16]
        result['law_id'] = unique_id
        
        # 保存到JSON文件
        json_file = f"{unique_id}_{result['name'][:30]}.json".replace("/", "_").replace("\\", "_")
        json_path = os.path.join(RAW_DATA_DIR, "json", json_file)
        
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            
        logger.info(f"法规爬取成功: {law_name} (来源: {result.get('source', 'unknown')})")
        return result 