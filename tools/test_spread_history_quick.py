#!/usr/bin/env python3
"""
历史记录功能快速测试脚本

用于快速验证历史记录功能是否正常工作
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 先检查必需依赖
print("检查依赖...")
missing_deps = []

try:
    import aiofiles
    print("  ✅ aiofiles")
except ImportError:
    print("  ❌ aiofiles 未安装")
    missing_deps.append("aiofiles>=23.0.0")

try:
    import aiosqlite
    print("  ✅ aiosqlite")
except ImportError:
    print("  ⚠️  aiosqlite 未安装（SQLite功能将不可用）")
    missing_deps.append("aiosqlite>=0.19.0")

try:
    import pandas
    print("  ✅ pandas")
except ImportError:
    print("  ❌ pandas 未安装")
    missing_deps.append("pandas>=2.1.3")

try:
    import plotly
    print("  ✅ plotly")
except ImportError:
    print("  ⚠️  plotly 未安装（图表功能将不可用）")
    missing_deps.append("plotly>=5.18.0")

if missing_deps:
    print("\n❌ 缺少以下依赖，请先安装：")
    print(f"   pip install {' '.join(missing_deps)}")
    print("\n或者安装所有依赖：")
    print("   pip install aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 pandas>=2.1.3")
    sys.exit(1)

print("✅ 所有必需依赖已安装\n")

# 现在可以安全导入
try:
    from core.services.arbitrage_monitor_v2.history import SpreadHistoryRecorder, SpreadHistoryReader
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("   请检查项目结构是否正确")
    sys.exit(1)


async def test_basic_functionality():
    """测试基础功能"""
    print("=" * 60)
    print("阶段1：基础功能测试")
    print("=" * 60)
    
    # 测试1：检查依赖（已在导入时检查，这里只做确认）
    print("\n[测试1] 确认依赖...")
    try:
        import aiofiles
        print("  ✅ aiofiles 已安装")
    except ImportError:
        print("  ❌ aiofiles 未安装")
        return False
    
    try:
        import aiosqlite
        print("  ✅ aiosqlite 已安装")
    except ImportError:
        print("  ⚠️  aiosqlite 未安装，SQLite功能将不可用")
    
    # 测试2：创建记录器
    print("\n[测试2] 创建历史记录器...")
    try:
        recorder = SpreadHistoryRecorder(
            data_dir="data/spread_history_test",
            sample_interval_seconds=60,
            sample_strategy="max",
            batch_size=10,
            batch_timeout=60.0,
            queue_maxsize=500
        )
        print("  ✅ 历史记录器创建成功")
    except Exception as e:
        print(f"  ❌ 历史记录器创建失败: {e}")
        return False
    
    # 测试3：启动记录器
    print("\n[测试3] 启动历史记录器...")
    try:
        await recorder.start()
        print("  ✅ 历史记录器启动成功")
    except Exception as e:
        print(f"  ❌ 历史记录器启动失败: {e}")
        return False
    
    # 测试4：记录数据
    print("\n[测试4] 测试数据记录...")
    test_data = {
        'timestamp': datetime.now(),
        'symbol': 'PAXG-USDC-PERP',
        'exchange_buy': 'edgex',
        'exchange_sell': 'lighter',
        'price_buy': 4174.60,
        'price_sell': 4179.69,
        'spread_pct': 0.122,
        'funding_rate_diff_annual': 56.5,
        'size_buy': 0.0690,
        'size_sell': 0.8473
    }
    
    try:
        # 记录多条数据（模拟1分钟内的数据）
        for i in range(5):
            await recorder.record_spread(test_data)
        print(f"  ✅ 已记录5条测试数据")
    except Exception as e:
        print(f"  ❌ 数据记录失败: {e}")
        await recorder.stop()
        return False
    
    # 等待采样和写入
    print("\n[测试5] 等待采样和写入（5秒）...")
    await asyncio.sleep(5)
    
    # 测试6：检查统计信息
    print("\n[测试6] 检查统计信息...")
    stats = recorder.get_stats()
    print(f"  接收记录数: {stats.get('records_received', 0)}")
    print(f"  采样次数: {stats.get('samples_taken', 0)}")
    print(f"  写入批次: {stats.get('batches_written', 0)}")
    
    # 停止记录器
    print("\n[测试7] 停止历史记录器...")
    try:
        await recorder.stop()
        print("  ✅ 历史记录器停止成功")
    except Exception as e:
        print(f"  ⚠️  停止时出现警告: {e}")
    
    return True


async def test_sqlite_functionality():
    """测试SQLite功能"""
    print("\n" + "=" * 60)
    print("阶段2：SQLite功能测试")
    print("=" * 60)
    
    # 检查数据库文件
    db_path = "data/spread_history_test/spread_history.db"
    db_file = Path(db_path)
    
    if not db_file.exists():
        print(f"\n  ⚠️  数据库文件不存在: {db_path}")
        print("      请先运行阶段1测试，生成数据")
        return False
    
    print(f"\n[测试1] 检查数据库文件...")
    print(f"  ✅ 数据库文件存在: {db_path}")
    print(f"  文件大小: {db_file.stat().st_size} 字节")
    
    # 测试2：创建读取器
    print("\n[测试2] 创建数据读取器...")
    try:
        reader = SpreadHistoryReader(db_path=db_path)
        print("  ✅ 数据读取器创建成功")
    except Exception as e:
        print(f"  ❌ 数据读取器创建失败: {e}")
        return False
    
    # 测试3：查询所有代币
    print("\n[测试3] 查询所有代币...")
    try:
        symbols = reader.get_all_symbols()
        print(f"  ✅ 找到 {len(symbols)} 个代币: {symbols}")
    except Exception as e:
        print(f"  ❌ 查询代币失败: {e}")
        return False
    
    if not symbols:
        print("  ⚠️  数据库中没有数据，请先运行阶段1测试")
        return False
    
    # 测试4：查询代币走势
    print("\n[测试4] 查询代币走势...")
    symbol = symbols[0]
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        df = reader.query_symbol_trend(
            symbol=symbol,
            start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        print(f"  ✅ 查询成功，找到 {len(df)} 条数据")
        if len(df) > 0:
            print(f"  数据示例:")
            print(df.head())
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return False
    
    # 测试5：查询最近数据
    print("\n[测试5] 查询最近数据...")
    try:
        df = reader.query_latest_data(symbol, minutes=60)
        print(f"  ✅ 查询成功，找到 {len(df)} 条数据")
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")
        return False
    
    # 测试6：获取统计信息
    print("\n[测试6] 获取统计信息...")
    try:
        stats = reader.get_statistics(symbol)
        print(f"  ✅ 统计信息:")
        for key, value in stats.items():
            print(f"    {key}: {value}")
    except Exception as e:
        print(f"  ❌ 获取统计信息失败: {e}")
        return False
    
    return True


def test_chart_functionality():
    """测试图表功能"""
    print("\n" + "=" * 60)
    print("阶段3：图表功能测试")
    print("=" * 60)
    
    # 测试1：检查plotly
    print("\n[测试1] 检查plotly...")
    try:
        import plotly.graph_objects as go
        print("  ✅ plotly 已安装")
    except ImportError:
        print("  ❌ plotly 未安装，请运行: pip install plotly")
        return False
    
    # 测试2：创建图表生成器
    print("\n[测试2] 创建图表生成器...")
    db_path = "data/spread_history_test/spread_history.db"
    try:
        from core.services.arbitrage_monitor_v2.history import ChartGenerator
        generator = ChartGenerator(db_path=db_path)
        print("  ✅ 图表生成器创建成功")
    except Exception as e:
        print(f"  ❌ 图表生成器创建失败: {e}")
        return False
    
    # 测试3：查询数据并生成图表
    print("\n[测试3] 生成测试图表...")
    try:
        reader = SpreadHistoryReader(db_path=db_path)
        symbols = reader.get_all_symbols()
        
        if not symbols:
            print("  ⚠️  数据库中没有数据，跳过图表测试")
            return True
        
        symbol = symbols[0]
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)
        
        df = reader.query_symbol_trend(
            symbol=symbol,
            start_date=start_date.strftime('%Y-%m-%d %H:%M:%S'),
            end_date=end_date.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        if len(df) > 0:
            fig = generator.create_ecg_style_chart(df, symbol)
            output_file = "test_chart_output.html"
            fig.write_html(output_file)
            print(f"  ✅ 图表已生成: {output_file}")
            print(f"  提示: 在浏览器中打开 {output_file} 查看图表")
        else:
            print("  ⚠️  没有足够的数据生成图表")
    except Exception as e:
        print(f"  ❌ 图表生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("历史记录功能快速测试")
    print("=" * 60)
    print("\n提示：")
    print("1. 测试将创建测试数据目录: data/spread_history_test/")
    print("2. 测试完成后可以删除测试目录: rm -rf data/spread_history_test/")
    print("")
    
    # 阶段1：基础功能
    result1 = await test_basic_functionality()
    if not result1:
        print("\n❌ 阶段1测试失败，请检查错误信息")
        return
    
    # 等待数据写入完成
    print("\n等待数据写入完成（3秒）...")
    await asyncio.sleep(3)
    
    # 阶段2：SQLite功能
    result2 = await test_sqlite_functionality()
    if not result2:
        print("\n⚠️  阶段2测试失败，可能是数据库中没有数据")
    
    # 阶段3：图表功能
    result3 = test_chart_functionality()
    if not result3:
        print("\n⚠️  阶段3测试失败，请检查错误信息")
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"阶段1（基础功能）: {'✅ 通过' if result1 else '❌ 失败'}")
    print(f"阶段2（SQLite功能）: {'✅ 通过' if result2 else '⚠️  跳过'}")
    print(f"阶段3（图表功能）: {'✅ 通过' if result3 else '⚠️  跳过'}")
    
    if result1 and result2 and result3:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试未通过，请查看详细错误信息")
    
    print("\n提示：")
    print("- 测试数据保存在: data/spread_history_test/")
    print("- 可以删除测试目录: rm -rf data/spread_history_test/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

