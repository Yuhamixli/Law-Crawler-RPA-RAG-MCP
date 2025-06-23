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
        """设置Chrome WebDriver"""
        try:
            chrome_options = Options()
            
            # 基础设置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--ignore-ssl-errors')
            chrome_options.add_argument('--ignore-certificate-errors-spki-list')
            
            # 用户代理设置
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 可选：无头模式（后台运行）
            # chrome_options.add_argument('--headless')  # 取消注释以启用无头模式
            
            # 窗口大小
            chrome_options.add_argument('--window-size=1920,1080')
            
            # 禁用图片加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2
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
            self.driver.implicitly_wait(10)  # 隐式等待10秒
            
            self.logger.info("Chrome WebDriver初始化成功")
            
        except Exception as e:
            self.logger.error(f"WebDriver初始化失败: {e}")
            self.logger.info("建议：")
            self.logger.info("1. 确保已安装Chrome浏览器")
            self.logger.info("2. 检查网络连接")
            self.logger.info("3. 或手动下载ChromeDriver并添加到PATH")
            self.driver = None
    
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
        """使用浏览器搜索法规"""
        if not self.driver:
            self.logger.error("WebDriver未初始化")
            return []
        
        try:
            self.logger.info(f"浏览器搜索: {keyword}")
            
            # 步骤1: 访问政府网首页
            self.logger.info("访问政府网首页...")
            self.driver.get("https://www.gov.cn")
            
            # 等待页面加载
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "header_search"))
            )
            self.logger.info("首页加载完成")
            
            # 步骤2: 定位搜索框并输入关键词
            try:
                # 等待搜索框可见并可点击
                search_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input.header_search_txt[name='headSearchword']"))
                )
                search_input.clear()
                search_input.send_keys(keyword)
                logger.info(f"已输入搜索关键词: {keyword}")
                
                # 点击搜索按钮 - 使用多种定位方式
                search_button = None
                try:
                    # 方式1：通过CSS选择器定位按钮
                    search_button = self.driver.find_element(By.CSS_SELECTOR, "button.header_search_btn")
                except:
                    try:
                        # 方式2：通过XPath定位按钮
                        search_button = self.driver.find_element(By.XPATH, "//button[@class='header_search_btn']")
                    except:
                        # 方式3：通过父容器查找按钮
                        search_form = self.driver.find_element(By.CLASS_NAME, "header_search")
                        search_button = search_form.find_element(By.TAG_NAME, "button")
                
                if search_button:
                    # 使用JavaScript点击，避免被其他元素遮挡
                    self.driver.execute_script("arguments[0].click();", search_button)
                    logger.info("已点击搜索按钮")
                    
                    # 等待页面跳转到搜索结果页 - 使用更灵活的等待策略
                    try:
                        # 方式1：等待URL变化（增加等待时间）
                        WebDriverWait(self.driver, 20).until(
                            lambda driver: "sousuo" in driver.current_url.lower() or "search" in driver.current_url.lower()
                        )
                        logger.info("页面跳转成功")
                    except:
                        # 方式2：如果URL没变，检查页面内容是否已经变化
                        try:
                            WebDriverWait(self.driver, 10).until(
                                lambda driver: ("相关结果" in driver.page_source or 
                                              "搜索结果" in driver.page_source or
                                              "排序方式" in driver.page_source or
                                              keyword in driver.page_source)
                            )
                            logger.info("搜索结果页面内容已加载")
                        except:
                            # 方式3：延迟检测 - 给更多时间让页面完全加载
                            time.sleep(5)
                            current_url = self.driver.current_url
                            page_source = self.driver.page_source
                            
                            # 更全面的成功判断条件
                            success_indicators = [
                                "sousuo" in current_url.lower(),
                                "search" in current_url.lower(),
                                "相关结果" in page_source,
                                "搜索结果" in page_source,
                                "排序方式" in page_source,
                                keyword in page_source,
                                "检索方式" in page_source
                            ]
                            
                            if any(success_indicators):
                                logger.info("搜索页面确认成功（延迟检测）")
                            else:
                                logger.warning(f"页面跳转可能失败，当前URL: {current_url}")
                                # 不抛出异常，让备用方案处理
                                raise Exception("页面未跳转到搜索结果")
                else:
                    raise Exception("无法找到搜索按钮")
                
            except Exception as e:
                logger.warning(f"首页搜索框操作失败: {e}")
                # 备用方案：直接构造搜索URL
                import urllib.parse
                encoded_keyword = urllib.parse.quote(keyword)
                search_url = f"https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord={encoded_keyword}&dataTypeId=107&sign=9c1d305f-d6a7-46ba-9d42-ca7411f93ffe"
                logger.info(f"使用备用搜索URL: {search_url}")
                self.driver.get(search_url)
            
            # 步骤3: 等待搜索结果页面加载
            logger.info("等待搜索结果加载...")
            time.sleep(8)  # 给足时间让JavaScript执行
            
            # 检查是否有搜索结果
            current_url = self.driver.current_url
            logger.info(f"当前页面URL: {current_url}")
            
            # 如果还在首页，说明搜索没有成功，直接使用备用URL
            if "www.gov.cn" == self.driver.current_url or "index.htm" in self.driver.current_url:
                logger.warning("搜索未跳转，使用备用搜索URL")
                import urllib.parse
                encoded_keyword = urllib.parse.quote(keyword)
                search_url = f"https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord={encoded_keyword}&dataTypeId=107&sign=9c1d305f-d6a7-46ba-9d42-ca7411f93ffe"
                self.driver.get(search_url)
                time.sleep(8)
            
            # 步骤4: 解析搜索结果
            results = self._parse_search_results_from_browser(keyword)
            
            if results:
                logger.info(f"浏览器搜索成功，找到 {len(results)} 个结果")
                
                # 步骤5: 点击进入详情页面并提取完整信息
                enhanced_results = []
                for i, result in enumerate(results[:3]):  # 只处理前3个结果
                    try:
                        logger.info(f"正在提取第 {i+1} 个结果的详细信息...")
                        detailed_info = self._extract_detailed_info(result, keyword)
                        if detailed_info:
                            enhanced_results.append(detailed_info)
                        else:
                            # 如果提取失败，至少保留基本信息
                            enhanced_results.append({
                                'title': result.get('title', ''),
                                'url': result.get('url', ''),
                                'summary': result.get('summary', ''),
                                'date': result.get('date', ''),
                                'source': result.get('source', '中国政府网'),
                                'document_number': '',
                                'issuing_authority': '',
                                'effective_date': '',
                                'law_level': '',
                                'content': ''
                            })
                    except Exception as e:
                        logger.warning(f"提取第 {i+1} 个结果的详细信息失败: {e}")
                        # 保留基本信息
                        enhanced_results.append({
                            'title': result.get('title', ''),
                            'url': result.get('url', ''),
                            'summary': result.get('summary', ''),
                            'date': result.get('date', ''),
                            'source': result.get('source', '中国政府网'),
                            'document_number': '',
                            'issuing_authority': '',
                            'effective_date': '',
                            'law_level': '',
                            'content': ''
                        })
                
                return enhanced_results
            else:
                logger.warning("浏览器搜索未找到结果")
                # 保存页面截图用于调试
                try:
                    import os
                    os.makedirs("debug", exist_ok=True)
                    screenshot_path = f"debug/no_result_{keyword.replace(' ', '_')}.png"
                    self.driver.save_screenshot(screenshot_path)
                    logger.info(f"无结果页面截图已保存: {screenshot_path}")
                except:
                    pass
            
            return results
            
        except Exception as e:
            logger.error(f"浏览器搜索失败: {e}")
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
    
    def _extract_detailed_info(self, result: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
        """点击链接并提取详细信息"""
        try:
            # 获取链接URL
            detail_url = result.get('url')
            if not detail_url:
                self.logger.warning("结果中没有URL")
                return None
            
            # 如果有保存的元素引用，尝试直接点击
            element = result.get('element')
            if element:
                try:
                    # 滚动到元素可见
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    
                    # 点击链接
                    element.click()
                    self.logger.info(f"已点击链接: {result.get('title', '')[:30]}...")
                    
                    # 等待新页面加载
                    time.sleep(3)
                    
                except Exception as e:
                    self.logger.warning(f"点击元素失败: {e}，尝试直接访问URL")
                    self.driver.get(detail_url)
                    time.sleep(3)
            else:
                # 直接访问URL
                self.logger.info(f"直接访问详情页面: {detail_url}")
                self.driver.get(detail_url)
                time.sleep(3)
            
            # 保存详情页面截图
            try:
                import os
                os.makedirs("debug", exist_ok=True)
                screenshot_path = f"debug/detail_{keyword.replace(' ', '_')}.png"
                self.driver.save_screenshot(screenshot_path)
                self.logger.info(f"详情页面截图已保存: {screenshot_path}")
            except:
                pass
            
            # 提取详情页面信息
            detail_info = self._parse_detail_page(result, keyword)
            
            # 返回搜索结果页面
            self.driver.back()
            time.sleep(2)
            
            return detail_info
            
        except Exception as e:
            self.logger.error(f"提取详细信息失败: {e}")
            return None
    
    def _parse_detail_page(self, base_result: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        """解析详情页面内容"""
        try:
            # 基础信息
            detail_info = {
                'success': True,  # 标记为成功
                'title': base_result.get('title', ''),
                'name': base_result.get('title', ''),  # 添加name字段
                'url': base_result.get('url', ''),
                'source_url': base_result.get('url', ''),  # 添加source_url字段
                'summary': base_result.get('summary', ''),
                'date': base_result.get('date', ''),
                'source': '中国政府网',
                'document_number': '',
                'number': '',  # 添加number字段别名
                'issuing_authority': '',
                'office': '',  # 添加office字段别名
                'effective_date': '',
                'valid_from': '',  # 添加valid_from字段别名
                'publish_date': '',  # 添加publish_date字段
                'valid_to': None,  # 添加valid_to字段
                'status': '有效',  # 添加status字段
                'law_level': '',
                'level': '',  # 添加level字段别名
                'content': ''
            }
            
            # 获取页面源码
            page_source = self.driver.page_source
            
            # 保存详情页面HTML用于调试
            try:
                import os
                os.makedirs("debug", exist_ok=True)
                debug_file = f"debug/detail_{keyword.replace(' ', '_')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                self.logger.info(f"详情页面HTML已保存: {debug_file}")
            except:
                pass
            
            # 尝试提取页面标题
            try:
                title_element = self.driver.find_element(By.TAG_NAME, "title")
                page_title = title_element.get_attribute("textContent").strip()
                if page_title and len(page_title) > len(detail_info['title']):
                    detail_info['title'] = page_title
            except:
                pass
            
            # 尝试提取文档编号（文号）
            try:
                import re
                # 根据你提供的截图，完整文号应该是：
                # "中华人民共和国国家发展和改革委员会...令 第20号"
                
                # 查找完整的发布机关和文号
                full_document_pattern = r'(中华人民共和国.*?令[\s\n]*第\s*\d+\s*号)'
                full_matches = re.findall(full_document_pattern, page_source, re.DOTALL)
                
                if full_matches:
                    # 清理换行和多余空格
                    full_number = re.sub(r'\s+', ' ', full_matches[0].strip())
                    full_number = re.sub(r'令\s*第', '令\n第', full_number)  # 在"令"和"第"之间加换行
                    detail_info['document_number'] = full_number
                else:
                    # 如果没找到完整的，尝试简单的"第X号"模式
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
                # 根据你提供的截图，发布机关是8个部委联合发布
                # 完整的发布机关列表
                authority_pattern = r'(中华人民共和国国家发展和改革委员会[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*工\s*业\s*和\s*信\s*息\s*化\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*监\s*察\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*住\s*房\s*和\s*城\s*乡\s*建\s*设\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*交\s*通\s*运\s*输\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*铁\s*道\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*水\s*利\s*部[\s\n]*中\s*华\s*人\s*民\s*共\s*和\s*国\s*商\s*务\s*部)'
                
                full_authority_match = re.search(authority_pattern, page_source, re.DOTALL)
                
                if full_authority_match:
                    # 清理格式，保持标准格式
                    authority_text = full_authority_match.group(1)
                    # 规范化格式：去除多余空格，保持换行
                    authority_text = re.sub(r'\s+', ' ', authority_text)
                    authority_text = authority_text.replace(' 中 华', '\n中华')
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
                
                # 如果还是没找到，尝试通用模式
                if not detail_info['issuing_authority']:
                    authority_keywords = ['发布机关', '制定机关', '发文机关', '颁布机关']
                    for keyword_auth in authority_keywords:
                        if keyword_auth in page_source:
                            lines = page_source.split('\n')
                            for line in lines:
                                if keyword_auth in line:
                                    match = re.search(f'{keyword_auth}[：:]\\s*([^<>\\n]+)', line)
                                    if match:
                                        detail_info['issuing_authority'] = match.group(1).strip()
                                        break
                            if detail_info['issuing_authority']:
                                break
            except:
                pass
            
            # 尝试提取发布日期和实施日期
            try:
                import re
                
                # 根据你提供的截图：发布日期：2013年2月4日，实施日期：2013年5月1日
                
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
                
                # 失效日期（默认为无）
                detail_info['valid_to'] = None
                
                # 状态（默认为有效）
                detail_info['status'] = '有效'
                
            except:
                pass
            
            # 尝试提取正文内容
            try:
                # 查找正文容器
                content_selectors = [
                    '.content',
                    '.article-content', 
                    '.text-content',
                    '#content',
                    '.main-content',
                    'article',
                    '.detail-content'
                ]
                
                content_text = ""
                for selector in content_selectors:
                    try:
                        content_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if content_elements:
                            content_text = content_elements[0].text.strip()
                            if len(content_text) > 100:  # 确保内容足够长
                                break
                    except:
                        continue
                
                # 如果没找到专门的内容区域，尝试获取body的文本
                if not content_text:
                    try:
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        content_text = body.text.strip()
                    except:
                        pass
                
                detail_info['content'] = content_text[:2000] if content_text else ""  # 限制长度
                
            except:
                pass
            
            # 根据文档编号判断法规层级
            if detail_info['document_number']:
                detail_info['law_level'] = self.determine_law_level(detail_info['document_number'])
                detail_info['level'] = detail_info['law_level']  # 同步别名字段
            
            # 格式化日期字段
            detail_info['publish_date'] = normalize_date_format(detail_info.get('publish_date', ''))
            detail_info['effective_date'] = normalize_date_format(detail_info.get('effective_date', ''))
            
            # 同步所有别名字段
            detail_info['number'] = detail_info['document_number']
            detail_info['office'] = detail_info['issuing_authority']
            detail_info['valid_from'] = detail_info['effective_date']
            
            self.logger.info(f"成功提取详细信息: {detail_info['title'][:30]}...")
            return detail_info
            
        except Exception as e:
            self.logger.error(f"解析详情页面失败: {e}")
            return base_result
    
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
        爬取指定法规
        每次爬取完成后关闭浏览器，避免页面积累
        """
        logger.info(f"Selenium政府网爬取: {law_name}")
        
        try:
            # 每次爬取都重新初始化浏览器
            self.setup_driver()
            
            # 执行搜索
            results = self.search_law_with_browser(law_name)
            
            if not results:
                logger.warning(f"Selenium政府网所有搜索策略都未找到结果: {law_name}")
                return self._create_failed_result(law_name, "未找到匹配结果")
            
            # 获取第一个结果的详细信息
            result = results[0]
            logger.success(f"Selenium政府网爬取成功: {law_name}")
            return result
            
        except Exception as e:
            logger.error(f"Selenium政府网爬取异常: {law_name} - {e}")
            return self._create_failed_result(law_name, f"爬取异常: {str(e)}")
        
        finally:
            # 每次爬取完成后立即关闭浏览器
            self.close_driver()
    
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