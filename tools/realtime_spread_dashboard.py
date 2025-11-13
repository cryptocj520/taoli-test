#!/usr/bin/env python3
"""
实时价差监控仪表板（Streamlit）

用于实时显示价差走势的心电图样式图表
"""

import streamlit as st
import plotly.graph_objects as go
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.arbitrage_monitor_v2.history import ChartGenerator, SpreadHistoryReader


def main():
    """创建实时监控仪表板"""
    st.set_page_config(
        page_title="实时价差监控",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("📊 实时价差监控（心电图样式）")
    
    # 侧边栏配置
    st.sidebar.header("⚙️ 配置")
    
    # 数据库路径配置
    db_path = st.sidebar.text_input(
        "数据库路径",
        value="data/spread_history.db",
        help="SQLite数据库文件路径"
    )
    
    # 初始化读取器和图表生成器
    try:
        reader = SpreadHistoryReader(db_path=db_path)
        generator = ChartGenerator(db_path=db_path)
    except Exception as e:
        st.error(f"❌ 初始化失败: {e}")
        st.stop()
    
    # 获取所有代币列表
    all_symbols = reader.get_all_symbols()
    if not all_symbols:
        st.warning("⚠️ 数据库中没有数据，请先运行监控程序并启用历史记录功能")
        st.info("💡 提示：在配置文件中设置 `spread_history.enabled: true` 启用历史记录功能")
        st.stop()
    
    # 选择代币
    symbol = st.sidebar.selectbox(
        "选择代币",
        options=all_symbols,
        index=0 if all_symbols else None
    )
    
    # 时间范围选择
    time_range = st.sidebar.selectbox(
        "时间范围",
        options=["最近1小时", "最近24小时", "最近7天", "最近30天", "自定义"],
        index=1
    )
    
    # 自定义时间范围
    start_date = None
    end_date = None
    
    if time_range == "自定义":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=datetime.now().date() - timedelta(days=1))
        with col2:
            end_date = st.date_input("结束日期", value=datetime.now().date())
        
        start_time = st.sidebar.time_input("开始时间", value=datetime.min.time())
        end_time = st.sidebar.time_input("结束时间", value=datetime.max.time())
        
        start_date = f"{start_date} {start_time}"
        end_date = f"{end_date} {end_time}"
    elif time_range == "最近1小时":
        minutes = 60
    elif time_range == "最近24小时":
        minutes = 24 * 60
    elif time_range == "最近7天":
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    elif time_range == "最近30天":
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 图表样式选择
    chart_style = st.sidebar.selectbox(
        "图表样式",
        options=["心电图样式", "普通样式"],
        index=0
    )
    
    # 自动刷新配置
    auto_refresh = st.sidebar.checkbox("自动刷新", value=True)
    refresh_interval = st.sidebar.slider("刷新间隔（秒）", 5, 60, 10)
    
    # 创建占位符（用于实时更新）
    chart_placeholder = st.empty()
    stats_placeholder = st.empty()
    status_placeholder = st.empty()
    
    # 多代币对比选项
    st.sidebar.header("📊 多代币对比")
    compare_symbols = st.sidebar.multiselect(
        "选择对比代币",
        options=all_symbols,
        default=[],
        help="选择多个代币进行对比"
    )
    
    # 主内容区
    if symbol:
        # 查询数据
        if time_range in ["最近1小时", "最近24小时"]:
            df = reader.query_latest_data(symbol, minutes=minutes)
        else:
            df = reader.query_symbol_trend(symbol, start_date, end_date)
        
        if len(df) > 0:
            # 创建图表
            if chart_style == "心电图样式":
                fig = generator.create_ecg_style_chart(df, symbol)
            else:
                fig = generator.create_spread_chart(df, symbol)
            
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            # 显示统计信息
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                current_spread = df['spread_pct'].iloc[-1] if len(df) > 0 else 0
                st.metric("当前价差", f"{current_spread:.4f}%")
            with col2:
                st.metric("平均价差", f"{df['spread_pct'].mean():.4f}%")
            with col3:
                st.metric("最大价差", f"{df['spread_pct'].max():.4f}%")
            with col4:
                st.metric("数据点数", len(df))
            
            # 显示时间范围信息
            st.caption(
                f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"数据范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}"
            )
        else:
            st.warning("⚠️ 暂无数据，等待数据写入...")
            st.info("💡 提示：确保监控程序正在运行并启用了历史记录功能")
    
    # 多代币对比图
    if compare_symbols and len(compare_symbols) > 1:
        st.header("📊 多代币对比")
        
        if time_range in ["最近1小时", "最近24小时"]:
            compare_start_date = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
            compare_end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            compare_start_date = start_date
            compare_end_date = end_date
        
        compare_fig = generator.create_multi_symbol_chart(
            compare_symbols,
            compare_start_date,
            compare_end_date
        )
        st.plotly_chart(compare_fig, use_container_width=True)
    
    # 自动刷新逻辑
    if auto_refresh:
        status_placeholder.info(f"⏱️ 将在 {refresh_interval} 秒后自动刷新...")
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()

