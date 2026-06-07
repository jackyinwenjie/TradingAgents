"""
直接运行股票分析脚本
用法: python run_analysis.py <股票代码> <分析日期>
示例: python run_analysis.py 000938 2026-06-06
"""
import sys
import os
import io

# Fix Windows GBK encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 加载.env
from dotenv import load_dotenv
load_dotenv()

# 解析参数
ticker = sys.argv[1] if len(sys.argv) > 1 else "000938"
analysis_date = sys.argv[2] if len(sys.argv) > 2 else "2026-06-06"

print(f"=" * 60)
print(f"  股票分析系统 - TradingAgents")
print(f"  股票代码: {ticker}")
print(f"  分析日期: {analysis_date}")
print(f"=" * 60)

# 配置
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["backend_url"] = "https://api.deepseek.com/v1"
config["deep_think_llm"] = "deepseek-chat"
config["quick_think_llm"] = "deepseek-chat"
config["max_debate_rounds"] = 1
config["online_tools"] = True

# 市场分析师（可选: market, social, news, fundamentals）
# 社交媒体分析师已禁用
analysts = ["market", "news", "fundamentals"]

print(f"\n使用的分析师: {analysts}")
print(f"使用的模型: {config['quick_think_llm']}")
print(f"后端地址: {config['backend_url']}")
print(f"\n开始分析...\n")

# 初始化
ta = TradingAgentsGraph(analysts, config=config, debug=True)

# 执行分析
_, decision = ta.propagate(ticker, analysis_date)
print("\n" + "=" * 60)
print("  分析结果:")
print("=" * 60)
print(decision)
