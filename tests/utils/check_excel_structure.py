#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查Excel文件结构
"""

import pandas as pd

def check_excel_structure():
    """检查Excel文件结构"""
    
    excel_files = [
        "Background info/law list.xls",
        "test_batch.xlsx"
    ]
    
    for file_path in excel_files:
        try:
            print(f"\n=== 检查文件: {file_path} ===")
            
            # 读取Excel文件
            df = pd.read_excel(file_path)
            
            print(f"形状: {df.shape}")
            print(f"列名: {list(df.columns)}")
            print(f"前5行:")
            print(df.head())
            print(f"数据类型:")
            print(df.dtypes)
            
            # 检查第一列的数据类型
            first_col = df.iloc[:, 0]
            print(f"\n第一列数据类型: {first_col.dtype}")
            print(f"第一列前10个值:")
            for i, val in enumerate(first_col.head(10)):
                print(f"  {i}: {val} (类型: {type(val)})")
                
        except Exception as e:
            print(f"❌ 读取 {file_path} 失败: {e}")

if __name__ == "__main__":
    check_excel_structure() 