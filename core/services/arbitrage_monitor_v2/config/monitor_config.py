"""
套利监控配置管理模块

职责：
- 加载和管理监控配置（交易对、阈值等）
- 提供配置访问接口
- 支持配置验证
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml
from dataclasses import dataclass, field


@dataclass
class MonitorConfig:
    """套利监控配置"""
    
    # 交易所配置
    exchanges: List[str] = field(default_factory=list)
    
    # 监控的交易对列表
    symbols: List[str] = field(default_factory=list)
    
    # 价差阈值配置
    min_spread_pct: float = 0.1  # 最小价差百分比
    
    # 资金费率配置
    min_funding_rate_diff: float = 0.01  # 最小资金费率差异
    
    # WebSocket配置
    ws_ping_interval: int = 30  # WebSocket心跳间隔（秒）
    ws_reconnect_delay: int = 5  # 重连延迟（秒）
    ws_max_reconnect_attempts: int = 5  # 最大重连次数
    
    # 数据队列配置
    orderbook_queue_size: int = 1000  # 订单簿队列大小
    ticker_queue_size: int = 500  # Ticker队列大小
    analysis_queue_size: int = 100  # 分析结果队列大小
    
    # 性能配置
    analysis_interval_ms: int = 10  # 分析间隔（毫秒）
    ui_refresh_interval_ms: int = 1000  # UI刷新间隔（毫秒）- 降低频率避免卡顿
    
    # 健康检查配置
    health_check_interval: int = 10  # 健康检查间隔（秒）
    data_timeout_seconds: int = 30  # 数据超时时间（秒）
    
    # 日志配置
    log_dir: str = "logs"
    log_file: str = "arbitrage_monitor_v2.log"
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5
    
    # 历史记录配置
    spread_history_enabled: bool = False  # 历史记录功能开关（默认关闭）
    spread_history_data_dir: str = "data/spread_history"  # 数据存储目录
    spread_history_sample_interval_seconds: int = 60  # 采样间隔（秒），默认1分钟
    spread_history_sample_strategy: str = "max"  # 采样策略：max(最大值), mean(平均值), latest(最新值)
    spread_history_batch_size: int = 10  # 批量写入大小
    spread_history_batch_timeout: float = 60.0  # 批量写入超时（秒）
    spread_history_queue_maxsize: int = 500  # 写入队列最大大小
    # 压缩和归档配置
    spread_history_compress_after_days: int = 10  # 压缩天数（10天后压缩）
    spread_history_archive_after_days: int = 30  # 归档天数（30天后归档）
    spread_history_cleanup_interval_hours: int = 24  # 清理任务执行间隔（小时）


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认配置
        """
        self.config_path = config_path
        self.config = MonitorConfig()
        
        if config_path and config_path.exists():
            self._load_from_file()
        else:
            self._load_defaults()
    
    def _load_from_file(self):
        """从YAML文件加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # 映射YAML配置到MonitorConfig
            if 'exchanges' in data:
                self.config.exchanges = data['exchanges']
            
            if 'symbols' in data:
                self.config.symbols = data['symbols']
            
            if 'thresholds' in data:
                thresholds = data['thresholds']
                self.config.min_spread_pct = thresholds.get('min_spread_pct', 0.1)
                self.config.min_funding_rate_diff = thresholds.get('min_funding_rate_diff', 0.01)
            
            if 'websocket' in data:
                ws = data['websocket']
                self.config.ws_ping_interval = ws.get('ping_interval', 30)
                self.config.ws_reconnect_delay = ws.get('reconnect_delay', 5)
                self.config.ws_max_reconnect_attempts = ws.get('max_reconnect_attempts', 5)
            
            if 'performance' in data:
                perf = data['performance']
                self.config.analysis_interval_ms = perf.get('analysis_interval_ms', 10)
                self.config.ui_refresh_interval_ms = perf.get('ui_refresh_interval_ms', 200)
            
            if 'health_check' in data:
                health = data['health_check']
                self.config.health_check_interval = health.get('interval', 10)
                self.config.data_timeout_seconds = health.get('data_timeout', 30)
            
            # 历史记录配置
            if 'spread_history' in data:
                history = data['spread_history']
                self.config.spread_history_enabled = history.get('enabled', False)
                self.config.spread_history_data_dir = history.get('data_dir', 'data/spread_history')
                if 'sampling' in history:
                    sampling = history['sampling']
                    self.config.spread_history_sample_interval_seconds = sampling.get('interval_seconds', 60)
                    self.config.spread_history_sample_strategy = sampling.get('strategy', 'max')
                if 'write' in history:
                    write = history['write']
                    self.config.spread_history_batch_size = write.get('batch_size', 10)
                    self.config.spread_history_batch_timeout = write.get('batch_timeout', 60.0)
                    self.config.spread_history_queue_maxsize = write.get('queue_maxsize', 500)
                if 'storage' in history:
                    storage = history['storage']
                    self.config.spread_history_compress_after_days = storage.get('compress_after_days', 10)
                    self.config.spread_history_archive_after_days = storage.get('archive_after_days', 30)
                    self.config.spread_history_cleanup_interval_hours = storage.get('cleanup_interval_hours', 24)
            
            print(f"✅ 配置已从文件加载: {self.config_path}")
            
        except Exception as e:
            print(f"⚠️  加载配置文件失败: {e}，使用默认配置")
            self._load_defaults()
    
    def _load_defaults(self):
        """加载默认配置"""
        # 🚀 47个高交易量代币（交易量 >= 1M USD）
        # 从 edgex_lighter_markets.json 筛选出的符合条件的代币
        high_volume_symbols = [
            '1000PEPE-USDC-PERP',
            '1000SHIB-USDC-PERP',
            'AAVE-USDC-PERP',
            'ADA-USDC-PERP',
            'APT-USDC-PERP',
            'ARB-USDC-PERP',
            'ASTER-USDC-PERP',
            'AVAX-USDC-PERP',
            'AVNT-USDC-PERP',
            'BCH-USDC-PERP',
            'BNB-USDC-PERP',
            'BTC-USDC-PERP',
            'CRO-USDC-PERP',
            'DOGE-USDC-PERP',
            'DOT-USDC-PERP',
            'ENA-USDC-PERP',
            'ETH-USDC-PERP',
            'FIL-USDC-PERP',
            'HBAR-USDC-PERP',
            'HYPE-USDC-PERP',
            'ICP-USDC-PERP',
            'IP-USDC-PERP',
            'KAITO-USDC-PERP',
            'LINK-USDC-PERP',
            'LTC-USDC-PERP',
            'MNT-USDC-PERP',
            'NEAR-USDC-PERP',
            'ONDO-USDC-PERP',
            'OP-USDC-PERP',
            'PAXG-USDC-PERP',
            'PUMP-USDC-PERP',
            'RESOLV-USDC-PERP',
            'SEI-USDC-PERP',
            'SOL-USDC-PERP',
            'SUI-USDC-PERP',
            'TAO-USDC-PERP',
            'TON-USDC-PERP',
            'TRUMP-USDC-PERP',
            'TRX-USDC-PERP',
            'UNI-USDC-PERP',
            'VIRTUAL-USDC-PERP',
            'WLD-USDC-PERP',
            'XMR-USDC-PERP',
            'XRP-USDC-PERP',
            'ZEC-USDC-PERP',
            'ZK-USDC-PERP',
            'ZORA-USDC-PERP',
        ]
        
        self.config = MonitorConfig(
            exchanges=['edgex', 'lighter'],
            # 🚀 使用V1的标准化格式（参考 config/arbitrage/monitor.yaml）
            # 这种格式会被SimpleSymbolConverter自动转换成各交易所需要的格式
            # EdgeX: BTC-USDC-PERP -> BTCUSD
            # Lighter: BTC-USDC-PERP -> BTC
            symbols=high_volume_symbols,  # 🔥 订阅47个高交易量代币
        )
        print(f"✅ 使用默认配置（监控 {len(high_volume_symbols)} 个高交易量代币）")
    
    def get_config(self) -> MonitorConfig:
        """获取配置对象"""
        return self.config
    
    def validate(self) -> bool:
        """
        验证配置有效性
        
        Returns:
            配置是否有效
        """
        if not self.config.exchanges:
            print("❌ 配置错误: 交易所列表为空")
            return False
        
        if not self.config.symbols:
            print("❌ 配置错误: 交易对列表为空")
            return False
        
        if len(self.config.exchanges) < 2:
            print("❌ 配置错误: 至少需要2个交易所才能进行套利监控")
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            'exchanges': self.config.exchanges,
            'symbols': self.config.symbols,
            'thresholds': {
                'min_spread_pct': self.config.min_spread_pct,
                'min_funding_rate_diff': self.config.min_funding_rate_diff,
            },
            'websocket': {
                'ping_interval': self.config.ws_ping_interval,
                'reconnect_delay': self.config.ws_reconnect_delay,
                'max_reconnect_attempts': self.config.ws_max_reconnect_attempts,
            },
            'queues': {
                'orderbook_queue_size': self.config.orderbook_queue_size,
                'ticker_queue_size': self.config.ticker_queue_size,
                'analysis_queue_size': self.config.analysis_queue_size,
            },
            'performance': {
                'analysis_interval_ms': self.config.analysis_interval_ms,
                'ui_refresh_interval_ms': self.config.ui_refresh_interval_ms,
            },
            'health_check': {
                'interval': self.config.health_check_interval,
                'data_timeout': self.config.data_timeout_seconds,
            },
        }

