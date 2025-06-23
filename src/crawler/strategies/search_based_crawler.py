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


class SearchBasedCrawler(BaseCrawler):
    """基于搜索的法规采集器"""
    
    def __init__(self):
        super().__init__("search_api")
        self.setup_headers()
        self.logger = logger
        
    def setup_headers(self):
        """设置请求头，参考示例项目的成功配置"""
        self.session = requests.Session()
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
            "cookie": "yfx_c_g_u_id_10006696=_ck22022520424713255117764923111; cna=NdafGk8tiAgCAd9IPxhfROag; yfx_f_l_v_t_10006696=f_t_1645792967326__r_t_1646401808964__v_t_1646401808964__r_c_5; Hm_lvt_54434aa6770b6d9fef104d146430b53b=1646407223,1646570042,1646666110,1647148584; acw_tc=75a1461516471485843844814eb808af266b8ede0e0502ec1c46ab1581; Hm_lpvt_54434aa6770b6d9fef104d146430b53b=1647148626",
        })
    
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
    
    def search_law(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索法规"""
        params = [
            ("searchType", "title;accurate;1,3"),
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
            response = self.session.get(
                "https://flk.npc.gov.cn/api/",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('result', {}).get('data'):
                    return result['result']['data']
            
            return []
            
        except Exception as e:
            self.logger.error(f"搜索法规失败: {str(e)}")
            return []
    
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
        """计算匹配分数"""
        if target == result:
            return 1.0
        
        # 计算包含关系
        if target in result:
            return 0.8 + (len(target) / len(result)) * 0.2
        if result in target:
            return 0.8 + (len(result) / len(target)) * 0.2
        
        # 计算公共子串
        common_length = 0
        for i in range(min(len(target), len(result))):
            if target[i] == result[i]:
                common_length += 1
            else:
                break
        
        if common_length > 0:
            return common_length / max(len(target), len(result))
        
        return 0.0
    
    def find_best_match(self, target_name: str, search_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """在搜索结果中找到最佳匹配"""
        if not search_results:
            return None
        
        # 标准化目标名称
        target_normalized = self.normalize_law_name(target_name)
        
        best_match = None
        best_score = 0
        
        for law in search_results:
            law_title = law.get('title', '')
            law_normalized = self.normalize_law_name(law_title)
            
            # 计算匹配分数
            score = self.calculate_match_score(target_normalized, law_normalized)
            
            if score > best_score:
                best_score = score
                best_match = law
        
        # 只有匹配分数足够高才返回
        if best_score >= 0.7:  # 70%匹配度
            return best_match
        
        return None
    
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
        if main_name != law_name:
            keywords.append(main_name.strip())
        
        # 4. 提取核心词汇
        if "法" in law_name:
            # 提取"法"前面的部分
            parts = law_name.split("法")
            if parts[0]:
                keywords.append(parts[0] + "法")
        
        # 去重并过滤空字符串
        keywords = list(set([k for k in keywords if k.strip()]))
        
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