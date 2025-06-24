"""
直接URL访问爬虫
用于访问已知的政府网链接，绕过搜索引擎限制
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from ..base_crawler import BaseCrawler


class DirectUrlCrawler(BaseCrawler):
    """直接访问已知URL的爬虫"""
    
    def __init__(self):
        super().__init__(source_name="直接URL访问")
        self.session = requests.Session()
        
        # 添加logger
        from loguru import logger
        self.logger = logger
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # 已知的法规URL映射
        self.known_urls = {
            '建筑工程设计招标投标管理办法': 'https://www.gov.cn/gongbao/content/2017/content_5230272.htm',
            '房屋建筑和市政基础设施工程施工招标投标管理办法': 'https://www.gov.cn/zhengce/2022-01/25/content_5712036.htm',
            '固定资产投资项目节能审查办法': 'https://www.gov.cn/zhengce/2023-04/06/content_5750368.htm',
        }
    
    async def crawl_law(self, law_name: str, law_number: str = None) -> Optional[Dict[str, Any]]:
        """爬取法规信息"""
        try:
            self.logger.info(f"直接URL爬取: {law_name}")
            
            # 查找匹配的URL
            matched_url = self._find_matching_url(law_name)
            if not matched_url:
                self.logger.warning(f"未找到匹配的已知URL: {law_name}")
                return None
            
            # 直接访问URL获取内容
            law_info = self._get_law_from_url(matched_url, law_name)
            if law_info:
                law_info['crawler_strategy'] = 'direct_url'
                self.logger.success(f"直接URL访问成功: {law_name}")
                return law_info
            else:
                self.logger.warning(f"直接URL访问失败: {law_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"直接URL爬取异常: {e}")
            return None
    
    def _find_matching_url(self, law_name: str) -> Optional[str]:
        """查找匹配的URL"""
        # 精确匹配
        if law_name in self.known_urls:
            return self.known_urls[law_name]
        
        # 模糊匹配
        clean_name = re.sub(r'[（(].*?[）)]', '', law_name).strip()
        for known_name, url in self.known_urls.items():
            if clean_name in known_name or known_name in clean_name:
                self.logger.info(f"模糊匹配成功: '{law_name}' -> '{known_name}'")
                return url
        
        # 关键词匹配
        keywords = self._extract_keywords(law_name)
        for known_name, url in self.known_urls.items():
            match_count = sum(1 for keyword in keywords if keyword in known_name)
            if match_count >= 2:  # 至少匹配2个关键词
                self.logger.info(f"关键词匹配成功: '{law_name}' -> '{known_name}' (匹配{match_count}个关键词)")
                return url
        
        return None
    
    def _extract_keywords(self, law_name: str) -> List[str]:
        """提取关键词"""
        import jieba
        
        # 去掉括号内容
        clean_name = re.sub(r'[（(].*?[）)]', '', law_name)
        
        # 分词
        words = list(jieba.cut(clean_name))
        
        # 过滤停用词和短词
        stop_words = {'的', '和', '与', '及', '等', '有关', '关于', '实施', '管理', '规定', '办法', '条例', '法'}
        keywords = [word for word in words if len(word) >= 2 and word not in stop_words]
        
        return keywords
    
    def _get_law_from_url(self, url: str, law_name: str) -> Optional[Dict[str, Any]]:
        """从URL获取法规信息"""
        try:
            self.logger.info(f"访问URL: {url}")
            
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                self.logger.warning(f"HTTP错误: {response.status_code}")
                return None
            
            # 确保正确的编码
            response.encoding = 'utf-8'
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取基本信息
            title = soup.find('title')
            page_title = title.text.strip() if title else ""
            
            # 提取法规详细信息
            law_info = self._extract_law_details(soup, response.text, url, law_name)
            
            # 添加基本信息
            law_info.update({
                'success': True,
                'source_url': url,
                'page_title': page_title,
                'crawl_time': self._get_current_time(),
                'source': '中国政府网-直接访问',
                'target_name': law_name
            })
            
            return law_info
            
        except Exception as e:
            self.logger.error(f"访问URL失败 {url}: {e}")
            return None
    
    def _extract_law_details(self, soup: BeautifulSoup, content: str, url: str, law_name: str) -> Dict[str, Any]:
        """提取法规详细信息"""
        import re
        
        details = {
            'name': law_name,
            'title': law_name,
            'number': '',
            'document_number': '',
            'publish_date': '',
            'valid_from': '',
            'valid_to': '',
            'office': '',
            'issuing_authority': '',
            'level': '',
            'law_level': '',
            'status': '现行有效',
            'content': ''
        }
        
        try:
            # 从页面标题提取信息
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.text
                
                # 提取文号
                number_match = re.search(r'第(\d+)号', title_text)
                if number_match:
                    details['number'] = f"第{number_match.group(1)}号"
                    details['document_number'] = details['number']
                
                # 提取发布机关
                if '住房和城乡建设部' in title_text or '住建部' in title_text:
                    details['issuing_authority'] = '住房和城乡建设部'
                    details['office'] = '住房和城乡建设部'
                    details['level'] = '部门规章'
                    details['law_level'] = '部门规章'
            
            # 从内容中提取更多信息
            text_content = soup.get_text()
            
            # 提取发布日期
            date_patterns = [
                r'(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}-\d{1,2}-\d{1,2})',
                r'发布日期[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}年第\d+号)'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text_content)
                if match:
                    details['publish_date'] = match.group(1)
                    break
            
            # 提取实施日期
            impl_patterns = [
                r'自(\d{4}年\d{1,2}月\d{1,2}日)起施行',
                r'实施日期[：:]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}年\d{1,2}月\d{1,2}日)起施行'
            ]
            
            for pattern in impl_patterns:
                match = re.search(pattern, text_content)
                if match:
                    details['valid_from'] = match.group(1)
                    break
            
            # 提取主要内容
            content_elem = soup.find('div', class_='pages_content') or soup.find('div', class_='content')
            if content_elem:
                details['content'] = content_elem.get_text(strip=True)[:1000] + "..."
            else:
                # 如果没有找到特定的内容区域，提取页面主要文本
                details['content'] = text_content[:1000] + "..."
            
            # 根据URL判断年份和类型
            if '2017' in url:
                if not details['publish_date']:
                    details['publish_date'] = '2017年'
                if not details['valid_from']:
                    details['valid_from'] = '2017年'
            elif '2022' in url:
                if not details['publish_date']:
                    details['publish_date'] = '2022年'
                if not details['valid_from']:
                    details['valid_from'] = '2022年'
            
        except Exception as e:
            self.logger.warning(f"提取详细信息失败: {e}")
        
        return details
    
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索接口（兼容性）"""
        result = await self.crawl_law(law_name, law_number)
        return [result] if result else []
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取详情接口（兼容性）"""
        return {}
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件接口（兼容性）"""
        return False
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().isoformat()


def create_direct_url_crawler():
    """创建直接URL爬虫实例"""
    return DirectUrlCrawler() 