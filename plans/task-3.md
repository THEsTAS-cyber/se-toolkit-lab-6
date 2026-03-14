# Task 3: The System Agent

## Overview

Extend the agent from Task 2 with a `query_api` tool to interact with the deployed backend API.

## New Tool: query_api

**Purpose:** Send HTTP requests to the deployed backend API.

**Schema:**
```json
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
```

**Implementation:**
- Use `httpx` to send HTTP requests
- Read `LMS_API_KEY` from `.env.docker.secret` for authentication
- Return JSON string with `status_code` and `body`

**Authentication:**
```python
headers = {
    "Authorization": f"Bearer {LMS_API_KEY}",
    "Content-Type": "application/json",
}
```

## Environment Variables

Add to `.env.agent.secret`:

```bash
# LLM configuration
LLM_API_KEY=my-secret-qwen-key
LLM_API_BASE=http://10.93.25.104:42005/v1
LLM_MODEL=qwen3-coder-plus

# Backend API configuration
LMS_API_URL=http://localhost:8000
LMS_API_KEY=your-backend-api-key
```

## System Prompt Update

Update system prompt to instruct the LLM:

```
You are a documentation and system assistant. You have access to:
1. Project files via read_file and list_files
2. The deployed backend API via query_api

When answering questions:
- For documentation questions: use list_files and read_file
- For system/data questions: use query_api to get real data
- For framework/port questions: use query_api or read configuration files
- Always cite sources when possible (file path or API endpoint)
```

## Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "/api/items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": {...}}"
    }
  ]
}
```

**Note:** `source` is now optional — system questions may not have a wiki source.

## Question Types

### 1. Static System Facts

Questions about framework, ports, status codes:
- "What framework is the backend built with?"
- "What port does the API run on?"
- "What status code does the API return for success?"

### 2. Data-Dependent Queries

Questions requiring live API calls:
- "How many items are in the database?"
- "What is the highest score?"
- "List all users"

## Files to Modify

- `agent.py` - Add `query_api` tool
- `AGENT.md` - Document the new tool
- `tests/test_agent.py` - Add tests for `query_api`
