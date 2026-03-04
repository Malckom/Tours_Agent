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

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

from agent.config import (
    GROQ_MODEL,
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
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY environment variable is not set. "
                "Create a .env file (see .env.example) or set it in your shell."
            )
        self.client = Groq(api_key=api_key)
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
        # Groq uses system as first message in the messages list
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
        ] + list(self.conversation_history)

        while True:
            response = self.client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                messages=messages,
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            logger.debug("Finish reason: %s", finish_reason)

            # If the model wants to call tools
            if finish_reason == "tool_calls":
                assistant_msg = choice.message
                # Append the assistant's tool-call message
                messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_msg.tool_calls
                    ],
                })

                # Execute each tool call and append results
                for tc in assistant_msg.tool_calls:
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.warning("Failed to parse tool arguments: %s", e)
                        tool_input = {}
                    logger.info("Tool call: %s(%s)", tc.function.name, json.dumps(tool_input, default=str))
                    try:
                        result = execute_tool(tc.function.name, tool_input)
                    except Exception as e:
                        result = {"error": str(e)}
                    logger.info("Tool result: %s", json.dumps(result, default=str)[:300])
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    })
                continue

            # Model produced a final text response
            return choice.message.content or ""


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
