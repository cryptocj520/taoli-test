#!/usr/bin/env python3
"""
修复数据库中错误的年化资金费率差数据

将历史数据中错误的年化值（funding_rate_diff * 365 * 24）修复为正确的值（funding_rate_diff * 1095）
"""

import sqlite3
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def fix_funding_rate_annual(db_path: str = "data/spread_history/spread_history.db", dry_run: bool = True):
    """
    修复数据库中错误的年化资金费率差
    
    Args:
        db_path: 数据库路径
        dry_run: 如果为True，只显示将要修复的数据，不实际修改
    """
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查需要修复的记录
    cursor.execute("""
        SELECT 
            id,
            timestamp,
            symbol,
            funding_rate_diff,
            funding_rate_diff_annual as stored_annual,
            funding_rate_diff * 1095 as correct_annual
        FROM spread_history_sampled
        WHERE funding_rate_diff IS NOT NULL
        AND funding_rate_diff_annual IS NOT NULL
        AND ABS(funding_rate_diff_annual - (funding_rate_diff * 1095)) > 0.001
    """)
    
    records_to_fix = cursor.fetchall()
    
    if len(records_to_fix) == 0:
        print("✅ 没有需要修复的记录（所有年化值都是正确的）")
        conn.close()
        return
    
    print("=" * 80)
    print(f"📊 发现 {len(records_to_fix)} 条需要修复的记录")
    print("=" * 80)
    
    # 显示前10条示例
    print("\n前10条记录示例：")
    for i, (record_id, timestamp, symbol, diff_8h, stored_annual, correct_annual) in enumerate(records_to_fix[:10], 1):
        print(f"\n{i}. ID: {record_id}, 代币: {symbol}, 时间: {timestamp}")
        print(f"   8小时费率差: {diff_8h}")
        print(f"   存储的年化值（错误）: {stored_annual:.6f}%")
        print(f"   正确的年化值: {correct_annual:.6f}%")
        print(f"   差异: {abs(stored_annual - correct_annual):.6f}%")
    
    if len(records_to_fix) > 10:
        print(f"\n... 还有 {len(records_to_fix) - 10} 条记录")
    
    if dry_run:
        print("\n" + "=" * 80)
        print("⚠️  这是预览模式（dry_run=True），不会实际修改数据")
        print("=" * 80)
        print("\n要实际修复数据，请运行：")
        print("  python tools/fix_funding_rate_annual.py --execute")
        conn.close()
        return
    
    # 实际修复
    print("\n" + "=" * 80)
    print("🔧 开始修复数据...")
    print("=" * 80)
    
    fixed_count = 0
    for record_id, _, _, diff_8h, _, correct_annual in records_to_fix:
        cursor.execute("""
            UPDATE spread_history_sampled
            SET funding_rate_diff_annual = ?
            WHERE id = ?
        """, (correct_annual, record_id))
        fixed_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 修复完成！共修复 {fixed_count} 条记录")
    print("\n💡 注意：图表显示已经修复，会从8小时费率差重新计算年化值")
    print("   修复数据库存储值主要是为了数据一致性")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='修复数据库中错误的年化资金费率差数据')
    parser.add_argument('--db-path', type=str, default='data/spread_history/spread_history.db',
                       help='数据库路径')
    parser.add_argument('--execute', action='store_true',
                       help='实际执行修复（默认只是预览）')
    
    args = parser.parse_args()
    
    fix_funding_rate_annual(args.db_path, dry_run=not args.execute)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

