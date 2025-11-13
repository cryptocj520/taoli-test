#!/usr/bin/env python3
"""
Lighter 交易所市场信息获取工具

功能：
1. 获取 Lighter 的所有交易对和 market_index
2. 保存到文档文件供后续查询
3. 同时更新到配置文件

使用方法：
    python3 tools/get_lighter_markets.py
    
输出：
    - docs/lighter_markets.md: 市场信息文档
    - config/exchanges/lighter_markets.json: JSON 格式配置
"""

import asyncio
import json
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class LighterMarketFetcher:
    """Lighter 市场信息获取器"""
    
    def __init__(self):
        self.api_url = "https://mainnet.zklighter.elliot.ai"
        self.markets_data = []
        
    async def fetch_markets(self) -> List[Dict]:
        """获取所有市场信息"""
        print("🔗 正在连接 Lighter API...")
        
        # 尝试多个可能的端点
        endpoints = [
            "/v1/markets",
            "/markets",
            "/api/v1/markets",
            "/orderbook/markets",
            "/v1/orderbook/markets",
        ]
        
        try:
            async with aiohttp.ClientSession() as session:
                for endpoint in endpoints:
                    url = f"{self.api_url}{endpoint}"
                    print(f"📡 尝试: {url}")
                    
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                # 尝试不同的数据结构
                                if isinstance(data, list):
                                    self.markets_data = data
                                elif isinstance(data, dict):
                                    self.markets_data = data.get('data', data.get('markets', []))
                                
                                if self.markets_data:
                                    print(f"✅ 成功获取 {len(self.markets_data)} 个市场")
                                    return self.markets_data
                            elif response.status != 404:
                                print(f"   ⚠️  HTTP {response.status}")
                    except asyncio.TimeoutError:
                        print(f"   ⏱️  超时")
                        continue
                    except Exception as e:
                        print(f"   ❌ {str(e)[:50]}")
                        continue
                
                print(f"\n❌ 所有端点都失败了")
                print(f"\n💡 提示：Lighter 可能需要通过 SDK 或 WebSocket 获取市场信息")
                print(f"   让我尝试使用 SDK...")
                
                # 尝试使用 Lighter SDK
                return await self._fetch_via_sdk()
                
        except Exception as e:
            print(f"❌ 获取市场信息失败: {e}")
            return []
    
    async def _fetch_via_sdk(self) -> List[Dict]:
        """尝试使用 Lighter SDK 获取市场信息"""
        try:
            print("\n🔧 使用 Lighter SDK...")
            
            # 参考: core/adapters/exchanges/adapters/lighter_rest.py 的 _load_markets 方法
            import lighter
            from lighter import Configuration, ApiClient
            from lighter.api import OrderApi
            
            print("📡 初始化 Lighter SDK...")
            
            # 参考: lighter_rest.py 第 166-171 行
            config = Configuration(host=self.api_url)
            api_client = ApiClient(configuration=config)
            order_api = OrderApi(api_client)
            
            print("📡 调用 order_api.order_books()...")
            
            # 参考: lighter_rest.py 第 266 行
            # 直接 await，order_books() 是异步方法
            response = await order_api.order_books()
            
            if hasattr(response, 'order_books'):
                print(f"✅ SDK 成功获取 {len(response.order_books)} 个市场")
                print(f"📡 正在获取每个市场的详细信息（价格精度等）...\n")
                
                # 转换为标准格式
                self.markets_data = []
                for idx, order_book_info in enumerate(response.order_books, 1):
                    if hasattr(order_book_info, 'symbol') and hasattr(order_book_info, 'market_id'):
                        market_id = order_book_info.market_id
                        symbol = order_book_info.symbol
                        
                        # 提取基础币种
                        base = symbol.split('-')[0] if '-' in symbol else symbol.split('/')[0]
                        quote = symbol.split('-')[1] if '-' in symbol else 'USD'
                        
                        # 获取市场详情以获取价格精度
                        price_decimals = None
                        size_decimals = None
                        min_order_size = None
                        
                        try:
                            # 参考: lighter_rest.py 第 911 行
                            # order_book_details 也是异步方法，直接 await
                            details_response = await order_api.order_book_details(market_id=market_id)
                            
                            if hasattr(details_response, 'order_book_details') and details_response.order_book_details:
                                detail = details_response.order_book_details[0]
                                
                                # 基本精度信息
                                price_decimals = getattr(detail, 'price_decimals', None)
                                size_decimals = getattr(detail, 'size_decimals', None)
                                
                                # 最小下单量
                                min_order_size = getattr(detail, 'min_base_amount', None)  # 最小基础币种数量
                                min_quote_amount = getattr(detail, 'min_quote_amount', None)  # 最小报价金额
                                
                                # 手续费信息
                                maker_fee = getattr(detail, 'maker_fee', None)
                                taker_fee = getattr(detail, 'taker_fee', None)
                                
                                # 保证金信息
                                maintenance_margin = getattr(detail, 'maintenance_margin_fraction', None)
                                initial_margin = getattr(detail, 'default_initial_margin_fraction', None)
                                min_initial_margin = getattr(detail, 'min_initial_margin_fraction', None)
                                closeout_margin = getattr(detail, 'closeout_margin_fraction', None)
                                liquidation_fee = getattr(detail, 'liquidation_fee', None)
                                
                                # 市场数据
                                quote_multiplier = getattr(detail, 'quote_multiplier', None)
                                open_interest = getattr(detail, 'open_interest', None)
                                last_trade_price = getattr(detail, 'last_trade_price', None)
                                
                                # 24小时数据
                                daily_price_change = getattr(detail, 'daily_price_change', None)
                                daily_price_high = getattr(detail, 'daily_price_high', None)
                                daily_price_low = getattr(detail, 'daily_price_low', None)
                                daily_volume_base = getattr(detail, 'daily_base_token_volume', None)
                                daily_volume_quote = getattr(detail, 'daily_quote_token_volume', None)
                                daily_trades = getattr(detail, 'daily_trades_count', None)
                        except Exception as e:
                            print(f"  ⚠️  Market {market_id:3d} ({symbol:10s}): 无法获取详情 - {str(e)[:30]}")
                        
                        # 添加小延迟避免限流
                        if idx % 10 == 0:
                            await asyncio.sleep(0.1)
                        
                        market_data = {
                            'market_id': market_id,
                            'symbol': symbol,
                            'base_token': {'symbol': base},
                            'quote_token': {'symbol': quote},
                            'is_active': True,
                            
                            # 精度信息
                            'price_decimals': price_decimals,
                            'size_decimals': size_decimals,
                            
                            # 最小下单量
                            'min_base_amount': min_order_size,
                            'min_quote_amount': min_quote_amount,
                            
                            # 手续费
                            'maker_fee': maker_fee,
                            'taker_fee': taker_fee,
                            
                            # 保证金
                            'maintenance_margin_fraction': maintenance_margin,
                            'initial_margin_fraction': initial_margin,
                            'min_initial_margin_fraction': min_initial_margin,
                            'closeout_margin_fraction': closeout_margin,
                            'liquidation_fee': liquidation_fee,
                            
                            # 市场数据
                            'quote_multiplier': quote_multiplier,
                            'open_interest': open_interest,
                            'last_trade_price': last_trade_price,
                            
                            # 24小时统计
                            'daily_price_change_pct': daily_price_change,
                            'daily_high': daily_price_high,
                            'daily_low': daily_price_low,
                            'daily_volume_base': daily_volume_base,
                            'daily_volume_quote': daily_volume_quote,
                            'daily_trades_count': daily_trades
                        }
                        
                        self.markets_data.append(market_data)
                        
                        # 打印包含精度信息和最小下单金额
                        price_dec_str = f"价格精度:{price_decimals}" if price_decimals is not None else "价格精度:N/A"
                        size_dec_str = f"数量精度:{size_decimals}" if size_decimals is not None else "数量精度:N/A"
                        min_size_str = f"最小:{min_order_size}" if min_order_size is not None else "最小:N/A"
                        maker_str = f"Maker:{maker_fee}" if maker_fee is not None else "Maker:N/A"
                        taker_str = f"Taker:{taker_fee}" if taker_fee is not None else "Taker:N/A"
                        print(f"  [{idx:3d}/{len(response.order_books)}] Market {market_id:3d}: {base:6s} ({symbol:15s}) {price_dec_str:12s} {size_dec_str:12s} {min_size_str:15s} {maker_str:15s} {taker_str}")
                
                return self.markets_data
            else:
                print("❌ 响应中没有 order_books 字段")
            
        except ImportError as e:
            print(f"❌ Lighter SDK 未安装或导入失败: {e}")
            print("   安装命令: pip install git+https://github.com/elliottech/lighter-python.git")
        except Exception as e:
            print(f"❌ SDK 获取失败: {e}")
            import traceback
            traceback.print_exc()
        
        return []
    
    def save_to_markdown(self, output_dir: Path):
        """保存为 Markdown 文档"""
        output_file = output_dir / "lighter_markets.md"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 按 market_id 排序
        sorted_markets = sorted(self.markets_data, key=lambda x: x.get('market_id', 0))
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Lighter 交易所市场信息\n\n")
            f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**市场总数**: {len(sorted_markets)}\n\n")
            f.write("---\n\n")
            
            # 创建表格
            f.write("## 📊 市场列表\n\n")
            f.write("| Market ID | Symbol | Base | Quote | 价格精度 | 数量精度 | 最小下单量 | Status |\n")
            f.write("|-----------|--------|------|-------|----------|----------|------------|--------|\n")
            
            for market in sorted_markets:
                market_id = market.get('market_id', 'N/A')
                symbol = market.get('symbol', 'N/A')
                base = market.get('base_token', {}).get('symbol', 'N/A')
                quote = market.get('quote_token', {}).get('symbol', 'N/A')
                price_decimals = market.get('price_decimals', 'N/A')
                size_decimals = market.get('size_decimals', 'N/A')
                min_base_amount = market.get('min_base_amount', 'N/A')
                status = '🟢' if market.get('is_active') else '🔴'
                
                f.write(f"| {market_id} | {symbol} | {base} | {quote} | {price_decimals} | {size_decimals} | {min_base_amount} | {status} |\n")
            
            # 添加常用币种快速查找
            f.write("\n---\n\n")
            f.write("## 🔍 常用币种快速查找\n\n")
            
            common_symbols = ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC', 'ARB', 'OP', 'LINK', 'UNI', 'AAVE']
            
            for symbol in common_symbols:
                found = None
                for market in sorted_markets:
                    base = market.get('base_token', {}).get('symbol', '')
                    if base == symbol:
                        found = market
                        break
                
                if found:
                    market_id = found.get('market_id')
                    full_symbol = found.get('symbol')
                    price_decimals = found.get('price_decimals', 'N/A')
                    size_decimals = found.get('size_decimals', 'N/A')
                    min_base = found.get('min_base_amount', 'N/A')
                    maker_fee = found.get('maker_fee', 'N/A')
                    taker_fee = found.get('taker_fee', 'N/A')
                    f.write(f"- **{symbol}**: `market_id = {market_id}` ({full_symbol})\n")
                    f.write(f"  - 价格精度: {price_decimals}位, 数量精度: {size_decimals}位, 最小下单: {min_base}\n")
                    f.write(f"  - Maker费率: {maker_fee}, Taker费率: {taker_fee}\n")
                else:
                    f.write(f"- **{symbol}**: ❌ 未找到\n")
            
            # 添加使用示例
            f.write("\n---\n\n")
            f.write("## 💡 使用示例\n\n")
            f.write("### Python 代码中使用\n\n")
            f.write("```python\n")
            f.write("# 订阅 BTC 的 market_stats\n")
            btc_market = next((m for m in sorted_markets if m.get('base_token', {}).get('symbol') == 'BTC'), None)
            if btc_market:
                f.write(f"btc_index = {btc_market.get('market_id')}  # BTC\n")
            f.write("stats_msg = {\n")
            f.write("    'type': 'subscribe',\n")
            f.write("    'channel': f'market_stats/{btc_index}'\n")
            f.write("}\n")
            f.write("```\n\n")
            
            # 添加详细信息
            f.write("---\n\n")
            f.write("## 📋 完整市场详情\n\n")
            
            for market in sorted_markets:
                market_id = market.get('market_id', 'N/A')
                symbol = market.get('symbol', 'N/A')
                base = market.get('base_token', {}).get('symbol', 'N/A')
                
                f.write(f"### {base} (Market ID: {market_id})\n\n")
                f.write(f"#### 基本信息\n")
                f.write(f"- **完整符号**: {symbol}\n")
                f.write(f"- **Base Token**: {base}\n")
                f.write(f"- **Quote Token**: {market.get('quote_token', {}).get('symbol', 'N/A')}\n")
                f.write(f"- **状态**: {'🟢 活跃' if market.get('is_active') else '🔴 暂停'}\n\n")
                
                f.write(f"#### 交易参数\n")
                f.write(f"- **价格精度**: {market.get('price_decimals', 'N/A')} 位小数\n")
                f.write(f"- **数量精度**: {market.get('size_decimals', 'N/A')} 位小数\n")
                f.write(f"- **最小基础币数量**: {market.get('min_base_amount', 'N/A')}\n")
                f.write(f"- **最小报价金额**: {market.get('min_quote_amount', 'N/A')}\n")
                f.write(f"- **Maker手续费**: {market.get('maker_fee', 'N/A')}\n")
                f.write(f"- **Taker手续费**: {market.get('taker_fee', 'N/A')}\n\n")
                
                f.write(f"#### 保证金要求\n")
                f.write(f"- **维持保证金率**: {market.get('maintenance_margin_fraction', 'N/A')}\n")
                f.write(f"- **初始保证金率**: {market.get('initial_margin_fraction', 'N/A')}\n")
                f.write(f"- **最小初始保证金率**: {market.get('min_initial_margin_fraction', 'N/A')}\n")
                f.write(f"- **强平保证金率**: {market.get('closeout_margin_fraction', 'N/A')}\n")
                f.write(f"- **清算费**: {market.get('liquidation_fee', 'N/A')}\n\n")
                
                f.write(f"#### 市场数据\n")
                f.write(f"- **报价乘数**: {market.get('quote_multiplier', 'N/A')}\n")
                f.write(f"- **未平仓合约**: {market.get('open_interest', 'N/A')}\n")
                f.write(f"- **最新成交价**: {market.get('last_trade_price', 'N/A')}\n\n")
                
                f.write(f"#### 24小时统计\n")
                f.write(f"- **涨跌幅**: {market.get('daily_price_change_pct', 'N/A')}\n")
                f.write(f"- **最高价**: {market.get('daily_high', 'N/A')}\n")
                f.write(f"- **最低价**: {market.get('daily_low', 'N/A')}\n")
                f.write(f"- **成交量(Base)**: {market.get('daily_volume_base', 'N/A')}\n")
                f.write(f"- **成交量(Quote)**: {market.get('daily_volume_quote', 'N/A')}\n")
                f.write(f"- **成交笔数**: {market.get('daily_trades_count', 'N/A')}\n\n")
        
        print(f"📄 Markdown 文档已保存: {output_file}")
        return output_file
    
    def save_to_json(self, output_dir: Path):
        """保存为 JSON 配置文件"""
        output_file = output_dir / "lighter_markets.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建简化的映射表（快速查询用）
        markets_map = {}
        for market in self.markets_data:
            base = market.get('base_token', {}).get('symbol', '')
            if base:
                markets_map[base] = {
                    'market_id': market.get('market_id'),
                    'symbol': market.get('symbol'),
                    'quote': market.get('quote_token', {}).get('symbol', 'USD'),
                    'is_active': market.get('is_active', False),
                    'min_base_amount': market.get('min_base_amount'),  # 最小基础币数量
                    'min_quote_amount': market.get('min_quote_amount'),  # 最小报价金额
                    'price_decimals': market.get('price_decimals'),
                    'size_decimals': market.get('size_decimals'),
                    'maker_fee': market.get('maker_fee'),
                    'taker_fee': market.get('taker_fee')
                }
        
        output_data = {
            'updated_at': datetime.now().isoformat(),
            'total_markets': len(self.markets_data),
            'markets': markets_map,
            'raw_data': self.markets_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 JSON 配置已保存: {output_file}")
        return output_file
    
    def print_summary(self):
        """打印摘要信息"""
        print("\n" + "="*80)
        print("📊 市场信息摘要")
        print("="*80)
        
        print(f"\n总市场数: {len(self.markets_data)}")
        
        # 统计活跃市场
        active_count = sum(1 for m in self.markets_data if m.get('is_active'))
        print(f"活跃市场: {active_count}")
        print(f"暂停市场: {len(self.markets_data) - active_count}")
        
        # 显示前10个市场
        print("\n前10个市场:")
        sorted_markets = sorted(self.markets_data, key=lambda x: x.get('market_id', 0))[:10]
        
        for market in sorted_markets:
            market_id = market.get('market_id')
            symbol = market.get('symbol')
            base = market.get('base_token', {}).get('symbol', 'N/A')
            status = '🟢' if market.get('is_active') else '🔴'
            print(f"  {status} Market {market_id:3d}: {base:6s} ({symbol})")
        
        print("\n" + "="*80 + "\n")


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("🚀 Lighter 市场信息获取工具")
    print("="*80 + "\n")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"
    config_dir = project_root / "config" / "exchanges"
    
    # 创建获取器
    fetcher = LighterMarketFetcher()
    
    # 获取市场数据
    markets = await fetcher.fetch_markets()
    
    if not markets:
        print("\n❌ 未能获取市场数据，退出")
        return
    
    # 打印摘要
    fetcher.print_summary()
    
    # 保存文件
    print("💾 正在保存文件...")
    md_file = fetcher.save_to_markdown(docs_dir)
    json_file = fetcher.save_to_json(config_dir)
    
    print("\n✅ 完成！")
    print(f"\n📚 查看文档: {md_file}")
    print(f"⚙️  查看配置: {json_file}")
    print("\n💡 提示: 你可以在代码中导入 JSON 文件来获取 market_id")
    

if __name__ == "__main__":
    asyncio.run(main())

