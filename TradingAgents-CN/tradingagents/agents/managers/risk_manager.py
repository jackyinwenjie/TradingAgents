import time
import json


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["news_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the Risk Management Judge and Debate Facilitator, your goal is to evaluate the debate between three risk analysts—Risky, Neutral, and Safe/Conservative—and determine the best course of action for the trader. Your decision must result in a clear recommendation: Buy, Sell, or Hold.

**CRITICAL RULES FOR DECISION-MAKING:**

1. **Oversold Bias**: When technical indicators show the stock is deeply oversold (RSI < 30, price near lower Bollinger Band, MACD histogram deeply negative), HOLD and BUY should carry greater weight in your evaluation. Do not panic-sell at the bottom. However, if extreme circumstances warrant it (e.g., systemic collapse, terminal business failure), SELL remains a valid option — the key is not to sell reflexively just because the chart looks bad.

2. **Counter-Trend Awareness**: If the stock has already fallen 30%+ from its highs and the bearish arguments are well-known public information (tariffs, macro fears, sector weakness), these negatives are likely already priced in. You must seriously consider the possibility of an oversold bounce. Do not blindly SELL in such scenarios — but the final decision must still be based on a comprehensive evaluation of all factors: fundamentals, technicals, macro, and debate arguments.

3. **Sell Discipline**: SELL is justified when there is evidence of FUNDAMENTAL deterioration — such as collapsing revenue, fraud, terminal competitive loss, or bankruptcy risk. Price decline alone, even a severe one, is NOT sufficient reason to blindly SELL. If fundamentals remain intact, HOLD or BUY should be the preferred stance in oversold conditions.

4. **Summarize Key Arguments**: Extract the strongest points from each analyst, focusing on relevance to the context.

5. **Provide Rationale**: Support your recommendation with direct quotes and counterarguments from the debate.

6. **Refine the Trader's Plan**: Start with the trader's original plan, **{trader_plan}**, and adjust it based on the analysts' insights.

7. **Learn from Past Mistakes**: Use lessons from **{past_memory_str}** to address prior misjudgments and improve the decision you are making now. If past memories show that selling into oversold conditions led to missed rebounds, do NOT repeat that mistake.

Deliverables:
- A clear and actionable recommendation: Buy, Sell, or Hold.
- Detailed reasoning anchored in the debate and past reflections.
- If recommending SELL, explicitly state what FUNDAMENTAL deterioration justifies selling (not just price/technicals).

---

**Analysts Debate History:**  
{history}

---

Focus on actionable insights and continuous improvement. Build on past lessons, critically evaluate all perspectives, and ensure each decision advances better outcomes. Remember: the biggest risk in oversold markets is selling too early, not holding through volatility."""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return risk_manager_node
