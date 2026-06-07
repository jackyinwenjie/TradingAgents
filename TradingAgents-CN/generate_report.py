"""
分析报告生成器
用法: python generate_report.py <股票代码> <分析日期>
示例: python generate_report.py 002747 2026-06-06

功能：
1. 运行完整的分析流程（四个分析师 + 两轮辩论）
2. 将所有过程输出翻译为中文
3. 生成结构化的分析报告文件
"""

import sys
import os
import io
import json
import datetime
from pathlib import Path

# Fix Windows GBK encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv
load_dotenv()

# ==================== 配置 ====================
ticker = sys.argv[1] if len(sys.argv) > 1 else "002747"
analysis_date = sys.argv[2] if len(sys.argv) > 2 else "2026-06-06"

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["backend_url"] = "https://api.deepseek.com/v1"
config["deep_think_llm"] = "deepseek-chat"
config["quick_think_llm"] = "deepseek-chat"
config["max_debate_rounds"] = 1
config["online_tools"] = True

# 社交媒体分析师已禁用
analysts = ["market", "news", "fundamentals"]

# ==================== 翻译工具 ====================
def translate_to_chinese(text: str) -> str:
    """使用 DeepSeek 将英文翻译为中文"""
    if not text or len(text.strip()) == 0:
        return text
    
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
    )
    
    prompt = f"""请将以下金融分析报告从英文翻译成中文。要求：
1. 保持原文的专业性和准确性
2. 金融术语翻译准确
3. Markdown表格格式保持不变
4. 保持原文的结构和分段
5. 只输出翻译结果，不要加任何说明

原文：
{text}
"""
    
    try:
        result = llm.invoke(prompt).content
        return result
    except Exception as e:
        print(f"翻译失败: {e}")
        return text


# ==================== 运行分析 ====================
print(f"{'=' * 60}")
print(f"  TradingAgents 分析报告生成器")
print(f"  股票代码: {ticker}")
print(f"  分析日期: {analysis_date}")
print(f"{'=' * 60}")
print(f"\n正在运行分析流程（三个分析师 + 两轮辩论）...\n")

ta = TradingAgentsGraph(analysts, config=config, debug=True)
final_state, decision = ta.propagate(ticker, analysis_date)

# ==================== 提取报告 ====================
reports = {
    "market": final_state.get("market_report", ""),
    "news": final_state.get("news_report", ""),
    "fundamentals": final_state.get("fundamentals_report", ""),
}

# 投资辩论
invest_debate = final_state.get("investment_debate_state", {})
bull_history = invest_debate.get("bull_history", "")
bear_history = invest_debate.get("bear_history", "")
invest_history = invest_debate.get("history", "")
invest_judge = invest_debate.get("judge_decision", "")

# 交易员
trader_plan = final_state.get("trader_investment_plan", "")

# 风险辩论
risk_debate = final_state.get("risk_debate_state", {})
risky_history = risk_debate.get("risky_history", "")
safe_history = risk_debate.get("safe_history", "")
neutral_history = risk_debate.get("neutral_history", "")
risk_history = risk_debate.get("history", "")
risk_judge = risk_debate.get("judge_decision", "")

# 最终决策
final_decision = final_state.get("final_trade_decision", "")

# ==================== 保存原始数据 ====================
output_dir = Path(f"reports/{ticker}")
output_dir.mkdir(parents=True, exist_ok=True)

# 保存原始 JSON
raw_data = {
    "meta": {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "generated_at": datetime.datetime.now().isoformat(),
    },
    "reports": reports,
    "investment_debate": {
        "bull_history": bull_history,
        "bear_history": bear_history,
        "history": invest_history,
        "judge_decision": invest_judge,
    },
    "trader_plan": trader_plan,
    "risk_debate": {
        "risky_history": risky_history,
        "safe_history": safe_history,
        "neutral_history": neutral_history,
        "history": risk_history,
        "judge_decision": risk_judge,
    },
    "final_decision": final_decision,
    "processed_decision": decision,
}

with open(output_dir / f"raw_data_{analysis_date}.json", "w", encoding="utf-8") as f:
    json.dump(raw_data, f, ensure_ascii=False, indent=2)

print(f"\n原始数据已保存至: {output_dir / f'raw_data_{analysis_date}.json'}")

# ==================== 翻译并生成中文报告 ====================
print("\n正在翻译为中文...")

translated = {}

sections = [
    ("市场技术分析报告", "market", reports.get("market", "")),
    ("全球新闻/宏观分析报告", "news", reports.get("news", "")),
    ("基本面分析报告", "fundamentals", reports.get("fundamentals", "")),
    ("多头研究员论点（投资辩论）", "bull_history", bull_history),
    ("空头研究员论点（投资辩论）", "bear_history", bear_history),
    ("投资辩论裁判裁决", "invest_judge", invest_judge),
    ("交易员交易计划", "trader_plan", trader_plan),
    ("激进风险分析师论点", "risky_history", risky_history),
    ("保守风险分析师论点", "safe_history", safe_history),
    ("中性风险分析师论点", "neutral_history", neutral_history),
    ("风险管理裁判最终裁决", "final_decision", final_decision),
]

for section_name, key, content in sections:
    if content and len(content.strip()) > 0:
        print(f"  翻译: {section_name} ({len(content)} 字符)...")
        translated[key] = translate_to_chinese(content)
    else:
        translated[key] = "(无数据)"

# ==================== 生成中文报告文件 ====================
report_lines = []
report_lines.append("# TradingAgents 股票分析报告\n")
report_lines.append(f"**股票代码**: {ticker}  ")
report_lines.append(f"**分析日期**: {analysis_date}  ")
report_lines.append(f"**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
report_lines.append(f"**最终决策**: **{decision}**\n")
report_lines.append("---\n")

# ===== 第一部分：三个分析师报告 =====
report_lines.append("## 第一部分：三大分析师研究报告\n")

report_lines.append("### 1.1 市场技术分析师\n")
report_lines.append("> 负责分析价格趋势、技术指标（MACD/RSI/布林带/均线等），给出技术面判断\n")
report_lines.append(translated.get("market", ""))
report_lines.append("\n---\n")

report_lines.append("### 1.2 全球新闻/宏观分析师\n")
report_lines.append("> 负责分析全球宏观新闻、行业动态、政策变化\n")
report_lines.append(translated.get("news", ""))
report_lines.append("\n---\n")

report_lines.append("### 1.3 基本面分析师\n")
report_lines.append("> 负责分析财务报表、内部人交易、公司基本面数据\n")
report_lines.append(translated.get("fundamentals", ""))
report_lines.append("\n---\n")

# ===== 第二部分：投资辩论 =====
report_lines.append("## 第二部分：投资辩论（多头 vs 空头）\n")
report_lines.append("> 多头和空头研究员基于四份分析报告进行辩论，最后由投资裁判做出裁决\n")

report_lines.append("### 2.1 多头研究员论点\n")
report_lines.append("> 强调增长潜力、竞争优势、正面指标，反驳空头观点\n")
report_lines.append(translated.get("bull_history", ""))
report_lines.append("")

report_lines.append("### 2.2 空头研究员论点\n")
report_lines.append("> 强调风险挑战、竞争劣势、负面指标，反驳多头观点\n")
report_lines.append(translated.get("bear_history", ""))
report_lines.append("")

report_lines.append("### 2.3 投资辩论裁判裁决\n")
report_lines.append("> 综合双方论点，做出买入/卖出/持有的投资建议\n")
report_lines.append(translated.get("invest_judge", ""))
report_lines.append("\n---\n")

# ===== 第三部分：交易员 =====
report_lines.append("## 第三部分：交易员交易计划\n")
report_lines.append("> 基于投资辩论结果，制定具体交易计划\n")
report_lines.append(translated.get("trader_plan", ""))
report_lines.append("\n---\n")

# ===== 第四部分：风险辩论 =====
report_lines.append("## 第四部分：风险辩论（激进 vs 保守 vs 中性）\n")
report_lines.append("> 三位风险分析师就交易员的计划进行辩论，最终由风险裁判做出最终决策\n")

report_lines.append("### 4.1 激进风险分析师\n")
report_lines.append("> 主张高风险高回报，强调机会和增长潜力\n")
report_lines.append(translated.get("risky_history", ""))
report_lines.append("")

report_lines.append("### 4.2 保守风险分析师\n")
report_lines.append("> 主张资产保护、降低波动，强调风险和安全性\n")
report_lines.append(translated.get("safe_history", ""))
report_lines.append("")

report_lines.append("### 4.3 中性风险分析师\n")
report_lines.append("> 主张平衡策略，综合考量风险与回报\n")
report_lines.append(translated.get("neutral_history", ""))
report_lines.append("")

report_lines.append("### 4.4 风险管理裁判最终裁决\n")
report_lines.append("> 综合三方观点，做出最终的买入/卖出/持有决策\n")
report_lines.append(translated.get("final_decision", ""))
report_lines.append("\n---\n")

# ===== 总结 =====
report_lines.append("## 总结\n")
report_lines.append(f"**最终交易决策**: **{decision}**\n")
report_lines.append(f"**分析流程**: 市场分析 → 新闻分析 → 基本面分析 → 投资辩论(多头vs空头) → 交易员计划 → 风险辩论(激进vs保守vs中性) → 最终决策\n")

# 写入文件
report_file = output_dir / f"analysis_report_{analysis_date}.md"
with open(report_file, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"\n{'=' * 60}")
print(f"  报告生成完成！")
print(f"{'=' * 60}")
print(f"\n原始数据: {output_dir / f'raw_data_{analysis_date}.json'}")
print(f"中文报告: {report_file}")
print(f"最终决策: {decision}")
