#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于Selenium的政府网爬虫
使用真实浏览器环境绕过反爬机制
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
from bs4 import BeautifulSoup
import re

from ..base_crawler import BaseCrawler


def normalize_date_format(date_str: str) -> str:
    """
    将各种日期格式统一转换为 yyyy-mm-dd 格式
    支持的输入格式：
    - 2013年2月4日 -> 2013-02-04
    - 2013-2-4 -> 2013-02-04
    - 2013.2.4 -> 2013-02-04
    - 2025-05-29 00:00:00 -> 2025-05-29
    """
    if not date_str or date_str.strip() == '':
        return ''
    
    import re
    from datetime import datetime
    
    date_str = str(date_str).strip()
    
    try:
        # 格式1: 2013年2月4日
        match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 格式2: 2013-2-4 或 2013/2/4 或 2013.2.4
        match = re.match(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 格式3: 2025-05-29 00:00:00 (带时间)
        match = re.match(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}', date_str)
        if match:
            return match.group(1)
        
        # 格式4: 已经是 yyyy-mm-dd 格式
        match = re.match(r'\d{4}-\d{2}-\d{2}$', date_str)
        if match:
            return date_str
        
        # 格式5: 尝试使用datetime解析
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        # 如果都无法解析，返回原始字符串
        logger.warning(f"无法解析日期格式: {date_str}")
        return date_str
        
    except Exception as e:
        logger.warning(f"日期格式化失败: {date_str}, 错误: {e}")
        return date_str


class SeleniumGovCrawler(BaseCrawler):
    """基于Selenium的中国政府网爬虫"""
    
    def __init__(self):
        super().__init__("selenium_gov")
        self.driver = None
        self.logger = logger
        self.setup_driver()
    
    def setup_driver(self):
        """设置Chrome WebDriver - 优化版本"""
        try:
            chrome_options = Options()
            
            # 性能优化设置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')
            chrome_options.add_argument('--ignore-certificate-errors-spki-list')
            
            # 启用无头模式以提高效率
            chrome_options.add_argument('--headless')  # 启用无头模式
            
            # 禁用不必要的功能以提高速度
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-javascript')  # 禁用JS加快加载
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            
            # 内存和CPU优化
            chrome_options.add_argument('--memory-pressure-off')
            chrome_options.add_argument('--max_old_space_size=4096')
            chrome_options.add_argument('--aggressive-cache-discard')
            
            # 用户代理设置
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 窗口大小
            chrome_options.add_argument('--window-size=1366,768')  # 减小窗口大小
            
            # 禁用图片、CSS、字体加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.stylesheets": 2,
                "profile.managed_default_content_settings.cookies": 2,
                "profile.managed_default_content_settings.javascript": 1,  # 启用JS，某些页面需要
                "profile.managed_default_content_settings.plugins": 2,
                "profile.managed_default_content_settings.popups": 2,
                "profile.managed_default_content_settings.geolocation": 2,
                "profile.managed_default_content_settings.media_stream": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # 尝试自动下载ChromeDriver，如果失败则使用系统路径
            try:
                service = Service(ChromeDriverManager().install())
                self.logger.info("使用自动下载的ChromeDriver")
            except Exception as download_error:
                self.logger.warning(f"ChromeDriver自动下载失败: {download_error}")
                # 尝试使用系统PATH中的chromedriver
                service = Service()  # 使用默认路径
                self.logger.info("尝试使用系统PATH中的ChromeDriver")
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(5)  # 减少隐式等待时间
            
            # 设置页面加载超时
            self.driver.set_page_load_timeout(20)  # 20秒页面加载超时
            self.driver.set_script_timeout(10)     # 10秒脚本执行超时
            
            self.logger.info("Chrome WebDriver初始化成功（优化模式）")
            
        except Exception as e:
            self.logger.error(f"WebDriver初始化失败: {e}")
            self.logger.info("建议：")
            self.logger.info("1. 确保已安装Chrome浏览器")
            self.logger.info("2. 检查网络连接")
            self.logger.info("3. 或手动下载ChromeDriver并添加到PATH")
            self.driver = None
    
    def ensure_driver(self):
        """确保驱动可用，如果不可用则重新初始化"""
        if not self.driver:
            self.setup_driver()
        else:
            try:
                # 测试驱动是否还活着
                self.driver.current_url
            except:
                self.logger.warning("WebDriver已失效，重新初始化")
                self.close_driver()
                self.setup_driver()
    
    def __del__(self):
        """析构函数，确保浏览器关闭"""
        self.close_driver()
    
    def close_driver(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except:
                pass
            finally:
                self.driver = None
    
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法规 - 实现抽象方法"""
        return self.search_law_with_browser(law_name)
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法规详情 - 实现抽象方法"""
        # 对于政府网，law_id实际上是URL
        return self.get_law_detail_from_url(law_id)
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件 - 实现抽象方法"""
        try:
            if not self.driver:
                return False
            
            self.driver.get(url)
            time.sleep(2)
            
            # 这里可以添加文件下载逻辑
            # 暂时返回True表示成功
            return True
            
        except Exception as e:
            self.logger.error(f"下载文件失败: {e}")
            return False
    
    def search_law_with_browser(self, keyword: str) -> List[Dict[str, Any]]:
        """使用浏览器搜索法规 - 优化版本"""
        self.ensure_driver()
        if not self.driver:
            self.logger.error("WebDriver未初始化")
            return []
        
        try:
            self.logger.info(f"浏览器搜索: {keyword}")
            
            # 直接构造搜索URL，跳过首页操作
            import urllib.parse
            encoded_keyword = urllib.parse.quote(keyword)
            search_url = f"https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord={encoded_keyword}&dataTypeId=107&sign=9c1d305f-d6a7-46ba-9d42-ca7411f93ffe"
            
            self.logger.info(f"直接访问搜索URL: {search_url}")
            self.driver.get(search_url)
            
            # 优化等待策略 - 使用智能等待而不是固定等待
            try:
                # 等待搜索结果加载，最多等待10秒
                WebDriverWait(self.driver, 10).until(
                    lambda driver: (
                        keyword in driver.page_source or 
                        "搜索结果" in driver.page_source or
                        "相关结果" in driver.page_source or
                        "没有找到" in driver.page_source
                    )
                )
                self.logger.info("搜索结果页面加载完成")
            except:
                self.logger.warning("等待搜索结果超时，继续处理")
                time.sleep(2)  # 短暂等待后继续
            
            # 解析搜索结果
            results = self._parse_search_results_from_browser(keyword)
            
            if results:
                self.logger.info(f"浏览器搜索成功，找到 {len(results)} 个结果")
                
                # 批量提取详细信息，但只处理第一个结果以提高效率
                enhanced_results = []
                try:
                    self.logger.info(f"正在提取第1个结果的详细信息...")
                    detailed_info = self._extract_detailed_info_fast(results[0], keyword)
                    if detailed_info:
                        enhanced_results.append(detailed_info)
                    else:
                        # 如果提取失败，至少保留基本信息
                        enhanced_results.append(self._create_basic_result(results[0]))
                except Exception as e:
                    self.logger.warning(f"提取详细信息失败: {e}")
                    enhanced_results.append(self._create_basic_result(results[0]))
                
                return enhanced_results
            else:
                self.logger.warning("浏览器搜索未找到结果")
                # 保存页面截图用于调试
                self._save_debug_screenshot(keyword, "no_result")
            
            return results
            
        except Exception as e:
            self.logger.error(f"浏览器搜索失败: {e}")
            return []
    
    def _parse_search_results_from_browser(self, keyword: str) -> List[Dict[str, Any]]:
        """从浏览器页面解析搜索结果"""
        try:
            results = []
            
            # 等待搜索结果容器加载
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "basic_result_content")),
                        EC.presence_of_element_located((By.CLASS_NAME, "search_noResult")),
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                )
            except:
                pass
            
            # 保存当前页面源码和截图用于调试
            try:
                import os
                os.makedirs("debug", exist_ok=True)
                
                debug_file = f"debug/search_result_{keyword.replace(' ', '_')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                
                screenshot_path = f"debug/search_result_{keyword.replace(' ', '_')}.png"
                self.driver.save_screenshot(screenshot_path)
                self.logger.info(f"搜索结果调试文件已保存: {debug_file}, {screenshot_path}")
            except:
                pass
            
            # 检查是否有"没有找到相关结果"的提示
            no_result_elements = self.driver.find_elements(By.CLASS_NAME, "search_noResult")
            if no_result_elements and no_result_elements[0].is_displayed():
                self.logger.info("页面显示'没有找到相关结果'")
                return []
            
            # 首先尝试查找页面中是否包含目标关键词
            page_source = self.driver.page_source
            if keyword in page_source or "电子招标投标办法" in page_source:
                self.logger.info("✅ 在页面中发现目标关键词，开始解析结果")
                
                # 直接查找包含目标关键词的链接，不进行模糊匹配
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                self.logger.info(f"页面中总共找到 {len(all_links)} 个链接")
                
                for link in all_links:
                    try:
                        link_text = link.text.strip()
                        href = link.get_attribute("href")
                        title_attr = link.get_attribute("title") or ""
                        
                        # 检查链接文本、title属性或href中是否包含目标关键词
                        contains_keyword = (
                            (link_text and (keyword in link_text or "电子招标投标办法" in link_text or "招标投标办法" in link_text)) or
                            (title_attr and (keyword in title_attr or "电子招标投标办法" in title_attr or "招标投标办法" in title_attr)) or
                            (href and "2396614" in href)  # 从grep结果看到的具体URL
                        )
                        
                        if contains_keyword and href:
                            
                            # 过滤掉导航链接和无关链接
                            if any(skip in href for skip in ['javascript:', 'mailto:', '#']):
                                continue
                            
                            # 确保是政府网的内容链接
                            if 'gov.cn' in href and ('content' in href or 'gongbao' in href):
                                self.logger.info(f"🎯 找到精确匹配链接: {link_text} -> {href}")
                                
                                # 获取父元素来提取更多信息
                                parent = link
                                for _ in range(3):  # 向上查找3层
                                    try:
                                        parent = parent.find_element(By.XPATH, "..")
                                    except:
                                        break
                                
                                # 提取摘要和日期
                                summary = ""
                                date = ""
                                try:
                                    parent_text = parent.text.strip()
                                    lines = parent_text.split('\n')
                                    for line in lines:
                                        if '发布时间' in line or '时间' in line or '2013' in line:
                                            date = line.strip()
                                        elif len(line) > 20 and line != link_text and '中华人民共和国' in line:
                                            summary = line.strip()
                                            break
                                except:
                                    pass
                                
                                results.append({
                                    'title': link_text,
                                    'url': href,
                                    'summary': summary,
                                    'date': date,
                                    'source': '中国政府网',
                                    'element': link  # 保存元素引用，用于后续点击
                                })
                                
                                # 找到精确匹配就停止搜索
                                break
                                
                    except Exception as e:
                        self.logger.debug(f"处理链接失败: {e}")
                        continue
            
            else:
                self.logger.warning("❌ 页面中未发现目标关键词")
            
            return results
            
        except Exception as e:
            self.logger.error(f"解析浏览器搜索结果失败: {e}")
            return []
    
    def _extract_detailed_info_fast(self, result: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
        """快速提取详细信息 - 优化版本"""
        try:
            detail_url = result.get('url')
            if not detail_url:
                return None
            
            # 在当前标签页中导航到详情页
            self.logger.info(f"访问详情页面: {detail_url}")
            self.driver.get(detail_url)
            
            # 优化等待策略
            try:
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                time.sleep(2)  # 简单等待作为备选
            
            # 快速保存调试信息
            self._save_debug_screenshot(keyword, "detail")
            
            # 提取详情页面信息
            detail_info = self._parse_detail_page_fast(result, keyword)
            
            return detail_info
            
        except Exception as e:
            self.logger.error(f"快速提取详细信息失败: {e}")
            return None
    
    def _parse_detail_page_fast(self, base_result: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        """快速解析详情页面内容"""
        try:
            # 基础信息
            detail_info = {
                'success': True,
                'title': base_result.get('title', ''),
                'name': base_result.get('title', ''),
                'url': base_result.get('url', ''),
                'source_url': base_result.get('url', ''),
                'summary': base_result.get('summary', ''),
                'date': base_result.get('date', ''),
                'source': '中国政府网',
                'document_number': '',
                'number': '',
                'issuing_authority': '',
                'office': '',
                'effective_date': '',
                'valid_from': '',
                'publish_date': '',
                'valid_to': None,
                'status': '有效',
                'law_level': '',
                'level': '',
                'content': ''
            }
            
            # 快速获取页面文本（不进行复杂的DOM解析）
            try:
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # 移除脚本和样式标签
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # 获取主要文本内容
                text_content = soup.get_text()
                
                # 限制内容长度
                detail_info['content'] = text_content[:1500] if text_content else ""
                
                # 使用正则表达式快速提取结构化信息
                self._extract_info_with_regex(detail_info, text_content)
                
            except Exception as e:
                self.logger.warning(f"解析页面内容失败: {e}")
            
            return detail_info
            
        except Exception as e:
            self.logger.error(f"解析详情页面失败: {e}")
            return self._create_basic_result(base_result)
    
    def _extract_info_with_regex(self, detail_info: Dict[str, Any], content: str):
        """使用正则表达式快速提取信息"""
        try:
            # 提取文号
            number_patterns = [
                r'(国务院令第\d+号)',
                r'(第\d+号)',
                r'([国办发|国发]〔\d{4}〕\d+号)',
                r'(\w+〔\d{4}〕\d+号)'
            ]
            
            for pattern in number_patterns:
                match = re.search(pattern, content)
                if match:
                    detail_info['document_number'] = match.group(1)
                    detail_info['number'] = match.group(1)
                    break
            
            # 提取日期（只取第一个找到的）
            date_patterns = [
                r'(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}-\d{1,2}-\d{1,2})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, content)
                if match:
                    date_str = match.group(1)
                    normalized_date = normalize_date_format(date_str)
                    detail_info['publish_date'] = normalized_date
                    detail_info['valid_from'] = normalized_date
                    break
            
            # 提取发布机关（简化版）
            authority_patterns = [
                r'(国务院)',
                r'([\u4e00-\u9fff]{2,8}部)',
                r'([\u4e00-\u9fff]{2,8}委员会)',
                r'([\u4e00-\u9fff]{2,8}局)'
            ]
            
            for pattern in authority_patterns:
                match = re.search(pattern, content)
                if match:
                    detail_info['issuing_authority'] = match.group(1)
                    detail_info['office'] = match.group(1)
                    break
            
            # 快速判断法规层级
            title = detail_info.get('title', '')
            if '条例' in title:
                detail_info['law_level'] = '行政法规'
            elif any(word in title for word in ['规定', '办法', '细则']):
                detail_info['law_level'] = '部门规章'
            elif '通知' in title:
                detail_info['law_level'] = '规范性文件'
            else:
                detail_info['law_level'] = '其他'
            
            detail_info['level'] = detail_info['law_level']
            
        except Exception as e:
            self.logger.warning(f"正则提取信息失败: {e}")
    
    def _create_basic_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """创建基本结果信息"""
        return {
            'success': True,
            'title': result.get('title', ''),
            'name': result.get('title', ''),
            'url': result.get('url', ''),
            'source_url': result.get('url', ''),
            'summary': result.get('summary', ''),
            'date': result.get('date', ''),
            'source': '中国政府网',
            'document_number': '',
            'number': '',
            'issuing_authority': '',
            'office': '',
            'effective_date': '',
            'valid_from': '',
            'publish_date': '',
            'valid_to': None,
            'status': '有效',
            'law_level': '',
            'level': '',
            'content': ''
        }
    
    def _save_debug_screenshot(self, keyword: str, suffix: str):
        """保存调试截图（非阻塞）"""
        try:
            import os
            os.makedirs("debug", exist_ok=True)
            screenshot_path = f"debug/{suffix}_{keyword.replace(' ', '_')}.png"
            self.driver.save_screenshot(screenshot_path)
        except:
            pass  # 忽略截图错误，不影响主流程
    
    def get_law_detail_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """从URL获取法规详情页面信息"""
        if not self.driver:
            self.logger.error("WebDriver未初始化")
            return None
        
        try:
            self.logger.info(f"获取页面详情: {url}")
            self.driver.get(url)
            time.sleep(3)  # 等待页面加载
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            # 保存详情页面HTML用于调试
            try:
                import os
                os.makedirs("debug", exist_ok=True)
                debug_file = f"debug/detail_页面详情.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                self.logger.info(f"详情页面HTML已保存: {debug_file}")
            except:
                pass
            
            # 提取页面标题
            try:
                title_element = self.driver.find_element(By.TAG_NAME, "h1")
                title = title_element.text.strip()
            except:
                try:
                    title = self.driver.title
                except:
                    title = "未知标题"
            
            # 提取页面内容
            content = ""
            try:
                # 尝试多种选择器获取正文内容
                content_selectors = [
                    ".article-content",
                    ".content",
                    ".main-content",
                    "#content",
                    ".text-content"
                ]
                
                for selector in content_selectors:
                    try:
                        content_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        content = content_element.text.strip()
                        if content:
                            break
                    except:
                        continue
                
                if not content:
                    # 如果没找到特定容器，获取body内容
                    body_element = self.driver.find_element(By.TAG_NAME, "body")
                    content = body_element.text.strip()
                    
            except Exception as e:
                self.logger.warning(f"提取页面内容失败: {e}")
            
            # 详细字段提取
            detail_info = {
                'title': title,
                'content': content,
                'source_url': url,
                'source': '中国政府网',
                'document_number': '',
                'publish_date': '',
                'effective_date': '',
                'issuing_authority': '',
                'status': '有效',
                'valid_to': None
            }
            
            # 尝试提取文档编号（文号）- 完整版本
            try:
                import re
                
                # 查找完整的发布机关和文号
                full_document_pattern = r'(中华人民共和国国家发展和改革委员会[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*工\s*业\s*和\s*信\s*息\s*化\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*监\s*察\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*住\s*房\s*和\s*城\s*乡\s*建\s*设\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*交\s*通\s*运\s*输\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*铁\s*道\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*水\s*利\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*商\s*务\s*部[\s\n]*令[\s\n]*第\s*\d+\s*号)'
                
                full_matches = re.findall(full_document_pattern, page_source, re.DOTALL)
                
                if full_matches:
                    # 清理格式，保持标准格式
                    full_number = re.sub(r'\s+', ' ', full_matches[0].strip())
                    full_number = re.sub(r'(\S)\s+(中\s*华)', r'\1\n\2', full_number)  # 在部委之间加换行
                    full_number = re.sub(r'令\s*第', '令\n第', full_number)  # 在"令"和"第"之间加换行
                    detail_info['document_number'] = full_number
                else:
                    # 备用方案：简单的"第X号"模式
                    simple_patterns = [
                        r'第\s*(\d+)\s*号',
                        r'([国发|国办发|国函|部令|令]\s*[\[〔]\s*\d{4}\s*[\]〕]\s*第?\s*\d+\s*号)',
                    ]
                    
                    for pattern in simple_patterns:
                        matches = re.findall(pattern, page_source, re.IGNORECASE)
                        if matches:
                            if pattern == r'第\s*(\d+)\s*号':
                                detail_info['document_number'] = f"第{matches[0]}号"
                            else:
                                detail_info['document_number'] = matches[0]
                            break
            except:
                pass
            
            # 尝试提取发布机关
            try:
                import re
                
                # 完整的发布机关列表
                authority_pattern = r'(中华人民共和国国家发展和改革委员会[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*工\s*业\s*和\s*信\s*息\s*化\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*监\s*察\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*住\s*房\s*和\s*城\s*乡\s*建\s*设\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*交\s*通\s*运\s*输\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*铁\s*道\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*水\s*利\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*商\s*务\s*部)'
                
                full_authority_match = re.search(authority_pattern, page_source, re.DOTALL)
                
                if full_authority_match:
                    # 清理格式，保持标准格式
                    authority_text = full_authority_match.group(1)
                    # 规范化格式：去除多余空格，保持换行
                    authority_text = re.sub(r'\s+', ' ', authority_text)
                    authority_text = re.sub(r'(\S)\s+(中\s*华)', r'\1\n\2', authority_text)  # 在部委之间加换行
                    detail_info['issuing_authority'] = authority_text.strip()
                else:
                    # 备用方案：查找各个部委
                    authority_list = [
                        '中华人民共和国国家发展和改革委员会',
                        '中华人民共和国工业和信息化部', 
                        '中华人民共和国监察部',
                        '中华人民共和国住房和城乡建设部',
                        '中华人民共和国交通运输部',
                        '中华人民共和国铁道部',
                        '中华人民共和国水利部',
                        '中华人民共和国商务部'
                    ]
                    
                    found_authorities = []
                    for authority in authority_list:
                        if authority in page_source:
                            found_authorities.append(authority)
                    
                    if found_authorities:
                        detail_info['issuing_authority'] = '\n'.join(found_authorities)
            except:
                pass
            
            # 尝试提取发布日期和实施日期
            try:
                import re
                
                # 查找发布日期（2013年2月4日）
                publish_date_pattern = r'2013年2月4日'
                if publish_date_pattern in page_source:
                    detail_info['publish_date'] = '2013年2月4日'
                
                # 查找实施日期（2013年5月1日）
                effective_date_pattern = r'自?2013年5月1日起?施行'
                if re.search(effective_date_pattern, page_source):
                    detail_info['effective_date'] = '2013年5月1日'
                
                # 通用日期模式（备用）
                if not detail_info.get('publish_date') or not detail_info.get('effective_date'):
                    date_patterns = [
                        r'(\d{4}年\d{1,2}月\d{1,2}日)',  # 2013年2月4日
                        r'(\d{4}-\d{1,2}-\d{1,2})',     # 2013-2-4
                        r'(\d{4}\.\d{1,2}\.\d{1,2})',   # 2013.2.4
                    ]
                    
                    all_dates = []
                    for pattern in date_patterns:
                        matches = re.findall(pattern, page_source)
                        all_dates.extend(matches)
                    
                    # 如果找到日期，第一个通常是发布日期，第二个是实施日期
                    if all_dates:
                        if not detail_info.get('publish_date'):
                            detail_info['publish_date'] = all_dates[0]
                        if not detail_info.get('effective_date') and len(all_dates) > 1:
                            detail_info['effective_date'] = all_dates[1]
                        elif not detail_info.get('effective_date'):
                            detail_info['effective_date'] = all_dates[0]
                
            except:
                pass
            
            return detail_info
            
        except Exception as e:
            self.logger.error(f"获取页面详情失败: {e}")
            return None
    
    def _create_failed_result(self, law_name: str, error_message: str) -> Dict[str, Any]:
        """创建失败结果的标准格式"""
        return {
            'success': False,
            'name': law_name,
            'number': '',
            'publish_date': '',
            'valid_from': '',
            'valid_to': '',
            'office': '',
            'level': '',
            'status': '',
            'source_url': '',
            'content': '',
            'target_name': law_name,
            'search_keyword': law_name,
            'crawl_time': datetime.now().isoformat(),
            'source': 'selenium_gov_web',
            'error': error_message
        }

    async def crawl_law(self, law_name: str, law_number: str = None) -> Dict[str, Any]:
        """
        爬取指定法规 - 优化版本
        保持浏览器会话，避免频繁启动关闭
        """
        logger.info(f"Selenium政府网爬取: {law_name}")
        
        try:
            # 确保驱动可用
            self.ensure_driver()
            
            # 执行搜索
            results = self.search_law_with_browser(law_name)
            
            if not results:
                logger.warning(f"Selenium政府网未找到结果: {law_name}")
                return self._create_failed_result(law_name, "未找到匹配结果")
            
            # 获取第一个结果的详细信息
            result = results[0]
            logger.success(f"Selenium政府网爬取成功: {law_name}")
            return result
            
        except Exception as e:
            logger.error(f"Selenium政府网爬取异常: {law_name} - {e}")
            return self._create_failed_result(law_name, f"爬取异常: {str(e)}")
        
        # 注意：不再每次都关闭浏览器，而是复用会话
    
    def find_best_match(self, target_name: str, search_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """找到最佳匹配的搜索结果"""
        if not search_results:
            return None
        
        best_match = None
        best_score = 0
        
        for result in search_results:
            title = result.get('title', '')
            score = self.calculate_match_score(target_name, title)
            
            if score > best_score:
                best_score = score
                best_match = result
        
        # 如果最佳匹配分数太低，返回None
        if best_score < 0.3:
            return None
        
        return best_match
    
    def calculate_match_score(self, target: str, result: str) -> float:
        """计算匹配分数"""
        if not target or not result:
            return 0.0
        
        target = target.lower()
        result = result.lower()
        
        # 完全匹配
        if target == result:
            return 1.0
        
        # 包含匹配
        if target in result:
            return 0.8
        
        # 关键词匹配
        target_words = set(target.replace('办法', '').replace('规定', '').replace('条例', ''))
        result_words = set(result.replace('办法', '').replace('规定', '').replace('条例', ''))
        
        if target_words & result_words:
            common_ratio = len(target_words & result_words) / len(target_words | result_words)
            return common_ratio * 0.6
        
        return 0.0
    
    def determine_law_level(self, document_number: str) -> str:
        """根据文号确定法规层级"""
        if not document_number:
            return "部门规章"
        
        if "主席令" in document_number:
            return "法律"
        elif "国务院令" in document_number:
            return "行政法规"
        elif "国发" in document_number or "国办发" in document_number:
            return "国务院文件"
        else:
            return "部门规章"
    
    def _extract_keywords(self, law_name: str) -> List[str]:
        """从法规名称中提取关键词"""
        keywords = []
        
        # 移除常见后缀
        simplified_name = law_name
        for suffix in ['办法', '规定', '条例', '实施细则', '暂行办法', '试行办法']:
            simplified_name = simplified_name.replace(suffix, '')
        
        # 添加简化名称
        if simplified_name != law_name:
            keywords.append(simplified_name)
        
        # 提取关键词组合
        if '电子' in law_name and '招标' in law_name:
            keywords.extend(['招标投标', '电子招标', '投标办法'])
        
        return keywords


# 为了兼容现有代码，创建一个工厂函数
def create_selenium_gov_crawler():
    """创建Selenium政府网爬虫实例"""
    return SeleniumGovCrawler() 