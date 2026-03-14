#!/usr/bin/env python3
"""CLI system agent with documentation and API query support.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": [...], "tool_calls": [...]}
    All debug output goes to stderr.
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

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

# System prompt for the system agent
SYSTEM_PROMPT = """You are a documentation and system assistant for a Learning Management Service.
You help users find information in project documentation AND query the live system.

You have access to these tools:
- read_file: Read documentation files (wiki/, docs/, contributing/, backend/)
- list_files: List files in a directory
- query_api: Query the backend LMS API for live system data

When answering questions:
1. For documentation questions (how to, concepts, workflows) → use read_file/list_files
2. For system data questions (counts, status, current data) → use query_api
3. For code questions (frameworks, libraries, implementation) → use read_file on backend/app/*.py
4. Cite your sources - include file paths or API endpoints in the 'source' field
5. Be concise and accurate
6. When asked to "list" multiple items, read ALL relevant files before providing your final answer

Project structure:
- backend/app/main.py - Main FastAPI application
- backend/app/settings.py - Configuration
- backend/app/routers/items.py - Learning items and tasks
- backend/app/routers/learners.py - Learner management
- backend/app/routers/interactions.py - Interaction logs
- backend/app/routers/analytics.py - Analytics and statistics
- backend/app/routers/pipeline.py - ETL pipeline
- wiki/ - Project documentation
- docs/ - Additional docs

Available API endpoints:
- /items/ - List all learning items (labs, tasks)
- /tasks/ - List all tasks
- /learners/ - List all learners
- /interactions/ - List interaction logs
- /analytics/summary - Get analytics summary
- /analytics/completion-rate - Get completion rate
- /analytics/top-learners - Get top learners

Always respond in the same language as the user's question.

IMPORTANT: Provide a complete final answer in your last message. Do not say "let me continue" - instead provide the full answer based on all the information you've gathered.

When API returns an empty list [], it means there are zero items - report this clearly (e.g., "There are 0 items in the database"). Do NOT make up numbers - only report what the API actually returns.

For questions about HTTP status codes or authentication errors, use query_api with use_auth=false to make requests without authentication and observe the error response."""


class AgentSettings(BaseSettings):
    """LLM and LMS configuration from .env files."""

    model_config = SettingsConfigDict(
        env_file=".env.agent.secret",
        env_file_encoding="utf-8",
    )

    # LLM configuration
    llm_api_key: str
    llm_api_base: str
    llm_model: str

    # LMS API configuration (optional, with defaults)
    lms_api_base: str = "http://127.0.0.1:42002"
    lms_api_key: str = "my-secret-api-key"


def load_settings() -> AgentSettings:
    """Load settings from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        print(
            "Copy .env.agent.example to .env.agent.secret and configure it",
            file=sys.stderr,
        )
        sys.exit(1)
    return AgentSettings(_env_file=str(env_file))  # type: ignore[call-arg]


def validate_path(relative_path: str) -> Path:
    """Validate and resolve a relative path securely.

    Prevents path traversal attacks by ensuring the path is within allowed directories.
    """
    # Check for path traversal attempts
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")

    # Resolve to absolute path
    base = Path(__file__).parent
    target = (base / relative_path).resolve()

    # Check if path is within allowed roots
    for allowed_root in ALLOWED_ROOTS:
        allowed_path = (base / allowed_root).resolve()
        if str(target).startswith(str(allowed_path)) or str(target) == str(
            allowed_path
        ):
            return target

    # Also allow root-level files like docker-compose.yml, Dockerfile
    if target.parent == base and target.is_file():
        return target

    raise ValueError(
        f"Access denied: {relative_path} is not within allowed directories ({ALLOWED_ROOTS})"
    )


def validate_api_endpoint(endpoint: str) -> bool:
    """Validate that an API endpoint is allowed."""
    # Normalize endpoint
    endpoint = endpoint.strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    # Check against allowed endpoints
    for allowed in ALLOWED_API_ENDPOINTS:
        if endpoint.startswith(allowed):
            return True

    return False


def read_file(path: str) -> str:
    """Read the content of a file."""
    try:
        validated_path = validate_path(path)
        content = validated_path.read_text(encoding="utf-8")
        print(f"read_file: {path} ({len(content)} chars)", file=sys.stderr)
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


def list_files(path: str) -> list[str]:
    """List files in a directory."""
    try:
        validated_path = validate_path(path)
        if not validated_path.is_dir():
            return [f"Error: Not a directory: {path}"]

        items: list[str] = []
        for item in validated_path.iterdir():
            if item.is_file():
                items.append(item.name)
            elif item.is_dir():
                items.append(f"{item.name}/")

        print(f"list_files: {path} ({len(items)} items)", file=sys.stderr)
        return sorted(items)
    except Exception as e:
        return [f"Error listing {path}: {e}"]


def query_api(
    endpoint: str, method: str = "GET", params: dict[str, Any] | None = None, use_auth: bool = True
) -> dict[str, Any]:
    """Query the backend LMS API with authentication.

    Args:
        endpoint: API endpoint path (e.g., '/api/items')
        method: HTTP method (GET or POST)
        params: Optional query parameters or JSON body
        use_auth: Whether to include authentication header (default: true)

    Returns:
        API response as dict, or error dict
    """
    settings = load_settings()

    # Validate endpoint
    if not validate_api_endpoint(endpoint):
        return {
            "error": f"Invalid endpoint: {endpoint}",
            "allowed": ALLOWED_API_ENDPOINTS,
        }

    # Normalize endpoint: ensure trailing slash for FastAPI compatibility
    if not endpoint.endswith("/"):
        endpoint = endpoint + "/"

    # Build URL
    url = f"{settings.lms_api_base}{endpoint}"

    # Build headers - include auth only if requested
    headers = {"Content-Type": "application/json"}
    if use_auth:
        headers["Authorization"] = f"Bearer {settings.lms_api_key}"

    print(f"query_api: {method} {url}", file=sys.stderr)

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, json=params)
            else:
                return {"error": f"Unsupported method: {method}"}

            response.raise_for_status()
            data = response.json()
            print(f"query_api: {endpoint} - success", file=sys.stderr)
            return data

    except httpx.HTTPStatusError as e:
        print(f"query_api: HTTP error {e.response.status_code}", file=sys.stderr)
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
    except httpx.RequestError as e:
        print(f"query_api: Request error: {e}", file=sys.stderr)
        return {"error": "Connection failed", "detail": str(e)}
    except Exception as e:
        print(f"query_api: Unexpected error: {e}", file=sys.stderr)
        return {"error": "Unexpected error", "detail": str(e)}


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
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items', '/tasks')",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method (default: GET)",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional query parameters or JSON body",
                    },
                    "use_auth": {
                        "type": "boolean",
                        "description": "Whether to include authentication header (default: true). Set to false to test authentication errors.",
                    },
                },
                "required": ["endpoint"],
            },
        },
    },
]


def execute_tool_call(
    name: str, arguments: dict[str, Any], settings: AgentSettings
) -> Any:
    """Execute a tool call and return the result."""
    print(f"Executing tool: {name}({arguments})", file=sys.stderr)

    if name == "read_file":
        return read_file(arguments.get("path", ""))
    elif name == "list_files":
        return list_files(arguments.get("path", ""))
    elif name == "query_api":
        # Load settings once and pass through
        endpoint = arguments.get("endpoint", "")
        method = arguments.get("method", "GET")
        params = arguments.get("params")
        use_auth = arguments.get("use_auth", True)
        return query_api(endpoint, method, params, use_auth)
    else:
        return f"Error: Unknown tool: {name}"


def call_llm_with_tools(
    question: str, settings: AgentSettings, max_iterations: int = 15
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Call the LLM API with tool support and agentic loop.

    Returns:
        tuple: (answer, sources, tool_calls)
    """
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    # Initialize conversation with system prompt
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls: list[dict[str, Any]] = []
    sources: set[str] = set()

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} ---", file=sys.stderr)

        # Build request payload
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

        # Parse response
        choice = data["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM provided final answer
            answer = message.get("content", "")
            print(f"Final answer received", file=sys.stderr)
            return answer, list(sources), all_tool_calls

        # Process tool calls
        print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)

        # Add assistant message with tool calls to conversation
        messages.append(message)

        # Execute each tool call
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "unknown")
            arguments_str = function.get("arguments", "{}")

            # Parse arguments
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}

            # Record tool call
            tool_call_record: dict[str, Any] = {
                "name": name,
                "arguments": arguments,
            }
            all_tool_calls.append(tool_call_record)

            # Execute tool
            result = execute_tool_call(name, arguments, settings)  # type: ignore[arg-type]

            # Track sources
            if name == "read_file" and not str(result).startswith("Error"):
                source_path = str(arguments.get("path", ""))  # type: ignore[unknown-argument-type]
                sources.add(source_path)
            elif name == "list_files" and not str(result).startswith("Error"):
                dir_path = str(arguments.get("path", ""))
                sources.add(dir_path)
            elif name == "query_api" and not (
                isinstance(result, dict) and "error" in result
            ):
                endpoint = str(arguments.get("endpoint", ""))  # type: ignore[unknown-argument-type]
                sources.add(endpoint)

            # Add tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": json.dumps(result)
                    if isinstance(result, dict)
                    else str(result),
                }
            )

    # If we reach max iterations, generate final answer from accumulated context
    print("Max iterations reached, generating final answer", file=sys.stderr)

    # Request final answer without tools
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

    # Load configuration
    settings = load_settings()
    print(f"Loaded settings from .env.agent.secret", file=sys.stderr)
    print(f"Model: {settings.llm_model}", file=sys.stderr)
    print(f"LMS API: {settings.lms_api_base}", file=sys.stderr)

    # Call LLM with tools
    answer, sources, tool_calls = call_llm_with_tools(question, settings)

    # Output JSON to stdout
    result: dict[str, Any] = {
        "answer": answer,
        "source": list(sources),
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
