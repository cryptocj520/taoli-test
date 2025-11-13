"""
数据处理层 - 订单簿维护和数据验证

职责：
- 从队列消费数据
- 维护最新的订单簿状态
- 数据验证和清洗
"""

import asyncio
import time
from typing import Dict, Optional, List
from datetime import datetime
from collections import defaultdict

from core.adapters.exchanges.models import OrderBookData, TickerData
from ..config.debug_config import DebugConfig


class DataProcessor:
    """
    数据处理器 - 独立任务运行
    
    设计原则：
    1. 从队列批量消费数据
    2. 维护内存中的最新状态
    3. 不阻塞数据接收
    """
    
    def __init__(
        self,
        orderbook_queue: asyncio.Queue,
        ticker_queue: asyncio.Queue,
        debug_config: DebugConfig,
        scroller=None  # 实时滚动区管理器（可选）
    ):
        """
        初始化数据处理器
        
        Args:
            orderbook_queue: 订单簿队列
            ticker_queue: Ticker队列
            debug_config: Debug配置
            scroller: 实时滚动区管理器（用于实时打印）
        """
        self.orderbook_queue = orderbook_queue
        self.ticker_queue = ticker_queue
        self.debug = debug_config
        self.scroller = scroller  # 🔥 混合模式：实时滚动输出
        
        # 数据存储 {exchange: {symbol: data}}
        self.orderbooks: Dict[str, Dict[str, OrderBookData]] = defaultdict(dict)
        self.tickers: Dict[str, Dict[str, TickerData]] = defaultdict(dict)
        
        # 数据时间戳 {exchange: {symbol: datetime}}
        self.orderbook_timestamps: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        self.ticker_timestamps: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        
        # 统计信息（滑动窗口：只统计过去1小时）
        # 🔥 使用时间戳列表记录每次处理的时间，实现滑动窗口统计
        self.orderbook_processed_timestamps: List[float] = []  # 订单簿处理时间戳列表
        self.ticker_processed_timestamps: List[float] = []      # Ticker处理时间戳列表
        
        # 启动时间（用于判断是否满1小时）
        self.start_time = time.time()
        
        # 其他统计信息
        self.stats = {
            'processing_errors': 0,
        }
        
        # 运行状态
        self.running = False
        self.process_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动数据处理任务"""
        if self.running:
            return
        
        self.running = True
        self.process_task = asyncio.create_task(self._process_loop())
        print("✅ 数据处理器已启动")
    
    async def stop(self):
        """停止数据处理任务"""
        self.running = False
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
        print("🛑 数据处理器已停止")
    
    async def _process_loop(self):
        """数据处理循环"""
        try:
            while self.running:
                # 批量处理订单簿数据
                orderbook_count = 0
                while not self.orderbook_queue.empty() and orderbook_count < 50:
                    try:
                        item = self.orderbook_queue.get_nowait()
                        self._process_orderbook(item)
                        self.orderbook_queue.task_done()
                        orderbook_count += 1
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        self.stats['processing_errors'] += 1
                        # 🔥 UI模式下不打印，避免界面闪动（错误已记录到stats）
                        # 只在滚动模式（SimplePrinter）下打印
                        if self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                            print(f"❌ [DataProcessor] 处理订单簿数据错误: {e}")
                            import traceback
                            traceback.print_exc()
                
                # 批量处理Ticker数据
                ticker_count = 0
                while not self.ticker_queue.empty() and ticker_count < 50:
                    try:
                        item = self.ticker_queue.get_nowait()
                        self._process_ticker(item)
                        self.ticker_queue.task_done()
                        ticker_count += 1
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        self.stats['processing_errors'] += 1
                        # 🔥 UI模式下不打印，避免界面闪动
                        if self.debug.debug_data_layer and self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                            print(f"⚠️  处理Ticker数据错误: {e}")
                
                # 短暂休眠，避免CPU占用过高
                await asyncio.sleep(0.001)  # 1ms
                
        except asyncio.CancelledError:
            # 🔥 UI模式下不打印，避免界面闪动
            if self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                print("🛑 数据处理循环已取消")
        except Exception as e:
            # 🔥 UI模式下不打印，避免界面闪动
            if self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                print(f"❌ 数据处理循环错误: {e}")
    
    def _process_orderbook(self, item: Dict):
        """
        处理单个订单簿数据
        
        Args:
            item: 队列中的数据项
        """
        exchange = item['exchange']
        symbol = item['symbol']
        orderbook = item['data']
        timestamp = item['timestamp']
        
        # 更新订单簿状态
        self.orderbooks[exchange][symbol] = orderbook
        self.orderbook_timestamps[exchange][symbol] = timestamp
        
        # 🔥 记录处理时间戳（用于滑动窗口统计）
        current_time = time.time()
        self.orderbook_processed_timestamps.append(current_time)
        
        # 实时滚动输出
        if self.scroller:
            if orderbook.best_bid and orderbook.best_ask:
                try:
                    # 🔥 获取对应的 ticker 数据（用于资金费率）
                    ticker = self.tickers.get(exchange, {}).get(symbol)
                    funding_rate = None
                    if ticker and hasattr(ticker, 'funding_rate') and ticker.funding_rate is not None:
                        funding_rate = float(ticker.funding_rate)
                    
                    self.scroller.print_orderbook_update(
                        exchange=exchange,
                        symbol=symbol,
                        bid_price=float(orderbook.best_bid.price),
                        bid_size=float(orderbook.best_bid.size),
                        ask_price=float(orderbook.best_ask.price),
                        ask_size=float(orderbook.best_ask.size),
                        funding_rate=funding_rate  # 🔥 传递资金费率
                    )
                except Exception as e:
                    # 🔥 UI模式下不打印，避免界面闪动
                    if self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                        print(f"❌ [DataProcessor] SimplePrinter异常: {e}")
                        import traceback
                        traceback.print_exc()
            else:
                # 🔥 UI模式下不打印，避免界面闪动
                if self.scroller and type(self.scroller).__name__ == 'SimplePrinter':
                    print(f"⚠️ [DataProcessor] 订单簿数据不完整，跳过: bid={orderbook.best_bid}, ask={orderbook.best_ask}")
    
    def _process_ticker(self, item: Dict):
        """
        处理单个Ticker数据
        
        Args:
            item: 队列中的数据项
        """
        exchange = item['exchange']
        symbol = item['symbol']
        ticker = item['data']
        timestamp = item['timestamp']
        
        # 更新Ticker状态
        self.tickers[exchange][symbol] = ticker
        self.ticker_timestamps[exchange][symbol] = timestamp
        
        # 🔥 记录处理时间戳（用于滑动窗口统计）
        current_time = time.time()
        self.ticker_processed_timestamps.append(current_time)
    
    def get_orderbook(self, exchange: str, symbol: str) -> Optional[OrderBookData]:
        """
        获取订单簿数据
        
        Args:
            exchange: 交易所
            symbol: 交易对
            
        Returns:
            订单簿数据，如果不存在则返回None
        """
        return self.orderbooks.get(exchange, {}).get(symbol)
    
    def get_ticker(self, exchange: str, symbol: str) -> Optional[TickerData]:
        """
        获取Ticker数据
        
        Args:
            exchange: 交易所
            symbol: 交易对
            
        Returns:
            Ticker数据，如果不存在则返回None
        """
        return self.tickers.get(exchange, {}).get(symbol)
    
    def get_all_orderbooks(self) -> Dict[str, Dict[str, OrderBookData]]:
        """获取所有订单簿数据"""
        return dict(self.orderbooks)
    
    def get_all_tickers(self) -> Dict[str, Dict[str, TickerData]]:
        """获取所有Ticker数据"""
        return dict(self.tickers)
    
    def get_stats(self) -> Dict:
        """获取统计信息（滑动窗口：只统计过去1小时）"""
        current_time = time.time()
        one_hour_ago = current_time - 3600  # 1小时前的时间戳
        
        # 🔥 计算过去1小时的处理量
        # 如果启动时间不足1小时，则统计从启动到现在的所有数据
        cutoff_time = max(one_hour_ago, self.start_time)
        
        # 清理过期的时间戳（超过1小时的数据）
        self.orderbook_processed_timestamps = [
            ts for ts in self.orderbook_processed_timestamps if ts >= cutoff_time
        ]
        self.ticker_processed_timestamps = [
            ts for ts in self.ticker_processed_timestamps if ts >= cutoff_time
        ]
        
        # 统计过去1小时（或从启动到现在）的处理量
        orderbook_processed = len(self.orderbook_processed_timestamps)
        ticker_processed = len(self.ticker_processed_timestamps)
        
        return {
            **self.stats,
            'orderbook_processed': orderbook_processed,
            'ticker_processed': ticker_processed,
            'orderbook_queue_size': self.orderbook_queue.qsize(),
            'ticker_queue_size': self.ticker_queue.qsize(),
            'orderbook_count': sum(len(obs) for obs in self.orderbooks.values()),
            'ticker_count': sum(len(tks) for tks in self.tickers.values()),
        }
    
    def is_data_available(self, exchange: str, symbol: str) -> bool:
        """
        检查数据是否可用
        
        Args:
            exchange: 交易所
            symbol: 交易对
            
        Returns:
            数据是否可用
        """
        has_orderbook = symbol in self.orderbooks.get(exchange, {})
        has_ticker = symbol in self.tickers.get(exchange, {})
        return has_orderbook  # Ticker是可选的

