"""
数据接收层 - 零延迟WebSocket数据接收

职责：
- 接收WebSocket推送的订单簿和Ticker数据
- 立即入队，不做任何处理
- 确保零延迟、零阻塞
"""

import asyncio
import logging
from typing import Dict, Callable, Optional, Any
from datetime import datetime
from collections import defaultdict

from core.adapters.exchanges.models import OrderBookData, TickerData
from core.services.arbitrage_monitor.utils.symbol_converter import SimpleSymbolConverter
from ..config.debug_config import DebugConfig


class DataReceiver:
    """
    数据接收器 - 零延迟设计
    
    设计原则：
    1. 回调函数只做最小验证 + 入队操作
    2. 不进行任何计算或复杂处理
    3. 使用put_nowait避免阻塞
    4. 队列满时丢弃旧数据（保证实时性）
    """
    
    def __init__(
        self,
        orderbook_queue: asyncio.Queue,
        ticker_queue: asyncio.Queue,
        debug_config: DebugConfig
    ):
        """
        初始化数据接收器
        
        Args:
            orderbook_queue: 订单簿队列
            ticker_queue: Ticker队列
            debug_config: Debug配置
        """
        self.orderbook_queue = orderbook_queue
        self.ticker_queue = ticker_queue
        self.debug = debug_config
        
        # 统计信息
        self.stats = {
            'orderbook_received': 0,
            'orderbook_dropped': 0,
            'ticker_received': 0,
            'ticker_dropped': 0,
            # 🔥 网络流量统计（字节数）
            'network_bytes_received': 0,  # 接收的字节数
            'network_bytes_sent': 0,      # 发送的字节数
        }
        
        # Debug计数器
        self._ws_message_counter = 0
        
        # 适配器注册表
        self.adapters: Dict[str, Any] = {}
        
        # 🚀 Symbol转换器（参考V1）
        logger = logging.getLogger(__name__)
        self.symbol_converter = SimpleSymbolConverter(logger)
        logger.info("✅ Symbol转换器已初始化")
    
    def register_adapter(self, exchange: str, adapter: Any):
        """
        注册交易所适配器
        
        Args:
            exchange: 交易所名称
            adapter: 交易所适配器
        """
        self.adapters[exchange] = adapter
        print(f"✅ [{exchange}] 适配器已注册到数据接收层")
    
    async def subscribe_all(self, symbols: list):
        """
        订阅所有交易对的数据
        
        Args:
            symbols: 交易对列表（标准格式，如 BTC-USDC-PERP）
        
        扩展说明：
        ============================================================
        🔥 新交易所接入指南
        ============================================================
        1. 如果新交易所的回调格式与标准格式相同（callback(symbol, data)）：
           - 无需修改，会自动使用 else 分支的标准订阅模式
        
        2. 如果新交易所的回调格式不同：
           - 在 subscribe_all 方法中添加新的 elif 分支
           - 参考 Lighter 和 EdgeX 的实现方式
           - 确保回调函数正确转换 symbol 并验证数据
        
        3. 回调格式说明：
           - 标准格式：callback(symbol: str, orderbook: OrderBookData)
           - Lighter格式：callback(orderbook: OrderBookData) - 只有orderbook参数
           - EdgeX格式：callback(orderbook: OrderBookData) - 只有orderbook参数
        ============================================================
        """
        for exchange, adapter in self.adapters.items():
            try:
                # ============================================================
                # 🔥 交易所特殊处理扩展点
                # ============================================================
                # 如果新交易所的回调格式与标准格式不同，在这里添加特殊处理
                # ============================================================
                
                # 🚀 Lighter特殊处理：使用统一回调模式（完全复制V1逻辑）
                if exchange == "lighter":
                    # 🔥 固定 exchange 值，避免闭包变量捕获问题
                    exchange_name = "lighter"
                    
                    # 创建Lighter专用的统一回调（只有一个参数）
                    def lighter_orderbook_callback(orderbook):
                        """Lighter订单簿统一回调（只接收orderbook参数）"""
                        try:
                            # 🔥 V1逻辑：先转换symbol
                            std_symbol = self.symbol_converter.convert_from_exchange(orderbook.symbol, "lighter")
                            
                            # 🔥 V1逻辑：检查symbol是否在监控列表中
                            if std_symbol in symbols:
                                # 🔥 直接验证并入队（跳过 callback 包装，避免数据丢失）
                                try:
                                    # 验证数据
                                    if not orderbook.best_bid or not orderbook.best_ask:
                                        return  # 静默忽略
                                    
                                    if orderbook.best_bid.price <= 0 or orderbook.best_ask.price <= 0:
                                        return  # 静默忽略
                                    
                                    # 直接入队（使用固定的 exchange_name）
                                    queue_item = {
                                        'exchange': exchange_name,  # 🔥 使用固定的 "lighter"
                                        'symbol': std_symbol,
                                        'data': orderbook,
                                        'timestamp': datetime.now()
                                    }
                                    self.orderbook_queue.put_nowait(queue_item)
                                    self.stats['orderbook_received'] += 1
                                except Exception as e:
                                    # 🔥 UI模式下不打印，避免界面闪动（错误已记录到stats）
                                    self.stats['orderbook_dropped'] = self.stats.get('orderbook_dropped', 0) + 1
                        except Exception as e:
                            # 🔥 UI模式下不打印，避免界面闪动（静默处理错误）
                            self.stats['orderbook_dropped'] = self.stats.get('orderbook_dropped', 0) + 1
                    
                    def lighter_ticker_callback(ticker):
                        """Lighter ticker统一回调（只接收ticker参数）"""
                        try:
                            # 🔥 V1逻辑：先转换symbol
                            std_symbol = self.symbol_converter.convert_from_exchange(ticker.symbol, "lighter")
                            
                            # 🔥 V1逻辑：检查symbol是否在监控列表中
                            if std_symbol in symbols:
                                # 调用标准回调（使用固定的 exchange_name）
                                self._create_ticker_callback(exchange_name)(std_symbol, ticker)
                        except Exception as e:
                            if self.debug.is_debug_enabled():
                                print(f"⚠️  [lighter] ticker回调失败: {e}")
                    
                    # 逐个订阅（首次注册回调，后续传None）
                    for idx, standard_symbol in enumerate(symbols):
                        try:
                            exchange_symbol = self.symbol_converter.convert_to_exchange(standard_symbol, exchange)
                            print(f"🔍 [Lighter] 准备订阅: {standard_symbol} -> {exchange_symbol}")
                            
                            # 订单簿订阅
                            if idx == 0:
                                print(f"🔍 [Lighter] 注册订单簿回调并订阅: {exchange_symbol}")
                                await adapter.subscribe_orderbook(exchange_symbol, lighter_orderbook_callback)
                                print(f"✅ [Lighter] 订单簿订阅完成: {exchange_symbol}")
                            else:
                                await adapter.subscribe_orderbook(exchange_symbol, None)
                            
                            # Ticker订阅
                            if idx == 0:
                                await adapter.subscribe_ticker(exchange_symbol, lighter_ticker_callback)
                            else:
                                await adapter.subscribe_ticker(exchange_symbol, None)
                        except Exception as e:
                            print(f"❌ [lighter] {standard_symbol} 订阅失败: {e}")
                            import traceback
                            traceback.print_exc()
                
                elif exchange == "edgex":
                    # 🚀 EdgeX特殊处理：使用批量订阅模式（设置全局回调）
                    print(f"⏳ [edgex] 等待metadata加载...")
                    await asyncio.sleep(5)  # 给EdgeX 5秒时间加载metadata
                    
                    # 🔥 创建EdgeX专用的统一回调（兼容两种调用方式）
                    # EdgeX会同时调用全局回调和特定订阅回调：
                    # - 全局回调：_safe_callback_with_symbol(callback, symbol, orderbook) - 传递两个参数
                    # - 特定订阅回调：_safe_callback(callback, orderbook) - 只传递一个参数
                    # 所以我们需要创建一个包装函数，能够处理两种情况
                    async def edgex_orderbook_callback_wrapper(*args):
                        """EdgeX订单簿回调包装器（兼容两种调用方式，异步）"""
                        try:
                            # 如果只有一个参数，说明是从特定订阅回调调用的（只有orderbook）
                            # 如果有两个参数，说明是从全局回调调用的（symbol, orderbook）
                            if len(args) == 1:
                                # 只有orderbook，需要从orderbook中提取symbol
                                orderbook = args[0]
                                symbol = orderbook.symbol if hasattr(orderbook, 'symbol') else None
                                if not symbol:
                                    return  # 无法处理，静默忽略
                            elif len(args) == 2:
                                # 有symbol和orderbook
                                symbol, orderbook = args
                            else:
                                return  # 参数错误，静默忽略
                            
                            # 🔥 从symbol转换为标准格式
                            std_symbol = self.symbol_converter.convert_from_exchange(symbol, "edgex")
                            
                            # 🔥 检查symbol是否在监控列表中
                            if std_symbol in symbols:
                                # 调用标准回调（需要symbol和orderbook两个参数）
                                self._create_orderbook_callback(exchange)(std_symbol, orderbook)
                        except Exception as e:
                            if self.debug.is_debug_enabled():
                                print(f"❌ [edgex] 订单簿回调失败: {e}")
                    
                    async def edgex_ticker_callback_wrapper(*args):
                        """EdgeX ticker回调包装器（兼容两种调用方式，异步）"""
                        try:
                            # Ticker回调通常有两个参数 (symbol, ticker)
                            if len(args) == 2:
                                symbol, ticker = args
                                # EdgeX 已经提供了symbol，只需要转换
                                std_symbol = self.symbol_converter.convert_from_exchange(symbol, "edgex")
                                if std_symbol in symbols:
                                    self._create_ticker_callback(exchange)(std_symbol, ticker)
                        except Exception as e:
                            if self.debug.is_debug_enabled():
                                print(f"❌ [edgex] ticker回调失败: {e}")
                    
                    # 🔥 转换所有符号为EdgeX格式
                    exchange_symbols = []
                    for standard_symbol in symbols:
                        try:
                            exchange_symbol = self.symbol_converter.convert_to_exchange(standard_symbol, exchange)
                            exchange_symbols.append(exchange_symbol)
                            print(f"🔍 [EdgeX] 准备订阅: {standard_symbol} -> {exchange_symbol}")
                        except Exception as e:
                            print(f"⚠️  [EdgeX] {standard_symbol} 符号转换失败: {e}")
                    
                    # 🔥 使用批量订阅方法（设置全局回调，所有符号共享）
                    # 注意：EdgeX的batch_subscribe_orderbooks会将回调同时保存到：
                    # 1. self.orderbook_callback（全局回调，使用_safe_callback_with_symbol调用，传递symbol和orderbook）
                    # 2. self._ws_subscriptions（特定订阅回调，使用_safe_callback调用，只传递orderbook）
                    # 所以我们需要使用包装器函数来兼容两种调用方式
                    if exchange_symbols:
                        print(f"📡 [EdgeX] 批量订阅 {len(exchange_symbols)} 个交易对的订单簿和Ticker...")
                        await adapter.websocket.batch_subscribe_orderbooks(exchange_symbols, callback=edgex_orderbook_callback_wrapper)
                        await adapter.websocket.batch_subscribe_tickers(exchange_symbols, callback=edgex_ticker_callback_wrapper)
                        print(f"✅ [EdgeX] 批量订阅完成")
                    else:
                        print(f"⚠️  [EdgeX] 没有可订阅的交易对")
                
                else:
                    # ============================================================
                    # 🔥 通用交易所订阅模式（占位符）
                    # ============================================================
                    # 大多数交易所使用标准订阅模式：
                    # - subscribe_orderbook(symbol, callback) - callback(symbol, orderbook)
                    # - subscribe_ticker(symbol, callback) - callback(symbol, ticker)
                    #
                    # 如果新交易所的回调格式不同，可以在这里添加特殊处理：
                    # if exchange == "new_exchange":
                    #     # 新交易所的特殊处理逻辑
                    #     pass
                    # ============================================================
                    
                    # 标准订阅模式（两个参数：symbol, callback）
                    for standard_symbol in symbols:
                        try:
                            exchange_symbol = self.symbol_converter.convert_to_exchange(standard_symbol, exchange)
                            
                            await adapter.subscribe_orderbook(
                                symbol=exchange_symbol,
                                callback=self._create_orderbook_callback(exchange)
                            )
                        except Exception as e:
                            print(f"❌ [{exchange}] {standard_symbol} 订单簿订阅失败: {e}")
                    
                    for standard_symbol in symbols:
                        try:
                            exchange_symbol = self.symbol_converter.convert_to_exchange(standard_symbol, exchange)
                            
                            await adapter.subscribe_ticker(
                                symbol=exchange_symbol,
                                callback=self._create_ticker_callback(exchange)
                            )
                        except Exception as e:
                            print(f"❌ [{exchange}] {standard_symbol} Ticker订阅失败: {e}")
                
                print(f"✅ [{exchange}] 已订阅 {len(symbols)} 个交易对")
                
            except Exception as e:
                print(f"❌ [{exchange}] 订阅失败: {e}")
    
    def _create_orderbook_callback(self, exchange: str) -> Callable:
        """
        创建订单簿回调函数
        
        Args:
            exchange: 交易所名称
            
        Returns:
            回调函数
        """
        def callback(symbol: str, orderbook: OrderBookData):
            """
            订单簿回调 - 零延迟设计
            
            Args:
                symbol: 交易对
                orderbook: 订单簿数据
            """
            # 🚀 快速验证（只检查必需字段）
            if not orderbook.best_bid or not orderbook.best_ask:
                # 🔥 UI模式下不打印，避免界面闪动（静默忽略无效数据）
                return  # 静默忽略
            
            if orderbook.best_bid.price <= 0 or orderbook.best_ask.price <= 0:
                # 🔥 UI模式下不打印，避免界面闪动（静默忽略无效数据）
                return  # 静默忽略
            
            # 🚀 立即入队（非阻塞）
            try:
                self.orderbook_queue.put_nowait({
                    'exchange': exchange,
                    'symbol': symbol,
                    'data': orderbook,
                    'timestamp': datetime.now()
                })
                self.stats['orderbook_received'] += 1
                
                # 🔥 Debug输出已禁用（UI模式下会导致界面闪动）
                # Debug输出应该通过UI的debug面板显示，而不是直接print
                # if self.debug.show_ws_messages and self.debug.should_show_ws_message(self._ws_message_counter):
                #     print(f"📥 [{exchange}] {symbol} 订单簿: Bid={orderbook.best_bid.price:.2f} Ask={orderbook.best_ask.price:.2f}")
                
                self._ws_message_counter += 1
                
            except asyncio.QueueFull:
                # 队列满了，丢弃最旧的数据
                try:
                    self.orderbook_queue.get_nowait()
                    self.orderbook_queue.put_nowait({
                        'exchange': exchange,
                        'symbol': symbol,
                        'data': orderbook,
                        'timestamp': datetime.now()
                    })
                except:
                    pass
                self.stats['orderbook_dropped'] += 1
        
        return callback
    
    def _create_ticker_callback(self, exchange: str) -> Callable:
        """
        创建Ticker回调函数
        
        Args:
            exchange: 交易所名称
            
        Returns:
            回调函数
        """
        def callback(symbol: str, ticker: TickerData):
            """
            Ticker回调 - 零延迟设计
            
            Args:
                symbol: 交易对
                ticker: Ticker数据
            """
            # 🚀 立即入队（非阻塞）
            try:
                self.ticker_queue.put_nowait({
                    'exchange': exchange,
                    'symbol': symbol,
                    'data': ticker,
                    'timestamp': datetime.now()
                })
                self.stats['ticker_received'] += 1
                
            except asyncio.QueueFull:
                # 队列满了，丢弃最旧的数据
                try:
                    self.ticker_queue.get_nowait()
                    self.ticker_queue.put_nowait({
                        'exchange': exchange,
                        'symbol': symbol,
                        'data': ticker,
                        'timestamp': datetime.now()
                    })
                except:
                    pass
                self.stats['ticker_dropped'] += 1
        
        return callback
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 🔥 从适配器获取网络流量统计和重连统计
        total_bytes_received = 0
        total_bytes_sent = 0
        reconnect_stats = {}  # {exchange: reconnect_count}
        
        for exchange, adapter in self.adapters.items():
            try:
                # 尝试从适配器的websocket获取网络流量统计和重连统计
                if hasattr(adapter, 'websocket') and adapter.websocket:
                    ws = adapter.websocket
                    if hasattr(ws, 'get_network_stats'):
                        net_stats = ws.get_network_stats()
                        total_bytes_received += net_stats.get('bytes_received', 0)
                        total_bytes_sent += net_stats.get('bytes_sent', 0)
                    
                    # 🔥 获取重连统计
                    if hasattr(ws, 'get_reconnect_stats'):
                        reconnect_stats[exchange] = ws.get_reconnect_stats().get('reconnect_count', 0)
            except Exception:
                pass  # 静默忽略错误
        
        # 更新网络流量统计
        stats['network_bytes_received'] = total_bytes_received
        stats['network_bytes_sent'] = total_bytes_sent
        
        # 🔥 更新重连统计
        stats['reconnect_stats'] = reconnect_stats
        
        return stats
    
    async def cleanup(self):
        """清理资源"""
        print("🧹 数据接收层正在清理...")
        for exchange, adapter in self.adapters.items():
            try:
                # 🔥 添加3秒超时，避免卡住
                await asyncio.wait_for(adapter.disconnect(), timeout=3.0)
                print(f"✅ [{exchange}] 已断开连接")
            except asyncio.TimeoutError:
                print(f"⏱️  [{exchange}] 断开连接超时，强制跳过")
            except Exception as e:
                print(f"⚠️  [{exchange}] 断开连接失败: {e}")

