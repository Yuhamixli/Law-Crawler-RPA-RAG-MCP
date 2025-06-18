"""
法律法规台账生成脚本
支持从数据库生成Excel、CSV、HTML格式的台账
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# 添加src到Python路径
sys.path.append(str(Path(__file__).parent))

from src.report.ledger_generator import LedgerGenerator
from src.storage.database import DatabaseManager
from src.storage.models import LawStatus
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='生成法律法规台账',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 生成Excel格式台账
  python generate_ledger.py --format excel
  
  # 生成所有格式的台账
  python generate_ledger.py --format all
  
  # 只生成有效法规的台账
  python generate_ledger.py --status effective
  
  # 生成特定类型法规的台账
  python generate_ledger.py --law-type "法律"
  
  # 指定输出文件名
  python generate_ledger.py --output my_ledger
        '''
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['excel', 'csv', 'html', 'all'],
        default='excel',
        help='输出格式 (默认: excel)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='输出文件名（不含扩展名）'
    )
    
    parser.add_argument(
        '--status', '-s',
        choices=['all', 'effective', 'amended', 'repealed', 'expired'],
        default='all',
        help='筛选法规状态 (默认: all)'
    )
    
    parser.add_argument(
        '--law-type', '-t',
        type=str,
        help='筛选法规类型'
    )
    
    parser.add_argument(
        '--summary', 
        action='store_true',
        help='同时生成汇总报告'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    try:
        # 初始化数据库和台账生成器
        db = DatabaseManager()
        generator = LedgerGenerator(db)
        
        # 准备过滤条件
        filters = {}
        if args.status != 'all':
            status_map = {
                'effective': LawStatus.EFFECTIVE,
                'amended': LawStatus.AMENDED,
                'repealed': LawStatus.REPEALED,
                'expired': LawStatus.EXPIRED
            }
            filters['status'] = status_map[args.status]
            
        if args.law_type:
            filters['law_type'] = args.law_type
            
        # 生成文件名
        if not args.output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"law_ledger_{timestamp}"
        else:
            filename = args.output
            
        # 根据格式生成台账
        formats = []
        if args.format == 'all':
            formats = ['excel', 'csv', 'html']
        else:
            formats = [args.format]
            
        generated_files = []
        
        for fmt in formats:
            logger.info(f"正在生成{fmt.upper()}格式的台账...")
            
            try:
                filepath = generator.generate_ledger(
                    output_format=fmt,
                    filename=f"{filename}_{fmt}" if len(formats) > 1 else filename,
                    filters=filters
                )
                
                if filepath:
                    generated_files.append(filepath)
                    logger.info(f"✓ {fmt.upper()}台账已生成: {filepath}")
                else:
                    logger.warning(f"✗ 未找到符合条件的法规数据")
                    
            except Exception as e:
                logger.error(f"✗ 生成{fmt.upper()}台账时出错: {str(e)}")
                
        # 生成汇总报告
        if args.summary and generated_files:
            logger.info("\n生成汇总报告...")
            summary = generator.generate_summary_report()
            
            print("\n" + "="*50)
            print("法律法规汇总统计")
            print("="*50)
            print(f"总记录数: {summary['total_count']}")
            
            print("\n按状态统计:")
            for status, count in summary['status_stats'].items():
                print(f"  {status}: {count}")
                
            if summary['type_stats']:
                print("\n按类型统计:")
                for law_type, count in summary['type_stats'].items():
                    print(f"  {law_type}: {count}")
                    
            if summary['year_stats']:
                print("\n按年份统计（最近10年）:")
                for year, count in summary['year_stats'].items():
                    print(f"  {year}年: {count}")
                    
        if generated_files:
            print(f"\n✓ 台账生成完成！共生成 {len(generated_files)} 个文件")
            print("\n生成的文件:")
            for f in generated_files:
                print(f"  - {f}")
        else:
            print("\n✗ 未生成任何台账文件")
            
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 