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

# Load environment variables from .env.agent.secret if available
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / ".env.agent.secret"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, use system environment variables

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
    id: str = ""


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

        # Load backend API configuration
        self.api_url = os.environ.get("LMS_API_URL", "")
        self.api_key = os.environ.get("LMS_API_KEY", "")

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

    def query_api(self, method: str, path: str, body: Optional[str] = None) -> str:
        """
        Query the deployed backend API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API endpoint path (e.g., '/items/')
            body: Optional JSON request body for POST/PUT

        Returns:
            JSON string with status_code and body, or error message
        """
        import httpx

        url = f"{self.api_url.rstrip('/')}{path}"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=30.0) as client:
                if method.upper() == "GET":
                    resp = client.get(url, headers=headers)
                elif method.upper() == "POST":
                    resp = client.post(url, headers=headers, content=body or "{}")
                elif method.upper() == "PUT":
                    resp = client.put(url, headers=headers, content=body or "{}")
                elif method.upper() == "DELETE":
                    resp = client.delete(url, headers=headers)
                else:
                    return f"Error: Unsupported method: {method}"

                return json.dumps({
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp.text,
                }, indent=2)

        except httpx.ConnectError as e:
            return f"Error: Could not connect to API at {url} - {e}"
        except Exception as e:
            return f"Error querying API: {e}"

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
            },
            {
                "type": "function",
                "function": {
                    "name": "query_api",
                    "description": "Query the deployed backend API. Use this to get real-time data from the system.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "method": {
                                "type": "string",
                                "description": "HTTP method (GET, POST, PUT, DELETE)",
                                "enum": ["GET", "POST", "PUT", "DELETE"]
                            },
                            "path": {
                                "type": "string",
                                "description": "API endpoint path (e.g., '/items/', '/api/items/')"
                            },
                            "body": {
                                "type": "string",
                                "description": "Optional JSON request body for POST/PUT requests"
                            }
                        },
                        "required": ["method", "path"]
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
        elif name == "query_api":
            return self.query_api(
                arguments.get("method", "GET"),
                arguments.get("path", ""),
                arguments.get("body"),
            )
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

        try:
            resp = self.client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            # Log error details for debugging
            error_body = e.response.text[:500] if e.response else "No response"
            print(f"LLM API error: {e.response.status_code} - {error_body}", file=sys.stderr)
            raise


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
                "You are a documentation and system assistant for a software engineering project. "
                "You have access to:\n"
                "1. Project files via read_file and list_files\n"
                "2. The deployed backend API via query_api\n\n"
                "When answering questions:\n"
                "- For documentation questions: use list_files to explore, then read_file to find answers\n"
                "- For system/data questions: use query_api to get real-time data from the backend\n"
                "- For framework/port/configuration questions: use query_api or read configuration files\n"
                "- Always cite sources when possible (file path with section anchor, or API endpoint)\n"
                "- If you don't find the answer, say so honestly"
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
                    id=tc.get("id", f"call_{len(tool_calls)}"),
                ))

        return tool_calls

    def _get_answer(self, response: dict) -> str:
        """Extract text answer from LLM response."""
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        return message.get("content", "")

    def _extract_source(self, answer: str, tool_calls: list[ToolCall]) -> str:
        """
        Extract source reference from the answer or tool calls.

        Looks for patterns like 'wiki/file.md#section' or API endpoints.
        If not found, returns empty string.
        """
        import re

        # Look for markdown-style file references
        match = re.search(r'(\w+/[\w\-]+\.md(?:#[\w\-]+)?)', answer)
        if match:
            return match.group(1)

        # Look for API endpoints in tool calls
        for tc in tool_calls:
            if tc.name == "query_api":
                path = tc.arguments.get("path", "")
                if path:
                    return path

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

                    # Add tool result to messages with matching tool_call_id
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Continue loop - LLM will process tool results
                continue
            else:
                # No tool calls - LLM provided final answer
                answer = self._get_answer(response)

                # Add assistant message to history
                self.messages.append({"role": "assistant", "content": answer})

                # Extract source from answer or tool calls
                source = self._extract_source(answer, self.tool_calls_history)

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
