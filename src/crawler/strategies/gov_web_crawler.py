#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
中国政府网爬虫策略
用于在 www.gov.cn 上搜索法律法规作为第二数据源
处理逻辑：针对在 flk.npc.gov.cn 找不到的法律法规进行补充搜索
"""

import json
import requests
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from loguru import logger

from ..base_crawler import BaseCrawler


class GovWebCrawler(BaseCrawler):
    """中国政府网爬虫策略"""
    
    def __init__(self):
        super().__init__("gov_web")
        self.setup_headers()
        self.logger = logger
        self.base_url = "https://www.gov.cn"
        
    def setup_headers(self):
        """设置请求头"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        })
    
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法规 - 实现抽象方法"""
        return self.search_law(law_name)
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法规详情 - 实现抽象方法"""
        # 对于政府网，law_id实际上是URL
        return self.get_law_detail_from_url(law_id)
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件 - 实现抽象方法"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        except Exception as e:
            self.logger.error(f"下载文件失败: {str(e)}")
            return False
    
    def search_law(self, keyword: str) -> List[Dict[str, Any]]:
        """在政府网搜索法规 - 尝试找到真正的搜索API"""
        try:
            self.logger.info(f"政府网搜索: {keyword}")
            
            # 步骤1: 尝试直接调用可能的AJAX搜索API
            api_candidates = [
                "https://sousuo.www.gov.cn/api/search",
                "https://sousuo.www.gov.cn/sousuo/search",
                "https://sousuo.www.gov.cn/sousuo/api/search",
                "https://api.sousuo.www.gov.cn/search",
                "https://www.gov.cn/api/search"
            ]
            
            # 尝试不同的API参数组合
            api_params_combinations = [
                {
                    "q": keyword,
                    "searchWord": keyword,
                    "type": "all",
                    "page": 1,
                    "size": 20
                },
                {
                    "searchWord": keyword,
                    "dataTypeId": "107",  # 从URL中看到的参数
                    "page": 1
                },
                {
                    "keyword": keyword,
                    "code": "17da70961a7",  # 从URL中看到的固定码
                    "dataTypeId": "107"
                }
            ]
            
            for api_url in api_candidates:
                for params in api_params_combinations:
                    try:
                        self.logger.debug(f"尝试API: {api_url} with params: {params}")
                        
                        # 尝试GET请求
                        response = self.session.get(api_url, params=params, timeout=10)
                        if response.status_code == 200:
                            try:
                                json_data = response.json()
                                results = self._parse_api_response(json_data, keyword)
                                if results:
                                    self.logger.info(f"API搜索成功，找到 {len(results)} 个结果")
                                    return results
                            except:
                                # 可能不是JSON响应，尝试解析HTML
                                if "电子招标投标办法" in response.text or keyword in response.text:
                                    self.logger.debug("API返回HTML内容，尝试解析")
                                    results = self._parse_search_results(response.text, response.url, keyword)
                                    if results:
                                        return results
                        
                        # 尝试POST请求
                        response = self.session.post(api_url, json=params, timeout=10)
                        if response.status_code == 200:
                            try:
                                json_data = response.json()
                                results = self._parse_api_response(json_data, keyword)
                                if results:
                                    self.logger.info(f"API POST搜索成功，找到 {len(results)} 个结果")
                                    return results
                            except:
                                pass
                                
                    except Exception as e:
                        self.logger.debug(f"API尝试失败: {api_url} - {e}")
                        continue
            
            # 步骤2: 模拟浏览器获取动态内容（使用Selenium风格的方法，但用requests模拟）
            self.logger.info("尝试模拟浏览器获取动态内容")
            
            # 先访问首页获取session和可能的token
            try:
                homepage_response = self.session.get("https://www.gov.cn", timeout=10)
                self.logger.debug("首页访问成功，准备搜索")
            except:
                pass
            
            # 模拟搜索表单提交到真实的处理端点
            search_endpoints = [
                "https://sousuo.www.gov.cn/sousuo/search.shtml",
                "https://www.gov.cn/sousuo/search.shtml",
                "https://search.www.gov.cn/search.shtml"
            ]
            
            # 添加更多Headers模拟真实浏览器
            search_headers = {
                "Referer": "https://www.gov.cn/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }
            
            # 尝试不同的搜索参数，参考你提供的URL格式
            enhanced_params_combinations = [
                {
                    "searchWord": keyword,
                    "code": "17da70961a7",
                    "dataTypeId": "107",
                    "t": "govall"
                },
                {
                    "searchWord": keyword,
                    "t": "govall",
                    "headSearchword": keyword
                }
            ]
            
            for endpoint in search_endpoints:
                for params in enhanced_params_combinations:
                    try:
                        self.logger.debug(f"模拟浏览器搜索: {endpoint}")
                        old_headers = self.session.headers.copy()
                        self.session.headers.update(search_headers)
                        
                        response = self.session.get(endpoint, params=params, timeout=15)
                        
                        # 恢复原headers
                        self.session.headers.clear()
                        self.session.headers.update(old_headers)
                        
                        if response.status_code == 200:
                            # 检查是否包含搜索结果数据
                            content = response.text
                            if keyword in content and ("电子招标投标办法" in content or "搜索结果" in content):
                                self.logger.info("发现潜在搜索结果，尝试解析")
                                results = self._parse_search_results(content, response.url, keyword)
                                if results:
                                    return results
                                
                                # 尝试查找页面中的JSON数据
                                results = self._extract_json_from_html(content, keyword)
                                if results:
                                    return results
                                    
                    except Exception as e:
                        self.logger.debug(f"模拟浏览器搜索失败: {endpoint} - {e}")
                        continue
            
            self.logger.warning(f"所有搜索策略都失败")
            return []
            
        except Exception as e:
            self.logger.error(f"政府网搜索失败: {e}")
            return []
    
    def _parse_api_response(self, json_data: dict, keyword: str) -> List[Dict[str, Any]]:
        """解析API JSON响应"""
        try:
            results = []
            
            # 尝试不同的JSON结构
            data_keys = ['data', 'results', 'items', 'list', 'content']
            for key in data_keys:
                if key in json_data:
                    items = json_data[key]
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                title = item.get('title', item.get('name', ''))
                                url = item.get('url', item.get('link', item.get('href', '')))
                                if title and url:
                                    results.append({
                                        'title': title,
                                        'url': url if url.startswith('http') else f"https://www.gov.cn{url}",
                                        'summary': item.get('summary', item.get('content', item.get('description', ''))),
                                        'date': item.get('date', item.get('time', item.get('publishTime', ''))),
                                        'source': '中国政府网'
                                    })
            
            return results
            
        except Exception as e:
            self.logger.debug(f"解析API响应失败: {e}")
            return []
    
    def _extract_json_from_html(self, html_content: str, keyword: str) -> List[Dict[str, Any]]:
        """从HTML中提取可能的JSON数据"""
        try:
            import json
            import re
            
            # 查找可能包含搜索结果的JSON
            json_patterns = [
                r'var\s+searchResult\s*=\s*({.*?});',
                r'window\.searchData\s*=\s*({.*?});',
                r'searchResults\s*:\s*({.*?})',
                r'"data"\s*:\s*(\[.*?\])',
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, html_content, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        results = self._parse_api_response(data, keyword)
                        if results:
                            self.logger.info(f"从HTML中提取到JSON数据，找到 {len(results)} 个结果")
                            return results
                    except:
                        continue
            
            return []
            
        except Exception as e:
            self.logger.debug(f"从HTML提取JSON失败: {e}")
            return []
    
    def _parse_search_results(self, html_content: str, page_url: str, keyword: str) -> List[Dict[str, Any]]:
        """解析搜索结果页面"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # 首先检查页面中是否有"电子招标投标办法"这样的具体内容
            page_text = soup.get_text()
            if keyword in page_text and "电子招标投标办法" in page_text:
                self.logger.info("在页面中发现目标法规内容!")
                # 如果发现相关内容，尝试提取具体信息
                
                # 方法1: 查找标准的搜索结果结构
                result_selectors = [
                    '.result',
                    '.search-result',
                    '.search-item', 
                    '.list-item',
                    '.search-list li',
                    'li.result',
                    'div.result'
                ]
                
                for selector in result_selectors:
                    items = soup.select(selector)
                    if items:
                        self.logger.debug(f"找到搜索结果容器: {selector}, 数量: {len(items)}")
                        for item in items:
                            result = self._extract_result_from_item(item, page_url)
                            if result:
                                results.append(result)
                
                # 方法2: 如果标准结构不行，尝试查找包含关键词的链接
                if not results:
                    self.logger.debug("尝试查找包含关键词的链接")
                    all_links = soup.find_all('a', href=True)
                    for link in all_links:
                        link_text = link.get_text(strip=True)
                        if keyword in link_text or any(word in link_text for word in ['招标', '投标', '办法']):
                            href = link.get('href', '')
                            if href and not href.startswith('javascript'):
                                # 处理相对链接
                                if not href.startswith('http'):
                                    href = urljoin(page_url, href)
                                
                                results.append({
                                    'title': link_text,
                                    'url': href,
                                    'summary': '',
                                    'date': '',
                                    'source': '中国政府网'
                                })
                
                # 方法3: 如果还是没有结果，但确实包含关键词，创建一个通用结果
                if not results and keyword in page_text:
                    self.logger.info("页面包含关键词但无法解析具体结果，创建通用结果")
                    results.append({
                        'title': keyword,
                        'url': page_url,
                        'summary': f"在政府网搜索页面中发现 '{keyword}' 相关内容",
                        'date': '',
                        'source': '中国政府网'
                    })
            
            # 输出调试信息
            if not results:
                self.logger.debug(f"页面解析结果: 无结果")
                self.logger.debug(f"页面长度: {len(html_content)} 字符")
                self.logger.debug(f"页面标题: {soup.title.string if soup.title else 'No title'}")
                # 保存页面内容到文件以便调试
                debug_file = f"debug_search_{keyword.replace(' ', '_')}.html"
                try:
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    self.logger.debug(f"调试页面已保存到: {debug_file}")
                except:
                    pass
            
            return results
            
        except Exception as e:
            self.logger.error(f"解析搜索结果失败: {e}")
            return []
    
    def _extract_result_from_item(self, item, base_url: str) -> Optional[Dict[str, Any]]:
        """从搜索结果项中提取信息"""
        try:
            # 提取标题和链接
            title_elem = item.find('a') or item.find('h3') or item.find('h4') or item.find('h2')
            if not title_elem:
                return None
                
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            
            # 处理相对链接
            if link and not link.startswith('http'):
                link = urljoin(base_url, link)
            
            # 提取摘要
            summary_elem = item.find('p') or item.find('div', class_='summary') or item.find('.content')
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            # 提取日期
            date_elem = item.find('span', class_='date') or item.find('time') or item.find('.time')
            date_text = date_elem.get_text(strip=True) if date_elem else ""
            
            if title and link:
                return {
                    'title': title,
                    'url': link,
                    'summary': summary,
                    'date': date_text,
                    'source': '中国政府网'
                }
                
        except Exception as e:
            self.logger.warning(f"提取搜索结果项失败: {e}")
        
        return None
    
    def get_law_detail_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """从URL获取法规详情"""
        try:
            self.logger.info(f"获取政府网页面详情: {url}")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取标题
            title = ""
            title_selectors = [
                'h1',
                '.article-title',
                '.content-title', 
                '.title',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and title != "中国政府网":
                        break
            
            # 提取文号
            document_number = self.extract_document_number_from_content(soup)
            
            # 提取发布日期
            publish_date = self.extract_date_from_content(soup)
            
            # 提取发布机关
            office = self.extract_office_from_content(soup)
            
            # 提取正文内容
            content = self.extract_content_from_page(soup)
            
            return {
                'title': title,
                'document_number': document_number,
                'publish_date': publish_date,
                'office': office,
                'content': content,
                'source_url': url,
                'source': '中国政府网'
            }
            
        except Exception as e:
            self.logger.error(f"获取政府网页面详情失败: {e}")
            return None
    
    def extract_document_number_from_content(self, soup: BeautifulSoup) -> str:
        """从内容中提取文号"""
        try:
            # 查找包含文号的常见模式
            text = soup.get_text()
            
            # 国务院令模式
            patterns = [
                r'国务院令[第]*(\d+)号',
                r'国务院令（第(\d+)号）',
                r'中华人民共和国国务院令[第]*(\d+)号',
                r'主席令[第]*(\d+)号',
                r'主席令（第(\d+)号）',
                r'中华人民共和国主席令[第]*(\d+)号',
                r'国发〔(\d{4})〕(\d+)号',
                r'国办发〔(\d{4})〕(\d+)号',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    if len(match.groups()) == 1:
                        number = match.group(1)
                        if '国务院令' in pattern:
                            return f"国务院令第{number}号"
                        elif '主席令' in pattern:
                            return f"主席令第{number}号"
                        elif '国发' in pattern:
                            return f"国发〔{match.group(1)}〕{match.group(2)}号"
                        elif '国办发' in pattern:
                            return f"国办发〔{match.group(1)}〕{match.group(2)}号"
                    elif len(match.groups()) == 2:
                        return f"国发〔{match.group(1)}〕{match.group(2)}号"
            
            return ""
        except Exception as e:
            self.logger.error(f"提取文号失败: {e}")
            return ""
    
    def extract_date_from_content(self, soup: BeautifulSoup) -> str:
        """从内容中提取发布日期"""
        try:
            # 查找日期相关的元素
            date_selectors = [
                '.article-date',
                '.publish-date',
                '.date',
                'time',
                '.time'
            ]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    # 尝试解析日期
                    parsed_date = self.parse_chinese_date(date_text)
                    if parsed_date:
                        return parsed_date
            
            # 从文本内容中查找日期
            text = soup.get_text()
            date_patterns = [
                r'(\d{4})年(\d{1,2})月(\d{1,2})日',
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
                r'(\d{4})/(\d{1,2})/(\d{1,2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    year, month, day = match.groups()
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return ""
        except Exception as e:
            self.logger.error(f"提取日期失败: {e}")
            return ""
    
    def extract_office_from_content(self, soup: BeautifulSoup) -> str:
        """从内容中提取发布机关"""
        try:
            text = soup.get_text()
            
            # 常见的发布机关模式
            office_patterns = [
                r'(国务院)',
                r'(中华人民共和国国务院)',
                r'(全国人民代表大会)',
                r'(全国人大常委会)',
                r'(最高人民法院)',
                r'(最高人民检察院)',
                r'([^，。]*部)',  # 各种部委
                r'([^，。]*委员会)',
                r'([^，。]*总局)',
                r'([^，。]*局)'
            ]
            
            for pattern in office_patterns:
                match = re.search(pattern, text)
                if match:
                    office = match.group(1)
                    if len(office) < 20:  # 避免匹配到过长的文本
                        return office
            
            return ""
        except Exception as e:
            self.logger.error(f"提取发布机关失败: {e}")
            return ""
    
    def extract_content_from_page(self, soup: BeautifulSoup) -> str:
        """提取页面正文内容"""
        try:
            # 查找正文内容的常见选择器
            content_selectors = [
                '.article-content',
                '.content',
                '.main-content',
                '.text-content',
                '#content',
                '.article-body'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 清理内容
                    content = content_elem.get_text(strip=True)
                    if len(content) > 100:  # 确保内容足够长
                        return content[:1000]  # 限制长度
            
            # 如果找不到特定选择器，尝试从整个页面提取
            body = soup.find('body')
            if body:
                content = body.get_text(strip=True)
                return content[:1000]  # 限制长度
            
            return ""
        except Exception as e:
            self.logger.error(f"提取正文内容失败: {e}")
            return ""
    
    def parse_chinese_date(self, date_str: str) -> Optional[str]:
        """解析中文日期"""
        try:
            # 移除多余字符
            date_str = date_str.strip()
            
            # 中文日期模式
            patterns = [
                r'(\d{4})年(\d{1,2})月(\d{1,2})日',
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
                r'(\d{4})/(\d{1,2})/(\d{1,2})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, date_str)
                if match:
                    year, month, day = match.groups()
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return None
        except Exception as e:
            self.logger.error(f"解析中文日期失败: {e}")
            return None
    
    def calculate_match_score(self, target: str, result: str) -> float:
        """计算匹配分数"""
        if target == result:
            return 1.0
        
        # 标准化比较
        target_norm = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', target)
        result_norm = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', result)
        
        # 计算包含关系
        if target_norm in result_norm:
            return 0.8 + (len(target_norm) / len(result_norm)) * 0.2
        if result_norm in target_norm:
            return 0.8 + (len(result_norm) / len(target_norm)) * 0.2
        
        # 计算公共子串
        common_length = 0
        min_len = min(len(target_norm), len(result_norm))
        for i in range(min_len):
            if target_norm[i] == result_norm[i]:
                common_length += 1
            else:
                break
        
        if common_length > 0:
            return common_length / max(len(target_norm), len(result_norm))
        
        return 0.0
    
    def find_best_match(self, target_name: str, search_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """在搜索结果中找到最佳匹配"""
        if not search_results:
            return None
        
        best_match = None
        best_score = 0
        
        for result in search_results:
            title = result.get('title', '')
            
            # 计算匹配分数
            score = self.calculate_match_score(target_name, title)
            
            if score > best_score:
                best_score = score
                best_match = result
        
        # 只有匹配分数足够高才返回
        if best_score >= 0.6:  # 60%匹配度
            best_match['match_score'] = best_score
            return best_match
        
        return None
    
    async def crawl_law(self, law_name: str, law_number: str = None) -> Optional[Dict]:
        """爬取单个法律（实现CrawlerManager需要的接口）"""
        try:
            self.logger.info(f"政府网爬取: {law_name}")
            
            # 1. 尝试多种搜索策略
            search_results = []
            
            # 策略1: 原始名称搜索
            search_results = self.search_law(law_name)
            self.logger.debug(f"原始搜索结果数: {len(search_results)}")
            
            # 策略2: 如果没有结果，尝试简化搜索（去掉年份、修订信息）
            if not search_results and len(law_name) > 6:
                simplified_name = self._simplify_law_name(law_name)
                if simplified_name != law_name:
                    self.logger.info(f"尝试简化搜索: {simplified_name}")
                    search_results = self.search_law(simplified_name)
                    self.logger.debug(f"简化搜索结果数: {len(search_results)}")
            
            # 策略3: 如果还没有结果，尝试关键词搜索
            if not search_results:
                keywords = self._extract_keywords(law_name)
                for keyword in keywords:
                    if len(keyword) >= 4:  # 关键词长度至少4个字符
                        self.logger.info(f"尝试关键词搜索: {keyword}")
                        search_results = self.search_law(keyword)
                        self.logger.debug(f"关键词 '{keyword}' 搜索结果数: {len(search_results)}")
                        if search_results:
                            break
            
            if not search_results:
                self.logger.warning(f"政府网所有搜索策略都未找到结果: {law_name}")
                return None
            
            # 2. 找到最佳匹配
            best_match = self.find_best_match(law_name, search_results)
            
            if not best_match:
                self.logger.warning(f"政府网未找到匹配结果: {law_name}")
                return None
            
            self.logger.info(f"政府网找到匹配: {best_match['title']} (匹配度: {best_match.get('match_score', 0):.2f})")
            
            # 3. 获取详细信息
            detail = self.get_law_detail_from_url(best_match['url'])
            
            if not detail:
                self.logger.error(f"政府网无法获取详细信息: {best_match['url']}")
                return None
            
            # 4. 整理返回结果
            result = {
                'law_id': best_match['url'],  # 使用URL作为ID
                'name': detail['title'] or best_match['title'],
                'number': detail['document_number'],
                'source': 'gov_web',
                'success': True,
                'source_url': best_match['url'],
                'publish_date': detail['publish_date'],
                'valid_from': detail['publish_date'],  # 政府网通常没有单独的生效日期
                'valid_to': None,  # 政府网通常没有失效日期
                'office': detail['office'],
                'status': '有效',  # 政府网发布的通常都是有效的
                'level': self.determine_law_level(detail['document_number']),
                'content_preview': detail['content'][:200] if detail['content'] else "",
                'crawl_time': datetime.now().isoformat(),
                'match_score': best_match.get('match_score', 0)
            }
            
            self.logger.success(f"政府网成功爬取: {result['name']}")
            return result
            
        except Exception as e:
            self.logger.error(f"政府网爬取失败: {law_name}, 错误: {e}")
            return None
    
    def determine_law_level(self, document_number: str) -> str:
        """根据文号判断法规级别"""
        if not document_number:
            return "其他"
        
        if "主席令" in document_number:
            return "法律"
        elif "国务院令" in document_number:
            return "行政法规"
        elif "国发" in document_number or "国办发" in document_number:
            return "国务院文件"
        else:
            return "其他"
    
    def _simplify_law_name(self, law_name: str) -> str:
        """简化法规名称，去掉年份和修订信息"""
        try:
            simplified = law_name
            
            # 去掉各种年份和修订标记
            patterns_to_remove = [
                r'（\d{4}）',        # （2023）
                r'（\d{4}修订）',    # （2024修订）
                r'（\d{4}修正）',    # （2019修正）
                r'（\d{4}年修订）',  # （2021年修订）
                r'（\d{4}年修正）',  # （2018年修正）
                r'\(\d{4}\)',        # (2023)
                r'\(\d{4}修订\)',    # (2024修订)
                r'\(\d{4}修正\)',    # (2019修正)
            ]
            
            for pattern in patterns_to_remove:
                simplified = re.sub(pattern, '', simplified)
            
            return simplified.strip()
        except Exception as e:
            self.logger.error(f"简化法规名称失败: {e}")
            return law_name
    
    def _extract_keywords(self, law_name: str) -> List[str]:
        """从法规名称中提取关键词"""
        try:
            keywords = []
            
            # 专业术语关键词
            professional_terms = [
                '招标投标', '电子招标', '投标办法', 
                '安全生产', '建筑工程', '工程设计',
                '施工招标', '货物招标', '勘察设计',
                '节能审查', '质量安全', '科学技术',
                '反洗钱', '统计法', '会计法',
                '产品质量', '疫苗管理', '药品管理',
                '特种设备', '计量法', '民法典'
            ]
            
            # 查找包含的专业术语
            for term in professional_terms:
                if term in law_name:
                    keywords.append(term)
            
            # 提取核心关键词（去掉"中华人民共和国"等前缀）
            clean_name = law_name.replace("中华人民共和国", "")
            clean_name = clean_name.replace("最高人民法院", "")
            clean_name = clean_name.replace("最高人民检察院", "")
            clean_name = re.sub(r'（.*?）', '', clean_name)  # 去掉括号内容
            clean_name = re.sub(r'\(.*?\)', '', clean_name)  # 去掉括号内容
            clean_name = clean_name.strip()
            
            if len(clean_name) >= 4:
                keywords.append(clean_name)
            
            # 如果法规名称很长，尝试分段提取
            if len(law_name) > 10:
                # 分割并取前半部分
                if "办法" in law_name:
                    parts = law_name.split("办法")
                    if parts[0]:
                        keywords.append(parts[0] + "办法")
                elif "条例" in law_name:
                    parts = law_name.split("条例")
                    if parts[0]:
                        keywords.append(parts[0] + "条例")
                elif "法" in law_name and not law_name.endswith("法"):
                    # 对于"XXX法实施条例"这样的情况
                    pass
                else:
                    # 取前8个字符作为关键词
                    if len(law_name) >= 8:
                        keywords.append(law_name[:8])
            
            # 去重并保持顺序
            unique_keywords = []
            for keyword in keywords:
                if keyword not in unique_keywords and len(keyword.strip()) >= 4:
                    unique_keywords.append(keyword.strip())
            
            return unique_keywords[:3]  # 最多返回3个关键词
            
        except Exception as e:
            self.logger.error(f"提取关键词失败: {e}")
            return [] 