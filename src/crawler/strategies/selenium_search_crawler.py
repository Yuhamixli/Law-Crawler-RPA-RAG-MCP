#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Selenium搜索引擎爬虫 - 通过浏览器访问搜索引擎页面
"""

import asyncio
import random
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger
from selenium.webdriver.common.keys import Keys

from ..base_crawler import BaseCrawler
from ..utils.webdriver_manager import get_search_driver


class SeleniumSearchCrawler(BaseCrawler):
    """Selenium搜索引擎爬虫"""
    
    def __init__(self, settings=None):
        # 为了兼容，如果没有传入settings，使用默认值
        source_name = "selenium_search_engine"
        super().__init__(source_name)
        self.name = "Selenium搜索引擎爬虫"
        self.settings = settings
        self.logger = logger
    
    async def crawl(self, law_name: str, **kwargs) -> Dict[str, Any]:
        """执行Selenium搜索引擎爬取"""
        results = {
            'source': 'selenium_search',
            'success': False,
            'data': {},
            'search_results': [],
            'metadata': {
                'search_engines_tried': [],
                'total_results_found': 0
            }
        }
        
        self.logger.info(f"🔍 Selenium搜索引擎爬虫启动: {law_name}")
        
        # 构建搜索查询
        query = self._build_search_query(law_name)
        
        # 尝试不同的搜索引擎
        search_engines = [
            self._search_baidu_selenium,
            self._search_bing_selenium,
            self._search_sogou_selenium
        ]
        
        for search_func in search_engines:
            try:
                search_results = await search_func(query)
                engine_name = search_func.__name__.replace('_search_', '').replace('_selenium', '')
                results['metadata']['search_engines_tried'].append(engine_name)
                
                if search_results:
                    results['search_results'].extend(search_results)
                    results['metadata']['total_results_found'] += len(search_results)
                    self.logger.success(f"✅ {engine_name} 找到 {len(search_results)} 个结果")
                else:
                    self.logger.warning(f"❌ {engine_name} 未找到相关结果")
                
                # 如果找到足够结果，可以提前结束
                if len(results['search_results']) >= 5:
                    break
                    
            except Exception as e:
                engine_name = search_func.__name__.replace('_search_', '').replace('_selenium', '')
                self.logger.error(f"❌ {engine_name} 搜索异常: {e}")
                results['metadata']['search_engines_tried'].append(f"{engine_name}(失败)")
        
        # 分析搜索结果
        if results['search_results']:
            # 找到最相关的法律文本
            best_result = await self._find_best_legal_result(results['search_results'], law_name)
            if best_result:
                # 尝试获取法律全文
                full_text = await self._extract_legal_full_text(best_result)
                if full_text:
                    results['success'] = True
                    results['data'] = {
                        'title': best_result.get('title', law_name),
                        'content': full_text,
                        'source_url': best_result.get('url', ''),
                        'publish_date': best_result.get('date', ''),
                        'issuing_authority': best_result.get('authority', ''),
                        'law_number': best_result.get('law_number', ''),
                        'search_engine': best_result.get('search_engine', 'selenium'),
                        'confidence': best_result.get('confidence', 0.0)
                    }
                    self.logger.success(f"🎯 成功获取法律全文: {results['data']['title']}")
        
        if not results['success']:
            self.logger.warning(f"❌ Selenium搜索引擎爬虫未能找到: {law_name}")
        
        return results
    
    def _build_search_query(self, law_name: str) -> str:
        """构建搜索查询"""
        # 添加法律相关关键词提高准确性
        keywords = ["法律法规", "全文", "条文", "政府", "官方"]
        query = f'"{law_name}" ' + ' OR '.join(keywords)
        return query[:100]  # 限制查询长度
    
    async def _search_baidu_selenium(self, query: str) -> List[Dict[str, Any]]:
        """百度Selenium搜索"""
        driver = None
        try:
            # 获取WebDriver - 优先直连
            driver = await get_search_driver()
            if not driver:
                self.logger.warning("无法获取WebDriver")
                return []
            
            # 访问百度
            driver.get("https://www.baidu.com")
            await asyncio.sleep(random.uniform(1, 2))
            
            # 输入查询
            search_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "kw"))
            )
            search_box.clear()
            search_box.send_keys(query)
            
            # 点击搜索
            search_btn = driver.find_element(By.ID, "su")
            search_btn.click()
            
            # 等待结果加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "content_left"))
            )
            await asyncio.sleep(random.uniform(1, 2))
            
            # 解析搜索结果
            results = []
            result_elements = driver.find_elements(By.CSS_SELECTOR, ".result.c-container")
            
            for elem in result_elements[:8]:  # 限制前8个结果
                try:
                    # 提取标题和链接
                    title_elem = elem.find_element(By.CSS_SELECTOR, "h3 a")
                    title = title_elem.text.strip()
                    url = title_elem.get_attribute("href")
                    
                    # 提取摘要
                    try:
                        summary_elem = elem.find_element(By.CSS_SELECTOR, ".c-abstract")
                        summary = summary_elem.text.strip()
                    except NoSuchElementException:
                        summary = ""
                    
                    if title and url and self._is_legal_relevant(title, summary):
                        results.append({
                            'title': title,
                            'url': url,
                            'summary': summary,
                            'search_engine': 'baidu',
                            'confidence': self._calculate_confidence(title, summary, query)
                        })
                
                except Exception as e:
                    continue
            
            # 按相关性排序
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results[:5]  # 返回前5个最相关的
            
        except Exception as e:
            self.logger.error(f"百度Selenium搜索失败: {e}")
            return []
    
    async def _search_bing_selenium(self, query: str) -> List[Dict[str, Any]]:
        """Bing Selenium搜索 - 增强版元素定位"""
        driver = None
        try:
            # 获取WebDriver - 可能需要代理
            proxy = await self._get_proxy_for_bing()
            driver = await get_search_driver(proxy)
            if not driver:
                return []
            
            # 访问Bing
            driver.get("https://www.bing.com")
            await asyncio.sleep(random.uniform(2, 3))
            
            # 输入查询 - 增强元素定位
            search_box = None
            search_selectors = [
                (By.NAME, "q"),
                (By.ID, "sb_form_q"),
                (By.CSS_SELECTOR, "input[name='q']"),
                (By.CSS_SELECTOR, "#sb_form_q")
            ]
            
            for selector_type, selector_value in search_selectors:
                try:
                    search_box = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    break
                except:
                    continue
            
            if not search_box:
                self.logger.warning("Bing搜索框未找到")
                return []
            
            # 清空并输入查询
            search_box.clear()
            await asyncio.sleep(0.5)
            search_box.send_keys(query)
            await asyncio.sleep(1)
            
            # 提交搜索 - 使用多种方式
            search_submitted = False
            
            # 方式1: 按Enter键
            try:
                search_box.send_keys(Keys.RETURN)
                search_submitted = True
                self.logger.debug("使用Enter键提交搜索")
            except Exception as e:
                self.logger.debug(f"Enter键提交失败: {e}")
            
            # 方式2: 点击搜索按钮
            if not search_submitted:
                search_button_selectors = [
                    (By.CSS_SELECTOR, "input[type='submit']"),
                    (By.ID, "sb_form_go"),
                    (By.CSS_SELECTOR, "#sb_form_go"),
                    (By.CSS_SELECTOR, ".b_searchboxSubmit"),
                    (By.CSS_SELECTOR, "[aria-label='搜索']"),
                    (By.CSS_SELECTOR, "[title='搜索']")
                ]
                
                for selector_type, selector_value in search_button_selectors:
                    try:
                        search_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        driver.execute_script("arguments[0].click();", search_btn)
                        search_submitted = True
                        self.logger.debug(f"使用按钮提交搜索: {selector_value}")
                        break
                    except Exception as e:
                        continue
            
            if not search_submitted:
                self.logger.warning("无法提交Bing搜索")
                return []
            
            # 等待结果加载 - 增强等待策略
            result_selectors = [
                (By.ID, "b_results"),
                (By.CSS_SELECTOR, "#b_results"),
                (By.CSS_SELECTOR, ".b_algo"),
                (By.CSS_SELECTOR, "[data-bm]")
            ]
            
            results_found = False
            for selector_type, selector_value in result_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    results_found = True
                    break
                except:
                    continue
            
            if not results_found:
                self.logger.warning("Bing搜索结果未加载")
                return []
            
            await asyncio.sleep(random.uniform(1, 2))
            
            # 解析搜索结果 - 增强结果提取
            results = []
            result_selectors = [".b_algo", "[data-bm]", ".b_title"]
            
            for result_selector in result_selectors:
                try:
                    result_elements = driver.find_elements(By.CSS_SELECTOR, result_selector)
                    if result_elements:
                        break
                except:
                    continue
            else:
                self.logger.warning("Bing搜索结果元素未找到")
                return []
            
            for elem in result_elements[:8]:
                try:
                    # 提取标题和链接 - 多种选择器
                    title_elem = None
                    title_selectors = ["h2 a", ".b_title a", "h3 a", "a[href]"]
                    
                    for title_selector in title_selectors:
                        try:
                            title_elem = elem.find_element(By.CSS_SELECTOR, title_selector)
                            break
                        except:
                            continue
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    url = title_elem.get_attribute("href")
                    
                    if not title or not url:
                        continue
                    
                    # 提取摘要 - 多种选择器
                    summary = ""
                    summary_selectors = [".b_caption p", ".b_caption", ".b_snippet", ".b_descript"]
                    
                    for summary_selector in summary_selectors:
                        try:
                            summary_elem = elem.find_element(By.CSS_SELECTOR, summary_selector)
                            summary = summary_elem.text.strip()
                            break
                        except:
                            continue
                    
                    if self._is_legal_relevant(title, summary):
                        results.append({
                            'title': title,
                            'url': url,
                            'summary': summary,
                            'search_engine': 'bing',
                            'confidence': self._calculate_confidence(title, summary, query)
                        })
                
                except Exception as e:
                    self.logger.debug(f"解析Bing结果元素失败: {e}")
                    continue
            
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results[:5]
            
        except Exception as e:
            self.logger.error(f"Bing Selenium搜索失败: {e}")
            return []
    
    async def _search_sogou_selenium(self, query: str) -> List[Dict[str, Any]]:
        """搜狗Selenium搜索 - 增强版元素定位"""
        driver = None
        try:
            driver = await get_search_driver()
            if not driver:
                return []
            
            # 访问搜狗
            driver.get("https://www.sogou.com")
            await asyncio.sleep(random.uniform(2, 3))
            
            # 输入查询 - 增强元素定位
            search_box = None
            search_selectors = [
                (By.ID, "query"),
                (By.NAME, "query"),
                (By.CSS_SELECTOR, "input[name='query']"),
                (By.CSS_SELECTOR, "#query")
            ]
            
            for selector_type, selector_value in search_selectors:
                try:
                    search_box = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    break
                except:
                    continue
            
            if not search_box:
                self.logger.warning("搜狗搜索框未找到")
                return []
            
            # 清空并输入查询
            search_box.clear()
            await asyncio.sleep(0.5)
            search_box.send_keys(query)
            await asyncio.sleep(1)
            
            # 提交搜索 - 使用多种方式
            search_submitted = False
            
            # 方式1: 按Enter键
            try:
                search_box.send_keys(Keys.RETURN)
                search_submitted = True
                self.logger.debug("使用Enter键提交搜索")
            except Exception as e:
                self.logger.debug(f"Enter键提交失败: {e}")
            
            # 方式2: 点击搜索按钮
            if not search_submitted:
                search_button_selectors = [
                    (By.ID, "stb"),
                    (By.CSS_SELECTOR, "#stb"),
                    (By.CSS_SELECTOR, "input[type='submit']"),
                    (By.CSS_SELECTOR, ".btn-search"),
                    (By.CSS_SELECTOR, "[value='搜索']")
                ]
                
                for selector_type, selector_value in search_button_selectors:
                    try:
                        search_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        driver.execute_script("arguments[0].click();", search_btn)
                        search_submitted = True
                        self.logger.debug(f"使用按钮提交搜索: {selector_value}")
                        break
                    except Exception as e:
                        continue
            
            if not search_submitted:
                self.logger.warning("无法提交搜狗搜索")
                return []
            
            # 等待结果加载 - 增强等待策略
            result_selectors = [
                (By.CLASS_NAME, "results"),
                (By.CSS_SELECTOR, ".results"),
                (By.CSS_SELECTOR, ".result"),
                (By.CSS_SELECTOR, "[data-md5]")
            ]
            
            results_found = False
            for selector_type, selector_value in result_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    results_found = True
                    break
                except:
                    continue
            
            if not results_found:
                self.logger.warning("搜狗搜索结果未加载")
                return []
            
            await asyncio.sleep(random.uniform(1, 2))
            
            # 解析搜索结果 - 增强结果提取
            results = []
            result_selectors = [".result", "[data-md5]", ".rb"]
            
            for result_selector in result_selectors:
                try:
                    result_elements = driver.find_elements(By.CSS_SELECTOR, result_selector)
                    if result_elements:
                        break
                except:
                    continue
            else:
                self.logger.warning("搜狗搜索结果元素未找到")
                return []
            
            for elem in result_elements[:8]:
                try:
                    # 提取标题和链接 - 多种选择器
                    title_elem = None
                    title_selectors = ["h3 a", ".title a", "h2 a", "a[href]"]
                    
                    for title_selector in title_selectors:
                        try:
                            title_elem = elem.find_element(By.CSS_SELECTOR, title_selector)
                            break
                        except:
                            continue
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    url = title_elem.get_attribute("href")
                    
                    if not title or not url:
                        continue
                    
                    # 提取摘要 - 多种选择器
                    summary = ""
                    summary_selectors = [".str_info", ".abstract", ".content", ".desc"]
                    
                    for summary_selector in summary_selectors:
                        try:
                            summary_elem = elem.find_element(By.CSS_SELECTOR, summary_selector)
                            summary = summary_elem.text.strip()
                            break
                        except:
                            continue
                    
                    if self._is_legal_relevant(title, summary):
                        results.append({
                            'title': title,
                            'url': url,
                            'summary': summary,
                            'search_engine': 'sogou',
                            'confidence': self._calculate_confidence(title, summary, query)
                        })
                
                except Exception as e:
                    self.logger.debug(f"解析搜狗结果元素失败: {e}")
                    continue
            
            results.sort(key=lambda x: x['confidence'], reverse=True)
            return results[:5]
            
        except Exception as e:
            self.logger.error(f"搜狗Selenium搜索失败: {e}")
            return []
    
    def _is_legal_relevant(self, title: str, summary: str) -> bool:
        """判断搜索结果是否与法律相关"""
        legal_keywords = [
            '法律', '法规', '条例', '办法', '规定', '条文', '全文',
            '政府', '国务院', '部委', '省政府', '市政府',
            '法院', '司法', '立法', '颁布', '实施', '修订',
            '公告', '通知', '决定', '意见', '措施'
        ]
        
        text = (title + " " + summary).lower()
        return any(keyword in text for keyword in legal_keywords)
    
    def _calculate_confidence(self, title: str, summary: str, query: str) -> float:
        """计算搜索结果的相关性得分"""
        score = 0.0
        text = (title + " " + summary).lower()
        query_lower = query.lower()
        
        # 标题匹配权重更高
        if query_lower in title.lower():
            score += 0.5
        
        # 摘要匹配
        if query_lower in summary.lower():
            score += 0.3
        
        # 关键词匹配
        legal_keywords = ['法律', '法规', '条例', '全文', '官方']
        for keyword in legal_keywords:
            if keyword in text:
                score += 0.1
        
        # 政府网站加分
        gov_domains = ['.gov.cn', 'gov.com', 'npc.gov.cn', 'court.gov.cn']
        for domain in gov_domains:
            if domain in text:
                score += 0.2
                break
        
        return min(score, 1.0)
    
    async def _find_best_legal_result(self, search_results: List[Dict], law_name: str) -> Optional[Dict]:
        """找到最佳的法律结果"""
        if not search_results:
            return None
        
        # 按confidence排序，返回最佳结果
        search_results.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # 优先选择政府网站结果
        for result in search_results:
            url = result.get('url', '')
            if '.gov.cn' in url or 'npc.gov.cn' in url:
                return result
        
        # 返回confidence最高的结果
        return search_results[0] if search_results else None
    
    async def _extract_legal_full_text(self, result: Dict) -> Optional[str]:
        """从搜索结果中提取法律全文"""
        driver = None
        try:
            url = result.get('url')
            if not url:
                return None
            
            # 获取WebDriver
            driver = await get_search_driver()
            if not driver:
                return None
            
            # 访问法律页面
            self.logger.debug(f"访问法律页面: {url}")
            driver.get(url)
            
            # 等待页面加载
            await asyncio.sleep(random.uniform(2, 4))
            
            # 尝试不同的内容提取策略
            text_selectors = [
                ".law-content",
                ".content",
                ".article-content",
                ".main-content",
                "#content",
                ".text-content",
                "article",
                ".law-text"
            ]
            
            content = ""
            for selector in text_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        content = elements[0].text.strip()
                        if len(content) > 200:  # 内容足够长
                            break
                except Exception:
                    continue
            
            # 如果没有找到特定选择器，尝试整个body
            if not content or len(content) < 200:
                try:
                    body = driver.find_element(By.TAG_NAME, "body")
                    content = body.text.strip()
                except Exception:
                    pass
            
            # 清理和验证内容
            if content and len(content) > 100:
                content = self._clean_legal_text(content)
                if self._is_valid_legal_content(content):
                    return content
            
        except Exception as e:
            self.logger.error(f"提取法律全文失败: {e}")
        
        return None
    
    def _clean_legal_text(self, text: str) -> str:
        """清理法律文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除HTML标签残留
        text = re.sub(r'<[^>]+>', '', text)
        # 移除特殊字符
        text = re.sub(r'[^\u4e00-\u9fff\w\s\.,;:!?()（）【】\-\n]', '', text)
        return text.strip()
    
    def _is_valid_legal_content(self, content: str) -> bool:
        """验证是否为有效法律内容"""
        if len(content) < 100:
            return False
        
        # 检查是否包含法律相关关键词
        legal_indicators = [
            '第一条', '第二条', '条文', '章节',
            '法律', '法规', '条例', '规定',
            '颁布', '实施', '修订', '废止'
        ]
        
        return any(indicator in content for indicator in legal_indicators)
    
    async def _get_proxy_for_bing(self) -> Optional[str]:
        """为Bing获取代理（如果需要）"""
        # 这里可以实现代理获取逻辑
        # 暂时返回None表示直连
        return None

    # 实现抽象方法
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法律法规 - 实现抽象方法"""
        try:
            result = await self.crawl(law_name)
            if result['success']:
                return [result['data']]
            else:
                return result.get('search_results', [])
        except Exception as e:
            self.logger.error(f"Selenium搜索失败: {e}")
            return []
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法律法规详情 - 实现抽象方法"""
        # 对于搜索引擎爬虫，law_id实际上是URL
        try:
            result = {'url': law_id}
            full_text = await self._extract_legal_full_text(result)
            if full_text:
                return {
                    'content': full_text,
                    'source_url': law_id,
                    'success': True
                }
            else:
                return {'success': False, 'error': '无法获取法律全文'}
        except Exception as e:
            self.logger.error(f"获取详情失败: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_file(self, url: str, save_path: str) -> bool:
        """下载文件 - 实现抽象方法"""
        try:
            # 对于搜索引擎爬虫，主要是下载法律文本
            content = await self._extract_legal_full_text({'url': url})
            if content:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True
            return False
        except Exception as e:
            self.logger.error(f"下载文件失败: {e}")
            return False