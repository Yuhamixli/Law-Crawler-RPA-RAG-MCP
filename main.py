#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
法律法规采集系统主程序 - 使用双数据源策略
支持：国家法律法规数据库 + 中国政府网

使用方法：
  python main.py                           # 批量爬取（按配置限制）
  python main.py --law "电子招标投标办法"    # 单独搜索指定法规
  python main.py --law "电子招标投标办法" -v # 详细模式显示搜索过程
"""

import asyncio
import os
import pandas as pd
import argparse
import time
from datetime import datetime
from typing import List, Dict, Any

from config.settings import settings
from src.crawler.crawler_manager import CrawlerManager
from src.report.crawl_result_exporter import save_crawl_results

def load_target_laws_from_excel(excel_path: str) -> List[str]:
    """从Excel文件加载目标法规列表"""
    try:
        # 正确读取Excel，使用第一行作为标题
        df = pd.read_excel(excel_path)
        
        # 检查是否有"名称"列
        if "名称" in df.columns:
            laws = df["名称"].dropna().astype(str).tolist()
        else:
            # 如果没有"名称"列，使用第一列
            print("警告：Excel文件中没有找到'名称'列，使用第一列")
            laws = df.iloc[:, 0].dropna().astype(str).tolist()
        
        # 清理数据：去除空白和无效条目
        laws = [law.strip() for law in laws if law.strip() and law.strip() != 'nan']
        return laws
    except Exception as e:
        print(f"读取Excel文件失败: {e}")
        return []

async def save_results(results: List[Dict[str, Any]], target_laws: List[str], output_dir: str = "data"):
    """保存采集结果到各种格式的文件"""
    summary = save_crawl_results(results, target_laws, output_dir)

    print(f"结果已保存:")
    print(f"  简化JSON: {summary.json_file}")
    print(f"  详细JSON: {summary.detailed_json_file} (包含完整API响应)")
    print(f"  Excel: {summary.excel_file}")

    if summary.source_stats:
        print(f"\n[STATS] 数据来源统计:")
        for channel, count in summary.source_stats.items():
            print(f"  - {channel}: {count} 条")


def get_default_law_list() -> List[str]:
    """获取默认的法规列表"""
    return [
        "中华人民共和国反洗钱法",
        "中华人民共和国关税法", 
        "中华人民共和国统计法",
        "中华人民共和国会计法",
        "国家科学技术奖励条例",
        "固定资产投资项目节能审查办法",
        "中华人民共和国农产品质量安全法",
        "最高人民法院、最高人民检察院关于办理危害生产安全刑事案件适用法律若干问题的解释",
        "中华人民共和国科学技术进步法",
        "中华人民共和国安全生产法",
        "中华人民共和国民法典",
        "中华人民共和国疫苗管理法",
        "中华人民共和国药品管理法",
        "中华人民共和国建筑法",
        "房屋建筑和市政基础设施工程施工招标投标管理办法",
        "中华人民共和国产品质量法",
        "中华人民共和国计量法",
        "重点用能单位节能管理办法",
        "建筑工程设计招标投标管理办法",
        "中华人民共和国特种设备安全法"
    ]


async def search_single_law(law_name: str, verbose: bool = False, strategy: int = None):
    """单独搜索指定法规"""
    print("=== 单法规搜索模式 ===")
    print(f"目标法规: {law_name}")
    print(f"详细模式: {'开启' if verbose else '关闭'}")
    
    if strategy:
        strategy_names = {
            1: "国家法律法规数据库",
            2: "HTTP搜索引擎",
            3: "Selenium搜索引擎", 
            4: "Selenium政府网",
            5: "直接URL访问"
        }
        print(f"指定策略: {strategy} - {strategy_names.get(strategy, '未知策略')}")
    else:
        print("数据源: 国家法律法规数据库 + 中国政府网")
    print()
    
    # 创建采集管理器（双数据源）
    crawler_manager = CrawlerManager()
    
    print("开始搜索...")
    result = await crawler_manager.crawl_law(law_name, strategy=strategy)
    
    if result:
        print(f"[SUCCESS] 搜索成功！")
        print(f"   来源: {result.get('source', 'unknown')}")
        print(f"   名称: {result.get('name', '未知')}")
        print(f"   文号: {result.get('number', '无')}")
        print(f"   级别: {result.get('level', '未知')}")
        print(f"   发布日期: {result.get('publish_date', '未知')}")
        print(f"   来源链接: {result.get('source_url', '无')}")
        
        if verbose:
            print(f"\n详细信息:")
            for key, value in result.items():
                if key not in ['raw_data']:  # 跳过过长的原始数据
                    print(f"   {key}: {value}")
        
        # 保存单个结果
        result['target_name'] = law_name
        await save_results([result], [law_name])
        print(f"\n结果已保存到data目录")
        
    else:
        print(f"[FAILED] 搜索失败")
        print(f"   在所有数据源中都未找到 '{law_name}'")
        print(f"   建议检查法规名称是否正确，或尝试简化搜索关键词")


async def _run_batch_processing(batches: List[Dict], strategy: int, target_laws: List[str]) -> tuple:
    """执行分批处理逻辑"""
    all_results = []
    total_start_time = time.time()
    
    for batch_info in batches:
        batch_num = batch_info["batch_num"]
        batch_laws = batch_info["laws"]
        batch_size = batch_info["size"]
        
        print(f"=== [BATCH {batch_num}] 开始处理第{batch_num}批 ===")
        print(f"范围: 第{batch_info['start']}-{batch_info['end']}条法规 (共{batch_size}条)")
        print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
        
        batch_start_time = time.time()
        
        # 准备法规信息列表
        law_list = [{'名称': law_name} for law_name in batch_laws]
        
        # 创建采集管理器
        crawler_manager = CrawlerManager()
        
        try:
            # 执行批次采集
            batch_results = await crawler_manager.crawl_laws_batch(law_list, limit=len(batch_laws), strategy=strategy)
            
            batch_duration = time.time() - batch_start_time
            avg_time = batch_duration / batch_size
            
            print(f"[BATCH {batch_num}] 批次完成!")
            print(f"耗时: {batch_duration:.1f}秒")
            print(f"平均: {avg_time:.2f}秒/法规")
            print(f"结束时间: {datetime.now().strftime('%H:%M:%S')}")
            print()
            
            # 添加到总结果
            all_results.extend(batch_results or [])
            
        except Exception as e:
            print(f"[BATCH {batch_num}] 批次处理失败: {e}")
            
        finally:
            # 清理批次资源
            try:
                await crawler_manager.async_cleanup()
            except Exception as e:
                print(f"清理批次{batch_num}资源时发生错误: {e}")
            
            # 批次间等待（除了最后一批）
            if batch_num < len(batches):
                wait_time = 5  # 5秒间隔
                print(f"等待{wait_time}秒后开始下一批...")
                await asyncio.sleep(wait_time)
    
    total_time = time.time() - total_start_time
    
    # 显示分批处理总结
    print("=" * 60)
    print("分批处理完成 - 总结报告")
    print("=" * 60)
    print(f"总处理时间: {total_time:.1f}秒 ({total_time/60:.1f}分钟)")
    print(f"总法规数: {len(target_laws)}条")
    print(f"成功批次: {len(batches)}/{len(batches)}")
    print(f"平均效率: {total_time/len(target_laws):.2f}秒/法规")
    print()
    
    return all_results, total_time


async def batch_crawl_optimized(limit: int = None, strategy: int = None):
    """批量爬取模式 - 终极优化版本（支持自动分批）"""
    print("=== 批量采集模式 (终极优化版) ===")
    print(f"版本: {settings.version} | 调试模式: {'开启' if settings.debug else '关闭'}")
    
    if strategy:
        strategy_names = {
            1: "国家法律法规数据库",
            2: "HTTP搜索引擎",
            3: "Selenium搜索引擎", 
            4: "Selenium政府网",
            5: "直接URL访问"
        }
        print(f"指定策略: {strategy} - {strategy_names.get(strategy, '未知策略')}")
    else:
        print("策略: 搜索引擎→法规库→优化Selenium (多层并行)")
    print()
    
    # 获取目标法规列表
    excel_path = "Background info/law list.xls"
    if os.path.exists(excel_path):
        print(f"从Excel文件加载法规列表: {excel_path}")
        target_laws = load_target_laws_from_excel(excel_path)
        if not target_laws:
            print("Excel文件为空或格式错误，程序退出")
            return
    else:
        print("Excel文件不存在，程序退出")
        return
    
    # 根据参数或配置决定爬取数量
    if limit is not None:
        crawl_limit = limit
        print(f"根据命令行参数限制，本次仅采集前 {crawl_limit} 条法规")
    else:
        crawl_limit = settings.crawler.crawl_limit
        if crawl_limit > 0:
            print(f"根据配置限制，本次仅采集前 {crawl_limit} 条法规")
        else:
            print(f"无爬取数量限制，将采集全部 {len(target_laws)} 条法规")
    
    if crawl_limit > 0:
        target_laws = target_laws[:crawl_limit]
    
    print(f"目标法规数: {len(target_laws)}")
    if target_laws:
        print("前5个法规:", target_laws[:5])
    print()
    
    # 检查是否需要分批处理
    batch_size = 50
    total_laws = len(target_laws)
    
    if total_laws > batch_size:
        print(f"[BATCH MODE] 法规数量超过{batch_size}条，启用分批处理模式")
        # 计算批次信息
        num_batches = (total_laws + batch_size - 1) // batch_size
        batches = []
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, total_laws)
            batches.append({
                "batch_num": i + 1,
                "start": start_idx + 1,
                "end": end_idx,
                "size": end_idx - start_idx,
                "laws": target_laws[start_idx:end_idx]
            })
        
        print(f"分批策略: {num_batches}批，每批最多{batch_size}条")
        for batch in batches:
            print(f"  第{batch['batch_num']}批: 第{batch['start']}-{batch['end']}条法规 (共{batch['size']}条)")
        print()
        
        # 执行分批处理
        results, total_time = await _run_batch_processing(batches, strategy, target_laws)
        
    else:
        print(f"[NORMAL MODE] 法规数量未超过{batch_size}条，使用常规处理模式")
        # 准备法规信息列表
        law_list = [{'名称': law_name} for law_name in target_laws]
        
        # 创建采集管理器
        crawler_manager = CrawlerManager()
        
        try:
            # 使用终极优化批量爬取
            print("[BATCH] 开始批量采集（终极优化模式）...")
            start_time = time.time()
            
            results = await crawler_manager.crawl_laws_batch(law_list, limit=crawl_limit, strategy=strategy)
            
            total_time = time.time() - start_time
        
        finally:
            # 清理资源
            try:
                await crawler_manager.async_cleanup()
            except Exception as e:
                print(f"清理资源时发生错误: {e}")
    
    # 处理结果和统计（通用部分）
    if results or target_laws:
        await save_results(results, target_laws)
        
        # 统计信息
        success_count = len([r for r in results if r and r.get('success', False)])
        total_count = len(target_laws)
        failed_count = total_count - success_count
        success_rate = success_count / total_count * 100 if total_count > 0 else 0
        avg_time = total_time / total_count if total_count > 0 else 0
        
        print(f"\n=== [COMPLETED] 采集完成（终极优化版）===")
        print(f"目标法规数: {total_count}")
        print(f"成功采集: {success_count}")
        print(f"未找到: {failed_count}")
        print(f"成功率: {success_rate:.1f}%")
        print(f"总耗时: {total_time:.1f}秒")
        print(f"平均耗时: {avg_time:.2f}秒/法规")
        
        # 效率对比显示
        original_estimated_time = total_count * 24  # 原版估计24秒/法规
        efficiency_improvement = ((original_estimated_time - total_time) / original_estimated_time) * 100
        print(f"[OPTIMIZE] 效率提升: {efficiency_improvement:.1f}% (相比原版预估)")
        
        # 显示成功采集的法规按策略分类
        if success_count > 0:
            print(f"\n[SUCCESS LIST] 成功采集的法规（按策略分类）:")
            
            strategy_groups = {}
            for result in results:
                if result and result.get('success'):
                    strategy = result.get('crawler_strategy', 'unknown')
                    if strategy not in strategy_groups:
                        strategy_groups[strategy] = []
                    strategy_groups[strategy].append(result)
            
            strategy_names = {
                'search_engine': '[SE] 搜索引擎',
                'search_based': '[DB] 国家法律法规数据库',
                'optimized_selenium': '[OPT] 优化版Selenium',
                'selenium_gov': '[STD] 标准Selenium',
                'direct_url': '[URL] 直接URL访问'
            }
            
            for strategy, laws in strategy_groups.items():
                strategy_name = strategy_names.get(strategy, f"[UNK] {strategy}")
                print(f"  {strategy_name} ({len(laws)}条):")
                for i, law in enumerate(laws, 1):
                    print(f"    {i}. {law.get('name', law.get('target_name'))} ({law.get('level', '未知级别')})")
        
        # 显示未找到的法规
        if failed_count > 0:
            print(f"\n[FAILED] 未找到的法规 ({failed_count}条):")
            successful_names = {r.get('name', r.get('target_name')) for r in results if r and r.get('success')}
            unfound_count = 0
            for target_law in target_laws:
                if target_law not in successful_names:
                    unfound_count += 1
                    print(f"  - {target_law}")
    else:
        print("[ERROR] 没有目标法规，也未采集到任何信息")
    
    print("[CLEANUP] 批量采集完成")


async def batch_crawl(limit: int = None, strategy: int = None):
    """批量爬取模式（原有功能，保持向后兼容）"""
    print("=== 批量采集模式 ===")
    print(f"版本: {settings.version} | 调试模式: {'开启' if settings.debug else '关闭'}")
    
    if strategy:
        strategy_names = {
            1: "国家法律法规数据库",
            2: "HTTP搜索引擎",
            3: "Selenium搜索引擎", 
            4: "Selenium政府网",
            5: "直接URL访问"
        }
        print(f"指定策略: {strategy} - {strategy_names.get(strategy, '未知策略')}")
    else:
        print("数据源: 国家法律法规数据库 + 中国政府网")
    print()
    
    # 获取目标法规列表
    excel_path = "Background info/law list.xls"
    if os.path.exists(excel_path):
        print(f"从Excel文件加载法规列表: {excel_path}")
        target_laws = load_target_laws_from_excel(excel_path)
        if not target_laws:
            print("Excel文件为空或格式错误，程序退出")
            return
    else:
        print("Excel文件不存在，程序退出")
        return
    
    # 根据参数或配置决定爬取数量
    if limit is not None:
        crawl_limit = limit
        print(f"根据命令行参数限制，本次仅采集前 {crawl_limit} 条法规")
    else:
        crawl_limit = settings.crawler.crawl_limit
        if crawl_limit > 0:
            print(f"根据配置限制，本次仅采集前 {crawl_limit} 条法规")
        else:
            print(f"无爬取数量限制，将采集全部 {len(target_laws)} 条法规")
    
    if crawl_limit > 0:
        target_laws = target_laws[:crawl_limit]
    
    print(f"目标法规数: {len(target_laws)}")
    if target_laws:
        print("前5个法规:", target_laws[:5])
    print()
    
    # 创建采集管理器（双数据源）
    crawler_manager = CrawlerManager()
    
    # 批量采集
    print("开始采集...")
    results = []
    
    for i, law_name in enumerate(target_laws, 1):
        print(f"[{i}/{len(target_laws)}] 处理: {law_name}")
        
        result = await crawler_manager.crawl_law(law_name, strategy=strategy)
        if result and result.get('success', False):
            # 确保包含目标法规名称
            result['target_name'] = law_name
            results.append(result)
            print(f"  [OK] 成功 - 来源: {result.get('source', 'unknown')}")
        else:
            print(f"  [FAIL] 未找到")
    
    # 保存结果
    if results or target_laws: # 即使没有结果也要保存
        await save_results(results, target_laws)
        
        # 统计信息
        success_count = len(results)
        total_count = len(target_laws)
        failed_count = total_count - success_count
        success_rate = success_count / total_count * 100 if total_count > 0 else 0
        
        print(f"\n=== 采集完成 ===")
        print(f"目标法规数: {total_count}")
        print(f"成功采集: {success_count}")
        print(f"未找到: {failed_count}")
        print(f"成功率: {success_rate:.1f}%")
        
        # 显示成功采集的法规按数据源分类
        if success_count > 0:
            print(f"\n[SUCCESS] 成功采集的法规（按数据源分类）:")
            
            # 按数据源分组
            source_groups = {}
            for law in results:
                source = law.get('source', 'unknown')
                if source not in source_groups:
                    source_groups[source] = []
                source_groups[source].append(law)
            
            for source, laws in source_groups.items():
                if source == "search_api":
                    source_name = "国家法律法规数据库"
                elif source == "selenium_gov_web":
                    source_name = "中国政府网(www.gov.cn)"
                elif source == "gov_web":
                    source_name = "中国政府网"
                else:
                    source_name = source
                print(f"  [DB] {source_name} ({len(laws)}条):")
                for i, law in enumerate(laws, 1):
                    print(f"    {i}. {law.get('name', law.get('target_name'))} ({law.get('level', '未知级别')})")
        
        # 显示未找到的法规
        if failed_count > 0:
            print(f"\n[FAILED] 未找到的法规:")
            results_map = {law['target_name']: law for law in results}
            unfound_count = 0
            for target_law in target_laws:
                if target_law not in results_map:
                    unfound_count += 1
                    print(f"  - {target_law}")
    else:
        print("[ERROR] 没有目标法规，也未采集到任何信息")
    
    # 清理资源
    try:
        await crawler_manager.async_cleanup()
    except Exception as e:
        print(f"清理资源时发生错误: {e}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="法律法规采集系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                           # 批量爬取（终极优化版）
  python main.py --limit 10                # 批量爬取前10条（优化版）
  python main.py --legacy                  # 使用原版批量爬取
  python main.py --law "电子招标投标办法"    # 单独搜索指定法规
  python main.py --law "中华人民共和国民法典" -v  # 详细模式
  
策略选择示例:
  python main.py --strategy 1              # 仅使用国家法律法规数据库
  python main.py --strategy 2 --limit 10   # 仅使用HTTP搜索引擎
  python main.py --strategy 3              # 仅使用Selenium搜索引擎
  python main.py --strategy 4              # 仅使用Selenium政府网
  python main.py --strategy 5              # 仅使用直接URL访问
        """
    )
    
    parser.add_argument(
        '--law', '-l',
        type=str,
        help='指定要搜索的单个法规名称'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='限制批量爬取的数量，覆盖配置文件设置'
    )
    
    parser.add_argument(
        '--legacy',
        action='store_true',
        help='使用原版批量爬取模式（逐个处理）'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='详细模式，显示更多信息'
    )
    
    parser.add_argument(
        '--strategy', '-s',
        type=int,
        choices=[1, 2, 3, 4, 5],
        help='''指定爬虫策略（单一策略模式）:
        1 - 国家法律法规数据库（权威数据源）
        2 - HTTP搜索引擎（快速搜索，先直连后代理）
        3 - Selenium搜索引擎（浏览器搜索引擎）
        4 - Selenium政府网（针对政府网优化）
        5 - 直接URL访问（最后保障）
        不指定则使用默认多层策略'''
    )
    
    return parser.parse_args()


async def main():
    """主函数 - 根据参数选择运行模式"""
    args = parse_args()
    
    if args.law:
        # 单法规搜索模式
        await search_single_law(args.law, args.verbose, args.strategy)
    else:
        # 批量爬取模式
        if args.legacy:
            # 使用原版批量爬取模式
            await batch_crawl(args.limit, args.strategy)
        else:
            # 使用终极优化版批量爬取模式（默认）
            await batch_crawl_optimized(args.limit, args.strategy)


if __name__ == "__main__":
    # 确保日志和数据目录存在
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        import traceback
        print(f"\n程序发生未知错误: {e}")
        if settings.debug:
            print("详细错误信息:")
            traceback.print_exc()
    finally:
        # 确保清理所有WebDriver实例
        try:
            from src.crawler.utils.webdriver_manager import cleanup_webdrivers
            asyncio.run(cleanup_webdrivers())
            print("WebDriver清理完成")
        except Exception as e:
            print(f"清理WebDriver时发生错误: {e}")
