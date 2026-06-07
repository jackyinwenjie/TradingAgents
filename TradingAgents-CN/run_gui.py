"""
TradingAgents 一键分析报告生成器
用法: python run_gui.py
功能: 输入股票代码和分析日期 → 选择分析师+分析深度 → 运行辩论 → 输出中文结构化报告
"""

import sys
import io
import json
import datetime
from pathlib import Path

# Fix Windows GBK encoding issue
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from cli.models import AnalystType
from dotenv import load_dotenv
load_dotenv()


# ==================== 分析师选项映射 ====================
ANALYST_OPTIONS = [
    ("1", "市场技术分析师", AnalystType.MARKET),
    ("2", "全球新闻/宏观分析师", AnalystType.NEWS),
    ("3", "基本面分析师", AnalystType.FUNDAMENTALS),
]

# ==================== 分析深度选项映射（含预估耗时） ====================
DEPTH_OPTIONS = [
    ("1", "快速模式 - 快速研究，较少辩论和策略讨论轮次（约 5-8 分钟）", 1),
    ("2", "标准模式 - 中等深度，适度辩论和策略讨论轮次（约 10-20 分钟）", 3),
    ("3", "深度模式 - 全面研究，深入辩论和策略讨论（约 25-40 分钟）", 5),
]


def get_user_inputs():
    """交互式获取用户输入（使用标准 input，兼容所有终端）"""

    # Step 1: 股票代码
    ticker = input("请输入要分析的股票代码 (如 000063): ").strip()
    if not ticker:
        print("未输入股票代码，退出。")
        exit(1)
    ticker = ticker.upper()

    # Step 2: 分析日期
    import re

    def validate_date(date_str: str) -> bool:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return False
        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    analysis_date = input("请输入分析日期 (YYYY-MM-DD): ").strip()
    if not validate_date(analysis_date):
        print("日期格式无效，使用今天日期。")
        analysis_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Step 3: 选择分析师（可多选，逗号分隔）
    print("\n--- 选择分析师团队（可多选） ---")
    for num, name, _ in ANALYST_OPTIONS:
        print(f"  [{num}] {name}")
    print("  [a] 全选")
    print("  输入编号，多个用逗号分隔（如 1,2,3）或输入 a 全选:")

    analyst_input = input("> ").strip().lower()
    if analyst_input == "a":
        selected_analysts = [a[2] for a in ANALYST_OPTIONS]
    else:
        chosen_nums = [x.strip() for x in analyst_input.split(",") if x.strip()]
        selected_analysts = []
        for num, _, atype in ANALYST_OPTIONS:
            if num in chosen_nums:
                selected_analysts.append(atype)
        if not selected_analysts:
            print("未选择任何分析师，默认全选。")
            selected_analysts = [a[2] for a in ANALYST_OPTIONS]

    # Step 4: 选择分析深度
    print("\n--- 选择分析深度 ---")
    for num, name, _ in DEPTH_OPTIONS:
        print(f"  [{num}] {name}")
    print("  输入编号:")

    depth_input = input("> ").strip()
    selected_depth = None
    for num, _, dval in DEPTH_OPTIONS:
        if depth_input == num:
            selected_depth = dval
            break
    if selected_depth is None:
        print("未选择分析深度，默认使用标准模式。")
        selected_depth = 3

    return ticker, analysis_date, selected_analysts, selected_depth


# ==================== 获取用户输入 ====================
ticker, analysis_date, analysts, research_depth = get_user_inputs()

# ==================== 配置 ====================
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["backend_url"] = "https://api.deepseek.com/v1"
config["deep_think_llm"] = "deepseek-chat"
config["quick_think_llm"] = "deepseek-chat"
config["max_debate_rounds"] = research_depth
config["max_risk_discuss_rounds"] = research_depth
config["online_tools"] = True

analyst_values = [a.value if hasattr(a, 'value') else a for a in analysts]

# 中文名称映射
analyst_name_map = {
    AnalystType.MARKET: "市场技术分析",
    AnalystType.NEWS: "全球新闻/宏观分析",
    AnalystType.FUNDAMENTALS: "基本面分析",
}
selected_names = [analyst_name_map.get(a, str(a)) for a in analysts]

# 深度名称映射
depth_name_map = {1: "快速模式", 3: "标准模式", 5: "深度模式"}

# ==================== 运行分析 ====================
print(f"\n{'=' * 60}")
print(f"  TradingAgents 分析报告生成器")
print(f"  股票代码: {ticker}")
print(f"  分析日期: {analysis_date}")
print(f"  分析师: {'、'.join(selected_names)}")
print(f"  分析深度: {depth_name_map.get(research_depth, str(research_depth))}")
print(f"{'=' * 60}")
print(f"\n正在运行分析流程...\n")

ta = TradingAgentsGraph(analyst_values, config=config, debug=True)
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

raw_data = {
    "meta": {
        "ticker": ticker,
        "analysis_date": analysis_date,
        "analysts": [str(a) for a in analysts],
        "research_depth": research_depth,
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

# ==================== 总结提炼工具 ====================
from langchain_openai import ChatOpenAI

summarize_llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)


def summarize_section(section_name: str, raw_text: str, context: str = "") -> str:
    """使用 LLM 将原始英文分析内容总结提炼为精炼的中文摘要"""
    if not raw_text or len(raw_text.strip()) == 0:
        return "（无数据）"

    prompt = f"""你是一位专业的金融分析师，请将以下"{section_name}"的原始英文分析内容总结为精炼的中文摘要。

要求：
1. 提炼核心观点和关键数据，不要逐字翻译
2. 保留重要的数字、指标数值、价格区间等定量信息
3. 使用清晰的中文金融术语
4. 结构清晰，分点列出关键结论（3-6个要点）
5. 控制在500字以内
6. 只输出总结内容，不要加"以下是总结"之类的开头

{context}

原始内容：
{raw_text[:8000]}
"""

    try:
        result = summarize_llm.invoke(prompt).content
        return str(result) if result else "（无数据）"
    except Exception as e:
        print(f"  总结失败: {e}，降级为简单截取")
        return f"[总结失败，以下是原始内容前段]\n\n{raw_text[:2000]}..."


print("\n正在生成中文分析报告（总结提炼模式）...")

# ==================== 第一部分：分析师总结 ====================
print("  [1/6] 总结分析师报告...")

analysts_summary = {}
for key, raw in reports.items():
    name_map = {"market": "市场技术分析", "news": "全球新闻/宏观分析", "fundamentals": "基本面分析"}
    if raw and len(raw.strip()) > 0:
        analysts_summary[key] = summarize_section(name_map[key], raw)
        print(f"    分析师总结完成 ({key})")
    else:
        analysts_summary[key] = "（无数据）"

analysts_combined = ""
for key in ["market", "news", "fundamentals"]:
    name_map = {"market": "市场技术分析", "news": "全球新闻/宏观分析", "fundamentals": "基本面分析"}
    if key in analysts_summary:
        analysts_combined += f"\n{name_map[key]}要点：\n{analysts_summary[key]}\n"

part1_summary = summarize_section(
    "分析师综合总结",
    analysts_combined,
    "请综合各位分析师的观点，给出一个整体性的总结摘要。"
)

# ==================== 第二部分：多空辩论总结 ====================
print("  [2/6] 总结多空辩论...")

bull_summary = summarize_section("多头研究员观点", bull_history) if bull_history else "（无数据）"
bear_summary = summarize_section("空头研究员观点", bear_history) if bear_history else "（无数据）"

debate_combined = f"""
多头研究员观点：
{bull_history[:5000] if bull_history else ''}

空头研究员观点：
{bear_history[:5000] if bear_history else ''}
"""

part2_summary = summarize_section(
    "多空辩论关键分歧点与结论",
    debate_combined,
    "请总结多头和空头辩论的核心分歧、各自最强论据，以及辩论的关键结论。"
)

# ==================== 第三部分：研究经理初步判定 ====================
print("  [3/6] 总结研究经理判定...")

part3_summary = summarize_section(
    "研究经理（投资辩论裁判）初步判定",
    invest_judge,
    "请提炼研究经理的核心判断、推荐方向和主要理由。"
) if invest_judge else "（无数据）"

# ==================== 第四部分：交易员初步交易计划 ====================
print("  [4/6] 总结交易员计划...")

part4_summary = summarize_section(
    "交易员初步交易计划",
    trader_plan,
    "请提炼交易计划的核心操作建议、关键价位和执行策略。"
) if trader_plan else "（无数据）"

# ==================== 第五部分：风控三方辩论总结 ====================
print("  [5/6] 总结风控三方辩论...")

risky_summary = summarize_section("激进风控观点", risky_history) if risky_history else "（无数据）"
safe_summary = summarize_section("保守风控观点", safe_history) if safe_history else "（无数据）"
neutral_summary = summarize_section("中性风控观点", neutral_history) if neutral_history else "（无数据）"

risk_combined = f"""
激进风控观点：
{risky_history[:4000] if risky_history else ''}

保守风控观点：
{safe_history[:4000] if safe_history else ''}

中性风控观点：
{neutral_history[:4000] if neutral_history else ''}
"""

part5_summary = summarize_section(
    "风控三方辩论核心分歧",
    risk_combined,
    "请总结激进、保守、中性三方风控分析师的核心观点分歧、各自最有力的论据，以及辩论中体现的关键权衡。"
)

# ==================== 第六部分：风控裁判最终决定 ====================
print("  [6/6] 总结最终决定...")

part6_summary = summarize_section(
    "风险管理裁判最终决定",
    final_decision,
    "请提炼最终决策、核心理由、执行建议和风险提示。"
) if final_decision else "（无数据）"

# ==================== 生成结构化报告 ====================
report_lines = []
report_lines.append("# 📊 TradingAgents 股票分析报告\n")
report_lines.append(f"| 项目 | 内容 |")
report_lines.append(f"|------|------|")
report_lines.append(f"| **股票代码** | {ticker} |")
report_lines.append(f"| **分析日期** | {analysis_date} |")
report_lines.append(f"| **分析师** | {'、'.join(selected_names)} |")
report_lines.append(f"| **分析深度** | {depth_name_map.get(research_depth, str(research_depth))} |")
report_lines.append(f"| **生成时间** | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |")
report_lines.append(f"| **最终决策** | **{decision}** |")
report_lines.append("")
report_lines.append("> 分析流程：分析师研究 → 多空辩论 → 研究经理判定 → 交易员计划 → 风控辩论 → 最终决策")
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 一、分析师研究总结\n")
report_lines.append(part1_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 二、多空研究员辩论总结\n")
report_lines.append("### 多头研究员核心观点\n")
report_lines.append(bull_summary)
report_lines.append("")
report_lines.append("### 空头研究员核心观点\n")
report_lines.append(bear_summary)
report_lines.append("")
report_lines.append("### 辩论关键分歧点与结论\n")
report_lines.append(part2_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 三、研究经理初步判定结论\n")
report_lines.append(part3_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 四、交易员初步交易计划\n")
report_lines.append(part4_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 五、风控三方辩论观点总结\n")
report_lines.append("### 激进风控观点\n")
report_lines.append(risky_summary)
report_lines.append("")
report_lines.append("### 保守风控观点\n")
report_lines.append(safe_summary)
report_lines.append("")
report_lines.append("### 中性风控观点\n")
report_lines.append(neutral_summary)
report_lines.append("")
report_lines.append("### 三方辩论核心分歧\n")
report_lines.append(part5_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 六、风险管理裁判最终决定\n")
report_lines.append(part6_summary)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 📌 决策总览\n")
report_lines.append(f"> **最终交易决策**: **{decision}**\n")
report_lines.append("")
report_lines.append("| 阶段 | 角色 | 倾向 |")
report_lines.append("|------|------|------|")
report_lines.append(f"| 投资辩论裁判 | 研究经理 | 见第三部分 |")
report_lines.append(f"| 交易计划 | 交易员 | 见第四部分 |")
report_lines.append(f"| 最终裁决 | 风险管理裁判 | **{decision}** |")
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("*本报告由 TradingAgents 多智能体分析系统自动生成，仅供参考，不构成投资建议。*")

# 写入文件
report_file = output_dir / f"analysis_report_{analysis_date}.md"
with open(report_file, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"\n{'=' * 60}")
print(f"  ✅ 分析已完成！")
print(f"{'=' * 60}")
print(f"\n📄 分析报告: {report_file.resolve()}")
print(f"📦 原始数据: {(output_dir / f'raw_data_{analysis_date}.json').resolve()}")
print(f"🎯 最终决策: {decision}")
print(f"\n{'=' * 60}")
print(f"  以上报告为 AI 自动生成，仅供参考，不构成投资建议。")
print(f"{'=' * 60}")
