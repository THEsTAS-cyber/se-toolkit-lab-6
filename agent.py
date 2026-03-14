#!/usr/bin/env python3
"""CLI system agent with documentation and API query support.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": [...], "tool_calls": [...]}
    All debug output goes to stderr.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
env_file = Path(__file__).parent / ".env.agent.secret"
if env_file.exists():
    load_dotenv(env_file)

# Allowed directories for file access
ALLOWED_ROOTS = ["wiki", "docs", "contributing", "backend", "lab"]

# Allowed API endpoints for security
ALLOWED_API_ENDPOINTS = [
    "/items",
    "/tasks",
    "/learners",
    "/interactions",
    "/analytics",
    "/pipeline",
]

# System prompt for the agent
SYSTEM_PROMPT = """You are a documentation and system assistant for a Learning Management Service.

You have access to these tools:
- read_file: Read documentation files (wiki/, docs/, contributing/, backend/)
- list_files: List files in a directory
- query_api: Query the backend LMS API for live system data

CRITICAL RULES:
1. NEVER answer from your own knowledge - ALWAYS use tools FIRST
2. For "List all" questions - you MUST read EVERY file before answering
3. For HTTP status code questions: use query_api with auth=false
4. For system data questions (counts, status): use query_api
5. For code questions: use read_file on backend/app/*.py
6. ALWAYS cite sources in your answer
7. When API returns [], report "0 items" - do NOT make up numbers

Project structure:
- backend/app/main.py - FastAPI application
- backend/app/settings.py - Configuration
- backend/app/routers/items.py - Learning items and tasks
- backend/app/routers/learners.py - Learner management
- backend/app/routers/interactions.py - Interaction logs
- backend/app/routers/analytics.py - Analytics and statistics
- backend/app/routers/pipeline.py - ETL pipeline
- wiki/ - Project documentation

Available API endpoints:
- /items/ - List all learning items
- /tasks/ - List all tasks
- /learners/ - List all learners
- /interactions/ - List interaction logs
- /analytics/summary - Get analytics summary
- /analytics/completion-rate - Get completion rate
- /analytics/top-learners - Get top learners

Always respond in the same language as the user's question.

Source format:
- For files: backend/app/routers/analytics.py
- For API: /items/ or /analytics/completion-rate/
"""


class AgentSettings:
    """LLM and LMS configuration from environment variables."""

    def __init__(self):
        self.llm_api_key = os.environ.get("LLM_API_KEY", "")
        self.llm_api_base = os.environ.get("LLM_API_BASE", "http://localhost:8080/v1")
        self.llm_model = os.environ.get("LLM_MODEL", "qwen3-coder-plus")
        self.lms_api_base = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
        self.lms_api_key = os.environ.get("LMS_API_KEY", "my-secret-api-key")


def validate_path(relative_path: str, project_root: Path) -> Path:
    """Validate and resolve a relative path securely."""
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")

    base = project_root
    target = (base / relative_path).resolve()

    for allowed_root in ALLOWED_ROOTS:
        allowed_path = (base / allowed_root).resolve()
        if str(target).startswith(str(allowed_path)) or str(target) == str(allowed_path):
            return target

    if target.parent == base and target.is_file():
        return target

    raise ValueError(
        f"Access denied: {relative_path} is not within allowed directories ({ALLOWED_ROOTS})"
    )


def validate_api_endpoint(endpoint: str) -> bool:
    """Validate that an API endpoint is allowed."""
    endpoint = endpoint.strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    for allowed in ALLOWED_API_ENDPOINTS:
        if endpoint.startswith(allowed):
            return True

    return False


def read_file(path: str, project_root: Path) -> str:
    """Read the content of a file."""
    try:
        validated_path = validate_path(path, project_root)
        content = validated_path.read_text(encoding="utf-8")
        print(f"read_file: {path} ({len(content)} chars)", file=sys.stderr)
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


def list_files(path: str, project_root: Path) -> str:
    """List files in a directory."""
    try:
        validated_path = validate_path(path, project_root)
        if not validated_path.is_dir():
            return f"Error: Not a directory: {path}"

        items: list[str] = []
        for item in validated_path.iterdir():
            if item.is_file():
                items.append(item.name)
            elif item.is_dir():
                items.append(f"{item.name}/")

        print(f"list_files: {path} ({len(items)} items)", file=sys.stderr)
        return "Files:\n" + "\n".join(f"- {f}" for f in sorted(items))
    except Exception as e:
        return f"Error listing {path}: {e}"


def query_api(
    method: str = "GET",
    path: str = "",
    body: str | None = None,
    auth: bool = True,
    settings: AgentSettings | None = None,
) -> str:
    """Query the backend LMS API with authentication."""
    if settings is None:
        settings = AgentSettings()

    if not validate_api_endpoint(path):
        return json.dumps({
            "error": f"Invalid endpoint: {path}",
            "allowed": ALLOWED_API_ENDPOINTS,
        })

    if not path.endswith("/"):
        path = path + "/"

    url = f"{settings.lms_api_base}{path}"

    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {settings.lms_api_key}"

    print(f"query_api: {method} {url} (auth={auth})", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, content=body or "{}")
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, content=body or "{}")
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return json.dumps({"error": f"Unsupported method: {method}"})

            result = {
                "status_code": response.status_code,
                "body": response.text,
            }
            print(f"query_api: {path} - status {response.status_code}", file=sys.stderr)
            return json.dumps(result)

    except httpx.HTTPStatusError as e:
        print(f"query_api: HTTP error {e.response.status_code}", file=sys.stderr)
        return json.dumps({
            "status_code": e.response.status_code,
            "body": e.response.text,
        })
    except httpx.RequestError as e:
        print(f"query_api: Request error: {e}", file=sys.stderr)
        return json.dumps({"error": "Connection failed", "detail": str(e)})
    except Exception as e:
        print(f"query_api: Unexpected error: {e}", file=sys.stderr)
        return json.dumps({"error": "Unexpected error", "detail": str(e)})


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the directory (e.g., 'wiki/')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend LMS API for live system data",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE"],
                        "description": "HTTP method (default: GET)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate/')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT requests",
                    },
                    "auth": {
                        "type": "boolean",
                        "description": "Whether to include authentication header (default: true). Set to false to test authentication errors.",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]


def execute_tool_call(
    name: str, arguments: dict[str, Any], settings: AgentSettings, project_root: Path
) -> Any:
    """Execute a tool call and return the result."""
    print(f"Executing tool: {name}({arguments})", file=sys.stderr)

    if name == "read_file":
        return read_file(arguments.get("path", ""), project_root)
    elif name == "list_files":
        return list_files(arguments.get("path", ""), project_root)
    elif name == "query_api":
        method = arguments.get("method", "GET")
        path = arguments.get("path", "")
        body = arguments.get("body")
        auth = arguments.get("auth", True)
        return query_api(method, path, body, auth, settings)
    else:
        return f"Error: Unknown tool: {name}"


def extract_tool_calls_from_response(response: dict) -> list[dict]:
    """Extract tool calls from LLM response using native function calling."""
    tool_calls = []
    choice = response.get("choices", [{}])[0]
    message = choice.get("message", {})
    
    # Check for native tool_calls
    native_calls = message.get("tool_calls", [])
    for tc in native_calls:
        function = tc.get("function", {})
        tool_calls.append({
            "id": tc.get("id", ""),
            "name": function.get("name", "unknown"),
            "arguments": json.loads(function.get("arguments", "{}")),
        })
    
    return tool_calls


def call_llm_with_tools(
    question: str, settings: AgentSettings, project_root: Path, max_iterations: int = 20
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Call the LLM API with tool support and agentic loop."""
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls: list[dict[str, Any]] = []
    sources: set[str] = set()
    
    # Track files to auto-read after list_files
    pending_files: list[str] = []

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} ---", file=sys.stderr)

        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": TOOLS,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e}", file=sys.stderr)
            print(f"Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except httpx.RequestError as e:
            print(f"Request error: {e}", file=sys.stderr)
            sys.exit(1)

        choice = data["choices"][0]
        message = choice["message"]
        tool_calls = extract_tool_calls_from_response(response)

        # If no tool calls from LLM but we have pending files, auto-read them
        if not tool_calls and pending_files:
            next_file = pending_files.pop(0)
            tool_calls = [{
                "id": f"auto_{iteration}",
                "name": "read_file",
                "arguments": {"path": next_file},
            }]

        if not tool_calls:
            answer = message.get("content") or ""
            print(f"Final answer received", file=sys.stderr)
            return answer, list(sources), all_tool_calls

        print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)
        messages.append(message)

        for tool_call in tool_calls:
            name = tool_call.get("name", "unknown")
            arguments = tool_call.get("arguments", {})

            result = execute_tool_call(name, arguments, settings, project_root)

            # Track sources
            if name == "read_file" and not str(result).startswith("Error"):
                source_path = str(arguments.get("path", ""))
                sources.add(source_path)
            elif name == "list_files" and not str(result).startswith("Error"):
                dir_path = str(arguments.get("path", ""))
                sources.add(dir_path)
                
                # Parse list_files result to find .py files to read
                for line in result.split("\n"):
                    line = line.strip()
                    if line.startswith("- ") and line.endswith(".py"):
                        file_name = line[2:]
                        full_path = f"{dir_path}{file_name}"
                        pending_files.append(full_path)
                
            elif name == "query_api" and not (
                isinstance(result, dict) and "error" in result
            ):
                endpoint = str(arguments.get("path", ""))
                sources.add(endpoint)

            # Store tool call with result for output
            tool_call_record: dict[str, Any] = {
                "tool": name,
                "args": arguments,
                "result": result,
            }
            all_tool_calls.append(tool_call_record)

            # Add tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": result,
                }
            )

    # Max iterations reached - generate final answer
    print("Max iterations reached, generating final answer", file=sys.stderr)

    payload = {
        "model": settings.llm_model,
        "messages": messages,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            return answer, list(sources), all_tool_calls
    except Exception as e:
        print(f"Error getting final answer: {e}", file=sys.stderr)
        return "Error: Failed to get final answer", list(sources), all_tool_calls


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    settings = AgentSettings()
    project_root = Path(__file__).parent.resolve()

    print(f"Loaded settings", file=sys.stderr)
    print(f"Model: {settings.llm_model}", file=sys.stderr)
    print(f"LMS API: {settings.lms_api_base}", file=sys.stderr)

    answer, sources, tool_calls = call_llm_with_tools(question, settings, project_root)

    result: dict[str, Any] = {
        "answer": answer,
        "source": list(sources),
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
