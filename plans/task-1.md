# Task 1: Call an LLM from Code

## LLM Provider

**Provider:** Qwen Code API (self-hosted via qwen-code-oai-proxy)

**Model:** `qwen3-coder-plus`

**Why this choice:**
- OpenAI-compatible API format (chat completions with function calling)
- Free to use through the university's proxy server
- Good code understanding and reasoning capabilities
- Supports tool/function calling which is required for agent loop

**Configuration:**
- API Base: `http://10.93.25.104:42005/v1`
- API Key: `my-secret-qwen-key` (from `.env.agent.secret`)
- Model: `qwen3-coder-plus`

## Agent Structure

### Components

1. **LLM Client** (`LLMClient` class)
   - Wraps HTTP calls to the LLM API
   - Uses OpenAI-compatible request/response format
   - Handles authentication and error handling

2. **Agent Loop** (`Agent` class)
   - Maintains conversation history
   - Sends user message to LLM
   - Parses response (text answer + tool calls)
   - Executes tools if requested
   - Feeds tool results back to LLM
   - Repeats until final answer

3. **Tools** (to be implemented in Task 2-3)
   - `read_file(path)` - read file contents
   - `list_files(dir)` - list directory contents
   - `query_api(path)` - query backend API

### Flow

```
User Input → LLM → Parse Response
                     │
                     ├─→ Has tool_call? → Execute Tool → Feed Result → LLM (repeat)
                     │
                     └─→ Final Answer → Output JSON
```

### Output Format

The agent outputs JSON to stdout:
```json
{
  "answer": "The final answer to the user's question",
  "tool_calls": [
    {"name": "read_file", "arguments": {"path": "README.md"}}
  ]
}
```

## Files to Create

- `agent.py` - Main agent implementation
- `AGENT.md` - Documentation
- `tests/test_agent.py` - Regression test
