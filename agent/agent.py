"""
Main agent loop for Kenya Group Joining Safaris AI Agent (Safi).

Usage:
    from agent.agent import SafiAgent
    agent = SafiAgent()
    response = agent.chat("Hello, I want to go on a safari!")
    print(response)

Or run interactively:
    python -m agent.agent
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

from agent.config import (
    CLAUDE_MODEL,
    MAX_TOKENS,
    SYSTEM_PROMPT_PATH,
    TEMPERATURE,
    get_season_context,
)
from agent.tool_schemas import TOOL_SCHEMAS
from agent.tools import execute_tool

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


def _load_system_prompt() -> str:
    """Load and render the system prompt, injecting current date and season context."""
    with open(SYSTEM_PROMPT_PATH, "r") as f:
        template = f.read()

    return template.replace(
        "{{CURRENT_DATE}}", date.today().strftime("%B %d, %Y")
    ).replace(
        "{{SEASON_CONTEXT}}", get_season_context()
    )


class SafiAgent:
    """
    Conversational AI agent for Kenya Group Joining Safaris.

    Maintains conversation history per session. Instantiate one SafiAgent
    per user session (e.g. per websocket connection or chat thread).
    """

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Create a .env file (see .env.example) or set it in your shell."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt: str = _load_system_prompt()
        self.conversation_history: list[dict[str, Any]] = []

    # ─────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────

    def chat(self, user_message: str) -> str:
        """
        Send a user message and return Safi's response text.
        Handles multi-turn tool use internally.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        response_text = self._run_turn()
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text,
        })
        return response_text

    def reset(self) -> None:
        """Clear conversation history to start a new session."""
        self.conversation_history = []

    # ─────────────────────────────────────────────
    # Internal: agentic turn loop
    # ─────────────────────────────────────────────

    def _run_turn(self) -> str:
        """
        Run one conversational turn, handling tool calls until a final
        text response is produced.
        """
        # Build a mutable copy of history that we extend with tool call/result pairs
        # within this turn only (tool use messages are ephemeral within the turn,
        # not stored in self.conversation_history)
        messages = list(self.conversation_history)

        while True:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=self.system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            logger.debug("Stop reason: %s", response.stop_reason)

            # If the model wants to call tools
            if response.stop_reason == "tool_use":
                # Add the assistant's tool-call message to the working messages
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                })

                # Execute each tool call and collect results
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info("Tool call: %s(%s)", block.name, json.dumps(block.input, default=str))
                        result = execute_tool(block.name, block.input)
                        logger.info("Tool result: %s", json.dumps(result, default=str)[:300])
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })

                # Add tool results as a user message and loop back
                messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                continue

            # Model produced a final text response
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_blocks)


# ─────────────────────────────────────────────────────────────
# Interactive CLI (run with: python -m agent.agent)
# ─────────────────────────────────────────────────────────────

def _run_cli() -> None:
    print("\n" + "═" * 60)
    print("  🦁  Safi — Kenya Group Joining Safaris AI Consultant")
    print("  Type 'quit' or 'exit' to end the session.")
    print("  Type 'reset' to start a new conversation.")
    print("═" * 60 + "\n")

    agent = SafiAgent()
    print("Safi: Karibu sana! Welcome to Kenya Group Joining Safaris. "
          "I'm Safi, your safari consultant. How can I help you plan "
          "an amazing Kenya safari today?\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSafi: Kwaheri! Safe travels. 🦁")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Safi: Kwaheri! Safe travels. 🦁")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("Safi: Conversation reset. Karibu tena! How can I help you?\n")
            continue

        print()
        response = agent.chat(user_input)
        print(f"Safi: {response}\n")


if __name__ == "__main__":
    _run_cli()
