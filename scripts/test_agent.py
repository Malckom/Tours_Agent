"""
Quick smoke-test for the Safi agent — runs three realistic customer scenarios
WITHOUT requiring real API keys (set ANTHROPIC_API_KEY in .env first).

Run: python scripts/test_agent.py
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("❌ Set ANTHROPIC_API_KEY in .env before running tests.")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import SafiAgent


SCENARIOS = [
    {
        "name": "Scenario 1 — First-timer pricing inquiry",
        "messages": [
            "Hi, I'm thinking of doing a safari. What do you offer?",
            "Sounds great — how much would it cost for 2 adults to visit Masai Mara in August with mid-range accommodation?",
        ],
    },
    {
        "name": "Scenario 2 — Nairobi National Park with add-ons",
        "messages": [
            "I have just one morning free in Nairobi. Can I see wildlife?",
            "I'd like to add the Giraffe Centre and the elephant orphanage. I'm travelling alone. How much total?",
        ],
    },
    {
        "name": "Scenario 3 — Budget solo traveller, January",
        "messages": [
            "I'm a solo traveller on a tight budget. I want to see the Masai Mara. Cheapest option in January?",
        ],
    },
]


def run_scenario(scenario: dict, agent: SafiAgent) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {scenario['name']}")
    print("═" * 60)
    for msg in scenario["messages"]:
        print(f"\n  You: {msg}")
        response = agent.chat(msg)
        print(f"\n  Safi: {response}")
    agent.reset()


def main() -> None:
    print("\n🦁  Safi Agent Test Suite")
    print("=" * 60)
    agent = SafiAgent()

    for scenario in SCENARIOS:
        try:
            run_scenario(scenario, agent)
        except Exception as e:
            print(f"\n❌ Scenario failed: {e}")
            raise

    print(f"\n{'=' * 60}")
    print("✅ All scenarios completed.")


if __name__ == "__main__":
    main()
