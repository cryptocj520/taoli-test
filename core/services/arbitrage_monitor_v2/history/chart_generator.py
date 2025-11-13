"""
图表生成工具

职责：
- 生成Plotly心电图样式图表
- 支持单代币和多代币对比
- 用于数据可视化展示
"""

from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .spread_history_reader import SpreadHistoryReader


class ChartGenerator:
    """图表生成器"""
    
    def __init__(self, db_path: str = "data/spread_history.db"):
        """
        初始化图表生成器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.reader = SpreadHistoryReader(db_path)
    
    def create_spread_chart(
        self,
        df: pd.DataFrame,
        symbol: str,
        title: Optional[str] = None
    ) -> go.Figure:
        """
        创建基础价差走势图表
        
        Args:
            df: 数据DataFrame
            symbol: 代币符号
            title: 图表标题（可选）
            
        Returns:
            Plotly图表对象
        """
        fig = go.Figure()
        
        # 添加价差走势线
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['spread_pct'],
            mode='lines+markers',
            name='价差',
            line=dict(color='blue', width=2),
            marker=dict(size=4)
        ))
        
        # 添加资金费率差（如果有）
        if 'funding_rate_diff_annual' in df.columns and df['funding_rate_diff_annual'].notna().any():
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['funding_rate_diff_annual'],
                mode='lines',
                name='资金费率差（年化）',
                yaxis='y2',
                line=dict(color='orange', width=1, dash='dot')
            ))
        
        fig.update_layout(
            title=title or f'{symbol} 价差走势图',
            xaxis_title='时间',
            yaxis_title='价差 (%)',
            yaxis2=dict(
                title='资金费率差（年化%）',
                overlaying='y',
                side='right'
            ) if 'funding_rate_diff_annual' in df.columns and df['funding_rate_diff_annual'].notna().any() else None,
            hovermode='x unified',
            legend=dict(x=0, y=1)
        )
        
        return fig
    
    def create_ecg_style_chart(
        self,
        df: pd.DataFrame,
        symbol: str,
        title: Optional[str] = None
    ) -> go.Figure:
        """
        创建心电图样式的价差走势图
        
        效果特点：
        - 连续的折线图，类似心电图波形
        - 深色背景，高对比度线条
        - 网格线辅助读数
        - 高亮显示异常值（高价差）
        - 平滑的曲线过渡
        
        Args:
            df: 数据DataFrame
            symbol: 代币符号
            title: 图表标题（可选）
            
        Returns:
            Plotly图表对象
        """
        if len(df) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20, color='white')
            )
            fig.update_layout(
                plot_bgcolor='#1e1e1e',
                paper_bgcolor='#1e1e1e'
            )
            return fig
        
        fig = go.Figure()
        
        # 计算异常值阈值（价差 > 平均值 + 2倍标准差）
        mean_spread = df['spread_pct'].mean()
        std_spread = df['spread_pct'].std()
        threshold_high = mean_spread + 2 * std_spread
        threshold_low = mean_spread - 2 * std_spread
        
        # 分离正常值和异常值
        normal_data = df[df['spread_pct'].between(threshold_low, threshold_high)]
        high_anomaly = df[df['spread_pct'] > threshold_high]
        low_anomaly = df[df['spread_pct'] < threshold_low]
        
        # 正常值：绿色线条（类似心电图正常波形）
        if len(normal_data) > 0:
            fig.add_trace(go.Scatter(
                x=normal_data['timestamp'],
                y=normal_data['spread_pct'],
                mode='lines',
                name='正常价差',
                line=dict(color='#00ff00', width=2, shape='spline'),  # 绿色，平滑曲线
                hovertemplate='<b>%{fullData.name}</b><br>' +
                            '时间: %{x}<br>' +
                            '价差: %{y:.4f}%<extra></extra>'
            ))
        
        # 高价差异常值：红色高亮（类似心电图异常波形）
        if len(high_anomaly) > 0:
            fig.add_trace(go.Scatter(
                x=high_anomaly['timestamp'],
                y=high_anomaly['spread_pct'],
                mode='markers+lines',
                name='高价差（异常）',
                line=dict(color='#ff0000', width=3, shape='spline'),
                marker=dict(size=8, color='#ff0000', symbol='diamond'),
                hovertemplate='<b>⚠️ %{fullData.name}</b><br>' +
                            '时间: %{x}<br>' +
                            '价差: %{y:.4f}%<extra></extra>'
            ))
        
        # 低价差异常值：黄色高亮
        if len(low_anomaly) > 0:
            fig.add_trace(go.Scatter(
                x=low_anomaly['timestamp'],
                y=low_anomaly['spread_pct'],
                mode='markers+lines',
                name='低价差（异常）',
                line=dict(color='#ffff00', width=2, shape='spline'),
                marker=dict(size=6, color='#ffff00', symbol='circle'),
                hovertemplate='<b>⚠️ %{fullData.name}</b><br>' +
                            '时间: %{x}<br>' +
                            '价差: %{y:.4f}%<extra></extra>'
            ))
        
        # 添加参考线（平均值）
        fig.add_hline(
            y=mean_spread,
            line_dash="dash",
            line_color="white",
            annotation_text=f"平均值: {mean_spread:.4f}%",
            annotation_position="right"
        )
        
        # 心电图样式布局
        fig.update_layout(
            title=dict(
                text=title or f'📊 {symbol} 价差走势图（心电图样式）',
                font=dict(size=20, color='white'),
                x=0.5
            ),
            xaxis=dict(
                title='时间',
                titlefont=dict(color='white', size=14),
                tickfont=dict(color='white'),
                gridcolor='rgba(255, 255, 255, 0.1)',
                gridwidth=1,
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                title='价差 (%)',
                titlefont=dict(color='white', size=14),
                tickfont=dict(color='white'),
                gridcolor='rgba(255, 255, 255, 0.1)',
                gridwidth=1,
                showgrid=True,
                zeroline=True,
                zerolinecolor='rgba(255, 255, 255, 0.3)',
                zerolinewidth=1
            ),
            plot_bgcolor='#1e1e1e',  # 深色背景
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            hovermode='x unified',
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(0, 0, 0, 0.5)',
                bordercolor='white',
                borderwidth=1,
                font=dict(color='white', size=12)
            ),
            height=600,
            width=1200
        )
        
        return fig
    
    def create_multi_symbol_chart(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        title: Optional[str] = None
    ) -> go.Figure:
        """
        创建多个代币的价差走势对比图
        
        Args:
            symbols: 代币符号列表
            start_date: 开始时间
            end_date: 结束时间
            title: 图表标题（可选）
            
        Returns:
            Plotly图表对象
        """
        fig = go.Figure()
        
        colors = ['#00ff00', '#00ffff', '#ff00ff', '#ffff00', '#ff8800', '#ff0088', '#0088ff']
        
        for i, symbol in enumerate(symbols):
            df = self.reader.query_symbol_trend(symbol, start_date, end_date)
            if len(df) > 0:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['spread_pct'],
                    mode='lines',
                    name=symbol,
                    line=dict(color=colors[i % len(colors)], width=2)
                ))
        
        fig.update_layout(
            title=title or '多个代币价差走势对比',
            xaxis_title='时间',
            yaxis_title='价差 (%)',
            hovermode='x unified',
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            legend=dict(
                bgcolor='rgba(0, 0, 0, 0.5)',
                bordercolor='white',
                borderwidth=1,
                font=dict(color='white', size=12)
            ),
            height=600,
            width=1200
        )
        
        return fig
    
    def create_ecg_multi_channel_chart(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        title: Optional[str] = None
    ) -> go.Figure:
        """
        创建多通道心电图样式图表（类似多导联心电图）
        
        效果：多个代币的价差走势并排显示，类似心电图的多导联显示
        
        Args:
            symbols: 代币符号列表
            start_date: 开始时间
            end_date: 结束时间
            title: 图表标题（可选）
            
        Returns:
            Plotly图表对象
        """
        num_symbols = len(symbols)
        fig = make_subplots(
            rows=num_symbols,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=symbols
        )
        
        colors = ['#00ff00', '#00ffff', '#ff00ff', '#ffff00', '#ff8800']
        
        for i, symbol in enumerate(symbols):
            df = self.reader.query_symbol_trend(symbol, start_date, end_date)
            if len(df) > 0:
                # 计算偏移量（让每个通道分开显示）
                offset = i * 0.5  # 每个通道偏移0.5%
                y_values = df['spread_pct'] + offset
                
                fig.add_trace(
                    go.Scatter(
                        x=df['timestamp'],
                        y=y_values,
                        mode='lines',
                        name=symbol,
                        line=dict(color=colors[i % len(colors)], width=2, shape='spline'),
                        showlegend=False
                    ),
                    row=i+1,
                    col=1
                )
                
                # 添加参考线
                mean_val = df['spread_pct'].mean() + offset
                fig.add_hline(
                    y=mean_val,
                    line_dash="dash",
                    line_color="rgba(255, 255, 255, 0.3)",
                    line_width=1,
                    row=i+1,
                    col=1
                )
        
        # 心电图样式布局
        fig.update_layout(
            title=dict(
                text=title or '📊 多代币价差走势图（多通道心电图样式）',
                font=dict(size=20, color='white'),
                x=0.5
            ),
            plot_bgcolor='#1e1e1e',
            paper_bgcolor='#1e1e1e',
            font=dict(color='white'),
            height=200 * num_symbols,
            width=1200
        )
        
        # 更新所有子图的样式
        for i in range(num_symbols):
            fig.update_xaxes(
                gridcolor='rgba(255, 255, 255, 0.1)',
                gridwidth=1,
                showgrid=True,
                zeroline=False,
                row=i+1,
                col=1
            )
            fig.update_yaxes(
                gridcolor='rgba(255, 255, 255, 0.1)',
                gridwidth=1,
                showgrid=True,
                zeroline=True,
                zerolinecolor='rgba(255, 255, 255, 0.3)',
                row=i+1,
                col=1
            )
        
        return fig
    
    def create_symbol_chart_from_db(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minutes: Optional[int] = None,
        style: str = "ecg"
    ) -> go.Figure:
        """
        从数据库查询数据并创建图表
        
        Args:
            symbol: 代币符号
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            minutes: 最近N分钟（可选，优先级高于start_date/end_date）
            style: 图表样式（"ecg"或"normal"）
            
        Returns:
            Plotly图表对象
        """
        if minutes:
            df = self.reader.query_latest_data(symbol, minutes)
        else:
            df = self.reader.query_symbol_trend(symbol, start_date, end_date)
        
        if style == "ecg":
            return self.create_ecg_style_chart(df, symbol)
        else:
            return self.create_spread_chart(df, symbol)

