import json
import os


def generate_markdown_report(shared_document_path: str, output_path: str):
    """
    Generates a Markdown report from the shared_document.json file.

    Args:
        shared_document_path (str): Path to the shared_document.json file.
        output_path (str): Path where the Markdown report will be saved.
    """
    try:
        with open(shared_document_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {shared_document_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {shared_document_path}")
        return

    ticker = data.get("ticker", "Unknown")
    date = data.get("current_date", "Unknown")

    markdown_content = f"# Investment Report for {ticker} on {date}\n\n"

    # Order of reports to include
    report_keys = [
        "fundamentals_analyst_report",
        "market_analyst_report",
        "analyst_coordinator_report",
        "bear_researcher_report",
        "bull_researcher_report",
        "research_manager_report",
        "trader_report",
        "aggressive_risk_analyst_report",
        "neutral_risk_analyst_report",
        "conservative_risk_analyst_report",
        "risk_manager_report",
        "investment_manager_report",
    ]

    for key in report_keys:
        if key in data:
            title = key.replace("_", " ").title()
            content = data[key]
            markdown_content += f"## {title}\n\n{content}\n\n---\n\n"

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        f.write(markdown_content)

    print(f"Report generated at {output_path}")


if __name__ == "__main__":
    # Example usage
    generate_markdown_report("data/shared_document.json", "report.md")
