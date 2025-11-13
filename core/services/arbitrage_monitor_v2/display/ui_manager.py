"""
UI管理器

职责：
- 管理UI布局和渲染
- 协调各个UI组件
- 控制UI刷新频率
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from .ui_components import UIComponents
from ..analysis.opportunity_finder import ArbitrageOpportunity
from ..config.debug_config import DebugConfig


class UIManager:
    """UI管理器"""
    
    def __init__(self, debug_config: DebugConfig, scroller=None):
        """
        初始化UI管理器
        
        Args:
            debug_config: Debug配置
            scroller: 实时滚动区管理器（可选）
        """
        self.debug = debug_config
        self.console = Console()
        self.components = UIComponents()
        self.scroller = scroller  # 🔥 混合模式：滚动区管理器
        
        # 数据缓存
        self.opportunities: List[ArbitrageOpportunity] = []
        self.stats: Dict = {}
        self.debug_messages: List[str] = []
        self.orderbook_data: Dict = {}  # 订单簿数据（实时接收）
        self.cached_orderbook_data: Dict = {}  # 订单簿数据（UI显示用，抽样）
        self.ticker_data: Dict = {}  # 🔥 Ticker数据（用于资金费率显示）
        self.cached_ticker_data: Dict = {}  # 🔥 Ticker数据（UI显示用，抽样）
        self.symbol_spreads: Dict[str, float] = {}  # 🔥 每个交易对的最佳价差（后台计算，保证数据一致性）
        self.config: Dict = {}  # 配置信息（exchanges, symbols）
        
        # 🔥 数据时间戳跟踪（用于检测过期数据）
        self.orderbook_data_timestamps: Dict[str, Dict[str, float]] = {}  # {exchange: {symbol: timestamp}}
        self.ticker_data_timestamps: Dict[str, Dict[str, float]] = {}  # {exchange: {symbol: timestamp}}
        self.data_timeout_seconds: float = 30.0  # 数据超时时间（30秒无更新则视为过期）
        
        # 🎯 UI更新节流配置
        self.last_price_update_time: float = 0  # 上次价格更新时间
        self.price_update_interval: float = 1.0  # 价格UI更新间隔（秒）
        
        # 运行状态
        self.running = False
        self.live: Optional[Live] = None
        self.ui_task: Optional[asyncio.Task] = None
        
        # 启动时间
        self.start_time = datetime.now()
        
        # 🔥 UI层持续时间容差和出现次数统计（不影响后台数据）
        # {opportunity_key: {'ui_duration_start': datetime, 'last_seen': datetime}}
        self._ui_opportunity_tracking: Dict[str, Dict] = {}
        # {symbol: [timestamp1, timestamp2, ...]} - 过去15分钟的出现时间戳
        self._symbol_occurrence_timestamps: Dict[str, List[datetime]] = {}
        self._ui_tolerance_seconds: float = 2.0  # 2秒容差
        self._occurrence_window_minutes: int = 15  # 15分钟窗口
        
        # 🔥 UI层显示延迟（5秒停留时间，仅用于显示）
        # {opportunity_key: {'opportunity': ArbitrageOpportunity, 'disappeared_at': datetime}}
        self._disappeared_opportunities: Dict[str, Dict] = {}
        self._display_delay_seconds: float = 5.0  # 5秒显示延迟
    
    def start(self, refresh_rate: int = 5):
        """
        启动UI（使用Rich Live模式）
        
        Args:
            refresh_rate: 刷新频率（Hz）
        """
        self.running = True
        self.start_time = datetime.now()
        
        # 🔥 混合模式：使用 screen=True（全屏模式，滚动区在 Rich UI 内部）
        self.live = Live(
            self._generate_layout(),
            console=self.console,
            screen=True,  # ← 全屏模式，滚动区在底部
            refresh_per_second=refresh_rate
        )
        
        print("✅ UI管理器已启动（顶部：汇总表 | 底部：实时滚动）")
    
    def stop(self):
        """停止UI"""
        self.running = False
        if self.live:
            self.live.stop()
        print("🛑 UI管理器已停止")
    
    async def update_loop(self, interval_ms: int = 200):
        """
        UI更新循环
        
        Args:
            interval_ms: 更新间隔（毫秒）
        """
        if not self.live:
            raise RuntimeError("UI未启动，请先调用start()")
        
        with self.live:
            while self.running:
                try:
                    # 更新布局
                    layout = self._generate_layout()
                    self.live.update(layout)
                    
                    # 等待下一次更新
                    await asyncio.sleep(interval_ms / 1000)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.add_debug_message(f"❌ UI更新错误: {e}")
                    await asyncio.sleep(1)
        
        print("🛑 UI更新循环已停止")
    
    def _generate_layout(self) -> Layout:
        """
        生成UI布局
        
        Returns:
            Rich Layout对象
        """
        # 🔥 混合模式：创建主布局（顶部表格 + 底部滚动区）
        layout = Layout()
        
        # 分割为三部分：头部、主体、底部滚动区
        layout.split_column(
            Layout(name="header", size=8),  # 🔥 压缩头部高度（从12减少到8）
            Layout(name="body", ratio=2),
            Layout(name="scroller", size=12)  # 🔥 底部滚动区
        )
        
        # 头部分为左右两部分
        layout["header"].split_row(
            Layout(name="summary", ratio=2),
            Layout(name="performance", ratio=1)
        )
        
        # 身体部分：分割为价格表格和套利机会
        if self.debug.is_debug_enabled():
            # Debug模式：价格表格 + (套利机会 + Debug面板)
            layout["body"].split_column(
                Layout(name="prices", ratio=5),  # 🔥 价格表格占更多空间（从3增加到5）
                Layout(name="opportunities_row", ratio=1)  # 🔥 套利机会向下移动，占更少空间（从2减少到1）
            )
            layout["opportunities_row"].split_row(
                Layout(name="opportunities", ratio=2),
                Layout(name="debug", ratio=1)
            )
        else:
            # 普通模式：价格表格 + 套利机会
            layout["body"].split_column(
                Layout(name="prices", ratio=5),  # 🔥 价格表格占更多空间（从3增加到5）
                Layout(name="opportunities", ratio=1)  # 🔥 套利机会向下移动，占更少空间（从2减少到1）
            )
        
        # 填充各个部分
        self._fill_summary(layout)
        self._fill_performance(layout)
        self._fill_prices(layout)
        self._fill_opportunities(layout)
        self._fill_scroller(layout)  # 🔥 填充底部滚动区
        
        if self.debug.is_debug_enabled():
            self._fill_debug(layout)
        
        return layout
    
    def _fill_summary(self, layout: Layout):
        """填充摘要面板"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        summary_stats = {
            'uptime_seconds': uptime,
            'exchanges': self.stats.get('exchanges', []),
            'symbols_count': self.stats.get('symbols_count', 0),
            'active_opportunities': len(self.opportunities),
            'reconnect_stats': self.stats.get('reconnect_stats', {}),  # 🔥 传递重连统计
        }
        
        layout["summary"].update(self.components.create_summary_panel(summary_stats))
    
    def _fill_performance(self, layout: Layout):
        """填充性能面板"""
        layout["performance"].update(self.components.create_performance_panel(self.stats))
    
    def _fill_prices(self, layout: Layout):
        """填充价格表格（使用抽样缓存数据，包含资金费率和后台计算的价差）"""
        exchanges = self.config.get('exchanges', [])
        symbols = self.config.get('symbols', [])
        
        # 🎯 使用缓存数据，而不是实时数据（抽样显示，避免UI卡顿）
        # 🔥 传递 ticker_data 以显示资金费率，传递 symbol_spreads 以保证数据一致性
        layout["prices"].update(
            self.components.create_price_table(
                self.cached_orderbook_data, 
                symbols, 
                exchanges,
                ticker_data=self.cached_ticker_data,  # 🔥 传递 Ticker 数据
                symbol_spreads=self.symbol_spreads  # 🔥 传递后台计算的价差数据
            )
        )
    
    def _fill_opportunities(self, layout: Layout):
        """填充机会表格"""
        # 🔥 合并当前机会和已消失但仍在5秒显示延迟内的机会
        display_opportunities = list(self.opportunities)
        
        # 添加已消失但仍在5秒内的机会（仅用于显示）
        current_time = datetime.now()
        for key, disappeared_info in self._disappeared_opportunities.items():
            time_since_disappeared = (current_time - disappeared_info['disappeared_at']).total_seconds()
            if time_since_disappeared <= self._display_delay_seconds:
                # 仍在5秒显示延迟内，添加到显示列表
                display_opportunities.append(disappeared_info['opportunity'])
        
        # 🔥 按价差排序（从大到小），确保表格显示顺序与实时数据流一致
        display_opportunities.sort(key=lambda x: x.spread_pct, reverse=True)
        
        # 🔥 显示所有机会（不限制数量，确保实时数据流中的机会都能显示）
        # 🔥 传递UI层的持续时间容差和出现次数统计
        layout["opportunities"].update(
            self.components.create_opportunities_table(
                display_opportunities,  # 🔥 使用合并后的机会列表（已排序）
                limit=50,  # 🔥 增加显示数量，确保所有机会都能显示（从10增加到50）
                ui_opportunity_tracking=self._ui_opportunity_tracking,
                symbol_occurrence_timestamps=self._symbol_occurrence_timestamps
            )
        )
    
    def _fill_scroller(self, layout: Layout):
        """填充底部滚动区"""
        from rich.panel import Panel
        from rich.text import Text
        
        # 获取最近的消息
        messages = []
        if self.scroller:
            messages = self.scroller.get_recent_messages()
        
        # 构建显示文本
        text = Text()
        if messages:
            for msg in messages:
                text.append(msg + "\n", style="dim white")
        else:
            text.append("等待实时数据...\n", style="dim white")
        
        # 创建面板（使用白色边框）
        panel = Panel(
            text,
            title="[bold white]📊 实时数据流（最近20条）[/bold white]",
            border_style="white",
            padding=(0, 1)
        )
        
        layout["scroller"].update(panel)
    
    def _fill_debug(self, layout: Layout):
        """填充Debug面板"""
        layout["debug"].update(self.components.create_debug_panel(self.debug_messages))
    
    def update_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """
        更新机会数据（带UI层持续时间容差和出现次数统计）
        
        Args:
            opportunities: 机会列表
        """
        current_time = datetime.now()
        
        # 🔥 保存旧的机会列表（用于查找已消失的机会）
        old_opportunities = self.opportunities.copy()
        
        # 🔥 清理超过15分钟的时间戳
        cutoff_time = current_time - timedelta(minutes=self._occurrence_window_minutes)
        for symbol in list(self._symbol_occurrence_timestamps.keys()):
            self._symbol_occurrence_timestamps[symbol] = [
                ts for ts in self._symbol_occurrence_timestamps[symbol] 
                if ts > cutoff_time
            ]
            if not self._symbol_occurrence_timestamps[symbol]:
                del self._symbol_occurrence_timestamps[symbol]
        
        # 🔥 更新UI层持续时间容差和出现次数统计
        current_keys = set()
        current_symbols = set()  # 🔥 当前出现的代币集合（用于重置5秒显示延迟）
        for opp in opportunities:
            key = opp.get_opportunity_key()
            current_keys.add(key)
            current_symbols.add(opp.symbol)  # 🔥 记录当前出现的代币
            
            # 记录出现时间戳（用于统计出现次数）
            if opp.symbol not in self._symbol_occurrence_timestamps:
                self._symbol_occurrence_timestamps[opp.symbol] = []
            # 检查是否是新出现（避免重复记录）
            if not self._symbol_occurrence_timestamps[opp.symbol] or \
               (current_time - self._symbol_occurrence_timestamps[opp.symbol][-1]).total_seconds() > 1.0:
                self._symbol_occurrence_timestamps[opp.symbol].append(current_time)
            
            # UI层持续时间容差逻辑
            if key in self._ui_opportunity_tracking:
                # 现有机会：检查是否在容差范围内
                tracking = self._ui_opportunity_tracking[key]
                time_since_last_seen = (current_time - tracking['last_seen']).total_seconds()
                
                if time_since_last_seen <= self._ui_tolerance_seconds:
                    # 在容差范围内，继续累计时间
                    tracking['last_seen'] = current_time
                else:
                    # 超过容差，重新开始计时
                    tracking['ui_duration_start'] = current_time
                    tracking['last_seen'] = current_time
            else:
                # 新机会：开始计时
                self._ui_opportunity_tracking[key] = {
                    'ui_duration_start': current_time,
                    'last_seen': current_time
                }
        
        # 🔥 处理已消失的机会（保留5秒显示时间）
        expired_keys = set(self._ui_opportunity_tracking.keys()) - current_keys
        for key in list(expired_keys):
            tracking = self._ui_opportunity_tracking[key]
            time_since_last_seen = (current_time - tracking['last_seen']).total_seconds()
            
            # 🔥 如果机会不在当前列表中，立即添加到已消失列表（开始5秒计时）
            # 不再等待2秒容差，因为5秒显示延迟是独立的UI功能
            if key not in self._disappeared_opportunities:
                # 找到对应的机会对象（从旧的机会列表中）
                disappeared_opp = None
                for opp in old_opportunities:
                    if opp.get_opportunity_key() == key:
                        disappeared_opp = opp
                        break
                
                if disappeared_opp:
                    self._disappeared_opportunities[key] = {
                        'opportunity': disappeared_opp,
                        'disappeared_at': current_time
                    }
            
            # 🔥 如果超过2秒容差，从跟踪中移除（但保留在已消失列表中）
            if time_since_last_seen > self._ui_tolerance_seconds:
                del self._ui_opportunity_tracking[key]
        
        # 🔥 清理超过5秒显示延迟的已消失机会
        for key in list(self._disappeared_opportunities.keys()):
            disappeared_info = self._disappeared_opportunities[key]
            time_since_disappeared = (current_time - disappeared_info['disappeared_at']).total_seconds()
            if time_since_disappeared > self._display_delay_seconds:
                # 超过5秒，从已消失列表中删除
                del self._disappeared_opportunities[key]
        
        # 🔥 如果已消失的机会重新出现，从已消失列表中移除
        for key in current_keys:
            if key in self._disappeared_opportunities:
                del self._disappeared_opportunities[key]
        
        # 🔥 如果同一个代币在5秒内接收到多次套利机会，重置该代币所有已消失机会的5秒计时
        # 这仅影响UI显示延迟，不影响次数统计和持续时间等数据
        for symbol in current_symbols:
            # 查找该代币的所有已消失机会
            for key, disappeared_info in self._disappeared_opportunities.items():
                if disappeared_info['opportunity'].symbol == symbol:
                    # 重置该已消失机会的消失时间，重新开始5秒计时
                    disappeared_info['disappeared_at'] = current_time
        
        self.opportunities = opportunities
    
    def update_stats(self, stats: Dict):
        """
        更新统计数据
        
        Args:
            stats: 统计字典
        """
        self.stats = stats
    
    def update_orderbook_data(
        self, 
        orderbook_data: Dict, 
        ticker_data: Optional[Dict] = None,
        symbol_spreads: Optional[Dict[str, float]] = None
    ):
        """
        更新订单簿数据（带抽样节流和数据过期清理）
        
        Args:
            orderbook_data: 订单簿数据 {exchange: {symbol: OrderBookData}}
            ticker_data: Ticker数据 {exchange: {symbol: TickerData}}，用于资金费率显示（可选）
            symbol_spreads: 每个交易对的最佳价差 {symbol: spread_pct}（后台计算，保证数据一致性）
        """
        import time
        current_time = time.time()
        
        # 🔥 更新数据时间戳（用于检测过期数据）
        for exchange, symbols_data in orderbook_data.items():
            if exchange not in self.orderbook_data_timestamps:
                self.orderbook_data_timestamps[exchange] = {}
            for symbol in symbols_data.keys():
                self.orderbook_data_timestamps[exchange][symbol] = current_time
        
        if ticker_data is not None:
            for exchange, symbols_data in ticker_data.items():
                if exchange not in self.ticker_data_timestamps:
                    self.ticker_data_timestamps[exchange] = {}
                for symbol in symbols_data.keys():
                    self.ticker_data_timestamps[exchange][symbol] = current_time
        
        # 🔥 清理过期数据（超过30秒未更新的数据）
        self._cleanup_stale_data(current_time)
        
        # 🎯 始终接收数据（不丢弃）
        self.orderbook_data = orderbook_data
        if ticker_data is not None:
            self.ticker_data = ticker_data
        if symbol_spreads is not None:
            self.symbol_spreads = symbol_spreads  # 🔥 保存后台计算的价差数据
        
        # 🎯 但只按固定频率更新UI缓存（抽样显示）
        if current_time - self.last_price_update_time >= self.price_update_interval:
            # 更新UI缓存（只包含未过期的数据）
            self.cached_orderbook_data = self._filter_stale_data(orderbook_data, self.orderbook_data_timestamps, current_time)
            if ticker_data is not None:
                self.cached_ticker_data = self._filter_stale_data(ticker_data, self.ticker_data_timestamps, current_time)
            if symbol_spreads is not None:
                self.symbol_spreads = symbol_spreads.copy()  # 🔥 更新价差缓存
            self.last_price_update_time = current_time
    
    def _cleanup_stale_data(self, current_time: float):
        """
        清理过期数据的时间戳
        
        Args:
            current_time: 当前时间戳
        """
        # 清理订单簿数据时间戳
        for exchange in list(self.orderbook_data_timestamps.keys()):
            for symbol in list(self.orderbook_data_timestamps[exchange].keys()):
                timestamp = self.orderbook_data_timestamps[exchange][symbol]
                if current_time - timestamp > self.data_timeout_seconds:
                    del self.orderbook_data_timestamps[exchange][symbol]
            if not self.orderbook_data_timestamps[exchange]:
                del self.orderbook_data_timestamps[exchange]
        
        # 清理Ticker数据时间戳
        for exchange in list(self.ticker_data_timestamps.keys()):
            for symbol in list(self.ticker_data_timestamps[exchange].keys()):
                timestamp = self.ticker_data_timestamps[exchange][symbol]
                if current_time - timestamp > self.data_timeout_seconds:
                    del self.ticker_data_timestamps[exchange][symbol]
            if not self.ticker_data_timestamps[exchange]:
                del self.ticker_data_timestamps[exchange]
    
    def _filter_stale_data(self, data: Dict, timestamps: Dict[str, Dict[str, float]], current_time: float) -> Dict:
        """
        过滤过期数据，只保留未过期的数据
        
        Args:
            data: 数据字典 {exchange: {symbol: Data}}
            timestamps: 时间戳字典 {exchange: {symbol: timestamp}}
            current_time: 当前时间戳
            
        Returns:
            过滤后的数据字典（只包含未过期的数据）
        """
        filtered_data = {}
        for exchange, symbols_data in data.items():
            if exchange not in timestamps:
                continue
            filtered_symbols = {}
            for symbol, symbol_data in symbols_data.items():
                if symbol in timestamps[exchange]:
                    timestamp = timestamps[exchange][symbol]
                    if current_time - timestamp <= self.data_timeout_seconds:
                        filtered_symbols[symbol] = symbol_data
            if filtered_symbols:
                filtered_data[exchange] = filtered_symbols
        return filtered_data
    
    def update_config(self, config: Dict):
        """
        更新配置信息
        
        Args:
            config: 配置字典（exchanges, symbols）
        """
        self.config = config
    
    def add_debug_message(self, message: str):
        """
        添加Debug消息
        
        Args:
            message: 消息内容
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_messages.append(f"[{timestamp}] {message}")
        
        # 只保留最近100条消息
        if len(self.debug_messages) > 100:
            self.debug_messages = self.debug_messages[-100:]
    
    def clear_debug_messages(self):
        """清空Debug消息"""
        self.debug_messages.clear()

