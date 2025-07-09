#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Strategy1 批量测试运行器
自动化测试不同参数组合，找出反爬临界点

功能：
- 测试不同请求间隔和数量的组合
- 自动分析最佳参数范围
- 生成综合测试报告
- 提供反爬策略建议

使用方法：
python batch_test_runner.py --config batch_test_config.json
"""

import asyncio
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from test_strategy1_anti_crawler import Strategy1AntiCrawlerTester

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'batch_test_logs/batch_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BatchTestRunner:
    """批量测试运行器"""
    
    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.output_dir = Path("batch_test_logs")
        self.output_dir.mkdir(exist_ok=True)
        
        # 测试结果
        self.batch_results: List[Dict[str, Any]] = []
        
        logger.info("🚀 批量测试运行器初始化完成")
        logger.info(f"📋 配置: {self.config}")
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """加载测试配置"""
        default_config = {
            "test_scenarios": [
                {
                    "name": "快速测试",
                    "request_count": 50,
                    "interval": 0.1,
                    "description": "高频率短时间测试，快速触发反爬"
                },
                {
                    "name": "正常测试",
                    "request_count": 100,
                    "interval": 0.5,
                    "description": "中等频率测试，模拟正常使用"
                },
                {
                    "name": "保守测试",
                    "request_count": 200,
                    "interval": 1.0,
                    "description": "低频率长时间测试，避免触发反爬"
                },
                {
                    "name": "极限测试",
                    "request_count": 500,
                    "interval": 0.05,
                    "description": "极高频率测试，测试系统极限"
                }
            ],
            "analysis_settings": {
                "success_rate_threshold": 80.0,
                "waf_trigger_threshold": 5,
                "response_time_threshold": 2.0
            }
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"📁 加载配置文件: {config_file}")
                return config
            except Exception as e:
                logger.warning(f"⚠️ 配置文件加载失败: {e}，使用默认配置")
        
        # 保存默认配置
        default_config_file = "batch_test_config.json"
        with open(default_config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        logger.info(f"📁 创建默认配置文件: {default_config_file}")
        
        return default_config
    
    async def run_single_scenario(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """运行单个测试场景"""
        logger.info(f"🎯 开始测试场景: {scenario['name']}")
        logger.info(f"📊 参数: 请求数={scenario['request_count']}, 间隔={scenario['interval']}秒")
        
        # 创建测试器
        tester = Strategy1AntiCrawlerTester(
            max_requests=scenario['request_count'],
            interval=scenario['interval'],
            output_dir=self.output_dir / scenario['name']
        )
        
        # 运行测试
        start_time = datetime.now()
        await tester.run_stress_test()
        end_time = datetime.now()
        
        # 分析结果
        result = self._analyze_scenario_result(tester, scenario, start_time, end_time)
        
        logger.info(f"✅ 场景 '{scenario['name']}' 测试完成")
        logger.info(f"📊 成功率: {result['success_rate']:.1f}%, WAF触发: {result['waf_triggered']}")
        
        return result
    
    def _analyze_scenario_result(self, tester: Strategy1AntiCrawlerTester, 
                               scenario: Dict[str, Any], 
                               start_time: datetime, 
                               end_time: datetime) -> Dict[str, Any]:
        """分析单个场景的测试结果"""
        duration = (end_time - start_time).total_seconds()
        
        # 基础统计
        success_rate = (tester.successful_requests / tester.total_requests) * 100 if tester.total_requests > 0 else 0
        avg_response_time = sum(r.response_time for r in tester.test_results) / len(tester.test_results) if tester.test_results else 0
        
        # 计算请求速率
        actual_rps = tester.total_requests / duration if duration > 0 else 0
        
        # 找到WAF触发点
        waf_trigger_point = None
        for i, result in enumerate(tester.test_results):
            if result.is_waf_blocked:
                waf_trigger_point = i + 1
                break
        
        # 计算成功率下降点
        success_decline_point = None
        if len(tester.test_results) > 10:
            window_size = 10
            for i in range(window_size, len(tester.test_results)):
                window_success = sum(1 for r in tester.test_results[i-window_size:i] if r.success)
                window_success_rate = (window_success / window_size) * 100
                if window_success_rate < 50:  # 成功率低于50%
                    success_decline_point = i
                    break
        
        # 评估等级
        evaluation = self._evaluate_scenario(success_rate, tester.waf_triggered, avg_response_time)
        
        return {
            "scenario_name": scenario['name'],
            "scenario_config": scenario,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "total_requests": tester.total_requests,
            "successful_requests": tester.successful_requests,
            "failed_requests": tester.failed_requests,
            "waf_blocked_requests": tester.waf_blocked_requests,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "actual_rps": actual_rps,
            "waf_triggered": tester.waf_triggered,
            "ip_blocked": tester.ip_blocked,
            "rate_limited": tester.rate_limited,
            "waf_trigger_point": waf_trigger_point,
            "success_decline_point": success_decline_point,
            "max_consecutive_failures": tester.max_consecutive_failures,
            "evaluation": evaluation
        }
    
    def _evaluate_scenario(self, success_rate: float, waf_triggered: bool, avg_response_time: float) -> Dict[str, Any]:
        """评估场景结果"""
        thresholds = self.config['analysis_settings']
        
        # 评分逻辑
        score = 0
        
        # 成功率评分 (40分)
        if success_rate >= thresholds['success_rate_threshold']:
            score += 40
        elif success_rate >= 60:
            score += 30
        elif success_rate >= 40:
            score += 20
        else:
            score += 10
        
        # WAF触发评分 (30分)
        if not waf_triggered:
            score += 30
        else:
            score += 10
        
        # 响应时间评分 (30分)
        if avg_response_time <= thresholds['response_time_threshold']:
            score += 30
        elif avg_response_time <= 5.0:
            score += 20
        else:
            score += 10
        
        # 确定等级
        if score >= 90:
            level = "优秀"
            color = "green"
        elif score >= 70:
            level = "良好"
            color = "blue"
        elif score >= 50:
            level = "一般"
            color = "orange"
        else:
            level = "差"
            color = "red"
        
        return {
            "score": score,
            "level": level,
            "color": color,
            "recommendations": self._get_recommendations(success_rate, waf_triggered, avg_response_time)
        }
    
    def _get_recommendations(self, success_rate: float, waf_triggered: bool, avg_response_time: float) -> List[str]:
        """获取改进建议"""
        recommendations = []
        
        if success_rate < 80:
            recommendations.append("建议降低请求频率，增加间隔时间")
        
        if waf_triggered:
            recommendations.append("建议使用代理IP或更换User-Agent")
            recommendations.append("考虑添加更多随机延迟")
        
        if avg_response_time > 2.0:
            recommendations.append("响应时间较长，建议优化网络连接")
        
        if not recommendations:
            recommendations.append("当前参数配置良好，可以继续使用")
        
        return recommendations
    
    async def run_all_scenarios(self):
        """运行所有测试场景"""
        logger.info("🚀 开始批量测试...")
        
        total_scenarios = len(self.config['test_scenarios'])
        
        for i, scenario in enumerate(self.config['test_scenarios']):
            logger.info(f"📋 [{i+1}/{total_scenarios}] 准备测试场景: {scenario['name']}")
            
            try:
                result = await self.run_single_scenario(scenario)
                self.batch_results.append(result)
                
                # 添加间隔，避免对服务器造成过大压力
                if i < total_scenarios - 1:
                    logger.info("⏱️ 等待10秒后继续下一个场景...")
                    await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"❌ 场景 '{scenario['name']}' 测试失败: {e}")
                # 记录失败结果
                self.batch_results.append({
                    "scenario_name": scenario['name'],
                    "error": str(e),
                    "success_rate": 0,
                    "evaluation": {"level": "错误", "score": 0}
                })
        
        logger.info("🏁 所有场景测试完成")
        
        # 生成综合报告
        self.generate_comprehensive_report()
    
    def generate_comprehensive_report(self):
        """生成综合测试报告"""
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建综合报告
        report = {
            "报告时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "测试配置": self.config,
            "场景结果": self.batch_results,
            "综合分析": self._generate_comprehensive_analysis(),
            "建议参数": self._suggest_optimal_parameters()
        }
        
        # 保存JSON报告
        json_file = self.output_dir / f"comprehensive_report_{report_time}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 生成CSV总结
        csv_data = []
        for result in self.batch_results:
            if 'error' not in result:
                csv_data.append({
                    "场景名称": result['scenario_name'],
                    "请求数": result['total_requests'],
                    "间隔(秒)": result['scenario_config']['interval'],
                    "成功率(%)": f"{result['success_rate']:.1f}",
                    "WAF触发": result['waf_triggered'],
                    "平均响应时间(秒)": f"{result['avg_response_time']:.3f}",
                    "实际RPS": f"{result['actual_rps']:.2f}",
                    "评估等级": result['evaluation']['level'],
                    "评分": result['evaluation']['score']
                })
        
        if csv_data:
            csv_file = self.output_dir / f"comprehensive_summary_{report_time}.csv"
            df = pd.DataFrame(csv_data)
            df.to_csv(csv_file, index=False, encoding='utf-8')
        
        # 生成图表
        self.generate_comprehensive_charts(report_time)
        
        # 打印报告
        self.print_comprehensive_report(report)
        
        logger.info(f"📁 综合报告已保存:")
        logger.info(f"   JSON报告: {json_file}")
        if csv_data:
            logger.info(f"   CSV总结: {csv_file}")
    
    def _generate_comprehensive_analysis(self) -> Dict[str, Any]:
        """生成综合分析"""
        if not self.batch_results:
            return {}
        
        # 过滤掉出错的结果
        valid_results = [r for r in self.batch_results if 'error' not in r]
        
        if not valid_results:
            return {"error": "没有有效的测试结果"}
        
        # 统计分析
        success_rates = [r['success_rate'] for r in valid_results]
        response_times = [r['avg_response_time'] for r in valid_results]
        waf_triggered_count = sum(1 for r in valid_results if r['waf_triggered'])
        
        # 找出最佳和最差场景
        best_scenario = max(valid_results, key=lambda x: x['evaluation']['score'])
        worst_scenario = min(valid_results, key=lambda x: x['evaluation']['score'])
        
        # 反爬临界点分析
        waf_trigger_points = [r['waf_trigger_point'] for r in valid_results if r['waf_trigger_point']]
        
        return {
            "场景总数": len(valid_results),
            "平均成功率": np.mean(success_rates),
            "成功率标准差": np.std(success_rates),
            "平均响应时间": np.mean(response_times),
            "WAF触发场景数": waf_triggered_count,
            "WAF触发率": (waf_triggered_count / len(valid_results)) * 100,
            "最佳场景": {
                "名称": best_scenario['scenario_name'],
                "成功率": best_scenario['success_rate'],
                "评分": best_scenario['evaluation']['score']
            },
            "最差场景": {
                "名称": worst_scenario['scenario_name'],
                "成功率": worst_scenario['success_rate'],
                "评分": worst_scenario['evaluation']['score']
            },
            "反爬临界点": {
                "平均触发点": np.mean(waf_trigger_points) if waf_trigger_points else None,
                "最早触发点": min(waf_trigger_points) if waf_trigger_points else None,
                "最晚触发点": max(waf_trigger_points) if waf_trigger_points else None
            }
        }
    
    def _suggest_optimal_parameters(self) -> Dict[str, Any]:
        """建议最佳参数"""
        valid_results = [r for r in self.batch_results if 'error' not in r]
        
        if not valid_results:
            return {"error": "没有有效的测试结果"}
        
        # 筛选出成功率高且未触发WAF的场景
        good_scenarios = [r for r in valid_results if r['success_rate'] >= 80 and not r['waf_triggered']]
        
        if good_scenarios:
            # 按评分排序
            good_scenarios.sort(key=lambda x: x['evaluation']['score'], reverse=True)
            best_scenario = good_scenarios[0]
            
            return {
                "推荐场景": best_scenario['scenario_name'],
                "推荐参数": {
                    "请求间隔": best_scenario['scenario_config']['interval'],
                    "最大请求数": best_scenario['scenario_config']['request_count'],
                    "预期成功率": f"{best_scenario['success_rate']:.1f}%",
                    "预期RPS": f"{best_scenario['actual_rps']:.2f}"
                },
                "使用建议": [
                    f"建议使用 {best_scenario['scenario_config']['interval']} 秒间隔",
                    f"单次批量不超过 {best_scenario['scenario_config']['request_count']} 个请求",
                    "建议配合代理IP使用以提高稳定性",
                    "建议添加随机延迟避免规律性检测"
                ]
            }
        else:
            # 如果没有完全理想的场景，选择相对最好的
            best_scenario = max(valid_results, key=lambda x: x['evaluation']['score'])
            return {
                "推荐场景": best_scenario['scenario_name'],
                "推荐参数": best_scenario['scenario_config'],
                "警告": "所有场景都存在问题，建议进一步优化",
                "使用建议": [
                    "建议进一步降低请求频率",
                    "使用代理IP池",
                    "增加更多反检测机制",
                    "考虑分时段请求"
                ]
            }
    
    def generate_comprehensive_charts(self, report_time: str):
        """生成综合图表"""
        valid_results = [r for r in self.batch_results if 'error' not in r]
        
        if not valid_results:
            return
        
        # 创建图表
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. 成功率对比
        scenarios = [r['scenario_name'] for r in valid_results]
        success_rates = [r['success_rate'] for r in valid_results]
        colors = [r['evaluation']['color'] for r in valid_results]
        
        bars1 = ax1.bar(scenarios, success_rates, color=colors, alpha=0.7)
        ax1.set_title('各场景成功率对比')
        ax1.set_ylabel('成功率 (%)')
        ax1.set_ylim(0, 100)
        ax1.grid(True, alpha=0.3)
        
        # 添加数值标签
        for bar, rate in zip(bars1, success_rates):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{rate:.1f}%', ha='center', va='bottom')
        
        # 2. 响应时间对比
        response_times = [r['avg_response_time'] for r in valid_results]
        bars2 = ax2.bar(scenarios, response_times, color='skyblue', alpha=0.7)
        ax2.set_title('平均响应时间对比')
        ax2.set_ylabel('响应时间 (秒)')
        ax2.grid(True, alpha=0.3)
        
        # 添加数值标签
        for bar, time in zip(bars2, response_times):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                    f'{time:.2f}s', ha='center', va='bottom')
        
        # 3. WAF触发情况
        waf_triggered = [1 if r['waf_triggered'] else 0 for r in valid_results]
        bars3 = ax3.bar(scenarios, waf_triggered, color=['red' if w else 'green' for w in waf_triggered], alpha=0.7)
        ax3.set_title('WAF触发情况')
        ax3.set_ylabel('WAF触发 (1=是, 0=否)')
        ax3.set_ylim(0, 1.2)
        ax3.grid(True, alpha=0.3)
        
        # 4. 评分对比
        scores = [r['evaluation']['score'] for r in valid_results]
        bars4 = ax4.bar(scenarios, scores, color=colors, alpha=0.7)
        ax4.set_title('综合评分对比')
        ax4.set_ylabel('评分')
        ax4.set_ylim(0, 100)
        ax4.grid(True, alpha=0.3)
        
        # 添加数值标签
        for bar, score in zip(bars4, scores):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{score}', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.xticks(rotation=45)
        
        # 保存图表
        chart_file = self.output_dir / f"comprehensive_charts_{report_time}.png"
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"   图表文件: {chart_file}")
    
    def print_comprehensive_report(self, report: Dict[str, Any]):
        """打印综合报告"""
        print(f"\n{'='*80}")
        print(f"🎯 Strategy1 批量测试综合报告")
        print(f"{'='*80}")
        
        # 综合分析
        analysis = report.get('综合分析', {})
        if analysis and 'error' not in analysis:
            print(f"📊 综合分析:")
            print(f"   场景总数: {analysis['场景总数']}")
            print(f"   平均成功率: {analysis['平均成功率']:.1f}%")
            print(f"   WAF触发率: {analysis['WAF触发率']:.1f}%")
            print(f"   最佳场景: {analysis['最佳场景']['名称']} (成功率: {analysis['最佳场景']['成功率']:.1f}%)")
            print(f"   最差场景: {analysis['最差场景']['名称']} (成功率: {analysis['最差场景']['成功率']:.1f}%)")
            
            # 反爬临界点
            threshold = analysis.get('反爬临界点', {})
            if threshold.get('平均触发点'):
                print(f"   反爬平均触发点: {threshold['平均触发点']:.0f} 个请求")
        
        # 建议参数
        suggestions = report.get('建议参数', {})
        if suggestions and 'error' not in suggestions:
            print(f"\n💡 建议参数:")
            print(f"   推荐场景: {suggestions['推荐场景']}")
            if '推荐参数' in suggestions:
                params = suggestions['推荐参数']
                print(f"   请求间隔: {params['请求间隔']} 秒")
                print(f"   最大请求数: {params['最大请求数']}")
                print(f"   预期成功率: {params['预期成功率']}")
            
            print(f"   使用建议:")
            for suggestion in suggestions.get('使用建议', []):
                print(f"     • {suggestion}")
        
        print(f"{'='*80}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Strategy1 批量测试运行器')
    parser.add_argument('--config', type=str, help='配置文件路径')
    
    args = parser.parse_args()
    
    # 创建输出目录
    Path("batch_test_logs").mkdir(exist_ok=True)
    
    # 创建批量测试运行器
    runner = BatchTestRunner(args.config)
    
    # 运行批量测试
    asyncio.run(runner.run_all_scenarios())

if __name__ == "__main__":
    main() 