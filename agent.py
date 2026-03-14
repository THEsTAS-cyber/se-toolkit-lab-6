#!/usr/bin/env python3
"""
Simple LLM Agent for Lab 6.

This agent calls an LLM API and returns a structured response with:
- answer: The LLM's text response
- tool_calls: List of tool invocations (if any)
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import httpx


@dataclass
class ToolCall:
    """Represents a tool/function call from the LLM."""
    name: str
    arguments: dict


@dataclass
class AgentResponse:
    """Response from the agent."""
    answer: str
    tool_calls: list[ToolCall]


class LLMClient:
    """Client for calling LLM APIs with OpenAI-compatible format."""

    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=60.0)

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> dict:
        """
        Send a chat completion request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions for function calling

        Returns:
            dict: The response from the LLM
        """
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = self.client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


class Agent:
    """Simple agent that calls LLM and parses tool calls."""

    def __init__(self):
        self.api_base = os.environ.get("LLM_API_BASE", "http://localhost:8080/v1")
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "qwen3-coder-plus")
        self.client = LLMClient(self.api_base, self.api_key, self.model)
        self.messages: list[dict] = []

    def _parse_tool_calls(self, response: dict) -> list[ToolCall]:
        """Extract tool calls from LLM response."""
        tool_calls = []
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        # OpenAI format: tool_calls array
        for tc in message.get("tool_calls", []):
            if tc.get("type") == "function":
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    name=func.get("name", "unknown"),
                    arguments=args,
                ))

        return tool_calls

    def _get_answer(self, response: dict) -> str:
        """Extract text answer from LLM response."""
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        return message.get("content", "")

    def run(self, user_input: str) -> AgentResponse:
        """
        Run the agent on user input.

        Args:
            user_input: The user's question or command

        Returns:
            AgentResponse with answer and tool_calls
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_input})

        # Call LLM
        system_prompt = {
            "role": "system",
            "content": (
                "You are a helpful assistant. "
                "Answer questions concisely. "
                "If you need to use tools, the framework will call them for you."
            ),
        }
        messages_with_system = [system_prompt] + self.messages

        response = self.client.chat(messages_with_system)

        # Parse response
        answer = self._get_answer(response)
        tool_calls = self._parse_tool_calls(response)

        # Add assistant message to history
        assistant_message = {"role": "assistant", "content": answer}
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]
        self.messages.append(assistant_message)

        return AgentResponse(answer=answer, tool_calls=tool_calls)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python agent.py <user_input>", file=sys.stderr)
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])

    agent = Agent()
    response = agent.run(user_input)

    # Output JSON
    output = {
        "answer": response.answer,
        "tool_calls": [asdict(tc) for tc in response.tool_calls],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
