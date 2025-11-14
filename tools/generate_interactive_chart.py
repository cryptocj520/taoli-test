#!/usr/bin/env python3
"""
交互式价差走势图表生成工具

生成一个HTML文件，可以在浏览器中切换查看不同代币的图表
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.services.arbitrage_monitor_v2.history import ChartGenerator, SpreadHistoryReader


def generate_interactive_html(symbols: list, db_path: str, output_file: str = "interactive_spread_chart.html"):
    """
    生成交互式HTML图表，支持切换代币
    
    Args:
        symbols: 代币列表
        db_path: 数据库路径
        output_file: 输出HTML文件路径
    """
    reader = SpreadHistoryReader(db_path=db_path)
    generator = ChartGenerator(db_path=db_path)
    
    # 生成每个代币的图表数据
    charts_data = {}
    for symbol in symbols:
        df = reader.query_latest_data(symbol, minutes=60)
        if len(df) > 0:
            fig = generator.create_ecg_style_chart(df, symbol)
            charts_data[symbol] = fig.to_json()
    
    if not charts_data:
        print("❌ 没有可用的数据")
        return
    
    # 生成HTML内容
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>交互式价差走势图表</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #1e1e1e;
            color: white;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .controls {{
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .control-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        label {{
            font-weight: bold;
        }}
        select {{
            padding: 8px 15px;
            background-color: #3d3d3d;
            color: white;
            border: 1px solid #555;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
        }}
        select:hover {{
            background-color: #4d4d4d;
        }}
        .chart-container {{
            background-color: #2d2d2d;
            padding: 20px;
            border-radius: 8px;
            min-height: 600px;
        }}
        .info {{
            margin-top: 20px;
            padding: 15px;
            background-color: #2d2d2d;
            border-radius: 8px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 交互式价差走势图表（心电图样式）</h1>
            <p>选择代币查看其价差走势</p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label for="symbolSelect">选择代币：</label>
                <select id="symbolSelect" onchange="updateChart()">
                    {chr(10).join([f'                    <option value="{symbol}">{symbol}</option>' for symbol in charts_data.keys()])}
                </select>
            </div>
            <div class="control-group">
                <label>数据范围：</label>
                <span>最近60分钟</span>
            </div>
        </div>
        
        <div class="chart-container">
            <div id="chart"></div>
        </div>
        
        <div class="info">
            <strong>使用说明：</strong>
            <ul>
                <li>使用下拉菜单切换查看不同代币的价差走势</li>
                <li>图表支持缩放、平移、悬停查看详细数据</li>
                <li>图表样式为心电图样式，深色背景，高对比度</li>
            </ul>
        </div>
    </div>
    
    <script>
        // 图表数据
        const chartsData = {charts_data};
        
        // 初始化图表
        function initChart() {{
            const symbol = document.getElementById('symbolSelect').value;
            const chartData = JSON.parse(chartsData[symbol]);
            Plotly.newPlot('chart', chartData.data, chartData.layout, {{responsive: true}});
        }}
        
        // 更新图表
        function updateChart() {{
            const symbol = document.getElementById('symbolSelect').value;
            const chartData = JSON.parse(chartsData[symbol]);
            Plotly.newPlot('chart', chartData.data, chartData.layout, {{responsive: true}});
        }}
        
        // 页面加载时初始化
        window.onload = function() {{
            initChart();
        }};
    </script>
</body>
</html>
"""
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ 交互式图表已生成: {output_file}")
    print(f"📊 包含 {len(charts_data)} 个代币的图表")
    print(f"💡 在浏览器中打开文件，使用下拉菜单切换代币")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成交互式价差走势图表（支持切换代币）')
    parser.add_argument('--db-path', type=str, default='data/spread_history/spread_history.db', 
                       help='数据库路径')
    parser.add_argument('--output', type=str, default='interactive_spread_chart.html',
                       help='输出HTML文件路径')
    parser.add_argument('--minutes', type=int, default=60,
                       help='查询最近N分钟的数据')
    
    args = parser.parse_args()
    
    # 创建读取器
    reader = SpreadHistoryReader(db_path=args.db_path)
    
    # 获取所有代币
    symbols = reader.get_all_symbols()
    if not symbols:
        print("❌ 数据库中没有数据")
        return
    
    print(f"📊 找到 {len(symbols)} 个代币")
    print(f"📊 代币列表: {', '.join(symbols)}")
    
    # 生成交互式HTML
    generate_interactive_html(symbols, args.db_path, args.output)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  操作被用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

