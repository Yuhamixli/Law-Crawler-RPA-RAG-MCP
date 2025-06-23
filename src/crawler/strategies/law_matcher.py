"""
法规匹配器 - 实现Excel列表与全量法规的精确比对
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from difflib import SequenceMatcher


class LawMatcher:
    """法规匹配器"""
    
    def __init__(self):
        self.all_laws = []
        
    def load_all_laws(self, laws: List[Dict[str, Any]]):
        """加载全量法规列表"""
        self.all_laws = laws
        logger.info(f"加载法规列表: {len(laws)} 条")
        
    def normalize_name(self, name: str) -> str:
        """标准化法规名称"""
        # 移除多余空格
        name = re.sub(r'\s+', '', name)
        # 统一括号
        name = name.replace('（', '(').replace('）', ')')
        # 移除特殊字符
        name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9()（）]', '', name)
        return name
        
    def normalize_number(self, number: str) -> str:
        """标准化法规编号"""
        if not number:
            return ""
        # 提取数字部分
        digits = re.findall(r'\d+', number)
        return ''.join(digits)
        
    def match_law(self, target_name: str, target_number: str = "") -> Optional[Dict[str, Any]]:
        """匹配单个法规"""
        target_name_norm = self.normalize_name(target_name)
        target_number_norm = self.normalize_number(target_number)
        
        best_match = None
        best_score = 0
        
        for law in self.all_laws:
            law_name = law.get("name", "")
            law_number = law.get("number", "")
            
            law_name_norm = self.normalize_name(law_name)
            law_number_norm = self.normalize_number(law_number)
            
            # 计算名称相似度
            name_similarity = SequenceMatcher(None, target_name_norm, law_name_norm).ratio()
            
            # 计算编号匹配度
            number_match = 0
            if target_number_norm and law_number_norm:
                if target_number_norm in law_number_norm or law_number_norm in target_number_norm:
                    number_match = 1
                elif target_number_norm == law_number_norm:
                    number_match = 1
                    
            # 综合评分
            score = name_similarity * 0.7 + number_match * 0.3
            
            if score > best_score and score > 0.6:  # 设置最低匹配阈值
                best_score = score
                best_match = law.copy()
                best_match["match_score"] = score
                best_match["match_type"] = "fuzzy"
                
        # 如果找到匹配，记录匹配信息
        if best_match:
            logger.info(f"匹配成功: {target_name} -> {best_match['name']} (相似度: {best_score:.2f})")
        else:
            logger.warning(f"未找到匹配: {target_name}")
            
        return best_match
        
    def batch_match(self, excel_laws: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量匹配Excel中的法规"""
        results = []
        
        for excel_law in excel_laws:
            name = excel_law.get("名称", "")
            number = excel_law.get("编号", "")
            
            match_result = self.match_law(name, number)
            
            if match_result:
                result = {
                    "excel_name": name,
                    "excel_number": number,
                    "matched_law": match_result,
                    "status": "success"
                }
            else:
                result = {
                    "excel_name": name,
                    "excel_number": number,
                    "matched_law": None,
                    "status": "failed"
                }
                
            results.append(result)
            
        return results
        
    def get_match_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取匹配统计信息"""
        total = len(results)
        success = sum(1 for r in results if r["status"] == "success")
        failed = total - success
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0
        } 