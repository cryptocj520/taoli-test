"""
UI组件模块

职责：
- 提供可复用的UI组件
- 表格、面板、文本等Rich组件
- 支持动态精度和资金费率显示（参考 simple_printer.py）
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from datetime import datetime, timedelta

from ..analysis.opportunity_finder import ArbitrageOpportunity


class UIComponents:
    """
    UI组件工厂
    
    支持动态精度和资金费率显示（参考 simple_printer.py）
    """
    
    # 🔥 类级别的精度配置缓存（参考 simple_printer.py）
    _market_precisions: Dict[str, Dict[str, int]] = {}
    _precision_loaded: bool = False
    
    @classmethod
    def _load_market_precisions(cls):
        """从配置文件加载市场精度信息（参考 simple_printer.py）"""
        if cls._precision_loaded:
            return
        
        try:
            # 尝试多个可能的配置文件路径
            config_paths = [
                Path("config/exchanges/lighter_markets.json"),  # 从当前工作目录（项目根目录）
                Path(__file__).parent.parent.parent.parent.parent / "config" / "exchanges" / "lighter_markets.json",  # 从文件位置向上5级
            ]
            
            config_path = None
            for path in config_paths:
                if path.exists():
                    config_path = path
                    break
            
            if config_path and config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                    markets = config_data.get('markets', {})
                    for symbol, market_info in markets.items():
                        # 提取精度信息
                        price_decimals = market_info.get('price_decimals')
                        size_decimals = market_info.get('size_decimals')
                        
                        if price_decimals is not None and size_decimals is not None:
                            cls._market_precisions[symbol] = {
                                'price_decimals': int(price_decimals),
                                'size_decimals': int(size_decimals)
                            }
                    
                    # 🔥 UI模式下不打印，避免界面闪动（静默加载）
                    pass
            
            cls._precision_loaded = True
        except Exception as e:
            # 🔥 UI模式下不打印，避免界面闪动（静默失败，使用默认精度）
            cls._precision_loaded = True  # 标记为已加载，避免重复尝试
    
    @classmethod
    def _get_precision(cls, symbol: str) -> Dict[str, int]:
        """
        获取交易对的精度信息（参考 simple_printer.py）
        
        Args:
            symbol: 交易对符号（如 "BTC-USDC-PERP"）
            
        Returns:
            {'price_decimals': int, 'size_decimals': int}
        """
        cls._load_market_precisions()
        
        # 提取基础币种（如 "BTC-USDC-PERP" -> "BTC"）
        base_symbol = symbol.split('-')[0] if '-' in symbol else symbol.split('/')[0]
        
        if base_symbol in cls._market_precisions:
            return cls._market_precisions[base_symbol]
        else:
            # 默认精度（向后兼容）
            return {'price_decimals': 2, 'size_decimals': 1}
    
    @staticmethod
    def _format_size(size: float, size_decimals: int) -> str:
        """
        格式化数量（根据精度，参考 simple_printer.py）
        
        Args:
            size: 数量
            size_decimals: 数量精度（小数位数）
            
        Returns:
            格式化后的字符串
        """
        if size_decimals == 0:
            # 整数格式
            return f"{size:,.0f}"
        else:
            # 小数格式
            return f"{size:,.{size_decimals}f}"
    
    @staticmethod
    def _format_funding_rate(funding_rate: Optional[float]) -> str:
        """
        格式化资金费率显示（参考 simple_printer.py）
        
        Args:
            funding_rate: 资金费率（8小时）
            
        Returns:
            格式化后的字符串，格式：8h%/年化%
        """
        if funding_rate is None:
            return "-"
        fr_8h = float(funding_rate * 100)
        fr_annual = fr_8h * 1095
        return f"{fr_8h:.4f}%/{fr_annual:.1f}%"
    
    @staticmethod
    def create_summary_panel(stats: Dict) -> Panel:
        """
        创建摘要面板
        
        Args:
            stats: 统计数据
            
        Returns:
            摘要面板
        """
        text = Text()
        text.append("🚀 套利监控系统 V2\n", style="bold white")  # 🔥 去掉空行
        
        # 运行时间
        uptime = stats.get('uptime_seconds', 0)
        text.append(f"运行时间: {UIComponents._format_duration(uptime)}\n", style="white")
        
        # 交易所数量
        exchanges = stats.get('exchanges', [])
        text.append(f"交易所: {', '.join(exchanges)}\n", style="white")
        
        # 监控代币数量
        symbols_count = stats.get('symbols_count', 0)
        text.append(f"监控代币: {symbols_count} 个\n", style="white")
        
        # 活跃机会
        active_opps = stats.get('active_opportunities', 0)
        text.append(f"💰 活跃套利机会: {active_opps} 个\n", style="bold white")  # 🔥 去掉前面的空行
        
        # 🔥 WS重连次数统计
        reconnect_stats = stats.get('reconnect_stats', {})
        if reconnect_stats:
            reconnect_info = []
            for exchange, count in reconnect_stats.items():
                if count > 0:
                    reconnect_info.append(f"{exchange.upper()}={count}")
            if reconnect_info:
                text.append(f"🔄 WS重连: {', '.join(reconnect_info)}\n", style="dim white")
            else:
                text.append(f"🔄 WS重连: 无\n", style="dim white")
        else:
            text.append(f"🔄 WS重连: 无\n", style="dim white")
        
        return Panel(text, title="[bold white]系统状态[/bold white]", border_style="white")
    
    @classmethod
    def create_opportunities_table(
        cls, 
        opportunities: List[ArbitrageOpportunity], 
        limit: int = 20,
        ui_opportunity_tracking: Optional[Dict[str, Dict]] = None,
        symbol_occurrence_timestamps: Optional[Dict[str, List]] = None
    ) -> Panel:
        """
        创建机会表格（使用Panel样式，不显示格子边框）
        
        Args:
            opportunities: 机会列表
            limit: 显示数量限制
            ui_opportunity_tracking: UI层持续时间跟踪 {key: {'ui_duration_start': datetime, 'last_seen': datetime}}
            symbol_occurrence_timestamps: 代币出现时间戳 {symbol: [timestamp1, timestamp2, ...]}
            
        Returns:
            机会面板
        """
        text = Text()
        text.append(f"🏆 套利机会 Top {min(len(opportunities), limit)}\n\n", style="bold white")
        
        if opportunities:
            # 表头（增加资金费率差列，精确对齐）
            # 定义列宽度常量，确保表头和数据行一致
            COL_WIDTH_TOKEN = 10
            COL_WIDTH_BUY_EX = 12
            COL_WIDTH_SELL_EX = 12
            COL_WIDTH_PRICE = 35
            COL_WIDTH_SPREAD = 10
            COL_WIDTH_FR_DIFF = 20
            COL_WIDTH_DURATION = 12
            COL_WIDTH_OCCURRENCE = 10  # 🔥 出现次数列宽度
            COL_WIDTH_SAME_DIR = 6  # 🔥 同向列宽度
            
            # 🔥 表头（确保与数据行对齐，列之间只有一个空格）
            header = (
                f"{'代币':<{COL_WIDTH_TOKEN}} "
                f"{'买入交易所':<{COL_WIDTH_BUY_EX}} "
                f"{'卖出交易所':<{COL_WIDTH_SELL_EX}} "
                f"{'买价/卖价':<{COL_WIDTH_PRICE}} "
                f"{'价差%':>{COL_WIDTH_SPREAD}} "  # 右对齐，后面有空格
                f"{'费率差(年化)':>{COL_WIDTH_FR_DIFF}} "  # 右对齐，后面有空格
                f"{'持续时间':<{COL_WIDTH_DURATION}} "  # 左对齐，后面有空格
                f"{'出现次数':>{COL_WIDTH_OCCURRENCE}} "  # 右对齐，后面有空格
                f"{'同向':<{COL_WIDTH_SAME_DIR}}\n"  # 左对齐
            )
            text.append(header, style="dim white")
            text.append("─" * 120 + "\n", style="dim white")
            
            # 数据行（使用相同的列宽度，确保对齐）
            for opp in opportunities[:limit]:
                # 🔥 获取精度信息（动态精度，与实时订单簿表格一致）
                precision = cls._get_precision(opp.symbol)
                price_decimals = precision['price_decimals']
                size_decimals = precision['size_decimals']
                
                # 🔥 使用动态精度格式化价格和数量
                price_buy_str = f"{opp.price_buy:,.{price_decimals}f}"
                size_buy_str = cls._format_size(opp.size_buy, size_decimals)
                price_sell_str = f"{opp.price_sell:,.{price_decimals}f}"
                size_sell_str = cls._format_size(opp.size_sell, size_decimals)
                
                price_str = f"{price_buy_str}({size_buy_str}) / {price_sell_str}({size_sell_str})"
                
                # 🔥 UI层持续时间（带2秒容差）
                ui_duration_seconds = 0.0
                if ui_opportunity_tracking:
                    key = opp.get_opportunity_key()
                    if key in ui_opportunity_tracking:
                        tracking = ui_opportunity_tracking[key]
                        current_time = datetime.now()
                        ui_duration_seconds = (current_time - tracking['ui_duration_start']).total_seconds()
                duration_str = UIComponents._format_duration(ui_duration_seconds)
                
                # 🔥 出现次数（过去15分钟）
                occurrence_count = 0
                if symbol_occurrence_timestamps and opp.symbol in symbol_occurrence_timestamps:
                    cutoff_time = datetime.now() - timedelta(minutes=15)
                    occurrence_count = len([
                        ts for ts in symbol_occurrence_timestamps[opp.symbol]
                        if ts > cutoff_time
                    ])
                occurrence_str = f"{occurrence_count}"
                
                # 🔥 格式化资金费率差（参考v1算法：8小时费率差转换为年化费率差）
                diff_annual = 0  # 🔥 初始化，用于样式判断
                if opp.funding_rate_diff is not None:
                    # opp.funding_rate_diff 是8小时费率差（小数形式，如0.0001表示0.01%）
                    # 🔥 资金费率差应该永远为正数（绝对值差值）
                    rate_diff = abs(opp.funding_rate_diff)  # 确保是正数
                    # 8小时差值（百分比）
                    diff_8h = float(rate_diff * 100)
                    # 年化差值：8小时差值 × 1095
                    diff_annual = diff_8h * 1095
                    # 费率差永远是正数，不需要符号，右对齐，固定宽度
                    funding_rate_diff_str = f"{diff_annual:.1f}%".rjust(COL_WIDTH_FR_DIFF)
                else:
                    funding_rate_diff_str = "-".rjust(COL_WIDTH_FR_DIFF)  # 🔥 右对齐
                
                # 🔥 使用相同的列宽度格式化，确保对齐（与表头对齐方式一致）
                # 价差%：右对齐，固定宽度
                spread_pct_str = f"{opp.spread_pct:>+{COL_WIDTH_SPREAD-1}.3f}%".rjust(COL_WIDTH_SPREAD)
                
                # 🔥 构建行内容，所有数据默认使用灰色（dim white），只有资金费率差在达到阈值时使用白色
                # 确保列之间只有一个空格，与表头一致
                row_prefix = (
                    f"{opp.symbol:<{COL_WIDTH_TOKEN}} "
                    f"{opp.exchange_buy:<{COL_WIDTH_BUY_EX}} "
                    f"{opp.exchange_sell:<{COL_WIDTH_SELL_EX}} "
                    f"{price_str:<{COL_WIDTH_PRICE}} "
                    f"{spread_pct_str} "  # 🔥 右对齐，后面有空格（与表头一致）
                )
                
                # 🔥 资金费率差样式：>=40时使用白色，否则使用dim white
                if funding_rate_diff_str.strip() != "-" and diff_annual >= 40:
                    funding_rate_diff_style = "white"
                else:
                    funding_rate_diff_style = "dim white"
                
                # 🔥 计算同向（参考实时订单簿表格的算法）
                # 1. 价差方向：买入交易所做多（因为买入交易所价格低），卖出交易所做空（因为卖出交易所价格高）
                # 2. 资金费率方向：费率低的交易所做多
                # 3. 判断是否同向：如果买入交易所的资金费率 <= 卖出交易所的资金费率，则同向
                same_direction_str = ""
                if opp.funding_rate_buy is not None and opp.funding_rate_sell is not None:
                    # 买入交易所做多，如果买入交易所的资金费率 <= 卖出交易所的资金费率，则同向
                    if opp.funding_rate_buy <= opp.funding_rate_sell:
                        same_direction_str = "同向"
                
                # 🔥 确保出现次数右对齐（与表头一致）
                occurrence_str_formatted = f"{occurrence_str:>{COL_WIDTH_OCCURRENCE}}"
                
                row_suffix = (
                    f"{duration_str:<{COL_WIDTH_DURATION}} "  # 🔥 左对齐，后面有空格（与表头一致）
                    f"{occurrence_str_formatted} "  # 🔥 右对齐，后面有空格（与表头一致）
                    f"{same_direction_str:<{COL_WIDTH_SAME_DIR}}\n"  # 🔥 左对齐（与表头一致）
                )
                
                # 🔥 使用Rich的Text对象分段设置样式（直接在text上append，确保样式正确应用）
                # 所有数据默认使用灰色（bright_black），只有资金费率差在达到阈值时使用白色
                # 使用bright_black确保灰色更明显，避免dim white在某些终端中看起来像白色
                text.append(row_prefix, style="bright_black")
                text.append(funding_rate_diff_str + " ", style=funding_rate_diff_style)  # 🔥 资金费率差使用单独样式
                text.append(row_suffix, style="bright_black")
        else:
            text.append("暂无套利机会\n", style="dim white")
        
        return Panel(text, title="[bold white]套利机会[/bold white]", border_style="white")
    
    @classmethod
    def create_price_table(
        cls, 
        orderbook_data: Dict, 
        symbols: List[str], 
        exchanges: List[str], 
        ticker_data: Optional[Dict] = None,
        symbol_spreads: Optional[Dict[str, float]] = None  # 🔥 后台计算的价差数据 {symbol: spread_pct}
    ) -> Panel:
        """
        创建实时价格表格（显示所有代币的订单簿数据，使用Table样式，类似Excel）
        
        Args:
            orderbook_data: 订单簿数据 {exchange: {symbol: OrderBookData}}
            symbols: 交易对列表
            exchanges: 交易所列表
            ticker_data: Ticker数据 {exchange: {symbol: TickerData}}，用于获取资金费率（可选）
            symbol_spreads: 后台计算的价差数据 {symbol: spread_pct}，用于保证数据一致性（可选）
            
        Returns:
            价格面板（包含Table）
        """
        # 🔥 创建Table（类似Excel样式，灰色边框和网格线）
        from rich.box import SQUARE  # 使用方形边框样式（类似Excel）
        table = Table(
            show_header=True,
            header_style="bold white",
            border_style="dim white",  # 🔥 灰色边框（与字体颜色一致的灰色）
            box=SQUARE,  # 🔥 使用方形边框样式（类似Excel，包含完整边框和网格线）
            show_lines=True,  # 🔥 显示内部网格线（行和列之间的分隔线）
            padding=(0, 1),  # 单元格内边距
            collapse_padding=False
        )
        
        # 🔥 添加表头列
        table.add_column("交易对", style="white", width=18, no_wrap=True)
        for exchange in exchanges:
            table.add_column(f"{exchange.upper()} 买1/卖1", style="white", width=30, no_wrap=True)
            table.add_column(f"{exchange.upper()} 费率", style="white", width=18, no_wrap=True)
        table.add_column("价差%", style="white", justify="right", width=12, no_wrap=True)
        table.add_column("费率差(年化)", style="white", justify="right", width=18, no_wrap=True)
        table.add_column("同向", style="white", justify="center", width=8, no_wrap=True)  # 🔥 新增同向列
        
        # 🔥 按字母排序交易对
        sorted_symbols = sorted(symbols)
        
        # 遍历所有交易对（按字母顺序）
        for symbol in sorted_symbols:
            # 🔥 获取精度信息（动态精度）
            precision = cls._get_precision(symbol)
            price_decimals = precision['price_decimals']
            size_decimals = precision['size_decimals']
            
            # 🔥 收集所有交易所的数据
            exchange_data = {}
            for exchange in exchanges:
                if exchange in orderbook_data and symbol in orderbook_data[exchange]:
                    ob = orderbook_data[exchange][symbol]
                    if ob and ob.best_bid and ob.best_ask:
                        # 获取资金费率
                        funding_rate = None
                        if ticker_data and exchange in ticker_data and symbol in ticker_data[exchange]:
                            ticker = ticker_data[exchange][symbol]
                            if hasattr(ticker, 'funding_rate') and ticker.funding_rate is not None:
                                funding_rate = float(ticker.funding_rate)
                        
                        exchange_data[exchange] = {
                            'bid_price': float(ob.best_bid.price),
                            'bid_size': float(ob.best_bid.size),
                            'ask_price': float(ob.best_ask.price),
                            'ask_size': float(ob.best_ask.size),
                            'funding_rate': funding_rate
                        }
            
            # 🔥 构建数据行
            row_cells = [symbol]  # 交易对列
            
            for exchange in exchanges:
                if exchange in exchange_data:
                    ex_data = exchange_data[exchange]
                    # 格式化价格和数量（使用动态精度，单行显示）
                    bid_price_str = f"${ex_data['bid_price']:>8,.{price_decimals}f}"
                    bid_size_str = cls._format_size(ex_data['bid_size'], size_decimals)
                    ask_price_str = f"${ex_data['ask_price']:>8,.{price_decimals}f}"
                    ask_size_str = cls._format_size(ex_data['ask_size'], size_decimals)
                    
                    # 🔥 单行显示：买1×数量 / 卖1×数量
                    price_str = f"{bid_price_str}×{bid_size_str} / {ask_price_str}×{ask_size_str}"
                    row_cells.append(price_str)
                    
                    # 格式化资金费率
                    fr_str = cls._format_funding_rate(ex_data['funding_rate'])
                    row_cells.append(fr_str)
                else:
                    row_cells.append("—")
                    row_cells.append("—")
            
            # 🔥 计算价差（优先使用后台计算的数据，保证数据一致性）
            spread_str = "—"
            spread_style = "white"
            
            # 🔥 优先使用后台计算的价差数据（与套利机会表格一致）
            if symbol_spreads and symbol in symbol_spreads:
                best_spread_pct = symbol_spreads[symbol]
                if best_spread_pct > 0:
                    spread_str = f"{best_spread_pct:+.3f}%"
                    if best_spread_pct >= 0.5:
                        spread_style = "bold white"
                    elif best_spread_pct >= 0.2:
                        spread_style = "white"
                    else:
                        spread_style = "dim white"
                else:
                    spread_str = f"{best_spread_pct:.3f}%"
                    spread_style = "dim white"
            elif len(exchange_data) >= 2:
                # 如果没有后台计算的价差数据，则在前端计算（向后兼容）
                best_spread_pct = 0
                for ex1 in exchange_data:
                    for ex2 in exchange_data:
                        if ex1 != ex2:
                            ex1_data = exchange_data[ex1]
                            ex2_data = exchange_data[ex2]
                            # 策略：ex1买 -> ex2卖
                            profit = ex2_data['bid_price'] - ex1_data['ask_price']
                            profit_pct = (profit / ex1_data['ask_price']) * 100 if ex1_data['ask_price'] > 0 else 0
                            if profit_pct > best_spread_pct:
                                best_spread_pct = profit_pct
                
                if best_spread_pct > 0:
                    spread_str = f"{best_spread_pct:+.3f}%"
                    if best_spread_pct >= 0.5:
                        spread_style = "bold white"
                    elif best_spread_pct >= 0.2:
                        spread_style = "white"
                    else:
                        spread_style = "dim white"
                else:
                    spread_str = f"{best_spread_pct:.3f}%"
                    spread_style = "dim white"
            else:
                spread_str = "—"
                spread_style = "dim white"
            
            # 🔥 价差列也使用Text对象，确保样式正确应用
            from rich.text import Text
            spread_text = Text(spread_str, style=spread_style)
            row_cells.append(spread_text)
            
            # 🔥 计算资金费率差（参考v1算法：8小时费率差转换为年化费率差）
            funding_rate_diff_str = "—"
            max_diff_annual = 0  # 🔥 初始化，用于样式判断
            if len(exchange_data) >= 2:
                # 收集所有交易所的资金费率（8小时费率，小数形式）
                funding_rates = {}
                for ex in exchange_data:
                    if exchange_data[ex]['funding_rate'] is not None:
                        funding_rates[ex] = exchange_data[ex]['funding_rate']
                
                # 如果有2个或更多交易所的资金费率，计算费率差
                if len(funding_rates) >= 2:
                    # 计算所有交易所之间的费率差，取绝对值最大的
                    max_diff_annual = 0
                    for ex1 in funding_rates:
                        for ex2 in funding_rates:
                            if ex1 != ex2:
                                # 🔥 资金费率差应该永远为正数（绝对值差值）
                                rate_diff = abs(funding_rates[ex2] - funding_rates[ex1])
                                # 8小时差值（百分比）
                                diff_8h = float(rate_diff * 100)
                                # 年化差值：8小时差值 × 1095
                                diff_annual = diff_8h * 1095
                                # 取最大的费率差（已经是正数）
                                if diff_annual > max_diff_annual:
                                    max_diff_annual = diff_annual
                    
                    if max_diff_annual != 0:
                        # 费率差永远是正数，不需要符号
                        funding_rate_diff_str = f"{max_diff_annual:.1f}%"
            
            # 🔥 费率差样式：绝对值>=40时使用白色，否则使用dim white
            # 使用Rich的Text对象为费率差列单独设置样式
            if funding_rate_diff_str != "—":
                funding_rate_diff_style = "white" if max_diff_annual >= 40 else "dim white"
                funding_rate_diff_text = Text(funding_rate_diff_str, style=funding_rate_diff_style)
            else:
                funding_rate_diff_text = Text(funding_rate_diff_str, style="dim white")
            
            row_cells.append(funding_rate_diff_text)
            
            # 🔥 计算同向（参考v1算法）
            same_direction_str = "—"
            if len(exchange_data) >= 2:
                # 1. 价差方向：使用中间价（bid+ask）/2来判断做多做空方向
                mid_prices = {}
                for ex in exchange_data:
                    ex_data = exchange_data[ex]
                    mid_price = (ex_data['bid_price'] + ex_data['ask_price']) / 2.0
                    mid_prices[ex] = mid_price
                
                # 价格低的交易所做多，价格高的交易所做空
                if len(mid_prices) >= 2:
                    price_long_ex = min(mid_prices.items(), key=lambda x: x[1])[0]  # 价格低的做多
                    
                    # 2. 资金费率方向：费率低（数学上小）的做多
                    funding_rates_for_direction = {}
                    for ex in exchange_data:
                        if exchange_data[ex]['funding_rate'] is not None:
                            funding_rates_for_direction[ex] = exchange_data[ex]['funding_rate']
                    
                    if len(funding_rates_for_direction) >= 2:
                        fr_long_ex = min(funding_rates_for_direction.items(), key=lambda x: x[1])[0]  # 费率低的做多
                        
                        # 3. 判断是否同向：如果价差方向中做多的交易所和资金费率方向中做多的交易所是同一个，就是同向
                        if price_long_ex == fr_long_ex:
                            same_direction_str = "是"
                        else:
                            same_direction_str = ""
            
            row_cells.append(same_direction_str)
            
            # 🔥 添加数据行（不使用行样式，让每个单元格的Text对象自己管理样式）
            table.add_row(*row_cells)
        
        # 🔥 返回Panel包装的Table
        return Panel(table, title="[bold white]实时订单簿价格 + 资金费率[/bold white]", border_style="white")
    
    @staticmethod
    def create_performance_panel(stats: Dict) -> Panel:
        """
        创建性能面板
        
        Args:
            stats: 性能统计
            
        Returns:
            性能面板
        """
        text = Text()
        text.append("⚡ 性能指标\n", style="bold white")  # 🔥 保持标题单独一行，但去掉多余空行
        
        # 队列状态
        ob_q = stats.get('orderbook_queue_size', 0)
        ticker_q = stats.get('ticker_queue_size', 0)
        analysis_q = stats.get('analysis_queue_size', 0)
        
        text.append(f"队列积压: ", style="bold white")
        text.append(f"订单簿={ob_q} Ticker={ticker_q} 分析={analysis_q}\n", style="white")
        
        # 分析延迟
        latency = stats.get('analysis_latency_ms', 0)
        text.append(f"分析延迟: ", style="bold white")
        text.append(f"{latency:.1f}ms\n", style="white")
        
        # 处理量（去掉前面的空行）
        ob_processed = stats.get('orderbook_processed', 0)
        ticker_processed = stats.get('ticker_processed', 0)
        text.append(f"处理量: ", style="bold white")
        text.append(f"订单簿={ob_processed} Ticker={ticker_processed}\n", style="dim white")
        
        # 🎯 UI更新频率（抽样率）
        ui_update_interval = stats.get('ui_update_interval', 1.0)
        text.append(f"UI抽样: ", style="bold white")
        text.append(f"{ui_update_interval:.1f}秒/次\n", style="white")
        
        # 丢弃量
        ob_dropped = stats.get('orderbook_dropped', 0)
        ticker_dropped = stats.get('ticker_dropped', 0)
        if ob_dropped > 0 or ticker_dropped > 0:
            text.append(f"丢弃量: ", style="bold white")
            text.append(f"订单簿={ob_dropped} Ticker={ticker_dropped}\n", style="white")
        
        # 🔥 网络流量统计（去掉前面的空行）
        bytes_received = stats.get('network_bytes_received', 0)
        bytes_sent = stats.get('network_bytes_sent', 0)
        
        def format_bytes(bytes_count: int) -> str:
            """格式化字节数为可读格式"""
            if bytes_count == 0:
                return "0 B"
            elif bytes_count < 1024:
                return f"{bytes_count} B"
            elif bytes_count < 1024 * 1024:
                return f"{bytes_count / 1024:.2f} KB"
            elif bytes_count < 1024 * 1024 * 1024:
                return f"{bytes_count / (1024 * 1024):.2f} MB"
            else:
                return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"
        
        text.append(f"网络流量: ", style="bold white")
        text.append(f"接收={format_bytes(bytes_received)} 发送={format_bytes(bytes_sent)}\n", style="white")
        
        return Panel(text, title="[bold white]性能[/bold white]", border_style="white")
    
    @staticmethod
    def create_debug_panel(debug_messages: List[str]) -> Panel:
        """
        创建Debug面板
        
        Args:
            debug_messages: Debug消息列表
            
        Returns:
            Debug面板
        """
        text = Text()
        text.append("🐛 Debug 输出\n\n", style="bold yellow")
        
        for msg in debug_messages[-10:]:  # 只显示最近10条
            text.append(f"{msg}\n", style="dim")
        
        if not debug_messages:
            text.append("（无Debug消息）\n", style="dim")
        
        return Panel(text, title="[bold]Debug[/bold]", border_style="yellow")
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """
        格式化持续时间
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化字符串
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m{int(seconds%60)}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h{mins}m"

