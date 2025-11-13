"""
套利机会识别器

职责：
- 识别符合条件的套利机会
- 过滤和排序机会
- 管理机会的持续时间
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .spread_calculator import SpreadData
from ..config.monitor_config import MonitorConfig
from ..config.debug_config import DebugConfig


@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    symbol: str
    exchange_buy: str
    exchange_sell: str
    price_buy: float
    price_sell: float
    size_buy: float
    size_sell: float
    spread_pct: float
    funding_rate_buy: Optional[float] = None
    funding_rate_sell: Optional[float] = None
    funding_rate_diff: Optional[float] = None
    duration_seconds: float = 0.0
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    def update_duration(self):
        """更新持续时间"""
        self.last_seen = datetime.now()
        self.duration_seconds = (self.last_seen - self.first_seen).total_seconds()
    
    def get_opportunity_key(self) -> str:
        """获取机会的唯一标识"""
        return f"{self.symbol}_{self.exchange_buy}_{self.exchange_sell}"


class OpportunityFinder:
    """套利机会识别器"""
    
    def __init__(
        self,
        monitor_config: MonitorConfig,
        debug_config: DebugConfig,
        scroller=None  # 实时滚动区管理器（可选）
    ):
        """
        初始化机会识别器
        
        Args:
            monitor_config: 监控配置
            debug_config: Debug配置
            scroller: 实时滚动区管理器（用于实时打印）
        """
        self.config = monitor_config
        self.debug = debug_config
        self.scroller = scroller  # 🔥 混合模式：实时滚动输出
        
        # 当前追踪的机会 {key: ArbitrageOpportunity}
        self.opportunities: Dict[str, ArbitrageOpportunity] = {}
        
        # 统计信息
        self.stats = {
            'opportunities_found': 0,
            'opportunities_expired': 0,
        }
    
    def find_opportunities(
        self,
        spreads: List[SpreadData],
        funding_rates: Optional[Dict[str, Dict[str, float]]] = None
    ) -> List[ArbitrageOpportunity]:
        """
        从价差数据中识别套利机会
        
        Args:
            spreads: 价差数据列表
            funding_rates: 资金费率 {exchange: {symbol: rate}}
            
        Returns:
            套利机会列表
        """
        current_opportunities = []
        current_keys = set()
        
        for spread in spreads:
            # 过滤：价差必须大于阈值
            if spread.spread_pct < self.config.min_spread_pct:
                continue
            
            # 创建或更新机会
            key = f"{spread.symbol}_{spread.exchange_buy}_{spread.exchange_sell}"
            current_keys.add(key)
            
            if key in self.opportunities:
                # 更新现有机会
                opp = self.opportunities[key]
                opp.price_buy = float(spread.price_buy)
                opp.price_sell = float(spread.price_sell)
                opp.size_buy = float(spread.size_buy)
                opp.size_sell = float(spread.size_sell)
                opp.spread_pct = spread.spread_pct
                opp.update_duration()
            else:
                # 新发现的机会
                opp = ArbitrageOpportunity(
                    symbol=spread.symbol,
                    exchange_buy=spread.exchange_buy,
                    exchange_sell=spread.exchange_sell,
                    price_buy=float(spread.price_buy),
                    price_sell=float(spread.price_sell),
                    size_buy=float(spread.size_buy),
                    size_sell=float(spread.size_sell),
                    spread_pct=spread.spread_pct,
                )
                self.opportunities[key] = opp
                self.stats['opportunities_found'] += 1
                
                # 🔥 混合模式：实时打印新发现的套利机会
                if self.scroller:
                    try:
                        self.scroller.print_opportunity(
                            symbol=spread.symbol,
                            exchange_buy=spread.exchange_buy,
                            exchange_sell=spread.exchange_sell,
                            price_buy=float(spread.price_buy),
                            price_sell=float(spread.price_sell),
                            spread_pct=spread.spread_pct
                        )
                    except Exception:
                        # 静默处理错误，不影响分析
                        pass
            
            # 🔥 添加资金费率信息（参考v1算法：直接相减，保留正负号）
            # 存储的是8小时费率差（小数形式），显示时转换为年化费率差
            funding_rate_diff = None
            if funding_rates:
                opp.funding_rate_buy = funding_rates.get(spread.exchange_buy, {}).get(spread.symbol)
                opp.funding_rate_sell = funding_rates.get(spread.exchange_sell, {}).get(spread.symbol)
                
                if opp.funding_rate_buy is not None and opp.funding_rate_sell is not None:
                    # v1算法：rate_diff = fr1 - fr2（直接相减，保留正负号）
                    # v2中：funding_rate_diff = funding_rate_sell - funding_rate_buy
                    # 存储8小时费率差（小数形式，如0.0001表示0.01%）
                    opp.funding_rate_diff = opp.funding_rate_sell - opp.funding_rate_buy
                    funding_rate_diff = opp.funding_rate_diff
            
            # 🔥 混合模式：实时打印新发现的套利机会（包含资金费率差）
            if self.scroller:
                try:
                    self.scroller.print_opportunity(
                        symbol=spread.symbol,
                        exchange_buy=spread.exchange_buy,
                        exchange_sell=spread.exchange_sell,
                        price_buy=float(spread.price_buy),
                        price_sell=float(spread.price_sell),
                        spread_pct=spread.spread_pct,
                        funding_rate_diff=funding_rate_diff  # 🔥 传递8小时费率差（小数形式）
                    )
                except Exception:
                    # 静默处理错误，不影响分析
                    pass
            
            current_opportunities.append(opp)
        
        # 清理过期的机会
        expired_keys = set(self.opportunities.keys()) - current_keys
        for key in expired_keys:
            del self.opportunities[key]
            self.stats['opportunities_expired'] += 1
        
        # 按价差排序（从大到小）
        current_opportunities.sort(key=lambda x: x.spread_pct, reverse=True)
        
        return current_opportunities
    
    def get_opportunities_by_symbol(self, symbol: str) -> List[ArbitrageOpportunity]:
        """
        获取指定交易对的机会
        
        Args:
            symbol: 交易对
            
        Returns:
            机会列表
        """
        return [opp for opp in self.opportunities.values() if opp.symbol == symbol]
    
    def get_all_opportunities(self) -> List[ArbitrageOpportunity]:
        """获取所有机会"""
        opps = list(self.opportunities.values())
        opps.sort(key=lambda x: x.spread_pct, reverse=True)
        return opps
    
    def get_top_opportunities(self, limit: int = 10) -> List[ArbitrageOpportunity]:
        """
        获取Top N的机会
        
        Args:
            limit: 数量限制
            
        Returns:
            Top机会列表
        """
        all_opps = self.get_all_opportunities()
        return all_opps[:limit]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'active_opportunities': len(self.opportunities),
        }
    
    def clear(self):
        """清空所有机会"""
        self.opportunities.clear()

