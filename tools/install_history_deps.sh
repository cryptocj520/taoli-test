#!/bin/bash
# 安装历史记录功能所需的依赖

echo "=========================================="
echo "安装历史记录功能依赖"
echo "=========================================="
echo ""

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

# 检测是否为 Homebrew Python（macOS）
# Homebrew Python 需要 --break-system-packages 标志
BREAK_FLAG=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS 系统，检查是否为 Homebrew Python
    if python3 -c "import sys; print(sys.prefix)" 2>/dev/null | grep -q "brew\|Cellar"; then
        echo ""
        echo "⚠️  检测到 Homebrew Python"
        echo "   将使用 --break-system-packages 标志"
        BREAK_FLAG="--break-system-packages"
    fi
fi

# 安装依赖
echo ""
echo "正在安装依赖..."
if [ -n "$BREAK_FLAG" ]; then
    pip3 install $BREAK_FLAG aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 streamlit>=1.28.0 pandas>=2.1.3
else
    # 先尝试正常安装
    pip3 install aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 streamlit>=1.28.0 pandas>=2.1.3 2>&1 | tee /tmp/pip_install.log
    if [ ${PIPESTATUS[0]} -ne 0 ] && grep -q "externally-managed" /tmp/pip_install.log; then
        echo ""
        echo "⚠️  检测到 externally-managed-environment，使用 --break-system-packages"
        pip3 install --break-system-packages aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 streamlit>=1.28.0 pandas>=2.1.3
    fi
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 依赖安装成功！"
    echo ""
    echo "验证安装..."
    python3 -c "import aiofiles; import aiosqlite; import pandas; import plotly; import streamlit; print('✅ 所有依赖已正确安装')" 2>&1
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "🎉 可以开始测试了！"
        echo "   运行: python3 tools/test_spread_history_quick.py"
    else
        echo ""
        echo "⚠️  部分依赖可能未正确安装，请检查错误信息"
        echo ""
        echo "提示：如果遇到导入错误，请尝试："
        echo "  1. 重启终端"
        echo "  2. 检查 Python 路径: which python3"
        echo "  3. 手动验证: python3 -c 'import aiofiles'"
    fi
else
    echo ""
    echo "❌ 依赖安装失败"
    echo ""
    echo "如果遇到 externally-managed-environment 错误，请尝试："
    echo "  方法1: pip3 install $BREAK_FLAG --user aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 streamlit>=1.28.0 pandas>=2.1.3"
    echo "  方法2: 使用虚拟环境"
    echo "    python3 -m venv venv"
    echo "    source venv/bin/activate"
    echo "    pip install aiofiles>=23.0.0 aiosqlite>=0.19.0 plotly>=5.18.0 streamlit>=1.28.0 pandas>=2.1.3"
    exit 1
fi

