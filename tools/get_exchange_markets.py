#!/usr/bin/env python3
"""
EdgeX 和 Lighter 交易所市场数据获取工具

功能：
1. 获取 EdgeX 和 Lighter 的所有交易对和市场数据
2. 提取重叠的交易对（两个交易所都有的）
3. 包含24小时交易量、合约数据等信息
4. 生成配置文件供套利监控使用

使用方法：
    python3 tools/get_exchange_markets.py
    
输出：
    - config/exchanges/edgex_lighter_markets.json: 重叠交易对配置
    - config/exchanges/edgex_markets.json: EdgeX 市场数据
    - config/exchanges/lighter_markets.json: Lighter 市场数据（更新）
    - docs/edgex_lighter_markets.md: 重叠交易对文档
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from decimal import Decimal

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class EdgeXMarketFetcher:
    """EdgeX 市场信息获取器"""
    
    def __init__(self):
        self.markets_data = []
        self.symbols = []
        
    async def fetch_markets(self) -> List[Dict]:
        """获取 EdgeX 市场信息（使用官方 REST API）"""
        print("\n" + "="*80)
        print("🔗 正在获取 EdgeX 市场数据...")
        print("="*80)
        
        try:
            from core.adapters.exchanges.adapters.edgex_rest import EdgeXRest
            
            rest = EdgeXRest(config=None)
            await rest.setup_session()
            
            try:
                # 1. 获取合约元数据（参考 edgex Meta Data API.md）
                print("📡 获取合约元数据...")
                metadata_response = await rest._request('GET', 'api/v1/public/meta/getMetaData')
                
                if metadata_response.get('code') != 'SUCCESS':
                    raise Exception(f"获取元数据失败: {metadata_response.get('msg')}")
                
                # 检查是主网还是测试网
                global_info = metadata_response.get('data', {}).get('global', {})
                app_env = global_info.get('appEnv', 'unknown')
                app_name = global_info.get('appName', 'unknown')
                base_url_used = rest.base_url
                
                print(f"  🔍 API 地址: {base_url_used}")
                print(f"  🔍 应用名称: {app_name}")
                print(f"  🔍 环境: {app_env}")
                
                if app_env == 'testnet':
                    print(f"  ⚠️  警告: 当前连接到 EdgeX 测试网！")
                    print(f"  💡 如需连接主网，请检查 base_url 配置")
                elif app_env == 'mainnet' or app_env == 'production':
                    print(f"  ✅ 确认: 当前连接到 EdgeX 主网")
                else:
                    print(f"  ℹ️  环境信息: {app_env}")
                
                contract_list = metadata_response.get('data', {}).get('contractList', [])
                print(f"✅ 获取到 {len(contract_list)} 个合约")
                
                # 构建 contractId -> contractName 映射
                contract_map = {}
                for contract in contract_list:
                    contract_id = contract.get('contractId')
                    contract_name = contract.get('contractName')
                    if contract_id and contract_name:
                        contract_map[contract_id] = contract
                
                # 2. 获取所有合约的 24 小时 ticker 数据（参考 edgex Quote API.md）
                # 注意：getTicker API 不传 contractId 时返回空列表，需要逐个获取
                print("📡 获取所有合约的 24 小时 ticker 数据...")
                print(f"  ℹ️  将逐个获取 {len(contract_list)} 个合约的 ticker 数据（分批处理）...")
                
                ticker_list = []
                batch_size = 20  # 每批处理 20 个合约
                failed_count = 0
                
                # 分批获取 ticker 数据
                for batch_start in range(0, len(contract_list), batch_size):
                    batch_end = min(batch_start + batch_size, len(contract_list))
                    batch_contracts = contract_list[batch_start:batch_end]
                    
                    for contract in batch_contracts:
                        contract_id = contract.get('contractId')
                        contract_name = contract.get('contractName')
                        
                        if not contract_id:
                            continue
                        
                        try:
                            # 传入 contractId 参数获取单个合约的 ticker 数据
                            ticker_response = await rest._request(
                                'GET', 
                                'api/v1/public/quote/getTicker',
                                params={'contractId': contract_id}
                            )
                            
                            if ticker_response.get('code') == 'SUCCESS':
                                ticker_data_list = ticker_response.get('data', [])
                                if ticker_data_list:
                                    ticker_list.extend(ticker_data_list)
                            else:
                                failed_count += 1
                                if failed_count <= 5:
                                    print(f"  ⚠️  {contract_name} (ID: {contract_id}): {ticker_response.get('msg', '获取失败')}")
                            
                            # 添加小延迟避免限流
                            await asyncio.sleep(0.05)
                            
                        except Exception as e:
                            failed_count += 1
                            if failed_count <= 5:
                                print(f"  ⚠️  {contract_name} (ID: {contract_id}): {str(e)[:50]}")
                            continue
                    
                    # 批次间延迟
                    if batch_end < len(contract_list):
                        await asyncio.sleep(0.2)
                        print(f"  📊 已处理 {batch_end}/{len(contract_list)} 个合约...")
                
                if failed_count > 5:
                    print(f"  ℹ️  共 {failed_count} 个合约无法获取 ticker 数据（已跳过）")
                
                print(f"✅ 获取到 {len(ticker_list)} 个合约的 ticker 数据")
                
                # 3. 合并数据
                self.markets_data = []
                for idx, ticker_data in enumerate(ticker_list, 1):
                    contract_id = ticker_data.get('contractId')
                    contract_name = ticker_data.get('contractName')
                    
                    if not contract_id or not contract_name:
                        continue
                    
                    # 从元数据获取更多信息
                    contract_meta = contract_map.get(contract_id, {})
                    
                    # 解析 symbol 获取 base 和 quote
                    # contractName 格式：BTCUSDT, ETHUSDT 等
                    symbol = contract_name
                    if symbol.endswith('USDT'):
                        base = symbol[:-4]
                        quote = 'USDT'
                    elif symbol.endswith('USD'):
                        base = symbol[:-3]
                        quote = 'USD'
                    else:
                        base = symbol
                        quote = 'USDT'
                    
                    # 解析 ticker 数据（参考 edgex Quote API.md 的响应格式）
                    # 字段名：size, value, trades, high, low, open, close, lastPrice, 
                    # priceChangePercent, openInterest, fundingRate
                    daily_volume_base = None
                    daily_volume_quote = None
                    daily_trades_count = None
                    last_trade_price = None
                    daily_high = None
                    daily_low = None
                    daily_price_change_pct = None
                    funding_rate = None
                    open_interest = None
                    
                    try:
                        if ticker_data.get('size'):
                            daily_volume_base = float(ticker_data['size'])
                        if ticker_data.get('value'):
                            daily_volume_quote = float(ticker_data['value'])
                        if ticker_data.get('trades'):
                            daily_trades_count = int(ticker_data['trades'])
                        if ticker_data.get('lastPrice'):
                            last_trade_price = float(ticker_data['lastPrice'])
                        if ticker_data.get('high'):
                            daily_high = float(ticker_data['high'])
                        if ticker_data.get('low'):
                            daily_low = float(ticker_data['low'])
                        if ticker_data.get('priceChangePercent'):
                            daily_price_change_pct = float(ticker_data['priceChangePercent'])
                        if ticker_data.get('openInterest'):
                            open_interest = float(ticker_data['openInterest'])
                        # EdgeX fundingRate 是4小时费率，需要×2转换为8小时
                        if ticker_data.get('fundingRate') is not None:
                            funding_rate = float(ticker_data['fundingRate']) * 2
                    except (ValueError, TypeError) as e:
                        print(f"  ⚠️  {contract_name}: 解析 ticker 数据失败 - {str(e)[:50]}")
                    
                    market_data = {
                        'symbol': symbol,
                        'base_token': {'symbol': base},
                        'quote_token': {'symbol': quote},
                        'contract_id': contract_id,
                        'is_active': contract_meta.get('enableTrade', True),
                        
                        # 24小时交易数据（从 REST API 获取）
                        'daily_volume_base': daily_volume_base,
                        'daily_volume_quote': daily_volume_quote,
                        'daily_trades_count': daily_trades_count,
                        
                        # 价格数据
                        'last_trade_price': last_trade_price,
                        'daily_high': daily_high,
                        'daily_low': daily_low,
                        'daily_price_change_pct': daily_price_change_pct,
                        
                        # 资金费率（EdgeX是4小时，转换为8小时）
                        'funding_rate': funding_rate,
                        
                        # 合约数据
                        'open_interest': open_interest,  # 未平仓合约数量
                        
                        # 元数据信息
                        'tick_size': contract_meta.get('tickSize'),
                        'step_size': contract_meta.get('stepSize'),
                        'min_order_size': contract_meta.get('minOrderSize'),
                        'max_order_size': contract_meta.get('maxOrderSize'),
                        'default_taker_fee_rate': contract_meta.get('defaultTakerFeeRate'),
                        'default_maker_fee_rate': contract_meta.get('defaultMakerFeeRate')
                    }
                    
                    self.markets_data.append(market_data)
                    
                    # 打印进度
                    if idx % 10 == 0 or idx == len(ticker_list):
                        vol_str = f"24h量:{daily_volume_quote:.0f}" if daily_volume_quote else "24h量:N/A"
                        print(f"  [{idx:3d}/{len(ticker_list)}] {base:6s} ({symbol:15s}) {vol_str}")
                
            finally:
                await rest.close_session()
            
            print(f"\n✅ EdgeX 数据获取完成：{len(self.markets_data)} 个市场")
            return self.markets_data
            
        except Exception as e:
            print(f"❌ EdgeX 数据获取失败: {e}")
            import traceback
            traceback.print_exc()
            return []


class LighterMarketFetcher:
    """Lighter 市场信息获取器（参考 get_lighter_markets.py）"""
    
    def __init__(self):
        self.api_url = "https://mainnet.zklighter.elliot.ai"
        self.markets_data = []
        
    async def fetch_markets(self) -> List[Dict]:
        """获取 Lighter 市场信息"""
        print("\n" + "="*80)
        print("🔗 正在获取 Lighter 市场数据...")
        print("="*80)
        
        try:
            print("\n🔧 使用 Lighter SDK...")
            
            import lighter
            from lighter import Configuration, ApiClient
            from lighter.api import OrderApi
            
            print("📡 初始化 Lighter SDK...")
            config = Configuration(host=self.api_url)
            api_client = ApiClient(configuration=config)
            order_api = OrderApi(api_client)
            
            print("📡 调用 order_api.order_books()...")
            response = await order_api.order_books()
            
            if not hasattr(response, 'order_books'):
                print("❌ 响应中没有 order_books 字段")
                return []
            
            print(f"✅ SDK 成功获取 {len(response.order_books)} 个市场")
            print(f"📡 正在获取每个市场的详细信息（价格精度、24小时数据等）...\n")
            
            self.markets_data = []
            for idx, order_book_info in enumerate(response.order_books, 1):
                if not (hasattr(order_book_info, 'symbol') and hasattr(order_book_info, 'market_id')):
                    continue
                
                market_id = order_book_info.market_id
                symbol = order_book_info.symbol
                
                # 提取基础币种
                base = symbol.split('-')[0] if '-' in symbol else symbol.split('/')[0]
                quote = symbol.split('-')[1] if '-' in symbol else 'USD'
                
                # 获取市场详情
                price_decimals = None
                size_decimals = None
                min_order_size = None
                min_quote_amount = None
                maker_fee = None
                taker_fee = None
                maintenance_margin = None
                initial_margin = None
                min_initial_margin = None
                closeout_margin = None
                liquidation_fee = None
                quote_multiplier = None
                open_interest = None
                last_trade_price = None
                daily_price_change = None
                daily_price_high = None
                daily_price_low = None
                daily_volume_base = None
                daily_volume_quote = None
                daily_trades = None
                funding_rate = None
                
                try:
                    details_response = await order_api.order_book_details(market_id=market_id)
                    
                    if hasattr(details_response, 'order_book_details') and details_response.order_book_details:
                        detail = details_response.order_book_details[0]
                        
                        # 基本精度信息
                        price_decimals = getattr(detail, 'price_decimals', None)
                        size_decimals = getattr(detail, 'size_decimals', None)
                        
                        # 最小下单量
                        min_order_size = getattr(detail, 'min_base_amount', None)
                        min_quote_amount = getattr(detail, 'min_quote_amount', None)
                        
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
                        
                        # 资金费率（Lighter是8小时）
                        funding_rate = getattr(detail, 'funding_rate', None)
                        
                except Exception as e:
                    print(f"  ⚠️  Market {market_id:3d} ({symbol:10s}): 无法获取详情 - {str(e)[:30]}")
                
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
                    'daily_trades_count': daily_trades,
                    
                    # 资金费率
                    'funding_rate': funding_rate
                }
                
                self.markets_data.append(market_data)
                
                # 打印进度
                price_dec_str = f"价格精度:{price_decimals}" if price_decimals is not None else "价格精度:N/A"
                size_dec_str = f"数量精度:{size_decimals}" if size_decimals is not None else "数量精度:N/A"
                vol_str = f"24h量:{daily_volume_quote:.0f}" if daily_volume_quote else "24h量:N/A"
                print(f"  [{idx:3d}/{len(response.order_books)}] Market {market_id:3d}: {base:6s} ({symbol:15s}) {price_dec_str:12s} {size_dec_str:12s} {vol_str}")
                
                # 添加延迟避免限流
                if idx % 10 == 0:
                    await asyncio.sleep(0.1)
            
            print(f"\n✅ Lighter 数据获取完成：{len(self.markets_data)} 个市场")
            return self.markets_data
            
        except ImportError as e:
            print(f"❌ Lighter SDK 未安装或导入失败: {e}")
            print("   安装命令: pip install git+https://github.com/elliottech/lighter-python.git")
            return []
        except Exception as e:
            print(f"❌ Lighter SDK 获取失败: {e}")
            import traceback
            traceback.print_exc()
            return []


class MarketDataMerger:
    """市场数据合并器"""
    
    def __init__(self, edgex_data: List[Dict], lighter_data: List[Dict]):
        self.edgex_data = edgex_data
        self.lighter_data = lighter_data
        
    def find_overlapping_symbols(self) -> Dict[str, Dict]:
        """
        查找重叠的交易对
        
        Returns:
            {base_symbol: {edgex: {...}, lighter: {...}}}
        """
        # 构建 EdgeX 的 base -> market_data 映射
        edgex_map = {}
        for market in self.edgex_data:
            base = market.get('base_token', {}).get('symbol', '')
            if base:
                edgex_map[base] = market
        
        # 构建 Lighter 的 base -> market_data 映射
        lighter_map = {}
        for market in self.lighter_data:
            base = market.get('base_token', {}).get('symbol', '')
            if base:
                lighter_map[base] = market
        
        # 找出重叠的 base
        overlapping = {}
        for base in set(edgex_map.keys()) & set(lighter_map.keys()):
            overlapping[base] = {
                'edgex': edgex_map[base],
                'lighter': lighter_map[base]
            }
        
        return overlapping
    
    def generate_config(self, overlapping: Dict[str, Dict]) -> Dict:
        """生成配置文件"""
        config = {
            'updated_at': datetime.now().isoformat(),
            'total_overlapping_symbols': len(overlapping),
            'edgex_total': len(self.edgex_data),
            'lighter_total': len(self.lighter_data),
            'overlapping_markets': {}
        }
        
        for base, markets in overlapping.items():
            edgex_market = markets['edgex']
            lighter_market = markets['lighter']
            
            config['overlapping_markets'][base] = {
                'base_token': base,
                'edgex': {
                    'symbol': edgex_market.get('symbol'),
                    'contract_id': edgex_market.get('contract_id'),
                    'quote': edgex_market.get('quote_token', {}).get('symbol', 'USDT'),
                    
                    # 24小时交易数据
                    'daily_volume_base': edgex_market.get('daily_volume_base'),
                    'daily_volume_quote': edgex_market.get('daily_volume_quote'),
                    'daily_trades_count': edgex_market.get('daily_trades_count'),
                    
                    # 价格数据
                    'last_trade_price': edgex_market.get('last_trade_price'),
                    'daily_high': edgex_market.get('daily_high'),
                    'daily_low': edgex_market.get('daily_low'),
                    'daily_price_change_pct': edgex_market.get('daily_price_change_pct'),
                    
                    # 资金费率
                    'funding_rate': edgex_market.get('funding_rate'),
                    
                    # 合约数据
                    'open_interest': edgex_market.get('open_interest')  # 未平仓合约数量
                },
                'lighter': {
                    'symbol': lighter_market.get('symbol'),
                    'market_id': lighter_market.get('market_id'),
                    'quote': lighter_market.get('quote_token', {}).get('symbol', 'USD'),
                    
                    # 精度信息
                    'price_decimals': lighter_market.get('price_decimals'),
                    'size_decimals': lighter_market.get('size_decimals'),
                    
                    # 最小下单量
                    'min_base_amount': lighter_market.get('min_base_amount'),
                    'min_quote_amount': lighter_market.get('min_quote_amount'),
                    
                    # 手续费
                    'maker_fee': lighter_market.get('maker_fee'),
                    'taker_fee': lighter_market.get('taker_fee'),
                    
                    # 24小时交易数据
                    'daily_volume_base': lighter_market.get('daily_volume_base'),
                    'daily_volume_quote': lighter_market.get('daily_volume_quote'),
                    'daily_trades_count': lighter_market.get('daily_trades_count'),
                    
                    # 价格数据
                    'last_trade_price': lighter_market.get('last_trade_price'),
                    'daily_high': lighter_market.get('daily_high'),
                    'daily_low': lighter_market.get('daily_low'),
                    'daily_price_change_pct': lighter_market.get('daily_price_change_pct'),
                    
                    # 资金费率
                    'funding_rate': lighter_market.get('funding_rate'),
                    
                    # 合约数据
                    'open_interest': lighter_market.get('open_interest'),
                    'maintenance_margin_fraction': lighter_market.get('maintenance_margin_fraction'),
                    'initial_margin_fraction': lighter_market.get('initial_margin_fraction')
                }
            }
        
        return config
    
    def save_config(self, config: Dict, output_file: Path):
        """保存配置文件"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"📄 配置文件已保存: {output_file}")
        return output_file
    
    def save_markdown(self, overlapping: Dict[str, Dict], output_file: Path):
        """保存 Markdown 文档"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# EdgeX 和 Lighter 重叠交易对\n\n")
            f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**重叠交易对数量**: {len(overlapping)}\n\n")
            f.write(f"**EdgeX 总交易对**: {len(self.edgex_data)}\n\n")
            f.write(f"**Lighter 总交易对**: {len(self.lighter_data)}\n\n")
            f.write("---\n\n")
            
            f.write("## 📊 重叠交易对列表\n\n")
            f.write("| Base | EdgeX Symbol | Lighter Symbol | EdgeX 24h量 | Lighter 24h量 | EdgeX费率 | Lighter费率 |\n")
            f.write("|------|-------------|----------------|-------------|---------------|-----------|-------------|\n")
            
            # 按交易量排序
            sorted_overlapping = sorted(
                overlapping.items(),
                key=lambda x: (
                    x[1]['lighter'].get('daily_volume_quote') or 0,
                    x[1]['edgex'].get('daily_volume_quote') or 0
                ),
                reverse=True
            )
            
            for base, markets in sorted_overlapping:
                edgex = markets['edgex']
                lighter = markets['lighter']
                
                edgex_symbol = edgex.get('symbol', 'N/A')
                lighter_symbol = lighter.get('symbol', 'N/A')
                
                edgex_vol = f"{edgex.get('daily_volume_quote', 0):,.0f}" if edgex.get('daily_volume_quote') else "N/A"
                lighter_vol = f"{lighter.get('daily_volume_quote', 0):,.0f}" if lighter.get('daily_volume_quote') else "N/A"
                
                edgex_fr = f"{edgex.get('funding_rate', 0)*100:.4f}%" if edgex.get('funding_rate') else "N/A"
                lighter_fr = f"{lighter.get('funding_rate', 0)*100:.4f}%" if lighter.get('funding_rate') else "N/A"
                
                f.write(f"| {base} | {edgex_symbol} | {lighter_symbol} | {edgex_vol} | {lighter_vol} | {edgex_fr} | {lighter_fr} |\n")
            
            f.write("\n---\n\n")
            f.write("## 📋 详细信息\n\n")
            
            for base, markets in sorted_overlapping:
                edgex = markets['edgex']
                lighter = markets['lighter']
                
                f.write(f"### {base}\n\n")
                f.write(f"#### EdgeX\n")
                f.write(f"- **Symbol**: {edgex.get('symbol')}\n")
                f.write(f"- **Contract ID**: {edgex.get('contract_id')}\n")
                f.write(f"- **24h 交易量**: {edgex.get('daily_volume_quote', 'N/A')}\n")
                f.write(f"- **24h 成交笔数**: {edgex.get('daily_trades_count', 'N/A')}\n")
                f.write(f"- **最新价格**: {edgex.get('last_trade_price', 'N/A')}\n")
                f.write(f"- **24h 涨跌幅**: {edgex.get('daily_price_change_pct', 'N/A')}%\n")
                f.write(f"- **资金费率**: {edgex.get('funding_rate', 'N/A')}\n\n")
                
                f.write(f"#### Lighter\n")
                f.write(f"- **Symbol**: {lighter.get('symbol')}\n")
                f.write(f"- **Market ID**: {lighter.get('market_id')}\n")
                f.write(f"- **价格精度**: {lighter.get('price_decimals', 'N/A')}\n")
                f.write(f"- **数量精度**: {lighter.get('size_decimals', 'N/A')}\n")
                f.write(f"- **24h 交易量**: {lighter.get('daily_volume_quote', 'N/A')}\n")
                f.write(f"- **24h 成交笔数**: {lighter.get('daily_trades_count', 'N/A')}\n")
                f.write(f"- **最新价格**: {lighter.get('last_trade_price', 'N/A')}\n")
                f.write(f"- **24h 涨跌幅**: {lighter.get('daily_price_change_pct', 'N/A')}%\n")
                f.write(f"- **资金费率**: {lighter.get('funding_rate', 'N/A')}\n")
                f.write(f"- **未平仓合约**: {lighter.get('open_interest', 'N/A')}\n\n")
        
        print(f"📄 Markdown 文档已保存: {output_file}")
        return output_file


async def main():
    """主函数"""
    print("\n" + "="*80)
    print("🚀 EdgeX 和 Lighter 市场数据获取工具")
    print("="*80 + "\n")
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config" / "exchanges"
    docs_dir = project_root / "docs"
    
    # 获取 EdgeX 数据
    edgex_fetcher = EdgeXMarketFetcher()
    edgex_data = await edgex_fetcher.fetch_markets()
    
    if not edgex_data:
        print("\n❌ 未能获取 EdgeX 数据，退出")
        return
    
    # 获取 Lighter 数据
    lighter_fetcher = LighterMarketFetcher()
    lighter_data = await lighter_fetcher.fetch_markets()
    
    if not lighter_data:
        print("\n❌ 未能获取 Lighter 数据，退出")
        return
    
    # 保存单独的交易所数据
    print("\n💾 正在保存单独的交易所数据...")
    
    # 保存 EdgeX 数据
    edgex_output = {
        'updated_at': datetime.now().isoformat(),
        'total_markets': len(edgex_data),
        'markets': edgex_data
    }
    edgex_file = config_dir / "edgex_markets.json"
    edgex_file.parent.mkdir(parents=True, exist_ok=True)
    with open(edgex_file, 'w', encoding='utf-8') as f:
        json.dump(edgex_output, f, indent=2, ensure_ascii=False)
    print(f"📄 EdgeX 数据已保存: {edgex_file}")
    
    # 保存 Lighter 数据（更新格式，参考 get_lighter_markets.py）
    lighter_map = {}
    for market in lighter_data:
        base = market.get('base_token', {}).get('symbol', '')
        if base:
            lighter_map[base] = {
                'market_id': market.get('market_id'),
                'symbol': market.get('symbol'),
                'quote': market.get('quote_token', {}).get('symbol', 'USD'),
                'is_active': market.get('is_active', False),
                'min_base_amount': market.get('min_base_amount'),
                'min_quote_amount': market.get('min_quote_amount'),
                'price_decimals': market.get('price_decimals'),
                'size_decimals': market.get('size_decimals'),
                'maker_fee': market.get('maker_fee'),
                'taker_fee': market.get('taker_fee'),
                'daily_volume_base': market.get('daily_volume_base'),
                'daily_volume_quote': market.get('daily_volume_quote'),
                'daily_trades_count': market.get('daily_trades_count'),
                'last_trade_price': market.get('last_trade_price'),
                'daily_high': market.get('daily_high'),
                'daily_low': market.get('daily_low'),
                'daily_price_change_pct': market.get('daily_price_change_pct'),
                'funding_rate': market.get('funding_rate'),
                'open_interest': market.get('open_interest')
            }
    
    lighter_output = {
        'updated_at': datetime.now().isoformat(),
        'total_markets': len(lighter_data),
        'markets': lighter_map,
        'raw_data': lighter_data
    }
    lighter_file = config_dir / "lighter_markets.json"
    with open(lighter_file, 'w', encoding='utf-8') as f:
        json.dump(lighter_output, f, indent=2, ensure_ascii=False)
    print(f"📄 Lighter 数据已保存: {lighter_file}")
    
    # 合并数据并提取重叠交易对
    print("\n🔍 正在分析重叠交易对...")
    merger = MarketDataMerger(edgex_data, lighter_data)
    overlapping = merger.find_overlapping_symbols()
    
    print(f"✅ 找到 {len(overlapping)} 个重叠交易对")
    
    if overlapping:
        # 生成配置文件
        config = merger.generate_config(overlapping)
        
        # 保存重叠交易对配置
        overlap_file = config_dir / "edgex_lighter_markets.json"
        merger.save_config(config, overlap_file)
        
        # 保存 Markdown 文档
        md_file = docs_dir / "edgex_lighter_markets.md"
        merger.save_markdown(overlapping, md_file)
        
        print("\n✅ 完成！")
        print(f"\n📚 查看文档: {md_file}")
        print(f"⚙️  查看配置: {overlap_file}")
        print(f"\n💡 提示: 重叠交易对可用于套利监控")
    else:
        print("\n⚠️  未找到重叠交易对")


if __name__ == "__main__":
    asyncio.run(main())

