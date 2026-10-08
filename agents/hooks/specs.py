"""Reviewable input/output and lifecycle contracts for every agent."""

from pathlib import Path

from agents.hooks.contracts import (
    AgentSpec,
    DebatePolicy,
    MemoryPolicy,
    ParticipantSpec,
    StateField,
)

AGENTS_ROOT = Path(__file__).resolve().parents[1]
IDENTITY = (
    StateField("ticker", required=True),
    StateField("current_date", required=True),
)
IDENTITY_BINDINGS = (("ticker", "ticker"), ("date", "current_date"))
ANALYST_REPORTS = (
    StateField("fundamentals_analyst_report"),
    StateField("market_analyst_report"),
    StateField("news_analyst_report"),
)
SITUATION = (
    ("Date", "current_date"),
    ("Ticker", "ticker"),
    ("Market Research Report", "market_analyst_report"),
    ("Latest World Affairs News", "news_analyst_report"),
    ("Company Fundamentals Report", "fundamentals_analyst_report"),
)


def bindings(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((name, name) for name in names)


AGENT_SPECS = {
    "fundamentals_analyst": AgentSpec(
        agent_id="fundamentals_analyst",
        prompt_path=AGENTS_ROOT / "analysts/fundamentals_analyst/prompt.txt",
        inputs=IDENTITY,
        prompt_bindings=IDENTITY_BINDINGS,
        output_keys=("fundamentals_analyst_report",),
    ),
    "market_analyst": AgentSpec(
        agent_id="market_analyst",
        prompt_path=AGENTS_ROOT / "analysts/market_analyst/prompt.txt",
        inputs=IDENTITY,
        prompt_bindings=IDENTITY_BINDINGS,
        output_keys=("market_analyst_report",),
    ),
    "news_analyst": AgentSpec(
        agent_id="news_analyst",
        prompt_path=AGENTS_ROOT / "analysts/news_analyst/prompt.txt",
        inputs=IDENTITY,
        prompt_bindings=IDENTITY_BINDINGS,
        output_keys=("news_analyst_report",),
    ),
    "analyst_coordinator": AgentSpec(
        agent_id="analyst_coordinator",
        prompt_path=AGENTS_ROOT / "analysts/analysts_coordinator/prompt.txt",
        inputs=IDENTITY,
        prompt_bindings=IDENTITY_BINDINGS,
        output_keys=("analyst_coordinator_report",),
    ),
    "investment_manager": AgentSpec(
        agent_id="investment_manager",
        prompt_path=AGENTS_ROOT / "investment_manager/prompt.txt",
        inputs=IDENTITY,
        prompt_bindings=IDENTITY_BINDINGS,
        output_keys=("investment_manager_report",),
    ),
    "bull_researcher": AgentSpec(
        agent_id="bull_researcher",
        prompt_path=AGENTS_ROOT / "researchers/bull/prompt.txt",
        inputs=IDENTITY
        + ANALYST_REPORTS
        + (
            StateField("bear_researcher_report", default="No report"),
            StateField("research_debate_history", default="No debate history yet."),
        ),
        prompt_bindings=bindings(
            "fundamentals_analyst_report",
            "market_analyst_report",
            "news_analyst_report",
            "bear_researcher_report",
            "past_memories",
            "research_debate_history",
        ),
        output_keys=("bull_researcher_report",),
        memory=MemoryPolicy(SITUATION, "Bull Researcher analysis"),
    ),
    "bear_researcher": AgentSpec(
        agent_id="bear_researcher",
        prompt_path=AGENTS_ROOT / "researchers/bear/prompt.txt",
        inputs=IDENTITY
        + ANALYST_REPORTS
        + (
            StateField("bull_researcher_report", default="No report"),
            StateField("research_debate_history", default="No debate history yet."),
        ),
        prompt_bindings=bindings(
            "fundamentals_analyst_report",
            "market_analyst_report",
            "news_analyst_report",
            "bull_researcher_report",
            "past_memories",
            "research_debate_history",
        ),
        output_keys=("bear_researcher_report",),
        memory=MemoryPolicy(SITUATION, "Bear Researcher analysis"),
    ),
    "research_manager": AgentSpec(
        agent_id="research_manager",
        prompt_path=AGENTS_ROOT / "researchers/manager/prompt.txt",
        inputs=IDENTITY
        + ANALYST_REPORTS
        + (
            StateField("bull_researcher_report", default="No report", refresh=True),
            StateField("bear_researcher_report", default="No report", refresh=True),
            StateField(
                "research_debate_history",
                default="No debate history yet.",
                refresh=True,
            ),
        ),
        prompt_bindings=IDENTITY_BINDINGS
        + bindings(
            "fundamentals_analyst_report",
            "market_analyst_report",
            "news_analyst_report",
            "bull_researcher_report",
            "bear_researcher_report",
            "past_memories",
            "debate_rounds",
            "debate_action",
            "debate_phase",
            "research_debate_history",
        ),
        output_keys=("research_manager_report",),
        memory=MemoryPolicy(
            SITUATION
            + (
                ("Bull Researcher Analysis", "bull_researcher_report"),
                ("Bear Researcher Analysis", "bear_researcher_report"),
            ),
            "Researcher Manager Decision",
        ),
        workflow=DebatePolicy(
            participants=(
                ParticipantSpec("bull_researcher", "bull_researcher_report"),
                ParticipantSpec("bear_researcher", "bear_researcher_report"),
            ),
            history_key="research_debate_history",
            final_action="Make final investment decision based on the analyses provided.",
        ),
    ),
    "trader": AgentSpec(
        agent_id="trader",
        prompt_path=AGENTS_ROOT / "traders/trader/prompt.txt",
        inputs=IDENTITY
        + ANALYST_REPORTS
        + (
            StateField(
                "investment_plan",
                source="research_manager_report",
                default="No investment plan provided",
            ),
        ),
        prompt_bindings=bindings("ticker", "investment_plan", "past_memories"),
        output_keys=("trader_report", "trader_investment_plan"),
        memory=MemoryPolicy(
            SITUATION + (("Investment Plan", "research_manager_report"),),
            "Trader Decision",
            empty_text="No relevant past trading decisions memories found.",
        ),
    ),
    "risk_manager": AgentSpec(
        agent_id="risk_manager",
        prompt_path=AGENTS_ROOT / "risk_mgt/risk_manager/prompt.txt",
        inputs=IDENTITY
        + ANALYST_REPORTS
        + (
            StateField("trader_investment_plan", default="No trader plan available"),
            StateField(
                "risk_debate_history", default="No debate history yet.", refresh=True
            ),
        ),
        prompt_bindings=bindings(
            "trader_investment_plan",
            "risk_debate_history",
            "past_memories",
            "debate_rounds",
            "debate_action",
            "debate_phase",
        ),
        output_keys=("risk_manager_report", "final_trade_decision"),
        memory=MemoryPolicy(SITUATION, "Risk Manager Decision"),
        workflow=DebatePolicy(
            participants=(
                ParticipantSpec(
                    "aggressive_risk_analyst", "aggressive_risk_analyst_report"
                ),
                ParticipantSpec(
                    "conservative_risk_analyst", "conservative_risk_analyst_report"
                ),
                ParticipantSpec("neutral_risk_analyst", "neutral_risk_analyst_report"),
            ),
            history_key="risk_debate_history",
            final_action="Make final risk-adjusted trading decision based on the analyses provided.",
        ),
    ),
}

RISK_INPUTS = IDENTITY + (
    StateField("market_analyst_report", default="No market analyst report available."),
    StateField("social_analyst_report", default="No social analyst report available."),
    StateField("news_analyst_report", default="No news report available."),
    StateField(
        "fundamentals_analyst_report", default="No fundamentals report available."
    ),
    StateField("trader_investment_plan", default="No trader decision available."),
    StateField("risk_debate_history", default="No debate history yet."),
)
RISK_BINDINGS = bindings(
    "market_analyst_report",
    "social_analyst_report",
    "news_analyst_report",
    "fundamentals_analyst_report",
    "trader_investment_plan",
    "risk_debate_history",
)

AGENT_SPECS.update(
    {
        "aggressive_risk_analyst": AgentSpec(
            agent_id="aggressive_risk_analyst",
            prompt_path=AGENTS_ROOT / "risk_mgt/aggressive_debator/prompt.txt",
            inputs=RISK_INPUTS
            + (
                StateField(
                    "conservative_risk_analyst_report",
                    default="No conservative analysis yet.",
                ),
                StateField(
                    "neutral_risk_analyst_report", default="No neutral analysis yet."
                ),
            ),
            prompt_bindings=RISK_BINDINGS
            + bindings(
                "conservative_risk_analyst_report",
                "neutral_risk_analyst_report",
            ),
            output_keys=("aggressive_risk_analyst_report",),
        ),
        "conservative_risk_analyst": AgentSpec(
            agent_id="conservative_risk_analyst",
            prompt_path=AGENTS_ROOT / "risk_mgt/conservative_debator/prompt.txt",
            inputs=RISK_INPUTS
            + (
                StateField(
                    "aggressive_risk_analyst_report",
                    default="No aggressive analysis yet.",
                ),
                StateField(
                    "neutral_risk_analyst_report", default="No neutral analysis yet."
                ),
            ),
            prompt_bindings=RISK_BINDINGS
            + bindings(
                "aggressive_risk_analyst_report",
                "neutral_risk_analyst_report",
            ),
            output_keys=("conservative_risk_analyst_report",),
        ),
        "neutral_risk_analyst": AgentSpec(
            agent_id="neutral_risk_analyst",
            prompt_path=AGENTS_ROOT / "risk_mgt/neutral_debator/prompt.txt",
            inputs=RISK_INPUTS
            + (
                StateField(
                    "aggressive_risk_analyst_report",
                    default="No aggressive analysis yet.",
                ),
                StateField(
                    "conservative_risk_analyst_report",
                    default="No conservative analysis yet.",
                ),
            ),
            prompt_bindings=RISK_BINDINGS
            + bindings(
                "aggressive_risk_analyst_report",
                "conservative_risk_analyst_report",
            ),
            output_keys=("neutral_risk_analyst_report",),
        ),
    }
)
