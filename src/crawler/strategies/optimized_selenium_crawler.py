#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化版Selenium政府网爬虫
关键优化:
1. 浏览器会话复用 - 避免重复启动Chrome
2. 智能等待策略 - 替代固定sleep
3. 批量处理模式 - 一次会话处理多个法规
4. 预加载优化 - 缓存常用页面元素
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from loguru import logger

from ..base_crawler import BaseCrawler
from ..utils.webdriver_manager import get_local_chromedriver_path


class OptimizedSeleniumCrawler(BaseCrawler):
    """优化版Selenium政府网爬虫 - 会话复用模式"""
    
    def __init__(self):
        super().__init__("optimized_selenium")
        self.driver = None
        self.wait = None
        self.session_start_time = None
        self.max_session_time = 1800  # 30分钟最大会话时间
        self.requests_count = 0
        self.max_requests_per_session = 50  # 每个会话最大请求数
        self.processed_count = 0
        self.batch_size = 10  # 每个会话处理的法规数量
        
        # 性能统计
        self.stats = {
            'browser_starts': 0,
            'total_time': 0,
            'search_time': 0,
            'detail_time': 0,
            'success_count': 0,
            'failure_count': 0
        }
    
    def setup_driver_session(self):
        """
        建立浏览器会话
        关键：一次启动，多次使用，避免频繁重启浏览器
        """
        if self.driver:
            return  # 会话已存在
        
        try:
            chrome_options = Options()
            
            # 极速模式设置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # 禁用图片加载
            chrome_options.add_argument('--disable-javascript')  # 部分页面可禁用JS
            chrome_options.add_argument('--headless')  # 无头模式
            
            # 禁用不必要的功能
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 设置页面加载策略
            chrome_options.add_argument('--page-load-strategy=eager')  # 快速加载策略
            
            # 减少资源占用
            chrome_options.add_argument('--max_old_space_size=4096')
            chrome_options.add_argument('--memory-pressure-off')
            
            # 使用本地缓存的ChromeDriver
            driver_path = get_local_chromedriver_path()
            if driver_path:
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info(f"使用本地缓存的ChromeDriver: {driver_path}")
            else:
                # 回退到默认方式
                self.driver = webdriver.Chrome(options=chrome_options)
                logger.info("使用系统PATH中的ChromeDriver")
            
            self.wait = WebDriverWait(self.driver, 10)  # 智能等待最大10秒
            
            # 设置页面加载超时
            self.driver.set_page_load_timeout(15)
            self.driver.implicitly_wait(3)
            
            self.session_start_time = time.time()
            self.stats['browser_starts'] += 1
            
            setup_time = time.time() - self.session_start_time
            logger.success(f"浏览器会话初始化成功 (耗时: {setup_time:.2f}秒)")
            
        except Exception as e:
            logger.error(f"浏览器会话初始化失败: {e}")
            raise
    
    def close_session(self):
        """关闭浏览器会话"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("浏览器会话已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器会话时出错: {e}")
            finally:
                self.driver = None
                self.wait = None
    
    async def crawl_laws_batch(self, law_names: List[str]) -> List[Dict[str, Any]]:
        """批量爬取法规 - 核心优化方法"""
        total_start = time.time()
        results = []
        
        logger.info(f"开始批量爬取 {len(law_names)} 个法规 (优化模式)")
        
        # 启动浏览器会话
        self.setup_driver_session()
        
        try:
            for i, law_name in enumerate(law_names, 1):
                logger.info(f"[{i}/{len(law_names)}] 处理: {law_name}")
                
                try:
                    result = await self.crawl_single_law_in_session(law_name)
                    results.append(result)
                    
                    if result and result.get('success'):
                        self.stats['success_count'] += 1
                        logger.info(f"✅ 成功: {law_name}")
                    else:
                        self.stats['failure_count'] += 1
                        logger.warning(f"❌ 失败: {law_name}")
                    
                    # 每处理batch_size个法规重启会话(避免内存泄漏)
                    self.processed_count += 1
                    if self.processed_count % self.batch_size == 0:
                        logger.info(f"达到批次限制({self.batch_size})，重启浏览器会话...")
                        self.close_session()
                        time.sleep(1)  # 短暂休息
                        self.setup_driver_session()
                        
                except Exception as e:
                    logger.error(f"处理法规异常: {law_name} - {e}")
                    results.append(self._create_failed_result(law_name, f"处理异常: {str(e)}"))
                    self.stats['failure_count'] += 1
        
        finally:
            self.close_session()
        
        total_time = time.time() - total_start
        self.stats['total_time'] = total_time
        
        self._log_performance_stats(len(law_names), total_time)
        
        return results
    
    async def crawl_single_law_in_session(self, law_name: str) -> Dict[str, Any]:
        """在已有会话中爬取单个法规"""
        search_start = time.time()
        
        try:
            # 1. 快速搜索
            search_url = self._build_search_url(law_name)
            self.driver.get(search_url)
            
            # 2. 智能等待搜索结果
            try:
                # 等待页面关键元素加载完成
                self.wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "result")),
                        EC.presence_of_element_located((By.CLASS_NAME, "no-result")),
                        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "没有找到")
                    )
                )
            except TimeoutException:
                logger.warning(f"搜索结果页面加载超时: {law_name}")
                return self._create_failed_result(law_name, "搜索超时")
            
            search_time = time.time() - search_start
            self.stats['search_time'] += search_time
            
            # 3. 快速解析搜索结果
            page_source = self.driver.page_source
            search_results = self._parse_search_results_fast(page_source, law_name)
            
            if not search_results:
                # 如果启用了调试模式，保存调试信息
                if getattr(self, 'debug_enabled', False):
                    self._save_debug_screenshot(law_name, "no_result")
                return self._create_failed_result(law_name, "未找到搜索结果")
            
            # 4. 获取详情页面信息
            detail_start = time.time()
            detail_info = await self._get_detail_info_fast(search_results[0]['url'])
            detail_time = time.time() - detail_start
            self.stats['detail_time'] += detail_time
            
            if not detail_info:
                # 如果启用了调试模式，保存调试信息
                if getattr(self, 'debug_enabled', False):
                    self._save_debug_screenshot(law_name, "detail_failed")
                return self._create_failed_result(law_name, "详情页面获取失败")
            
            # 5. 整合结果
            result = {
                **search_results[0],
                **detail_info,
                'success': True,
                'target_name': law_name,
                'search_keyword': law_name,
                'crawl_time': datetime.now().isoformat(),
                'source': '中国政府网',
                'crawler_strategy': 'optimized_selenium'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"爬取法规失败: {law_name} - {e}")
            return self._create_failed_result(law_name, f"爬取异常: {str(e)}")
    
    def _build_search_url(self, law_name: str) -> str:
        """构建搜索URL"""
        encoded_name = quote_plus(law_name)
        return f"https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord={encoded_name}&dataTypeId=107&sign=9c1d305f-d6a7-46ba-9d42-ca7411f93ffe"
    
    def _parse_search_results_fast(self, html_content: str, target_name: str) -> List[Dict[str, Any]]:
        """快速解析搜索结果"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # 检查是否有结果
            if "没有找到相关结果" in html_content or "no-result" in html_content:
                return results
            
            # 查找所有链接
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                title = link.get('title', '')
                
                # 筛选政府网链接
                if 'gov.cn' in href and any(keyword in (text + title).replace(' ', '') 
                                          for keyword in target_name.replace('（', '').replace('）', '').split('（')[0][:6]):
                    
                    # 确保完整URL
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = f"https://www.gov.cn{href}"
                    
                    results.append({
                        'name': text or title or target_name,
                        'title': title or text or target_name,
                        'url': full_url,
                        'source_url': full_url
                    })
                    
                    # 只取第一个匹配结果，提高效率
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"解析搜索结果失败: {e}")
            return []
    
    async def _get_detail_info_fast(self, detail_url: str) -> Optional[Dict[str, Any]]:
        """快速获取详情页面信息"""
        try:
            self.driver.get(detail_url)
            
            # 等待页面内容加载
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                logger.warning(f"详情页面加载超时: {detail_url}")
                return None
            
            page_source = self.driver.page_source
            return self._extract_law_details_from_html(page_source)
            
        except Exception as e:
            logger.error(f"获取详情页面失败: {detail_url} - {e}")
            return None
    
    def _extract_law_details_from_html(self, html_content: str) -> Dict[str, Any]:
        """从HTML中提取法规详细信息"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取完整内容
            content_div = soup.find('div', class_='pages_content') or soup.find('div', class_='TRS_Editor')
            content = content_div.get_text(strip=True) if content_div else ""
            
            # 基础信息提取
            result = {
                'content': content,
                'publish_date': '',
                'valid_from': '',
                'valid_to': '',
                'office': '',
                'issuing_authority': '',
                'document_number': '',
                'law_level': '部门规章',
                'status': '有效'
            }
            
            # 通过正则表达式快速提取关键信息
            import re
            
            # 提取发布时间
            date_patterns = [
                r'(\d{4}年\d{1,2}月\d{1,2}日)',
                r'(\d{4}-\d{1,2}-\d{1,2})',
                r'(\d{4}\.\d{1,2}\.\d{1,2})'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, content[:1000])  # 只在前1000字符中查找
                if matches:
                    result['publish_date'] = matches[0]
                    break
            
            # 提取文号
            number_patterns = [
                r'第(\d+)号',
                r'(\d+年第\d+号)',
                r'令\s*(\d+号)'
            ]
            
            for pattern in number_patterns:
                matches = re.findall(pattern, content[:500])
                if matches:
                    result['document_number'] = matches[0]
                    break
            
            return result
            
        except Exception as e:
            logger.error(f"提取法规详情失败: {e}")
            return {}
    
    def _log_performance_stats(self, total_laws: int, total_time: float):
        """记录性能统计"""
        avg_time = total_time / total_laws if total_laws > 0 else 0
        success_rate = (self.stats['success_count'] / total_laws) * 100 if total_laws > 0 else 0
        
        logger.info("=" * 50)
        logger.info("📊 优化版爬虫性能统计")
        logger.info("=" * 50)
        logger.info(f"总法规数: {total_laws}")
        logger.info(f"成功数: {self.stats['success_count']}")
        logger.info(f"失败数: {self.stats['failure_count']}")
        logger.info(f"成功率: {success_rate:.1f}%")
        logger.info(f"总耗时: {total_time:.2f}秒")
        logger.info(f"平均耗时: {avg_time:.2f}秒/法规")
        logger.info(f"浏览器启动次数: {self.stats['browser_starts']}")
        logger.info(f"搜索总耗时: {self.stats['search_time']:.2f}秒")
        logger.info(f"详情获取总耗时: {self.stats['detail_time']:.2f}秒")
        
        # 效率提升计算
        old_avg_time = 24  # 之前的平均耗时
        improvement = ((old_avg_time - avg_time) / old_avg_time) * 100
        logger.info(f"效率提升: {improvement:.1f}%")
        logger.info("=" * 50)
    
    def _create_failed_result(self, law_name: str, error_message: str) -> Dict[str, Any]:
        """创建失败结果"""
        return {
            'success': False,
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
            'status': '',
            'source_url': '',
            'content': '',
            'target_name': law_name,
            'search_keyword': law_name,
            'crawl_time': datetime.now().isoformat(),
            'source': 'failed',
            'error': error_message,
            'crawler_strategy': 'optimized_selenium'
        }
    
    # 兼容现有接口
    async def crawl_law(self, law_name: str, law_number: str = None) -> Dict[str, Any]:
        """单个法规爬取接口(兼容性)"""
        self.setup_driver_session()
        try:
            return await self.crawl_single_law_in_session(law_name)
        finally:
            self.close_session()
    
    def close_driver(self):
        """兼容性方法"""
        self.close_session()
    
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法规 - 实现抽象方法"""
        result = await self.crawl_law(law_name, law_number)
        return [result] if result and result.get('success') else []
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法规详情 - 实现抽象方法"""
        return await self._get_detail_info_fast(law_id) or {}
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件 - 实现抽象方法"""
        try:
            if not self.driver:
                return False
            
            self.driver.get(url)
            page_source = self.driver.page_source
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            return True
        except Exception as e:
            logger.error(f"下载文件失败: {e}")
            return False

    # ========== 从 selenium_gov_crawler 迁移的调试功能 ==========
    
    def _save_debug_screenshot(self, keyword: str, suffix: str = "debug"):
        """保存调试截图和页面源码"""
        if not self.driver:
            return
            
        try:
            import os
            os.makedirs("tests/debug", exist_ok=True)
            
            # 保存页面源码
            safe_keyword = keyword.replace(' ', '_').replace('/', '_').replace('\\', '_')
            debug_file = f"tests/debug/optimized_selenium_{safe_keyword}_{suffix}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            
            # 保存页面截图
            screenshot_path = f"tests/debug/optimized_selenium_{safe_keyword}_{suffix}.png"
            self.driver.save_screenshot(screenshot_path)
            
            logger.info(f"调试文件已保存: {debug_file}, {screenshot_path}")
            
        except Exception as e:
            logger.warning(f"保存调试文件失败: {e}")
    
    def enable_debug_mode(self, enabled: bool = True):
        """启用或禁用调试模式"""
        self.debug_enabled = getattr(self, 'debug_enabled', False)
        self.debug_enabled = enabled
        if enabled:
            logger.info("调试模式已启用 - 将保存页面截图和源码")
        else:
            logger.info("调试模式已禁用") 