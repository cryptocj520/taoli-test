"""
差价计算引擎

职责：
- 计算交易所间的价差
- 识别低买高卖机会
- 提供差价数据
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

from core.adapters.exchanges.models import OrderBookData
from ..config.debug_config import DebugConfig


@dataclass
class SpreadData:
    """价差数据"""
    symbol: str
    exchange_buy: str   # 低价交易所（买入）
    exchange_sell: str  # 高价交易所（卖出）
    price_buy: Decimal  # 买入价（Ask1）
    price_sell: Decimal # 卖出价（Bid1）
    size_buy: Decimal   # 买入数量
    size_sell: Decimal  # 卖出数量
    spread_abs: Decimal # 绝对差价
    spread_pct: float   # 差价百分比


class SpreadCalculator:
    """差价计算器"""
    
    def __init__(self, debug_config: DebugConfig):
        """
        初始化差价计算器
        
        Args:
            debug_config: Debug配置
        """
        self.debug = debug_config
        self._calc_counter = 0
    
    def calculate_spreads(
        self,
        symbol: str,
        orderbooks: Dict[str, OrderBookData]
    ) -> List[SpreadData]:
        """
        计算所有交易所间的价差
        
        Args:
            symbol: 交易对
            orderbooks: {exchange: orderbook}
            
        Returns:
            价差数据列表（只包含有利可图的机会）
        """
        spreads = []
        exchanges = list(orderbooks.keys())
        
        # 遍历所有交易所对
        for i, ex1 in enumerate(exchanges):
            for ex2 in enumerate(exchanges[i+1:], start=i+1):
                ex2_idx, ex2 = ex2
                
                ob1 = orderbooks[ex1]
                ob2 = orderbooks[ex2]
                
                # 验证数据完整性
                if not self._validate_orderbook(ob1) or not self._validate_orderbook(ob2):
                    continue
                
                # 方向1: ex1买 -> ex2卖 (ex1的Ask < ex2的Bid)
                if ob2.best_bid.price > ob1.best_ask.price:
                    spread_abs = ob2.best_bid.price - ob1.best_ask.price
                    spread_pct = float((spread_abs / ob1.best_ask.price) * 100)
                    
                    if spread_pct > 0:  # 有利可图
                        spreads.append(SpreadData(
                            symbol=symbol,
                            exchange_buy=ex1,
                            exchange_sell=ex2,
                            price_buy=ob1.best_ask.price,
                            price_sell=ob2.best_bid.price,
                            size_buy=ob1.best_ask.size,
                            size_sell=ob2.best_bid.size,
                            spread_abs=spread_abs,
                            spread_pct=spread_pct
                        ))
                
                # 方向2: ex2买 -> ex1卖 (ex2的Ask < ex1的Bid)
                if ob1.best_bid.price > ob2.best_ask.price:
                    spread_abs = ob1.best_bid.price - ob2.best_ask.price
                    spread_pct = float((spread_abs / ob2.best_ask.price) * 100)
                    
                    if spread_pct > 0:  # 有利可图
                        spreads.append(SpreadData(
                            symbol=symbol,
                            exchange_buy=ex2,
                            exchange_sell=ex1,
                            price_buy=ob2.best_ask.price,
                            price_sell=ob1.best_bid.price,
                            size_buy=ob2.best_ask.size,
                            size_sell=ob1.best_bid.size,
                            spread_abs=spread_abs,
                            spread_pct=spread_pct
                        ))
        
        # Debug输出（采样）
        self._calc_counter += 1
        if self.debug.show_spread_calc and self.debug.should_show_spread_calc(self._calc_counter):
            if spreads:
                for s in spreads:
                    print(f"💰 {s.symbol} 套利机会: "
                          f"{s.exchange_buy}买@{s.price_buy:.2f} → "
                          f"{s.exchange_sell}卖@{s.price_sell:.2f} | "
                          f"差价={s.spread_pct:.3f}%")
        
        return spreads
    
    def _validate_orderbook(self, orderbook: OrderBookData) -> bool:
        """
        验证订单簿数据
        
        Args:
            orderbook: 订单簿数据
            
        Returns:
            是否有效
        """
        if not orderbook.best_bid or not orderbook.best_ask:
            return False
        
        if orderbook.best_bid.price <= 0 or orderbook.best_ask.price <= 0:
            return False
        
        if orderbook.best_bid.size <= 0 or orderbook.best_ask.size <= 0:
            return False
        
        # 检查价差合理性（Bid应该小于Ask）
        if orderbook.best_bid.price >= orderbook.best_ask.price:
            return False
        
        return True
    
    def calculate_single_spread(
        self,
        exchange1: str,
        orderbook1: OrderBookData,
        exchange2: str,
        orderbook2: OrderBookData,
        symbol: str
    ) -> Optional[SpreadData]:
        """
        计算两个交易所间的最佳价差
        
        Args:
            exchange1: 交易所1
            orderbook1: 交易所1的订单簿
            exchange2: 交易所2
            orderbook2: 交易所2的订单簿
            symbol: 交易对
            
        Returns:
            最佳价差数据，如果无利可图则返回None
        """
        if not self._validate_orderbook(orderbook1) or not self._validate_orderbook(orderbook2):
            return None
        
        # 方向1: ex1买 -> ex2卖
        spread1_abs = orderbook2.best_bid.price - orderbook1.best_ask.price
        spread1_pct = float((spread1_abs / orderbook1.best_ask.price) * 100)
        
        # 方向2: ex2买 -> ex1卖
        spread2_abs = orderbook1.best_bid.price - orderbook2.best_ask.price
        spread2_pct = float((spread2_abs / orderbook2.best_ask.price) * 100)
        
        # 选择更大的价差
        if spread1_pct > spread2_pct and spread1_pct > 0:
            return SpreadData(
                symbol=symbol,
                exchange_buy=exchange1,
                exchange_sell=exchange2,
                price_buy=orderbook1.best_ask.price,
                price_sell=orderbook2.best_bid.price,
                size_buy=orderbook1.best_ask.size,
                size_sell=orderbook2.best_bid.size,
                spread_abs=spread1_abs,
                spread_pct=spread1_pct
            )
        elif spread2_pct > 0:
            return SpreadData(
                symbol=symbol,
                exchange_buy=exchange2,
                exchange_sell=exchange1,
                price_buy=orderbook2.best_ask.price,
                price_sell=orderbook1.best_bid.price,
                size_buy=orderbook2.best_ask.size,
                size_sell=orderbook1.best_bid.size,
                spread_abs=spread2_abs,
                spread_pct=spread2_pct
            )
        
        return None

