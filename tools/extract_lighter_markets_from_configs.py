#!/usr/bin/env python3
"""
从现有配置文件中提取 Lighter 市场信息

功能：
1. 扫描所有 lighter-*.yaml 配置文件
2. 提取交易对和 market_index
3. 生成市场信息文档

使用方法：
    python3 tools/extract_lighter_markets_from_configs.py
"""

import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def extract_markets_from_configs():
    """从配置文件中提取市场信息"""
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config" / "grid"
    
    markets = {}
    config_files = []
    
    print("🔍 扫描配置文件...")
    
    # 查找所有 lighter 配置文件
    for config_file in config_dir.glob("lighter-*.yaml"):
        if '模版' not in config_file.name:  # 跳过模板文件
            config_files.append(config_file)
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    
                    # 提取交易所信息
                    exchange = config.get('exchange', 'unknown')
                    if exchange != 'lighter':
                        continue
                    
                    # 提取交易对信息
                    symbol = config.get('symbol', '')
                    
                    # 尝试从不同字段获取 market_index
                    market_index = None
                    
                    # 方法1: 直接从配置中
                    if 'market_index' in config:
                        market_index = config['market_index']
                    
                    # 方法2: 从 exchange_config 中
                    elif 'exchange_config' in config:
                        market_index = config['exchange_config'].get('market_index')
                    
                    # 方法3: 从 symbol_config 中
                    elif 'symbol_config' in config:
                        market_index = config['symbol_config'].get('market_index')
                    
                    if symbol and market_index is not None:
                        # 提取基础币种
                        base = symbol.split('-')[0] if '-' in symbol else symbol.split('/')[0]
                        
                        if base not in markets:
                            markets[base] = {
                                'market_id': market_index,
                                'symbol': symbol,
                                'config_file': config_file.name
                            }
                            print(f"  ✅ {base:6s} -> market_id: {market_index:3d} (来自: {config_file.name})")
                        
            except Exception as e:
                print(f"  ⚠️  读取 {config_file.name} 失败: {e}")
    
    print(f"\n📊 共扫描 {len(config_files)} 个配置文件")
    print(f"✅ 提取到 {len(markets)} 个市场信息\n")
    
    return markets


def save_to_markdown(markets: dict, output_dir: Path):
    """保存为 Markdown 文档"""
    output_file = output_dir / "lighter_markets.md"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 按 market_id 排序
    sorted_markets = sorted(markets.items(), key=lambda x: x[1]['market_id'])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Lighter 交易所市场信息\n\n")
        f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**数据来源**: 从现有配置文件中提取\n\n")
        f.write(f"**市场总数**: {len(markets)}\n\n")
        f.write("---\n\n")
        
        # 创建表格
        f.write("## 📊 已知市场列表\n\n")
        f.write("| Market ID | Base Symbol | Full Symbol | 配置文件 |\n")
        f.write("|-----------|-------------|-------------|----------|\n")
        
        for base, info in sorted_markets:
            market_id = info['market_id']
            symbol = info['symbol']
            config_file = info['config_file']
            
            f.write(f"| {market_id} | {base} | {symbol} | {config_file} |\n")
        
        # 添加快速查找
        f.write("\n---\n\n")
        f.write("## 🔍 快速查找\n\n")
        
        for base, info in sorted_markets:
            market_id = info['market_id']
            symbol = info['symbol']
            f.write(f"- **{base}**: `market_id = {market_id}` ({symbol})\n")
        
        # 添加使用示例
        f.write("\n---\n\n")
        f.write("## 💡 使用示例\n\n")
        f.write("### WebSocket 订阅\n\n")
        f.write("```python\n")
        
        if markets:
            first_base, first_info = sorted_markets[0]
            f.write(f"# 订阅 {first_base} 的 market_stats\n")
            f.write(f"market_index = {first_info['market_id']}  # {first_base}\n")
            f.write("\n")
        
        f.write("# Market Stats 订阅\n")
        f.write("stats_msg = {\n")
        f.write("    'type': 'subscribe',\n")
        f.write("    'channel': f'market_stats/{market_index}'\n")
        f.write("}\n\n")
        f.write("# Order Book 订阅\n")
        f.write("orderbook_msg = {\n")
        f.write("    'type': 'subscribe',\n")
        f.write("    'channel': f'order_book/{market_index}'\n")
        f.write("}\n")
        f.write("```\n\n")
        
        # 添加Python代码映射
        f.write("### Python 字典映射\n\n")
        f.write("```python\n")
        f.write("LIGHTER_MARKETS = {\n")
        for base, info in sorted_markets:
            f.write(f"    '{base}': {info['market_id']},\n")
        f.write("}\n")
        f.write("```\n\n")
        
        # 添加注意事项
        f.write("---\n\n")
        f.write("## ⚠️ 注意事项\n\n")
        f.write("1. 此文档从现有配置文件中提取，可能不完整\n")
        f.write("2. 如需完整列表，请运行 `tools/get_lighter_markets.py`\n")
        f.write("3. 如果需要添加新的交易对，请：\n")
        f.write("   - 访问 Lighter 网站查看可用市场\n")
        f.write("   - 或通过 WebSocket 订阅测试获取 market_id\n")
        f.write("4. Market ID 可能会变化，建议定期更新\n\n")
    
    print(f"📄 Markdown 文档已保存: {output_file}")
    return output_file


def main():
    """主函数"""
    print("\n" + "="*80)
    print("🚀 从配置文件提取 Lighter 市场信息")
    print("="*80 + "\n")
    
    # 提取市场信息
    markets = extract_markets_from_configs()
    
    if not markets:
        print("\n❌ 未能提取任何市场信息")
        print("💡 请确保 config/grid/ 目录中有 lighter-*.yaml 配置文件")
        return
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"
    
    # 保存文件
    print("💾 正在保存文件...")
    md_file = save_to_markdown(markets, docs_dir)
    
    print("\n✅ 完成！")
    print(f"\n📚 查看文档: {md_file}")
    print("\n💡 提示: 如需测试新的交易对，可以运行 test_sol_orderbook.py")
    

if __name__ == "__main__":
    main()

