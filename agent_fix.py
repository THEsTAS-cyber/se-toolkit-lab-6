#!/usr/bin/env python3
"""Fix agent.py for Task 3 requirements"""

with open('agent.py', 'r') as f:
    content = f.read()

# 1. Change auth default from False to True
content = content.replace(
    'def query_api(self, method: str, path: str, body: Optional[str] = None, auth: bool = False)',
    'def query_api(self, method: str, path: str, body: Optional[str] = None, auth: bool = True)'
)

# 2. Update AGENT_API_BASE_URL usage
content = content.replace(
    'self.api_url = os.environ.get("LMS_API_URL", "http://localhost:8000")',
    'self.api_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")'
)

# 3. Update system prompt with auth examples
old_prompt = '''"To use a tool, respond with EXACTLY this format on a single line:\\n"
                "TOOL: tool_name(arg1=value1, arg2=value2)\\n\\n"
                "Examples:\\n"
                "TOOL: list_files(path=wiki)\\n"
                "TOOL: read_file(path=wiki/git.md)\\n"
                "TOOL: query_api(method=GET, path=/items/)\\n\\n"'''

new_prompt = '''"To use a tool, respond with EXACTLY this format on a single line:\\n"
                "TOOL: tool_name(arg1=value1, arg2=value2)\\n\\n"
                "Examples:\\n"
                "TOOL: list_files(path=wiki)\\n"
                "TOOL: read_file(path=wiki/git.md)\\n"
                "TOOL: query_api(method=GET, path=/items/, auth=true) - with authentication\\n"
                "TOOL: query_api(method=GET, path=/items/, auth=false) - without authentication\\n\\n"'''

content = content.replace(old_prompt, new_prompt)

with open('agent.py', 'w') as f:
    f.write(content)

print("Fixed agent.py for Task 3!")
print("- auth=True by default")
print("- AGENT_API_BASE_URL from env (default: http://localhost:42002)")
print("- Updated system prompt with auth examples")
