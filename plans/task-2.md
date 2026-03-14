# Task 2: The Documentation Agent

## Overview

Extend the agent from Task 1 with tools to read project files and navigate the wiki.

## Tool Schemas

### read_file

**Purpose:** Read contents of a file from the project repository.

**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read a file from the project repository",
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
}
```

**Implementation:**
- Use Python's `pathlib.Path` to read file
- Security: reject paths with `..` traversal
- Return error message if file doesn't exist

### list_files

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "list_files",
    "description": "List files and directories in a directory",
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
```

**Implementation:**
- Use `os.listdir()` or `pathlib.Path.iterdir()`
- Security: reject paths with `..` traversal
- Return newline-separated listing

## Path Security

Both tools must prevent directory traversal attacks:

```python
def is_safe_path(base_path: Path, requested_path: str) -> bool:
    """Check if requested path is within base_path (no ../ traversal)."""
    try:
        resolved = (base_path / requested_path).resolve()
        return str(resolved).startswith(str(base_path.resolve()))
    except Exception:
        return False
```

## Agentic Loop

```
1. Send user question + tool definitions to LLM
2. Parse response:
   - If tool_calls: execute each tool, append results, go to step 1
   - If text answer: extract answer + source, output JSON, exit
3. Stop after 10 tool calls maximum
```

## System Prompt Strategy

The system prompt should instruct the LLM to:
1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to read relevant documentation
3. Always include a `source` field with file path and section anchor
4. Be concise and cite sources

Example:
```
You are a documentation assistant. You have access to project files via tools.

When answering questions:
1. First explore the wiki structure with list_files("wiki")
2. Read relevant files with read_file(path)
3. Answer the question and cite the source as "path#section-anchor"
4. If you don't find the answer, say so honestly

Always include the source field in your final answer.
```

## Output Format

```json
{
  "answer": "The answer text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "file contents..."
    }
  ]
}
```

## Files to Modify

- `agent.py` - Add tools and agentic loop
- `AGENT.md` - Document tools and loop
- `tests/test_agent.py` - Add 2 regression tests
