#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分批测试脚本 - 194条法规分4批测试
第1批：1-50条
第2批：51-100条  
第3批：101-150条
第4批：151-194条（44条）
"""

import asyncio
import time
import os
from datetime import datetime
from pathlib import Path

# 添加项目路径
import sys
sys.path.append(os.path.dirname(__file__))

from main import batch_crawl_optimized

class BatchTestRunner:
    def __init__(self):
        self.total_laws = 194
        self.batch_size = 50
        self.batches = [
            {"start": 1, "end": 50, "size": 50},
            {"start": 51, "end": 100, "size": 50}, 
            {"start": 101, "end": 150, "size": 50},
            {"start": 151, "end": 194, "size": 44}
        ]
        self.results = []
        
        # 创建测试日志目录
        self.log_dir = Path("batch_test_logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 生成时间戳
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def log_message(self, message):
        """记录消息到控制台和文件"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        print(formatted_msg)
        
        # 写入总日志文件
        with open(self.log_dir / f"batch_test_{self.timestamp}.log", "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    
    async def run_single_batch(self, batch_num, batch_info):
        """运行单个批次的测试"""
        start_idx = batch_info["start"] - 1  # 转换为0-based索引
        batch_size = batch_info["size"]
        
        self.log_message(f"=" * 60)
        self.log_message(f"开始第{batch_num}批测试")
        self.log_message(f"范围: 第{batch_info['start']}-{batch_info['end']}条法规 (共{batch_size}条)")
        self.log_message(f"开始时间: {datetime.now()}")
        
        batch_start_time = time.time()
        
        try:
            # 设置offset参数，让系统从指定位置开始读取
            # 需要修改main.py来支持offset参数，这里先用limit模拟
            
            # 由于当前main.py不支持offset，我们需要另想办法
            # 先运行完整测试，然后截取结果
            self.log_message(f"正在执行批次测试...")
            
            # 临时方案：修改Excel读取来支持范围
            await self.run_batch_with_range(start_idx, batch_size)
            
            batch_duration = time.time() - batch_start_time
            avg_time = batch_duration / batch_size
            
            batch_result = {
                "batch_num": batch_num,
                "range": f"{batch_info['start']}-{batch_info['end']}",
                "size": batch_size,
                "duration": batch_duration,
                "avg_time": avg_time,
                "success": True,
                "timestamp": datetime.now()
            }
            
            self.results.append(batch_result)
            
            self.log_message(f"第{batch_num}批完成!")
            self.log_message(f"耗时: {batch_duration:.1f}秒")
            self.log_message(f"平均: {avg_time:.2f}秒/法规")
            self.log_message(f"结束时间: {datetime.now()}")
            
            return batch_result
            
        except Exception as e:
            batch_duration = time.time() - batch_start_time
            self.log_message(f"第{batch_num}批测试失败: {e}")
            self.log_message(f"运行时间: {batch_duration:.1f}秒")
            
            batch_result = {
                "batch_num": batch_num,
                "range": f"{batch_info['start']}-{batch_info['end']}",
                "size": batch_size,
                "duration": batch_duration,
                "avg_time": 0,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now()
            }
            
            self.results.append(batch_result)
            return batch_result
    
    async def run_batch_with_range(self, start_idx, batch_size):
        """运行指定范围的批次测试"""
        # 临时创建一个修改版的测试函数
        import pandas as pd
        
        # 读取Excel文件
        excel_path = "Background info/law list.xls"
        df = pd.read_excel(excel_path)
        
        # 提取指定范围的法规
        batch_df = df.iloc[start_idx:start_idx + batch_size]
        target_laws = batch_df.iloc[:, 0].tolist()  # 假设法规名称在第一列
        
        self.log_message(f"提取到{len(target_laws)}条法规:")
        for i, law in enumerate(target_laws[:5], 1):
            self.log_message(f"  {i}. {law}")
        if len(target_laws) > 5:
            self.log_message(f"  ... 还有{len(target_laws)-5}条")
        
        # 将法规列表保存到临时文件，然后调用测试
        temp_excel = self.log_dir / f"temp_batch_{start_idx}_{batch_size}.xlsx"
        batch_df.to_excel(temp_excel, index=False)
        
        # 备份原Excel文件并替换
        original_excel = Path(excel_path)
        backup_excel = self.log_dir / f"backup_original.xlsx"
        
        import shutil
        shutil.copy2(original_excel, backup_excel)
        shutil.copy2(temp_excel, original_excel)
        
        try:
            # 运行测试
            await batch_crawl_optimized(limit=batch_size)
        finally:
            # 恢复原Excel文件
            shutil.copy2(backup_excel, original_excel)
            # 清理临时文件
            if temp_excel.exists():
                temp_excel.unlink()
            if backup_excel.exists():
                backup_excel.unlink()
    
    async def run_all_batches(self, wait_between_batches=30):
        """运行所有批次的测试"""
        self.log_message("=" * 80)
        self.log_message("法律爬虫分批测试开始")
        self.log_message(f"总法规数: {self.total_laws}条")
        self.log_message(f"分批策略: 4批，每批最多{self.batch_size}条")
        self.log_message(f"批次间隔: {wait_between_batches}秒")
        self.log_message(f"测试开始时间: {datetime.now()}")
        self.log_message("=" * 80)
        
        total_start_time = time.time()
        
        for i, batch_info in enumerate(self.batches, 1):
            # 运行批次
            await self.run_single_batch(i, batch_info)
            
            # 批次间等待（除了最后一批）
            if i < len(self.batches):
                self.log_message(f"等待{wait_between_batches}秒后开始下一批...")
                await asyncio.sleep(wait_between_batches)
        
        total_duration = time.time() - total_start_time
        
        # 生成总结报告
        self.generate_final_report(total_duration)
    
    def generate_final_report(self, total_duration):
        """生成最终测试报告"""
        self.log_message("=" * 80)
        self.log_message("分批测试完成 - 总结报告")
        self.log_message("=" * 80)
        
        successful_batches = [r for r in self.results if r["success"]]
        failed_batches = [r for r in self.results if not r["success"]]
        
        total_laws_tested = sum(r["size"] for r in self.results)
        total_test_time = sum(r["duration"] for r in self.results)
        
        self.log_message(f"总测试时间: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
        self.log_message(f"纯测试时间: {total_test_time:.1f}秒 (不含等待)")
        self.log_message(f"总法规数: {total_laws_tested}条")
        self.log_message(f"成功批次: {len(successful_batches)}/{len(self.results)}")
        
        if successful_batches:
            avg_time_per_law = total_test_time / total_laws_tested
            self.log_message(f"平均效率: {avg_time_per_law:.2f}秒/法规")
        
        self.log_message("\n各批次详细信息:")
        for result in self.results:
            status = "成功" if result["success"] else "失败"
            self.log_message(f"  第{result['batch_num']}批 ({result['range']}): "
                           f"{status} - {result['duration']:.1f}秒 - "
                           f"{result['avg_time']:.2f}秒/法规")
            
            if not result["success"]:
                self.log_message(f"    错误: {result.get('error', '未知错误')}")
        
        # 保存详细报告到文件
        report_file = self.log_dir / f"batch_test_report_{self.timestamp}.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("法律爬虫分批测试报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"测试时间: {datetime.now()}\n")
            f.write(f"总耗时: {total_duration:.1f}秒\n")
            f.write(f"总法规数: {total_laws_tested}条\n")
            f.write(f"成功批次: {len(successful_batches)}/{len(self.results)}\n\n")
            
            for result in self.results:
                f.write(f"批次{result['batch_num']} ({result['range']}):\n")
                f.write(f"  状态: {'成功' if result['success'] else '失败'}\n")
                f.write(f"  耗时: {result['duration']:.1f}秒\n")
                f.write(f"  效率: {result['avg_time']:.2f}秒/法规\n")
                if not result["success"]:
                    f.write(f"  错误: {result.get('error', '未知')}\n")
                f.write("\n")
        
        self.log_message(f"\n详细报告已保存: {report_file}")
        self.log_message("=" * 80)

async def main():
    """主函数"""
    runner = BatchTestRunner()
    
    print("法律爬虫分批测试程序")
    print("=" * 50)
    print("测试计划:")
    print("  第1批: 1-50条法规")
    print("  第2批: 51-100条法规")
    print("  第3批: 101-150条法规") 
    print("  第4批: 151-194条法规 (44条)")
    print("=" * 50)
    
    confirm = input("确认开始分批测试? (y/N): ").strip().lower()
    if confirm != 'y':
        print("测试已取消")
        return
    
    wait_time = input("批次间等待时间（秒，默认30）: ").strip()
    try:
        wait_time = int(wait_time) if wait_time else 30
    except:
        wait_time = 30
    
    print(f"\n开始分批测试，批次间隔{wait_time}秒...")
    await runner.run_all_batches(wait_between_batches=wait_time)

if __name__ == "__main__":
    asyncio.run(main()) 