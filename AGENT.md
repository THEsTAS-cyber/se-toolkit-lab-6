# Agent Documentation

## Overview

This is a documentation agent for Lab 6. It calls an LLM API with tools (`read_file`, `list_files`) to answer questions about project documentation by reading actual files from the repository.

## LLM Provider

- **Provider:** Qwen Code API (via qwen-code-oai-proxy)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible chat completions with function calling

## Configuration

Set the following environment variables (or use `.env.agent.secret`):

```bash
# LLM configuration
LLM_API_KEY=my-secret-qwen-key
LLM_API_BASE=http://10.93.25.104:42005/v1
LLM_MODEL=qwen3-coder-plus

# Backend API configuration (for query_api tool)
LMS_API_URL=http://localhost:8000
LMS_API_KEY=my-secret-api-key
```

## Usage

### CLI

```bash
# Load environment variables
set -a && source .env.agent.secret && set +a

# Run the agent
python agent.py "How do you resolve a merge conflict?"
```

### Output Format

The agent outputs JSON to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\nbranching.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git Workflow\n\n## Resolving Merge Conflicts\n..."
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's text response |
| `source` | string | Reference to the source (file path like `wiki/file.md#section` or API endpoint like `/api/items/`). Optional for system questions. |
| `tool_calls` | array | All tool invocations with `tool`, `args`, and `result` |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Loop                               │
│                                                                  │
│  User Input ──▶ Add to messages ──▶ LLM Call                    │
│                                          │                       │
│                     ┌────────────────────┼────────────────────┐  │
│                     │                    │                    │  │
│                     ▼                    ▼                    │  │
│              Tool Calls?           Text Answer?                │  │
│                 │  yes                │  no                   │  │
│                 ▼                     ▼                       │  │
│         Execute Tools          Extract Answer                  │  │
│         Append results         Extract Source                  │  │
│         Back to LLM            Output JSON                     │  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Tools

### read_file

Read a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as string, or error message

**Security:** Rejects paths with `..` traversal to prevent reading files outside project directory.

### list_files

List files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries

**Security:** Rejects paths with `..` traversal to prevent listing directories outside project directory.

### query_api

Query the deployed backend API.

**Parameters:**
- `method` (string): HTTP method (GET, POST, PUT, DELETE)
- `path` (string): API endpoint path (e.g., `/items/`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code`, `headers`, and `body`

**Authentication:** Uses `LMS_API_KEY` from environment for Bearer token authentication.

**Configuration:**
- `LMS_API_URL`: Backend API URL (default: `http://localhost:8000`)
- `LMS_API_KEY`: API key for authentication (from `.env.docker.secret`)

## Agentic Loop

1. Send user question + tool definitions to LLM
2. Parse response:
   - If `tool_calls`: execute each tool, append results as `tool` role messages, repeat from step 1
   - If text answer: extract answer and source, output JSON, exit
3. Stop after 10 tool calls maximum

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Use `list_files("wiki")` to discover wiki files when needed
2. Use `read_file(path)` to read relevant documentation
3. Use `query_api(method, path)` to get real-time data from the backend
4. Always cite sources with file path and section anchor (`path#section`) or API endpoint
5. Be concise and honest if the answer is not found

## Components

| Component | Description |
|-----------|-------------|
| `Agent` | Main agent class with agentic loop |
| `LLMClient` | HTTP client for OpenAI-compatible API calls |
| `Tools` | Collection of tool implementations |
| `AgentResponse` | Dataclass for structured output |
| `ToolCall` | Dataclass representing a tool invocation |

## Running Tests

```bash
# Run all tests
python -m pytest tests/test_agent.py -v

# Run specific test
python -m pytest tests/test_agent.py::test_merge_conflict_question -v
```

## Project Structure

```
se-toolkit-lab-6/
├── agent.py           # Main agent implementation
├── AGENT.md           # This documentation
├── plans/
│   ├── task-1.md      # Task 1 plan
│   └── task-2.md      # Task 2 plan
├── tests/
│   └── test_agent.py  # Regression tests
└── wiki/              # Documentation files
    └── ...
```
