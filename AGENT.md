# Agent Documentation

## Overview

This is a simple LLM-powered agent for Lab 6. It calls an LLM API and returns structured responses.

## LLM Provider

- **Provider:** Qwen Code API (via qwen-code-oai-proxy)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible chat completions

## Configuration

Set the following environment variables (or use `.env.agent.secret`):

```bash
LLM_API_KEY=my-secret-qwen-key
LLM_API_BASE=http://10.93.25.104:42005/v1
LLM_MODEL=qwen3-coder-plus
```

## Usage

### CLI

```bash
# Load environment variables
set -a && source .env.agent.secret && set +a

# Run the agent
python agent.py "What is 2+2?"
```

### Output Format

The agent outputs JSON to stdout:

```json
{
  "answer": "The answer from the LLM",
  "tool_calls": []
}
```

When tools are used (Task 2-3):

```json
{
  "answer": "",
  "tool_calls": [
    {"name": "read_file", "arguments": {"path": "README.md"}}
  ]
}
```

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  agent.py   │────▶│  LLMClient       │────▶│  HTTP API   │
│  (Agent)    │◀────│  (httpx)         │◀────│  (Qwen)     │
└─────────────┘     └──────────────────┘     └─────────────┘
```

### Components

1. **`Agent`** - Main agent class that manages conversation history and calls the LLM
2. **`LLMClient`** - HTTP client for OpenAI-compatible API calls
3. **`AgentResponse`** - Dataclass for structured output
4. **`ToolCall`** - Dataclass representing a tool invocation

## Running Tests

```bash
# Run the regression test
python -m pytest tests/test_agent.py -v
```

## Next Steps (Task 2-3)

1. Add tools: `read_file`, `list_files`, `query_api`
2. Implement tool execution in the agent loop
3. Expand system prompt with domain knowledge
