#!/usr/bin/env python3
"""
展示 EdgeX 和 Lighter 交易所数据对比

功能：
1. 读取 edgex_lighter_markets.json 配置文件
2. 以表格形式展示两个交易所的数据对比
3. 支持自定义筛选条件（交易量、持仓量阈值）
4. 生成 Markdown 文档，包含完整的数据对比表格

使用方法：
    # 使用默认条件（交易量 >= 1M USD，持仓量 >= 1M USD）
    python3 tools/display_exchange_comparison.py
    
    # 自定义筛选条件
    python3 tools/display_exchange_comparison.py --min-volume 5000000 --min-oi 10000000
    
    # 查看帮助
    python3 tools/display_exchange_comparison.py --help
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def format_number(value: Optional[float], decimals: int = 2, show_thousands: bool = True) -> str:
    """格式化数字显示"""
    if value is None:
        return "N/A"
    
    if isinstance(value, float):
        if abs(value) < 0.0001 and value != 0:
            # 科学计数法格式
            return f"{value:.2e}"
        elif show_thousands and abs(value) >= 1000:
            # 千分位格式
            return f"{value:,.{decimals}f}"
        else:
            return f"{value:,.{decimals}f}"
    else:
        return str(value)


def format_percentage(value: Optional[float], decimals: int = 2) -> str:
    """格式化百分比"""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_funding_rate(value: Optional[float]) -> str:
    """格式化资金费率（8小时）"""
    if value is None:
        return "N/A"
    # 转换为百分比显示
    pct = value * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.6f}%"


def format_small_number(value: Optional[float], decimals: int = 0) -> str:
    """格式化小数字（如交易量）"""
    if value is None:
        return "N/A"
    
    if value == 0:
        return "0"
    
    if value < 1:
        return f"{value:.{decimals}f}"
    elif value < 1000:
        return f"{value:.{decimals}f}"
    elif value < 1000000:
        return f"{value/1000:.2f}K"
    elif value < 1000000000:
        return f"{value/1000000:.2f}M"
    else:
        return f"{value/1000000000:.2f}B"


def load_market_data(json_file: Path) -> Dict[str, Any]:
    """加载市场数据 JSON 文件"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"❌ 文件不存在: {json_file}")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        return {}


def generate_summary_table(data: Dict[str, Any]) -> str:
    """生成汇总信息表格"""
    md = []
    md.append("## 📊 数据汇总\n\n")
    
    md.append("| 项目 | 数值 |\n")
    md.append("|------|------|\n")
    md.append(f"| 更新时间 | {data.get('updated_at', 'N/A')} |\n")
    md.append(f"| EdgeX 总市场数 | {data.get('edgex_total', 0)} |\n")
    md.append(f"| Lighter 总市场数 | {data.get('lighter_total', 0)} |\n")
    md.append(f"| 重叠交易对数量 | {data.get('total_overlapping_symbols', 0)} |\n")
    
    return "".join(md)


def generate_main_comparison_table(markets: Dict[str, Dict]) -> str:
    """生成主要对比表格（包含核心数据）"""
    md = []
    md.append("## 📈 核心数据对比表\n\n")
    
    # 表头
    md.append("| 交易对 | EdgeX 价格 | Lighter 价格 | 价差% | EdgeX 24h量 | Lighter 24h量 | EdgeX 费率 | Lighter 费率 | EdgeX 持仓 | Lighter 持仓 |\n")
    md.append("|--------|------------|--------------|-------|-------------|---------------|------------|--------------|------------|--------------|\n")
    
    # 按交易对排序
    sorted_symbols = sorted(markets.keys())
    
    for symbol in sorted_symbols:
        market = markets[symbol]
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        # 提取数据
        edgex_price = edgex.get('last_trade_price')
        lighter_price = lighter.get('last_trade_price')
        
        # 计算价差百分比
        price_diff_pct = None
        if edgex_price and lighter_price and lighter_price != 0:
            price_diff_pct = ((edgex_price - lighter_price) / lighter_price) * 100
        
        edgex_vol = edgex.get('daily_volume_quote')
        lighter_vol = lighter.get('daily_volume_quote')
        edgex_fr = edgex.get('funding_rate')
        lighter_fr = lighter.get('funding_rate')
        edgex_oi = edgex.get('open_interest')
        lighter_oi = lighter.get('open_interest')
        
        # 格式化数据
        edgex_price_str = format_number(edgex_price, decimals=4)
        lighter_price_str = format_number(lighter_price, decimals=4)
        price_diff_str = format_percentage(price_diff_pct, decimals=4) if price_diff_pct is not None else "N/A"
        edgex_vol_str = format_small_number(edgex_vol, decimals=0)
        lighter_vol_str = format_small_number(lighter_vol, decimals=0)
        edgex_fr_str = format_funding_rate(edgex_fr)
        lighter_fr_str = format_funding_rate(lighter_fr)
        edgex_oi_str = format_small_number(edgex_oi, decimals=2)
        lighter_oi_str = format_small_number(lighter_oi, decimals=2)
        
        md.append(f"| {symbol} | {edgex_price_str} | {lighter_price_str} | {price_diff_str} | {edgex_vol_str} | {lighter_vol_str} | {edgex_fr_str} | {lighter_fr_str} | {edgex_oi_str} | {lighter_oi_str} |\n")
    
    return "".join(md)


def generate_detailed_table(markets: Dict[str, Dict]) -> str:
    """生成详细数据表格（包含所有字段）"""
    md = []
    md.append("## 📋 详细数据对比表\n\n")
    
    # 表头 - 分为 EdgeX 和 Lighter 两大部分
    md.append("| 交易对 | EdgeX Symbol | EdgeX ID | EdgeX 价格 | EdgeX 高 | EdgeX 低 | EdgeX 涨跌% | EdgeX 基础量 | EdgeX 计价量 | EdgeX 成交数 | EdgeX 费率 | EdgeX 持仓 | ")
    md.append("Lighter Symbol | Lighter ID | Lighter 价格 | Lighter 高 | Lighter 低 | Lighter 涨跌% | Lighter 基础量 | Lighter 计价量 | Lighter 成交数 | Lighter 费率 | Lighter 持仓 | Lighter 精度(价/量) | Lighter 手续费(M/T) |\n")
    
    # 分隔行
    md.append("|--------|-------------|----------|------------|---------|---------|-------------|--------------|--------------|-------------|------------|------------|")
    md.append("---------------|------------|-------------|------------|------------|-------------|---------------|---------------|--------------|-------------|-------------|---------------------|-------------------|\n")
    
    # 按交易对排序
    sorted_symbols = sorted(markets.keys())
    
    for symbol in sorted_symbols:
        market = markets[symbol]
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        # EdgeX 数据
        edgex_symbol = edgex.get('symbol', 'N/A')
        edgex_id = edgex.get('contract_id', 'N/A')
        edgex_price = format_number(edgex.get('last_trade_price'), decimals=4)
        edgex_high = format_number(edgex.get('daily_high'), decimals=4)
        edgex_low = format_number(edgex.get('daily_low'), decimals=4)
        edgex_change = format_percentage(edgex.get('daily_price_change_pct'), decimals=2)
        edgex_vol_base = format_small_number(edgex.get('daily_volume_base'), decimals=0)
        edgex_vol_quote = format_small_number(edgex.get('daily_volume_quote'), decimals=0)
        edgex_trades = format_number(edgex.get('daily_trades_count'), decimals=0, show_thousands=False)
        edgex_fr = format_funding_rate(edgex.get('funding_rate'))
        edgex_oi = format_small_number(edgex.get('open_interest'), decimals=2)
        
        # Lighter 数据
        lighter_symbol = lighter.get('symbol', 'N/A')
        lighter_id = lighter.get('market_id', 'N/A')
        lighter_price = format_number(lighter.get('last_trade_price'), decimals=4)
        lighter_high = format_number(lighter.get('daily_high'), decimals=4)
        lighter_low = format_number(lighter.get('daily_low'), decimals=4)
        lighter_change = format_percentage(lighter.get('daily_price_change_pct'), decimals=2)
        lighter_vol_base = format_small_number(lighter.get('daily_volume_base'), decimals=0)
        lighter_vol_quote = format_small_number(lighter.get('daily_volume_quote'), decimals=0)
        lighter_trades = format_number(lighter.get('daily_trades_count'), decimals=0, show_thousands=False)
        lighter_fr = format_funding_rate(lighter.get('funding_rate'))
        lighter_oi = format_small_number(lighter.get('open_interest'), decimals=2)
        
        # Lighter 特有字段
        price_dec = lighter.get('price_decimals', 'N/A')
        size_dec = lighter.get('size_decimals', 'N/A')
        precision_str = f"{price_dec}/{size_dec}" if price_dec != 'N/A' and size_dec != 'N/A' else "N/A"
        
        maker_fee = lighter.get('maker_fee', 'N/A')
        taker_fee = lighter.get('taker_fee', 'N/A')
        fee_str = f"{maker_fee}/{taker_fee}" if maker_fee != 'N/A' and taker_fee != 'N/A' else "N/A"
        
        md.append(f"| {symbol} | {edgex_symbol} | {edgex_id} | {edgex_price} | {edgex_high} | {edgex_low} | {edgex_change} | {edgex_vol_base} | {edgex_vol_quote} | {edgex_trades} | {edgex_fr} | {edgex_oi} | ")
        md.append(f"{lighter_symbol} | {lighter_id} | {lighter_price} | {lighter_high} | {lighter_low} | {lighter_change} | {lighter_vol_base} | {lighter_vol_quote} | {lighter_trades} | {lighter_fr} | {lighter_oi} | {precision_str} | {fee_str} |\n")
    
    return "".join(md)


def generate_statistics_section(markets: Dict[str, Dict]) -> str:
    """生成统计信息部分"""
    md = []
    md.append("## 📊 统计信息\n\n")
    
    # 计算统计数据
    total_symbols = len(markets)
    
    # 价格差异统计
    price_diffs = []
    volume_ratios = []
    funding_rate_diffs = []
    
    for symbol, market in markets.items():
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        edgex_price = edgex.get('last_trade_price')
        lighter_price = lighter.get('last_trade_price')
        if edgex_price and lighter_price and lighter_price != 0:
            diff_pct = ((edgex_price - lighter_price) / lighter_price) * 100
            price_diffs.append(abs(diff_pct))
        
        edgex_vol = edgex.get('daily_volume_quote')
        lighter_vol = lighter.get('daily_volume_quote')
        if edgex_vol and lighter_vol and lighter_vol > 0:
            ratio = edgex_vol / lighter_vol
            volume_ratios.append(ratio)
        
        edgex_fr = edgex.get('funding_rate')
        lighter_fr = lighter.get('funding_rate')
        if edgex_fr is not None and lighter_fr is not None:
            diff = abs(edgex_fr - lighter_fr) * 100  # 转换为百分比
            funding_rate_diffs.append(diff)
    
    md.append("### 价差统计\n\n")
    if price_diffs:
        avg_diff = sum(price_diffs) / len(price_diffs)
        max_diff = max(price_diffs)
        min_diff = min(price_diffs)
        md.append(f"- **平均价差**: {avg_diff:.4f}%\n")
        md.append(f"- **最大价差**: {max_diff:.4f}%\n")
        md.append(f"- **最小价差**: {min_diff:.4f}%\n")
        md.append(f"- **有效数据**: {len(price_diffs)}/{total_symbols} 个交易对\n\n")
    
    md.append("### 交易量对比\n\n")
    if volume_ratios:
        avg_ratio = sum(volume_ratios) / len(volume_ratios)
        md.append(f"- **平均交易量比 (EdgeX/Lighter)**: {avg_ratio:.2f}x\n")
        md.append(f"- **有效数据**: {len(volume_ratios)}/{total_symbols} 个交易对\n\n")
    
    md.append("### 资金费率差异\n\n")
    if funding_rate_diffs:
        avg_diff = sum(funding_rate_diffs) / len(funding_rate_diffs)
        max_diff = max(funding_rate_diffs)
        md.append(f"- **平均费率差**: {avg_diff:.6f}%\n")
        md.append(f"- **最大费率差**: {max_diff:.6f}%\n")
        md.append(f"- **有效数据**: {len(funding_rate_diffs)}/{total_symbols} 个交易对\n\n")
    
    return "".join(md)


def save_to_markdown(data: Dict[str, Any], output_dir: Path) -> Path:
    """保存为 Markdown 文档"""
    output_file = output_dir / "edgex_lighter_comparison.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    markets = data.get('overlapping_markets', {})
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 标题和说明
        f.write("# EdgeX 和 Lighter 交易所数据对比\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("**数据来源**: `config/exchanges/edgex_lighter_markets.json`\n\n")
        f.write("---\n\n")
        
        # 汇总信息
        f.write(generate_summary_table(data))
        f.write("\n")
        
        # 统计信息
        f.write(generate_statistics_section(markets))
        f.write("\n")
        
        # 核心对比表
        f.write(generate_main_comparison_table(markets))
        f.write("\n")
        
        # 详细对比表
        f.write(generate_detailed_table(markets))
        f.write("\n")
        
        # 使用说明
        f.write("---\n\n")
        f.write("## 💡 使用说明\n\n")
        f.write("1. **核心数据对比表**: 展示最重要的价格、交易量、费率和持仓数据\n")
        f.write("2. **详细数据对比表**: 包含所有可用字段的完整对比\n")
        f.write("3. **统计信息**: 提供价差、交易量比、费率差等统计指标\n")
        f.write("4. 数据更新：运行 `tools/get_exchange_markets.py` 更新数据\n\n")
        
        # 字段说明
        f.write("## 📖 字段说明\n\n")
        f.write("### 价格相关\n")
        f.write("- **价格**: 最新成交价\n")
        f.write("- **高/低**: 24小时最高/最低价\n")
        f.write("- **涨跌%**: 24小时价格变化百分比\n")
        f.write("- **价差%**: EdgeX 和 Lighter 之间的价格差异百分比\n\n")
        
        f.write("### 交易量相关\n")
        f.write("- **基础量**: 以基础资产为单位的24小时交易量\n")
        f.write("- **计价量**: 以计价资产（USD）为单位的24小时交易额\n")
        f.write("- **成交数**: 24小时成交笔数\n\n")
        
        f.write("### 费率相关\n")
        f.write("- **资金费率**: 每8小时的资金费率（已统一转换）\n")
        f.write("- **费率差**: 两个交易所之间的资金费率差异\n\n")
        
        f.write("### 持仓相关\n")
        f.write("- **持仓量**: 未平仓合约数量（以基础资产为单位）\n")
        f.write("- **持仓量差异**: 反映两个交易所的市场深度差异\n\n")
    
    return output_file


def filter_high_volume_markets(markets: Dict[str, Dict], 
                                min_volume: Optional[float] = None,
                                min_open_interest_usd: Optional[float] = None) -> Dict[str, Dict]:
    """
    筛选高交易量和高持仓量的交易对
    
    Args:
        markets: 市场数据字典
        min_volume: 最小24小时交易量（USD，计价量），如果为 None 则不筛选
        min_open_interest_usd: 最小持仓量（USD价值），如果为 None 则不筛选
    
    Returns:
        筛选后的市场数据字典
    """
    filtered = {}
    
    for symbol, market in markets.items():
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        # 检查交易量条件
        volume_qualified = True
        if min_volume is not None:
            edgex_volume = edgex.get('daily_volume_quote', 0) or 0
            lighter_volume = lighter.get('daily_volume_quote', 0) or 0
            volume_qualified = (edgex_volume >= min_volume and lighter_volume >= min_volume)
        
        # 检查持仓量条件
        oi_qualified = True
        if min_open_interest_usd is not None:
            # 获取持仓量（基础资产单位）和价格
            edgex_oi_base = edgex.get('open_interest', 0) or 0
            lighter_oi_base = lighter.get('open_interest', 0) or 0
            edgex_price = edgex.get('last_trade_price', 0) or 0
            lighter_price = lighter.get('last_trade_price', 0) or 0
            
            # 计算持仓量的USD价值
            edgex_oi_usd = edgex_oi_base * edgex_price if edgex_price > 0 else 0
            lighter_oi_usd = lighter_oi_base * lighter_price if lighter_price > 0 else 0
            
            oi_qualified = (edgex_oi_usd >= min_open_interest_usd and 
                           lighter_oi_usd >= min_open_interest_usd)
        
        # 只有所有设置的条件都满足时才通过筛选
        if volume_qualified and oi_qualified:
            filtered[symbol] = market
    
    return filtered


def print_all_markets_with_status(markets: Dict[str, Dict], 
                                   min_volume: Optional[float] = None,
                                   min_open_interest_usd: Optional[float] = None):
    """打印所有交易对，标注是否符合条件"""
    print(f"{'交易对':<12} | {'EdgeX 交易量':<15} | {'Lighter 交易量':<17} | {'EdgeX 持仓(USD)':<18} | {'Lighter 持仓(USD)':<18} | {'状态':<8}")
    print("-" * 120)
    
    # 按交易对排序
    sorted_symbols = sorted(markets.keys())
    
    qualified_count = 0
    unqualified_count = 0
    
    for symbol in sorted_symbols:
        market = markets[symbol]
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        edgex_vol = edgex.get('daily_volume_quote', 0) or 0
        lighter_vol = lighter.get('daily_volume_quote', 0) or 0
        
        # 计算持仓量的USD价值
        edgex_oi_base = edgex.get('open_interest', 0) or 0
        lighter_oi_base = lighter.get('open_interest', 0) or 0
        edgex_price = edgex.get('last_trade_price', 0) or 0
        lighter_price = lighter.get('last_trade_price', 0) or 0
        
        edgex_oi_usd = edgex_oi_base * edgex_price if edgex_price > 0 else 0
        lighter_oi_usd = lighter_oi_base * lighter_price if lighter_price > 0 else 0
        
        # 判断是否符合条件
        volume_ok = True
        if min_volume is not None:
            volume_ok = (edgex_vol >= min_volume and lighter_vol >= min_volume)
        
        oi_ok = True
        if min_open_interest_usd is not None:
            oi_ok = (edgex_oi_usd >= min_open_interest_usd and lighter_oi_usd >= min_open_interest_usd)
        
        is_qualified = volume_ok and oi_ok
        
        if is_qualified:
            qualified_count += 1
            status = "✅ 符合"
        else:
            unqualified_count += 1
            status = "❌ 不符合"
        
        edgex_vol_str = format_small_number(edgex_vol, decimals=0)
        lighter_vol_str = format_small_number(lighter_vol, decimals=0)
        edgex_oi_str = format_small_number(edgex_oi_usd, decimals=0)
        lighter_oi_str = format_small_number(lighter_oi_usd, decimals=0)
        
        print(f"{symbol:<12} | {edgex_vol_str:<15} | {lighter_vol_str:<17} | {edgex_oi_str:<18} | {lighter_oi_str:<18} | {status:<8}")
    
    print("\n" + "-" * 120)
    print(f"📊 统计: ✅ 符合条件: {qualified_count} 个 | ❌ 不符合条件: {unqualified_count} 个 | 总计: {len(markets)} 个")


def print_filtered_markets(filtered_markets: Dict[str, Dict]):
    """打印筛选后的交易对列表"""
    if not filtered_markets:
        print("\n❌ 未找到符合条件的交易对")
        return
    
    print(f"\n✅ 找到 {len(filtered_markets)} 个符合条件的交易对：\n")
    
    # 表头
    print(f"{'交易对':<12} | {'EdgeX 交易量(USD)':<20} | {'Lighter 交易量(USD)':<22} | {'EdgeX 持仓(USD)':<18} | {'Lighter 持仓(USD)':<18}")
    print("-" * 110)
    
    # 按交易对排序
    sorted_symbols = sorted(filtered_markets.keys())
    
    for symbol in sorted_symbols:
        market = filtered_markets[symbol]
        edgex = market.get('edgex', {})
        lighter = market.get('lighter', {})
        
        edgex_vol = edgex.get('daily_volume_quote', 0) or 0
        lighter_vol = lighter.get('daily_volume_quote', 0) or 0
        
        # 计算持仓量的USD价值
        edgex_oi_base = edgex.get('open_interest', 0) or 0
        lighter_oi_base = lighter.get('open_interest', 0) or 0
        edgex_price = edgex.get('last_trade_price', 0) or 0
        lighter_price = lighter.get('last_trade_price', 0) or 0
        
        edgex_oi_usd = edgex_oi_base * edgex_price if edgex_price > 0 else 0
        lighter_oi_usd = lighter_oi_base * lighter_price if lighter_price > 0 else 0
        
        edgex_vol_str = format_small_number(edgex_vol, decimals=0)
        lighter_vol_str = format_small_number(lighter_vol, decimals=0)
        edgex_oi_str = format_small_number(edgex_oi_usd, decimals=0)
        lighter_oi_str = format_small_number(lighter_oi_usd, decimals=0)
        
        print(f"{symbol:<12} | {edgex_vol_str:<20} | {lighter_vol_str:<22} | {edgex_oi_str:<18} | {lighter_oi_str:<18}")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='EdgeX 和 Lighter 交易所数据对比工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 不设置任何条件（显示所有交易对）
  python3 tools/display_exchange_comparison.py

  # 只筛选交易量（>= 1M USD）
  python3 tools/display_exchange_comparison.py --min-volume 1000000

  # 只筛选持仓量（>= 10M USD）
  python3 tools/display_exchange_comparison.py --min-oi 10000000

  # 同时设置两个条件
  python3 tools/display_exchange_comparison.py --min-volume 5000000 --min-oi 10000000

  # 不显示完整列表，只显示符合条件的
  python3 tools/display_exchange_comparison.py --min-volume 1000000 --no-full-list

  # 不生成文档
  python3 tools/display_exchange_comparison.py --no-doc
        """
    )
    
    parser.add_argument(
        '--min-volume',
        type=float,
        default=None,
        help='最小24小时交易量（USD），如果未设置则不筛选交易量'
    )
    
    parser.add_argument(
        '--min-oi',
        '--min-open-interest',
        type=float,
        default=None,
        dest='min_open_interest',
        help='最小持仓量（USD价值），如果未设置则不筛选持仓量'
    )
    
    parser.add_argument(
        '--no-full-list',
        action='store_true',
        help='不显示所有交易对的完整列表'
    )
    
    parser.add_argument(
        '--no-doc',
        action='store_true',
        help='不生成 Markdown 文档'
    )
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()
    
    print("\n" + "="*80)
    print("🚀 EdgeX 和 Lighter 交易所数据对比工具")
    print("="*80 + "\n")
    
    # 显示筛选条件
    print("📋 筛选条件:")
    if args.min_volume is not None:
        print(f"   - 最小交易量(USD): {args.min_volume:,.0f} ({format_small_number(args.min_volume)})")
    else:
        print(f"   - 最小交易量(USD): 未设置（不筛选）")
    
    if args.min_open_interest is not None:
        print(f"   - 最小持仓量(USD): {args.min_open_interest:,.0f} ({format_small_number(args.min_open_interest)})")
    else:
        print(f"   - 最小持仓量(USD): 未设置（不筛选）")
    print()
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    config_file = project_root / "config" / "exchanges" / "edgex_lighter_markets.json"
    docs_dir = project_root / "docs"
    
    # 加载数据
    print("📖 正在加载数据...")
    data = load_market_data(config_file)
    
    if not data:
        print("\n❌ 未能加载数据")
        print(f"💡 请确保文件存在: {config_file}")
        print("💡 如果文件不存在，请先运行: python3 tools/get_exchange_markets.py")
        return
    
    markets = data.get('overlapping_markets', {})
    if not markets:
        print("\n❌ 未找到重叠交易对数据")
        return
    
    print(f"✅ 加载成功: {len(markets)} 个重叠交易对\n")
    
    # 筛选高交易量和高持仓量的交易对
    print("🔍 正在筛选符合条件的交易对...")
    conditions = []
    if args.min_volume is not None:
        conditions.append(f"两个交易所的24小时交易量(USD) >= {format_small_number(args.min_volume)}")
    if args.min_open_interest is not None:
        conditions.append(f"持仓量(USD价值) >= {format_small_number(args.min_open_interest)}")
    
    if conditions:
        print(f"   条件：{' 且 '.join(conditions)}\n")
    else:
        print("   条件：无（显示所有交易对）\n")
    
    filtered = filter_high_volume_markets(
        markets, 
        min_volume=args.min_volume, 
        min_open_interest_usd=args.min_open_interest
    )
    print_filtered_markets(filtered)
    
    # 列出所有交易对，标注符合/不符合条件
    if not args.no_full_list:
        print("\n" + "="*110)
        print(f"📋 所有交易对完整列表（{len(markets)}个）")
        print("="*110 + "\n")
        print_all_markets_with_status(
            markets, 
            min_volume=args.min_volume, 
            min_open_interest_usd=args.min_open_interest
        )
    
    # 生成文档
    if not args.no_doc:
        print("\n📝 正在生成对比文档...")
        md_file = save_to_markdown(data, docs_dir)
        
        print("\n✅ 完成！")
        print(f"\n📚 查看文档: {md_file}")
    else:
        print("\n✅ 完成！")
    
    print(f"\n💡 提示: 文档包含核心数据对比表和详细数据对比表")
    print(f"💡 数据更新: 运行 python3 tools/get_exchange_markets.py 更新数据")
    print(f"💡 自定义筛选: 使用 --min-volume 和 --min-oi 参数")


if __name__ == "__main__":
    main()

