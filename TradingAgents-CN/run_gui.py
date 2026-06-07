"""
启动 TradingAgents CLI 交互式 GUI 界面
用法: python run_gui.py
"""
import sys
import os
import io

# Fix Windows GBK encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

# 设置环境变量确保 DeepSeek 配置可用
os.environ.setdefault("OPENAI_API_KEY", "sk-c949be1fe3404e3db1a5feb229306038")

from cli.main import run_analysis

if __name__ == "__main__":
    run_analysis()
