#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于搜索的法规采集器策略
参考示例项目的成功方法，使用搜索API + 详情API的组合方案
"""

import json
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
import re
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
import sys
sys.path.append('..')
from ..base_crawler import BaseCrawler
import random
from urllib.parse import urljoin
import asyncio
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from ..utils.enhanced_proxy_pool import get_enhanced_proxy_pool, EnhancedProxyPool
from ..utils.ip_pool import get_ip_pool, SmartIPPool
from config.settings import get_settings


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


class SearchBasedCrawler(BaseCrawler):
    """基于搜索的法规采集器"""
    
    def __init__(self):
        super().__init__("search_api")
        self.logger = logger
        self.session = requests.Session()
        
        # 代理池相关
        self.enhanced_proxy_pool: Optional[EnhancedProxyPool] = None
        self.ip_pool: Optional[SmartIPPool] = None
        self.current_proxy = None
        self.proxy_failures = 0
        self.max_proxy_failures = 3
        self._proxy_pools_initialized = False
        
        self.setup_headers()
        self.base_url = "https://flk.npc.gov.cn"
        
        # WAF状态追踪
        self.waf_triggered = False
        self.consecutive_waf_count = 0
        self.last_successful_time = time.time()
        
        # 初始化访问，获取必要的cookies
        self._initialize_session()
    
    def setup_headers(self):
        """设置请求头 - 使用原始示例项目成功的headers配置"""
        # 基于原始示例项目中成功的REQUEST_HEADER配置
        self.session.headers.update({
            "authority": "flk.npc.gov.cn",
            "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="99", "Microsoft Edge";v="99"',
            "accept": "application/json, text/javascript, */*; q=0.01",
            "x-requested-with": "XMLHttpRequest", 
            "sec-ch-ua-mobile": "?0",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36 Edg/99.0.1150.39",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors", 
            "sec-fetch-dest": "empty",
            "referer": "https://flk.npc.gov.cn/fl.html",
            "accept-language": "en-AU,en-GB;q=0.9,en;q=0.8,en-US;q=0.7,zh-CN;q=0.6,zh;q=0.5",
            # 关键：使用示例项目中成功的cookie（模拟真实会话）
            "cookie": "yfx_c_g_u_id_10006696=_ck22022520424713255117764923111; cna=NdafGk8tiAgCAd9IPxhfROag; yfx_f_l_v_t_10006696=f_t_1645792967326__r_t_1646401808964__v_t_1646401808964__r_c_5; Hm_lvt_54434aa6770b6d9fef104d146430b53b=1646407223,1646570042,1646666110,1647148584; acw_tc=75a1461516471485843844814eb808af266b8ede0e0502ec1c46ab1581; Hm_lpvt_54434aa6770b6d9fef104d146430b53b=1647148626",
        })
        
        # 设置Session级别的配置
        self.session.verify = True
        self.session.allow_redirects = True
        self.session.max_redirects = 5
    
    def _initialize_session(self):
        """初始化session，访问首页获取cookies"""
        try:
            # 先访问首页
            home_response = self.session.get(
                "https://flk.npc.gov.cn/",
                timeout=10,
                allow_redirects=True
            )
            self.logger.debug(f"首页访问状态码: {home_response.status_code}")
            
            # 再访问法规搜索页面
            search_page_response = self.session.get(
                "https://flk.npc.gov.cn/fl.html",
                timeout=10,
                allow_redirects=True
            )
            self.logger.debug(f"搜索页面访问状态码: {search_page_response.status_code}")
            
            # 等待一下，模拟真实用户行为
            time.sleep(1)
            
        except Exception as e:
            self.logger.warning(f"初始化session失败: {str(e)}")
            # 不中断，继续尝试
    
    async def search(self, law_name: str, law_number: Optional[str] = None) -> List[Dict[str, Any]]:
        """搜索法规 - 实现抽象方法"""
        return self.search_law(law_name)
    
    async def get_detail(self, law_id: str) -> Dict[str, Any]:
        """获取法规详情 - 实现抽象方法"""
        result = self.get_law_detail(law_id)
        return result or {}
    
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
    
    def search_law_selenium(self, keyword: str) -> List[Dict[str, Any]]:
        """使用Selenium搜索法规 - 模拟首页搜索，支持代理"""
        driver = None
        try:
            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
            
            # 配置代理（如果有的话）
            if self.current_proxy:
                proxy_url = self.current_proxy
                if proxy_url.startswith('http://'):
                    proxy_url = proxy_url[7:]  # 移除http://前缀
                elif proxy_url.startswith('https://'):
                    proxy_url = proxy_url[8:]  # 移除https://前缀
                
                chrome_options.add_argument(f'--proxy-server={proxy_url}')
                self.logger.debug(f"🌍 Selenium使用代理: {proxy_url}")
            
            # 启动浏览器
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 10)
            
            self.logger.debug(f"    Selenium访问首页进行搜索...")
            
            # 访问首页
            driver.get("https://flk.npc.gov.cn/")
            
            # 等待页面加载
            time.sleep(2)
            
            # 查找搜索输入框（根据HTML结构）
            search_input = wait.until(
                EC.presence_of_element_located((By.ID, "flfgTitle"))
            )
            
            # 输入搜索关键词
            search_input.clear()
            search_input.send_keys(keyword)
            
            self.logger.debug(f"    已输入关键词: {keyword}")
            
            # 点击搜索按钮（根据HTML，搜索按钮通过confirmFilter()函数触发）
            search_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "li[onclick='confirmFilter()']"))
            )
            search_button.click()
            
            self.logger.debug(f"    已点击搜索按钮")
            
            # 等待搜索结果加载
            time.sleep(3)
            
            # 等待结果表格出现
            results_table = wait.until(
                EC.presence_of_element_located((By.ID, "flData"))
            )
            
            # 解析搜索结果
            results = []
            rows = results_table.find_elements(By.CSS_SELECTOR, "tr.list-b")
            
            for row in rows:
                try:
                    # 提取标题和链接
                    title_element = row.find_element(By.CSS_SELECTOR, ".l-wen")
                    title = title_element.get_attribute("title") or title_element.text.strip()
                    
                    # 提取详情链接和ID
                    onclick_attr = title_element.get_attribute("onclick")
                    detail_url = None
                    law_id = ""
                    if onclick_attr and "showDetail" in onclick_attr:
                        # 从onclick属性中提取URL
                        import re
                        match = re.search(r"showDetail\('([^']+)'\)", onclick_attr)
                        if match:
                            detail_url = urljoin("https://flk.npc.gov.cn/", match.group(1))
                            # 从URL中提取法规ID（通常在问号后面）
                            if "?" in detail_url:
                                law_id = detail_url.split("?")[1]
                    
                    # 提取制定机关
                    agency_elements = row.find_elements(By.CSS_SELECTOR, ".l-sx2 .l-wen1")
                    agency = agency_elements[0].text.strip() if agency_elements else ""
                    
                    # 提取法律性质
                    type_elements = row.find_elements(By.CSS_SELECTOR, ".l-sx3 .l-wen1")
                    law_type = type_elements[0].text.strip() if len(type_elements) > 0 else ""
                    
                    # 提取时效性并转换为数字状态
                    status_text = type_elements[1].text.strip() if len(type_elements) > 1 else ""
                    status = 1  # 默认有效
                    if "已修改" in status_text:
                        status = 5
                    elif "已废止" in status_text:
                        status = 9
                    elif "尚未生效" in status_text:
                        status = 3
                    
                    # 提取公布日期并格式化
                    date_elements = row.find_elements(By.CSS_SELECTOR, ".l-sx4 .l-wen1")
                    publish_date = ""
                    if date_elements:
                        date_text = date_elements[0].text.strip()
                        # 移除方括号：[2024-12-25] -> 2024-12-25
                        publish_date = date_text.replace("[", "").replace("]", "")
                    
                    if title and law_id:
                        # 构建与HTTP API一致的返回格式
                        results.append({
                            'id': law_id,
                            'title': title,
                            'link': detail_url,
                            'publish_date': publish_date,
                            'status': status,
                            'agency': agency,
                            'type': law_type,
                            'score': 1.0  # Selenium搜索的结果都认为是高匹配度
                        })
                        
                except Exception as e:
                    self.logger.debug(f"    解析行数据失败: {e}")
                    continue
            
            self.logger.debug(f"    Selenium搜索找到 {len(results)} 个结果")
            return results
            
        except TimeoutException:
            self.logger.debug(f"    Selenium搜索超时")
            return []
        except WebDriverException as e:
            self.logger.debug(f"    Selenium WebDriver错误: {e}")
            return []
        except Exception as e:
            self.logger.debug(f"    Selenium搜索失败: {e}")
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _initialize_proxy_pools_sync(self):
        """初始化代理池 - 完全禁用"""
        # 完全禁用代理池初始化，使用直连模式
        self.logger.info("🚀 使用直连模式，跳过代理池初始化")
        return
        
        # # 原代理池初始化逻辑已禁用
        # if self._proxy_pools_initialized:
        #     return
        # 
        # self.logger.info("🔄 开始初始化代理池...")
        # 
        # try:
        #     # 1. 优先使用enhanced_proxy_pool
        #     if not self.enhanced_proxy_pool:
        #         settings = get_settings()
        #         if settings.proxy_pool.enabled:
        #             loop = asyncio.new_event_loop()
        #             asyncio.set_event_loop(loop)
        #             try:
        #                 from ..utils.enhanced_proxy_pool import get_enhanced_proxy_pool
        #                 self.enhanced_proxy_pool = loop.run_until_complete(
        #                     get_enhanced_proxy_pool(settings.proxy_pool.config_file)
        #                 )
        #                 self.logger.success("🔄 Enhanced代理池初始化成功")
        #             except Exception as e:
        #                 self.logger.warning(f"Enhanced代理池初始化失败: {e}")
        #             finally:
        #                 loop.close()
        # 
        # except Exception as e:
        #     self.logger.warning(f"代理池初始化失败: {e}")
        # 
        # self._proxy_pools_initialized = True

    def _get_proxy_for_request_sync(self):
        """获取代理 - 完全禁用，强制直连"""
        # 完全禁用代理，使用直连模式提高速度和稳定性
        return None
        
        # # 原代理逻辑已禁用
        # if self.enhanced_proxy_pool:
        #     try:
        #         proxy_info = self.enhanced_proxy_pool.get_proxy_sync(prefer_paid=True)
        #         if proxy_info:
        #             self.logger.debug(f"🌍 使用Enhanced代理: {proxy_info.name}")
        #             return proxy_info.proxy_url
        #     except Exception as e:
        #         self.logger.debug(f"Enhanced代理获取失败: {e}")
        # 
        # if self.ip_pool:
        #     try:
        #         proxy = self.ip_pool.get_proxy_sync()
        #         if proxy:
        #             self.logger.debug(f"🌍 使用IP池代理: {proxy.ip}:{proxy.port}")
        #             return proxy.proxy_url
        #     except Exception as e:
        #         self.logger.debug(f"IP池代理获取失败: {e}")
        # 
        # return None

    def _configure_session_proxy(self, proxy_url: str = None):
        """配置session的代理"""
        if proxy_url:
            # 解析代理URL
            if proxy_url.startswith('http://') or proxy_url.startswith('https://'):
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url,
                }
            elif proxy_url.startswith('socks5://'):
                proxies = {
                    'http': proxy_url,
                    'https': proxy_url,
                }
            else:
                # 默认HTTP代理
                proxies = {
                    'http': f'http://{proxy_url}',
                    'https': f'http://{proxy_url}',
                }
            
            self.session.proxies.update(proxies)
            self.current_proxy = proxy_url
            self.logger.info(f"✅ Session代理已配置: {proxy_url}")
        else:
            # 清除代理，使用直连
            if self.session.proxies:
                self.session.proxies.clear()
                self.current_proxy = None
                self.logger.debug("🔄 使用直连模式，代理已清除")

    def _rotate_proxy_on_waf_sync(self):
        """WAF检测时轮换代理 - 同步版本"""
        self.proxy_failures += 1
        
        if self.proxy_failures >= self.max_proxy_failures:
            self.logger.warning(f"🔄 代理连续失败{self.proxy_failures}次，强制轮换")
            
            # 标记当前代理失败
            if self.current_proxy and self.enhanced_proxy_pool:
                try:
                    # 使用线程池执行异步操作
                    import concurrent.futures
                    
                    def mark_failed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(
                                self.enhanced_proxy_pool.mark_proxy_failed(self.current_proxy)
                            )
                        finally:
                            loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(mark_failed)
                        future.result(timeout=5)
                        
                except Exception as e:
                    self.logger.debug(f"标记代理失败时出错: {e}")
            
            # 获取新代理
            new_proxy = self._get_proxy_for_request_sync()
            self._configure_session_proxy(new_proxy)
            
            self.proxy_failures = 0  # 重置失败计数
            
            # 添加轮换延迟
            delay = random.uniform(3, 8)
            self.logger.info(f"⏱️ 代理轮换延迟: {delay:.1f}秒")
            time.sleep(delay)

    def search_law(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索法规 - 智能版：优先API，WAF激活时自动切换Selenium，支持代理轮换"""
        
        # 如果WAF已激活，直接使用Selenium
        if self.waf_triggered:
            self.logger.debug(f"    WAF已激活，直接使用Selenium搜索")
            # 确保Selenium也使用代理
            if not self.current_proxy:
                proxy_url = self._get_proxy_for_request_sync()
                self._configure_session_proxy(proxy_url)
                if proxy_url:
                    self.logger.info(f"🌍 为Selenium获取代理: {proxy_url}")
            return self.search_law_selenium(keyword)
        
        # 尝试HTTP API搜索
        results = self._search_law_http(keyword)
        
        # 检查结果并处理WAF状态
        if results:
            self._handle_waf_detection(False)  # 成功，重置WAF状态
            return results
        else:
            # API失败，可能是WAF拦截，尝试Selenium备用
            self.logger.debug(f"    HTTP API失败，尝试Selenium备用搜索")
            # 确保Selenium也使用代理
            if not self.current_proxy:
                proxy_url = self._get_proxy_for_request_sync()
                self._configure_session_proxy(proxy_url)
                if proxy_url:
                    self.logger.info(f"🌍 为Selenium获取代理: {proxy_url}")
            
            selenium_results = self.search_law_selenium(keyword)
            
            # 如果Selenium成功而API失败，说明可能是WAF问题
            if selenium_results:
                self._handle_waf_detection(True)  # 标记可能的WAF拦截
            
            return selenium_results
    
    def _search_law_http(self, keywords, search_type="title;vague"):
        """HTTP API搜索法规"""
        strategies = [
            "title;vague",
            "title;accurate;1,3",
            "title;accurate;2,4", 
            "all;accurate;1,3"
        ]
        
        if search_type not in strategies:
            strategies = [search_type] + strategies
        
        for strategy in strategies:
            self.logger.debug(f"    🔍 尝试API搜索策略: {strategy}")
            
            # 完全使用直连模式，禁用代理
            self._configure_session_proxy(None)  # 强制清除代理
            
            # 极速优化延迟：0.1-0.5秒
            delay = random.uniform(0.1, 0.5)
            self.logger.debug(f"    ⏱️ 添加随机延迟: {delay:.1f}秒")
            time.sleep(delay)
            
            try:
                # 构建查询参数
                params = {
                    "type": "flfg",
                    "searchType": strategy,
                    "sortTr": "f_bbrq_s;desc",
                    "gbrqStart": "",
                    "gbrqEnd": "",
                    "sxrqStart": "",
                    "sxrqEnd": "",
                    "sort": "true",
                    "page": "1",
                    "size": "20",
                    "fgbt": keywords,
                    "_": str(int(time.time() * 1000))
                }
                
                url = f"{self.base_url}/api/"
                
                # 直连请求，超时优化
                response = self.session.get(
                    url, 
                    params=params,
                    timeout=(3, 8),  # 连接超时3秒，读取超时8秒
                    verify=False
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get("result") and data["result"].get("data"):
                            results = data["result"]["data"]
                            self.logger.success(f"    ✅ 直连API搜索成功 (策略: {strategy}): 找到 {len(results)} 个结果")
                            return results
                        else:
                            self.logger.debug(f"    📋 API搜索无结果 (策略: {strategy})")
                    except ValueError as e:
                        self.logger.warning(f"    ⚠️ API响应JSON解析失败 (策略: {strategy}): {e}")
                else:
                    self.logger.debug(f"    ❌ API请求失败 (策略: {strategy}): HTTP {response.status_code}")
                    
            except Exception as e:
                self.logger.debug(f"    ❌ API请求异常 (策略: {strategy}): {e}")
                continue
        
        self.logger.debug(f"    🚫 所有API搜索策略都失败")
        return []
    
    def _check_waf_response(self, response) -> bool:
        """检查响应是否被WAF拦截"""
        # 检查Content-Type
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type:
            return True
        
        # 检查WAF标识
        if 'WZWS-RAY' in response.headers:
            return True
        
        # 检查响应内容
        if "<!DOCTYPE HTML>" in response.text and "JavaScript" in response.text:
            return True
        
        return False
    
    def _handle_waf_detection(self, waf_detected: bool):
        """处理WAF检测结果"""
        if waf_detected:
            self.consecutive_waf_count += 1
            if self.consecutive_waf_count >= 2:  # 连续2次被拦截才认为WAF激活
                self.waf_triggered = True
                self.logger.warning(f"🚫 WAF已激活，连续拦截{self.consecutive_waf_count}次，切换到Selenium模式")
        else:
            # 成功请求，重置计数器
            self.consecutive_waf_count = 0
            self.last_successful_time = time.time()
            if self.waf_triggered:
                self.logger.info("✅ API恢复正常，WAF可能已解除")
                self.waf_triggered = False
    
    def get_law_detail(self, law_id: str) -> Optional[Dict[str, Any]]:
        """获取法规详情"""
        try:
            response = self.session.post(
                "https://flk.npc.gov.cn/api/detail",
                data={"id": law_id},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('result'):
                    return result['result']
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取法规详情失败: {str(e)}")
            return None
    
    def normalize_law_name(self, law_name: str) -> str:
        """标准化法规名称"""
        # 移除括号内容
        normalized = re.sub(r'[（(].*?[）)]', '', law_name)
        # 移除"修订"、"修正"等后缀
        normalized = re.sub(r'（\d{4}.*?修订.*?）', '', normalized)
        normalized = re.sub(r'（\d{4}.*?修正.*?）', '', normalized)
        # 移除主席令等编号
        normalized = re.sub(r'（.*?主席令.*?）', '', normalized)
        normalized = re.sub(r'（.*?令.*?）', '', normalized)
        # 清理多余空格
        normalized = re.sub(r'\s+', '', normalized)
        
        return normalized.strip()
    
    def calculate_match_score(self, target: str, result: str) -> float:
        """计算匹配分数 - 改进版"""
        if not target or not result:
            return 0.0
            
        # 完全匹配
        if target == result:
            return 1.0
        
        # 标准化处理
        target_clean = re.sub(r'[（(].*?[）)]', '', target).strip()
        result_clean = re.sub(r'[（(].*?[）)]', '', result).strip()
        
        # 去掉修订年份后的匹配
        if target_clean == result_clean:
            return 0.95
        
        # 包含关系 - 但要避免匹配到司法解释
        if "解释" in result and "解释" not in target:
            return 0.1  # 大幅降低司法解释的匹配分数
        
        if "意见" in result and "意见" not in target:
            return 0.1  # 大幅降低意见类文件的匹配分数
            
        # 检查核心关键词匹配
        target_core = target_clean.replace("中华人民共和国", "")
        result_core = result_clean.replace("中华人民共和国", "")
        
        if target_core and result_core:
            # 完全匹配核心部分
            if target_core == result_core:
                return 0.9
            
            # 包含关系
            if target_core in result_core:
                ratio = len(target_core) / len(result_core)
                return 0.7 + ratio * 0.2
            if result_core in target_core:
                ratio = len(result_core) / len(target_core)
                return 0.7 + ratio * 0.2
        
        # 计算公共子串
        common_length = 0
        min_len = min(len(target), len(result))
        for i in range(min_len):
            if target[i] == result[i]:
                common_length += 1
            else:
                break
        
        if common_length > 0:
            base_score = common_length / max(len(target), len(result))
            # 如果公共前缀很长，给更高分数
            if common_length >= 6:
                return min(0.8, base_score * 1.2)
            return base_score
        
        return 0.0
    
    def find_best_match(self, target_name: str, search_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """在搜索结果中找到最佳匹配 - 优化版，优先选择有效法规"""
        if not search_results:
            return None
        
        # 标准化目标名称
        target_normalized = self.normalize_law_name(target_name)
        
        # 记录所有候选项的分数和状态
        candidates = []
        
        for law in search_results:
            law_title = law.get('title', '')
            law_normalized = self.normalize_law_name(law_title)
            
            # 计算匹配分数
            score = self.calculate_match_score(target_normalized, law_normalized)
            
            # 获取法规状态 (1=有效, 5=失效) - 处理字符串类型
            status = law.get('status', 0)
            # 确保状态是整数类型
            try:
                status_int = int(status)
            except (ValueError, TypeError):
                status_int = 0
            
            is_valid = (status_int == 1)
            
            candidates.append({
                'title': law_title,
                'score': score,
                'law': law,
                'status': status_int,
                'is_valid': is_valid,
                'status_text': '有效' if is_valid else '失效'
            })
        
        # 按分数排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 调试信息
        self.logger.debug(f"    匹配候选项:")
        for candidate in candidates[:5]:  # 显示前5个
            self.logger.debug(f"      {candidate['title']}: {candidate['score']:.3f} ({candidate['status_text']})")
        
        # 设置匹配阈值
        threshold = 0.75
        
        # 筛选出达到阈值的候选项
        qualified_candidates = [c for c in candidates if c['score'] >= threshold]
        
        if not qualified_candidates:
            self.logger.debug(f"    没有候选项达到阈值 {threshold}")
            return None
        
        # 优先级选择逻辑
        # 1. 优先选择有效的法规
        valid_candidates = [c for c in qualified_candidates if c['is_valid']]
        
        if valid_candidates:
            # 有有效法规，选择分数最高的有效法规
            best_candidate = valid_candidates[0]  # 已按分数排序
            self.logger.debug(f"    优先选择有效法规: {best_candidate['title']} (分数: {best_candidate['score']:.3f}, 状态: {best_candidate['status_text']})")
            return best_candidate['law']
        else:
            # 没有有效法规，选择分数最高的失效法规
            best_candidate = qualified_candidates[0]  # 已按分数排序
            self.logger.debug(f"    无有效法规，选择失效法规: {best_candidate['title']} (分数: {best_candidate['score']:.3f}, 状态: {best_candidate['status_text']})")
            return best_candidate['law']
    
    def generate_search_keywords(self, law_name: str) -> List[str]:
        """生成搜索关键词"""
        keywords = []
        
        # 1. 完整名称
        keywords.append(law_name)
        
        # 2. 移除"中华人民共和国"前缀
        if law_name.startswith("中华人民共和国"):
            keywords.append(law_name.replace("中华人民共和国", ""))
        
        # 3. 提取主干名称（移除括号内容）
        main_name = re.sub(r'[（(].*?[）)]', '', law_name)
        if main_name != law_name and main_name.strip():
            keywords.append(main_name.strip())
        
        # 4. 提取核心词汇
        if "法" in law_name:
            # 提取"法"前面的部分
            parts = law_name.split("法")
            if parts[0]:
                core_name = parts[0] + "法"
                if core_name not in keywords:
                    keywords.append(core_name)
        
        # 5. 对于办法、条例等，尝试不同的搜索策略
        if any(word in law_name for word in ["办法", "条例", "规定", "细则"]):
            # 提取关键词组合
            for suffix in ["办法", "条例", "规定", "细则"]:
                if suffix in law_name:
                    # 找到第一个关键词
                    parts = law_name.split(suffix)
                    if parts[0]:
                        # 尝试不同长度的关键词
                        base = parts[0].strip()
                        # 移除修订年份
                        base = re.sub(r'[（(].*?[）)]', '', base).strip()
                        if base and len(base) >= 4:  # 至少4个字符
                            keywords.append(base + suffix)
                            # 尝试更短的关键词
                            if len(base) > 6:
                                keywords.append(base[-6:] + suffix)
        
        # 去重并过滤空字符串
        keywords = list(dict.fromkeys([k for k in keywords if k.strip()]))  # 保持顺序的去重
        
        return keywords
    
    def extract_document_number(self, detail: dict) -> str:
        """提取文号"""
        try:
            # 方法1: 从otherFile列表中的主席令文件名提取文号
            other_files = detail.get('otherFile', [])
            if isinstance(other_files, list):
                for file_info in other_files:
                    if isinstance(file_info, dict):
                        file_name = file_info.get('name', '')
                        if '主席令' in file_name:
                            # 提取主席令号码
                            import re
                            # 匹配各种主席令格式
                            patterns = [
                                r'主席令（第(\w+)号）',  # 主席令（第三十一号）
                                r'主席令第(\w+)号',      # 主席令第一二〇号
                                r'主席令.*?(\d+)号',     # 包含数字的主席令
                            ]
                            for pattern in patterns:
                                match = re.search(pattern, file_name)
                                if match:
                                    return f"主席令第{match.group(1)}号"
            
            # 方法2: 从标题中提取（备用方案）
            title = detail.get('title', '')
            if title:
                # 简单的文号提取逻辑，可以根据需要扩展
                return ""
            
            return ""
        except Exception as e:
            self.logger.error(f"提取文号时出错: {e}")
            return ""
    
    def crawl_law_by_search(self, law_name: str) -> Optional[Dict[str, Any]]:
        """通过搜索采集单个法规"""
        self.logger.info(f"搜索法规: {law_name}")
        
        # 生成搜索关键词
        keywords = self.generate_search_keywords(law_name)
        self.logger.debug(f"搜索关键词: {keywords}")
        
        for keyword in keywords:
            self.logger.debug(f"  尝试关键词: {keyword}")
            
            search_results = self.search_law(keyword)
            
            if search_results:
                self.logger.debug(f"    找到 {len(search_results)} 个结果")
                
                # 找到最佳匹配
                best_match = self.find_best_match(law_name, search_results)
                
                if best_match:
                    self.logger.info(f"    ✅ 找到匹配: {best_match.get('title', '')}")
                    self.logger.debug(f"    ID: {best_match.get('id', '')}")
                    
                    # 获取详细信息
                    detail = self.get_law_detail(best_match['id'])
                    if not detail:
                        self.logger.error(f"  ❌ 无法获取详细信息")
                        return None
                    
                    # 提取和整理文件信息
                    body_files = detail.get('body', [])
                    other_files = detail.get('otherFile', [])
                    
                    # 整理正文文件信息
                    formatted_body_files = []
                    if isinstance(body_files, list):
                        for file_info in body_files:
                            if isinstance(file_info, dict):
                                formatted_body_files.append({
                                    'type': file_info.get('type', ''),
                                    'path': file_info.get('path', ''),
                                    'url': file_info.get('url', ''),
                                    'mobile_url': file_info.get('mobile', ''),
                                    'addr': file_info.get('addr', '')
                                })
                    
                    # 整理其他文件信息
                    formatted_other_files = []
                    if isinstance(other_files, list):
                        for file_info in other_files:
                            if isinstance(file_info, dict):
                                formatted_other_files.append({
                                    'name': file_info.get('name', ''),
                                    'type': file_info.get('type', ''),
                                    'hdfs_path': file_info.get('hdfsPath', ''),
                                    'oss_path': file_info.get('ossPath', ''),
                                    'order': file_info.get('order', '')
                                })
                    
                    result_data = {
                        # 基本信息
                        'law_id': best_match.get('id', ''),
                        'target_name': law_name,
                        'search_keyword': keyword,
                        'title': detail.get('title', ''),
                        'document_number': self.extract_document_number(detail),
                        
                        # 日期信息
                        'publish_date': normalize_date_format(detail.get('publish', '')),
                        'implement_date': normalize_date_format(detail.get('expiry', '')),
                        'invalidate_date': '',  # API中没有失效日期字段
                        
                        # 机关和分类信息
                        'office': detail.get('office', ''),
                        'level': detail.get('level', ''),  # 法规级别：法律、行政法规、司法解释等
                        'status': '有效' if detail.get('status', '') == '1' else '失效',
                        
                        # 文件信息
                        'body_files': formatted_body_files,  # 正文文件（WORD/PDF/HTML）
                        'other_files': formatted_other_files,  # 其他文件（主席令等）
                        
                        # 原始数据
                        'raw_api_response': detail,  # 保存完整的API响应
                        
                        # 元数据
                        'source_url': f"https://flk.npc.gov.cn/detail2.html?id={best_match.get('id', '')}",
                        'crawl_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'crawler_version': '1.0.0'
                    }
                    
                    self.logger.info(f"    🔢 文号: {result_data['document_number']}")
                    self.logger.info(f"    📅 发布日期: {result_data['publish_date']}")
                    self.logger.info(f"    📅 实施日期: {result_data['implement_date']}")
                    self.logger.info(f"    🚦 状态: {result_data['status']} (status原值: {detail.get('status', '')})")
                    self.logger.info(f"    🏛️ 发布机关: {result_data['office']}")
                    self.logger.info(f"    📋 法规级别: {result_data['level']}")
                    
                    return result_data
                else:
                    self.logger.warning(f"    ❌ 未找到匹配")
            else:
                self.logger.warning(f"    ❌ 搜索无结果")
            
            time.sleep(1)  # 避免请求过快
        
        self.logger.error(f"  ❌ 所有关键词都未找到匹配")
        return None
    
    async def crawl_law(self, law_name: str, law_number: str = None) -> Optional[Dict]:
        """爬取单个法律（实现CrawlerManager需要的接口）"""
        try:
            self.logger.info(f"人大网爬取: {law_name}")
            
            result = self.crawl_law_by_search(law_name)
            
            if result:
                # 转换为标准格式
                return {
                    'law_id': result.get('law_id', ''),
                    'name': result.get('title', ''),
                    'number': result.get('document_number', ''),
                    'source': 'search_api',
                    'success': True,
                    'source_url': result.get('source_url', ''),
                    'publish_date': result.get('publish_date', ''),
                    'valid_from': result.get('implement_date', ''),
                    'valid_to': result.get('invalidate_date', ''),
                    'office': result.get('office', ''),
                    'status': result.get('status', ''),
                    'level': result.get('level', ''),
                    'crawl_time': result.get('crawl_date', ''),
                    'raw_data': result
                }
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"人大网爬取失败: {law_name}, 错误: {e}")
            return None
    
    def crawl_laws(self, target_laws: List[str]) -> List[Dict[str, Any]]:
        """批量采集法规"""
        self.logger.info("=== 基于搜索的法规采集器 ===")
        self.logger.info(f"目标法规数: {len(target_laws)}")
        
        results = []
        success_count = 0
        
        for i, law_name in enumerate(target_laws, 1):
            self.logger.info(f"进度: {i}/{len(target_laws)}")
            
            result = self.crawl_law_by_search(law_name)
            
            if result:
                results.append(result)
                success_count += 1
                self.logger.info(f"✅ 成功采集: {result['title']}")
            else:
                self.logger.error(f"❌ 采集失败: {law_name}")
            
            self.logger.info("-" * 50)
        
        self.logger.info(f"\n=== 采集完成 ===")
        self.logger.info(f"成功: {success_count}/{len(target_laws)}")
        self.logger.info(f"成功率: {success_count/len(target_laws)*100:.1f}%")
        
        return results 