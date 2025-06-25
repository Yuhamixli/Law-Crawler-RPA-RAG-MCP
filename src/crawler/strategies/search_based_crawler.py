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
        self.setup_headers()
        self.base_url = "https://flk.npc.gov.cn"
        
        # WAF状态追踪
        self.waf_triggered = False
        self.consecutive_waf_count = 0
        self.last_successful_time = time.time()
        
        # 初始化访问，获取必要的cookies
        self._initialize_session()
    
    def setup_headers(self):
        """设置请求头 - 增强版，模拟真实浏览器"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://flk.npc.gov.cn/',
            'Origin': 'https://flk.npc.gov.cn',
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
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
        """使用Selenium搜索法规 - WAF绕过方案"""
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
            
            # 启动浏览器
            driver = webdriver.Chrome(options=chrome_options)
            wait = WebDriverWait(driver, 10)
            
            self.logger.debug(f"    使用Selenium搜索: {keyword}")
            
            # 访问搜索页面
            driver.get("https://flk.npc.gov.cn/fl.html")
            
            # 等待页面加载
            wait.until(EC.presence_of_element_located((By.ID, "fgbt")))
            
            # 输入搜索关键词
            search_input = driver.find_element(By.ID, "fgbt")
            search_input.clear()
            search_input.send_keys(keyword)
            
            # 点击搜索按钮
            search_button = driver.find_element(By.CSS_SELECTOR, ".search_btn")
            search_button.click()
            
            # 等待搜索结果
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".search_result")))
            
            # 解析搜索结果
            results = []
            result_items = driver.find_elements(By.CSS_SELECTOR, ".search_result .result_item")
            
            for item in result_items:
                try:
                    title_element = item.find_element(By.CSS_SELECTOR, ".title a")
                    title = title_element.text.strip()
                    link = title_element.get_attribute("href")
                    
                    # 提取法规ID
                    law_id = ""
                    if "id=" in link:
                        law_id = link.split("id=")[1].split("&")[0]
                    
                    # 获取其他信息
                    info_elements = item.find_elements(By.CSS_SELECTOR, ".info span")
                    publish_date = ""
                    status = 1  # 默认有效
                    
                    for info_elem in info_elements:
                        text = info_elem.text.strip()
                        if "发布日期" in text:
                            publish_date = text.replace("发布日期：", "")
                        elif "失效" in text:
                            status = 5
                    
                    result = {
                        'id': law_id,
                        'title': title,
                        'link': link,
                        'publish_date': publish_date,
                        'status': status
                    }
                    results.append(result)
                    
                except Exception as e:
                    self.logger.warning(f"解析搜索结果项失败: {str(e)}")
                    continue
            
            self.logger.debug(f"    Selenium搜索找到 {len(results)} 个结果")
            return results
            
        except Exception as e:
            self.logger.error(f"Selenium搜索失败: {str(e)}")
            return []
        finally:
            if driver:
                driver.quit()
    
    def search_law(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索法规 - 智能版：优先API，WAF激活时自动切换Selenium"""
        
        # 如果WAF已激活，直接使用Selenium
        if self.waf_triggered:
            self.logger.debug(f"    WAF已激活，直接使用Selenium搜索")
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
            selenium_results = self.search_law_selenium(keyword)
            
            # 如果Selenium成功而API失败，说明可能是WAF问题
            if selenium_results:
                self._handle_waf_detection(True)  # 标记可能的WAF拦截
            
            return selenium_results
    
    def _search_law_http(self, keyword: str) -> List[Dict[str, Any]]:
        """HTTP API搜索法规 - 增强WAF检测"""
        search_strategies = [
            ("title;vague", keyword),  # 标题模糊搜索
            ("title;accurate;1,3", keyword),  # 标题精确搜索（法律+行政法规）
        ]
        
        for search_type, search_keyword in search_strategies:
            # 检查是否需要WAF冷却等待
            self._should_wait_for_waf()
            
            params = [
                ("type", search_type),
                ("searchType", "title;vague" if "vague" in search_type else "title;accurate"),
                ("sortTr", "f_bbrq_s;desc"),
                ("gbrqStart", ""),
                ("gbrqEnd", ""),
                ("sxrqStart", ""),
                ("sxrqEnd", ""),
                ("sort", "true"),
                ("page", "1"),
                ("size", "20"),
                ("fgbt", keyword),  # 搜索关键词
                ("_", int(time.time() * 1000)),
            ]
            
            try:
                self.logger.debug(f"    尝试API搜索策略: {search_type}")
                
                # 添加随机延迟，避免触发WAF
                if self.consecutive_waf_count > 0:
                    delay = random.uniform(2, 5)
                    self.logger.debug(f"    添加随机延迟: {delay:.1f}秒")
                    time.sleep(delay)
                
                response = self.session.get(
                    "https://flk.npc.gov.cn/api/",
                    params=params,
                    timeout=15
                )
                
                # 详细的响应检查
                self.logger.debug(f"    API响应状态码: {response.status_code}")
                content_type = response.headers.get('Content-Type', '')
                self.logger.debug(f"    API响应Content-Type: {content_type}")
                
                if response.status_code == 200:
                    # 检查是否被WAF拦截
                    waf_detected = self._check_waf_response(response)
                    
                    if waf_detected:
                        self.logger.debug(f"    检测到WAF拦截 (策略: {search_type})")
                        self._handle_waf_detection(True)
                        continue  # 尝试下一个策略
                    
                    # 正常JSON响应
                    if not response.text.strip():
                        self.logger.debug(f"    API返回空内容 (策略: {search_type})")
                        continue
                        
                    try:
                        result = response.json()
                        if result.get('success') and result.get('result', {}).get('data'):
                            results = result['result']['data']
                            self.logger.debug(f"    API搜索成功: {len(results)} 个结果 (策略: {search_type})")
                            self._handle_waf_detection(False)  # 成功，重置WAF状态
                            return results
                        else:
                            self.logger.debug(f"    API搜索无结果 (策略: {search_type})")
                    except json.JSONDecodeError as e:
                        self.logger.debug(f"    JSON解析失败 (策略: {search_type}): {str(e)}")
                        # 可能是WAF返回的HTML
                        self._handle_waf_detection(True)
                        continue
                else:
                    self.logger.debug(f"    API HTTP错误 (策略: {search_type}): {response.status_code}")
                    
            except Exception as e:
                self.logger.debug(f"    API请求异常 (策略: {search_type}): {str(e)}")
                continue
        
        self.logger.debug(f"    所有API搜索策略都失败")
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
    
    def _should_wait_for_waf(self) -> bool:
        """判断是否需要等待WAF冷却"""
        if not self.waf_triggered:
            return False
        
        # 如果WAF被触发，等待一定时间再尝试
        time_since_last_success = time.time() - self.last_successful_time
        if time_since_last_success < 60:  # 60秒冷却时间
            wait_time = 60 - time_since_last_success
            self.logger.info(f"⏱️ WAF冷却中，等待 {wait_time:.1f} 秒...")
            time.sleep(wait_time)
        
        return True
    
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