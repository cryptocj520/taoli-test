#!/usr/bin/env python3
"""
价差走势图表生成工具

用于生成历史数据的可视化图表（心电图样式）
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.arbitrage_monitor_v2.history import ChartGenerator, SpreadHistoryReader


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成价差走势图表')
    parser.add_argument('--symbol', type=str, help='代币符号（如：PAXG-USDC-PERP）')
    parser.add_argument('--symbols', type=str, nargs='+', help='多个代币符号（用于对比图）')
    parser.add_argument('--start-date', type=str, help='开始时间（格式：YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--end-date', type=str, help='结束时间（格式：YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--minutes', type=int, help='最近N分钟的数据')
    parser.add_argument('--style', type=str, choices=['ecg', 'normal', 'multi-channel'], 
                       default='ecg', help='图表样式')
    parser.add_argument('--output', type=str, help='输出文件路径（HTML格式）')
    parser.add_argument('--db-path', type=str, default='data/spread_history/spread_history.db', 
                       help='数据库路径')
    
    args = parser.parse_args()
    
    # 创建图表生成器
    generator = ChartGenerator(db_path=args.db_path)
    reader = SpreadHistoryReader(db_path=args.db_path)
    
    # 如果没有指定代币，列出所有可用的代币
    if not args.symbol and not args.symbols:
        symbols = reader.get_all_symbols()
        if not symbols:
            print("❌ 数据库中没有数据")
            return
        
        print("📊 可用的代币列表：")
        for i, symbol in enumerate(symbols, 1):
            print(f"  {i}. {symbol}")
        print(f"\n使用方法：")
        print(f"  python {sys.argv[0]} --symbol PAXG-USDC-PERP --minutes 60")
        print(f"  python {sys.argv[0]} --symbols PAXG-USDC-PERP AAVE-USDC-PERP --start-date '2025-11-13 00:00:00' --end-date '2025-11-13 23:59:59'")
        return
    
    # 生成图表
    fig = None
    
    if args.symbols:
        # 多代币对比图
        if not args.start_date or not args.end_date:
            # 默认查询最近24小时
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            args.start_date = start_date.strftime('%Y-%m-%d %H:%M:%S')
            args.end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if args.style == 'multi-channel':
            fig = generator.create_ecg_multi_channel_chart(
                args.symbols,
                args.start_date,
                args.end_date
            )
        else:
            fig = generator.create_multi_symbol_chart(
                args.symbols,
                args.start_date,
                args.end_date
            )
    else:
        # 单代币图表
        if args.style == 'ecg':
            fig = generator.create_symbol_chart_from_db(
                args.symbol,
                start_date=args.start_date,
                end_date=args.end_date,
                minutes=args.minutes,
                style='ecg'
            )
        else:
            fig = generator.create_symbol_chart_from_db(
                args.symbol,
                start_date=args.start_date,
                end_date=args.end_date,
                minutes=args.minutes,
                style='normal'
            )
    
    if fig is None:
        print("❌ 无法生成图表（可能没有数据）")
        return
    
    # 保存或显示图表
    if args.output:
        fig.write_html(args.output)
        print(f"✅ 图表已保存到: {args.output}")
    else:
        fig.show()
        print("✅ 图表已在浏览器中打开")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

