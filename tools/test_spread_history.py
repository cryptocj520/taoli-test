#!/usr/bin/env python3
"""
历史记录功能测试脚本

用于测试历史记录功能的写入和查询性能
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.arbitrage_monitor_v2.history import SpreadHistoryRecorder, SpreadHistoryReader


async def test_history_recorder():
    """测试历史记录器"""
    print("=" * 60)
    print("历史记录功能测试")
    print("=" * 60)
    
    # 创建测试数据目录
    test_data_dir = "data/test_spread_history"
    
    # 初始化记录器
    print("\n1. 初始化历史记录器...")
    recorder = SpreadHistoryRecorder(
        data_dir=test_data_dir,
        sample_interval_seconds=5,  # 测试用5秒间隔
        sample_strategy="max",
        batch_size=5,
        batch_timeout=10.0
    )
    
    # 启动记录器
    print("2. 启动历史记录器...")
    await recorder.start()
    
    # 模拟写入数据
    print("3. 模拟写入数据（10条记录）...")
    test_symbols = ["PAXG-USDC-PERP", "AAVE-USDC-PERP", "BTC-USDC-PERP"]
    
    start_time = time.time()
    for i in range(10):
        symbol = test_symbols[i % len(test_symbols)]
        await recorder.record_spread({
            'symbol': symbol,
            'exchange_buy': 'edgex',
            'exchange_sell': 'lighter',
            'price_buy': 4174.60 + i * 0.1,
            'price_sell': 4179.69 + i * 0.1,
            'spread_pct': 0.122 + i * 0.01,
            'funding_rate_diff_annual': 56.5 + i,
            'size_buy': 0.0690,
            'size_sell': 0.8473,
        })
        await asyncio.sleep(0.1)  # 模拟100ms间隔
    
    write_time = time.time() - start_time
    print(f"   ✅ 写入10条记录耗时: {write_time*1000:.3f}ms")
    print(f"   ✅ 平均每条记录耗时: {write_time*1000/10:.3f}ms")
    
    # 等待采样和写入
    print("4. 等待采样和写入（等待10秒）...")
    await asyncio.sleep(10)
    
    # 检查统计信息
    stats = recorder.get_stats()
    print("\n5. 统计信息:")
    print(f"   - 接收记录数: {stats['records_received']}")
    print(f"   - 采样次数: {stats['samples_taken']}")
    print(f"   - CSV批次写入: {stats['batches_written']}")
    print(f"   - SQLite批次写入: {stats.get('sqlite_batches_written', 0)}")
    print(f"   - 队列大小: {stats['queue_size']}")
    
    # 停止记录器
    print("\n6. 停止历史记录器...")
    await recorder.stop()
    
    # 测试查询功能
    print("\n7. 测试查询功能...")
    reader = SpreadHistoryReader(db_path=Path(test_data_dir) / "spread_history.db")
    
    # 查询所有数据
    df = reader.query_spread_history()
    print(f"   ✅ 查询到 {len(df)} 条记录")
    
    if len(df) > 0:
        print(f"   - 时间范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
        print(f"   - 代币列表: {df['symbol'].unique().tolist()}")
        
        # 查询特定代币
        symbol_df = reader.query_symbol_trend("PAXG-USDC-PERP")
        print(f"\n   ✅ PAXG-USDC-PERP 查询到 {len(symbol_df)} 条记录")
        
        # 查询统计信息
        stats = reader.get_statistics("PAXG-USDC-PERP")
        print(f"\n   ✅ PAXG-USDC-PERP 统计信息:")
        print(f"      - 记录数: {stats['count']}")
        print(f"      - 平均价差: {stats['mean_spread']:.4f}%")
        print(f"      - 最大价差: {stats['max_spread']:.4f}%")
        print(f"      - 最小价差: {stats['min_spread']:.4f}%")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_history_recorder())
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

