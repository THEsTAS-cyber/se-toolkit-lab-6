#!/usr/bin/env python3
"""CLI system agent with documentation and API query support."""

import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_ROOTS = ["wiki", "docs", "contributing", "backend", "lab"]
ALLOWED_API_ENDPOINTS = ["/items", "/tasks", "/learners", "/interactions", "/analytics", "/pipeline"]

SYSTEM_PROMPT = """You are a documentation and system assistant for a Learning Management Service.

You have access to these tools:
- read_file: Read documentation files (wiki/, docs/, contributing/, backend/)
- list_files: List files in a directory
- query_api: Query the backend LMS API for live system data

CRITICAL RULES:
1. NEVER answer from your own knowledge - ALWAYS use tools FIRST
2. For "List all" questions: list_files, then read_file for EACH file, THEN answer
3. For bug diagnosis: query_api to see error, read_file to find bug, identify exact error type
4. For code questions: use read_file on backend/app/*.py
5. For system data: use query_api
6. Cite your sources - include file paths or API endpoints
7. When API returns [], report "0 items"

Project structure:
- backend/app/main.py - FastAPI application
- backend/app/routers/items.py - Learning items and tasks
- backend/app/routers/learners.py - Learner management
- backend/app/routers/interactions.py - Interaction logs
- backend/app/routers/analytics.py - Analytics
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

IMPORTANT:
- Provide a complete final answer in your last message
- For bug questions: identify the EXACT error type (TypeError, ZeroDivisionError) and the line
- For HTTP/auth errors: use query_api with use_auth=false"""


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.agent.secret", env_file_encoding="utf-8", extra="ignore")
    llm_api_key: str
    llm_api_base: str
    llm_model: str
    lms_api_base: str = "http://127.0.0.1:42002"
    lms_api_key: str = "my-secret-api-key"


def load_settings() -> AgentSettings:
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)
    return AgentSettings(_env_file=str(env_file))


def validate_path(relative_path: str) -> Path:
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")
    base = Path(__file__).parent
    target = (base / relative_path).resolve()
    for allowed_root in ALLOWED_ROOTS:
        allowed_path = (base / allowed_root).resolve()
        if str(target).startswith(str(allowed_path)) or str(target) == str(allowed_path):
            return target
    if target.parent == base and target.is_file():
        return target
    raise ValueError(f"Access denied: {relative_path}")


def validate_api_endpoint(endpoint: str) -> bool:
    endpoint = endpoint.strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return any(endpoint.startswith(allowed) for allowed in ALLOWED_API_ENDPOINTS)


def read_file(path: str) -> str:
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


def query_api(endpoint: str, method: str = "GET", params: dict[str, Any] | None = None, use_auth: bool = True) -> dict[str, Any]:
    settings = load_settings()
    if not validate_api_endpoint(endpoint):
        return {"error": f"Invalid endpoint: {endpoint}", "allowed": ALLOWED_API_ENDPOINTS}
    if not endpoint.endswith("/"):
        endpoint = endpoint + "/"
    url = f"{settings.lms_api_base}{endpoint}"
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


TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Relative path"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "List files in a directory", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "query_api", "description": "Query the backend API", "parameters": {"type": "object", "properties": {"endpoint": {"type": "string"}, "method": {"type": "string", "enum": ["GET", "POST"]}, "params": {"type": "object"}, "use_auth": {"type": "boolean"}}, "required": ["endpoint"]}}},
]


def execute_tool_call(name: str, arguments: dict[str, Any], settings: AgentSettings) -> Any:
    print(f"Executing tool: {name}({arguments})", file=sys.stderr)
    if name == "read_file":
        return read_file(arguments.get("path", ""))
    elif name == "list_files":
        return list_files(arguments.get("path", ""))
    elif name == "query_api":
        return query_api(arguments.get("endpoint", ""), arguments.get("method", "GET"), arguments.get("params"), arguments.get("use_auth", True))
    return f"Error: Unknown tool: {name}"


def call_llm_with_tools(question: str, settings: AgentSettings, max_iterations: int = 30) -> tuple[str, list[str], list[dict[str, Any]]]:
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    all_tool_calls: list[dict[str, Any]] = []
    sources: set[str] = set()
    pending_files: list[str] = []

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} ---", file=sys.stderr)

        # Auto-read pending files
        if pending_files:
            next_file = pending_files.pop(0)
            tool_calls = [{"id": f"auto_{iteration}", "function": {"name": "read_file", "arguments": json.dumps({"path": next_file})}}]
        else:
            payload = {"model": settings.llm_model, "messages": messages, "tools": TOOLS}
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
            except httpx.HTTPStatusError as e:
                print(f"HTTP error: {e}", file=sys.stderr)
                sys.exit(1)
            except httpx.RequestError as e:
                print(f"Request error: {e}", file=sys.stderr)
                sys.exit(1)

            choice = data["choices"][0]
            message = choice["message"]
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                answer = message.get("content", "")
                print(f"Final answer received", file=sys.stderr)
                return answer, list(sources), all_tool_calls

            print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)
            messages.append(message)

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "unknown")
            arguments = json.loads(function.get("arguments", "{}"))

            tool_call_record = {"name": name, "arguments": arguments}
            all_tool_calls.append(tool_call_record)
            result = execute_tool_call(name, arguments, settings)

            if name == "read_file" and not str(result).startswith("Error"):
                sources.add(arguments.get("path", ""))
            elif name == "list_files" and not str(result).startswith("Error"):
                dir_path = arguments.get("path", "")
                sources.add(dir_path)
                for file_name in result:
                    if file_name.endswith("/"):
                        subdir = f"{dir_path}{file_name}"
                        if subdir in ["backend/app/", "backend/caddy/", "caddy/"]:
                            for key_file in ["main.py", "settings.py", "Dockerfile", "Caddyfile"]:
                                full_path = f"{subdir}{key_file}"
                                if full_path not in pending_files:
                                    pending_files.append(full_path)
                    elif file_name.endswith(".py") and file_name != "__init__.py":
                        full_path = f"{dir_path}{file_name}"
                        if full_path not in pending_files:
                            pending_files.append(full_path)
                    elif file_name in ["Dockerfile", "docker-compose.yml", "Caddyfile"]:
                        full_path = f"{dir_path}{file_name}"
                        if full_path not in pending_files:
                            pending_files.append(full_path)
            elif name == "query_api" and not (isinstance(result, dict) and "error" in result):
                sources.add(arguments.get("endpoint", ""))

            messages.append({"role": "tool", "tool_call_id": tool_call.get("id", ""), "content": json.dumps(result) if isinstance(result, dict) else str(result)})

    print("Max iterations reached", file=sys.stderr)
    payload = {"model": settings.llm_model, "messages": messages}
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"], list(sources), all_tool_calls
    except Exception as e:
        return "Error: Failed to get final answer", list(sources), all_tool_calls


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)
    settings = load_settings()
    print(f"Loaded settings from .env.agent.secret", file=sys.stderr)
    print(f"Model: {settings.llm_model}", file=sys.stderr)
    print(f"LMS API: {settings.lms_api_base}", file=sys.stderr)
    answer, sources, tool_calls = call_llm_with_tools(sys.argv[1], settings)
    result = {"answer": answer, "source": list(sources), "tool_calls": tool_calls}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
