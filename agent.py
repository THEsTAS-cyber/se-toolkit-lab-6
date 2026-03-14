#!/usr/bin/env python3
"""
Documentation Agent for Lab 6.

This agent calls an LLM API with tools (read_file, list_files) to answer
questions about project documentation. It implements an agentic loop that
executes tool calls until the LLM provides a final answer.
"""

import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import httpx


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ToolCall:
    """Represents a tool/function call from the LLM."""
    name: str
    arguments: dict
    result: str = ""


@dataclass
class AgentResponse:
    """Response from the agent."""
    answer: str
    source: str
    tool_calls: list[ToolCall] = field(default_factory=list)


# =============================================================================
# Tools
# =============================================================================


class Tools:
    """Collection of tools available to the agent."""

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()

    def _is_safe_path(self, requested_path: str) -> bool:
        """Check if requested path is within project root (no ../ traversal)."""
        try:
            resolved = (self.project_root / requested_path).resolve()
            return str(resolved).startswith(str(self.project_root))
        except Exception:
            return False

    def read_file(self, path: str) -> str:
        """
        Read a file from the project repository.

        Args:
            path: Relative path from project root

        Returns:
            File contents or error message
        """
        if not self._is_safe_path(path):
            return f"Error: Access denied - path traversal not allowed: {path}"

        file_path = self.project_root / path
        if not file_path.exists():
            return f"Error: File not found: {path}"

        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"

    def list_files(self, path: str) -> str:
        """
        List files and directories at a given path.

        Args:
            path: Relative directory path from project root

        Returns:
            Newline-separated listing or error message
        """
        if not self._is_safe_path(path):
            return f"Error: Access denied - path traversal not allowed: {path}"

        dir_path = self.project_root / path
        if not dir_path.exists():
            return f"Error: Directory not found: {path}"

        if not dir_path.is_dir():
            return f"Error: Not a directory: {path}"

        try:
            entries = sorted(os.listdir(dir_path))
            return "\n".join(entries)
        except Exception as e:
            return f"Error listing directory: {e}"

    def get_tool_definitions(self) -> list[dict]:
        """Return OpenAI-compatible tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the project repository. Use this to read documentation files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files and directories in a directory. Use this to explore the project structure.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative directory path from project root (e.g., 'wiki')"
                            }
                        },
                        "required": ["path"]
                    }
                }
            }
        ]

    def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool by name with given arguments."""
        if name == "read_file":
            return self.read_file(arguments.get("path", ""))
        elif name == "list_files":
            return self.list_files(arguments.get("path", ""))
        else:
            return f"Error: Unknown tool: {name}"


# =============================================================================
# LLM Client
# =============================================================================


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


# =============================================================================
# Agent
# =============================================================================


class Agent:
    """
    Documentation agent with tools and agentic loop.

    The agent:
    1. Sends user question + tool definitions to LLM
    2. If LLM returns tool_calls, executes them and feeds results back
    3. Repeats until LLM provides a text answer
    4. Outputs JSON with answer, source, and tool_calls
    """

    MAX_ITERATIONS = 10

    def __init__(self):
        self.api_base = os.environ.get("LLM_API_BASE", "http://localhost:8080/v1")
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "qwen3-coder-plus")
        self.client = LLMClient(self.api_base, self.api_key, self.model)

        # Project root is the directory containing this script
        self.project_root = Path(__file__).parent.resolve()
        self.tools = Tools(self.project_root)

        self.messages: list[dict] = []
        self.tool_calls_history: list[ToolCall] = []

    def _get_system_prompt(self) -> dict:
        """Return the system prompt for the agent."""
        return {
            "role": "system",
            "content": (
                "You are a documentation assistant for a software engineering project. "
                "You have access to project files via tools.\n\n"
                "When answering questions:\n"
                "1. First explore the wiki structure with list_files('wiki') if needed\n"
                "2. Read relevant files with read_file(path)\n"
                "3. Answer the question concisely and cite the source as 'path#section-anchor'\n"
                "4. If you don't find the answer, say so honestly\n\n"
                "Always include the source field in your final answer with the file path and section anchor."
            ),
        }

    def _parse_tool_calls(self, response: dict) -> list[ToolCall]:
        """Extract tool calls from LLM response."""
        tool_calls = []
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

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

    def _extract_source(self, answer: str) -> str:
        """
        Extract source reference from the answer.

        Looks for patterns like 'wiki/file.md#section' in the answer.
        If not found, returns empty string.
        """
        import re
        # Look for markdown-style references
        match = re.search(r'(\w+/[\w\-]+\.md(?:#[\w\-]+)?)', answer)
        if match:
            return match.group(1)
        return ""

    def run(self, user_input: str) -> AgentResponse:
        """
        Run the agentic loop on user input.

        Args:
            user_input: The user's question

        Returns:
            AgentResponse with answer, source, and tool_calls
        """
        # Initialize messages with system prompt
        self.messages = [self._get_system_prompt()]
        self.messages.append({"role": "user", "content": user_input})
        self.tool_calls_history = []

        for iteration in range(self.MAX_ITERATIONS):
            # Call LLM with tool definitions
            tools = self.tools.get_tool_definitions()
            response = self.client.chat(self.messages, tools=tools)

            # Parse tool calls
            tool_calls = self._parse_tool_calls(response)

            if tool_calls:
                # Execute each tool
                for tc in tool_calls:
                    result = self.tools.execute(tc.name, tc.arguments)
                    tc.result = result
                    self.tool_calls_history.append(tc)

                    # Add tool result to messages
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": f"call_{len(self.tool_calls_history)}",
                        "content": result,
                    })

                # Continue loop - LLM will process tool results
                continue
            else:
                # No tool calls - LLM provided final answer
                answer = self._get_answer(response)

                # Add assistant message to history
                self.messages.append({"role": "assistant", "content": answer})

                # Extract source
                source = self._extract_source(answer)

                return AgentResponse(
                    answer=answer,
                    source=source,
                    tool_calls=self.tool_calls_history,
                )

        # Max iterations reached
        return AgentResponse(
            answer="Reached maximum number of tool calls (10). Here's what I found so far.",
            source="",
            tool_calls=self.tool_calls_history,
        )


# =============================================================================
# CLI
# =============================================================================


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
        "source": response.source,
        "tool_calls": [
            {
                "tool": tc.name,
                "args": tc.arguments,
                "result": tc.result,
            }
            for tc in response.tool_calls
        ],
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
