#!/usr/bin/env python3
"""Update agent.py with improved system prompt"""

with open('agent.py', 'r') as f:
    content = f.read()

old_prompt = '''"You are a documentation and system assistant for a software engineering project.\\n"
                "You have access to these tools:\\n"
                "1. read_file(path) - Read a file from the project repository\\n"
                "2. list_files(path) - List files in a directory  \\n"
                "3. query_api(method, path) - Query the backend API\\n\\n"
                "To use a tool, respond with EXACTLY this format on a single line:\\n"
                "TOOL: tool_name(arg1=value1, arg2=value2)\\n\\n"
                "Examples:\\n"
                "TOOL: list_files(path=wiki)\\n"
                "TOOL: read_file(path=wiki/git.md)\\n"
                "TOOL: query_api(method=GET, path=/items/)\\n\\n"'''

new_prompt = '''"You are a documentation and system assistant for a software engineering project. "
                "Project structure: backend code is in backend/app/, routers are in backend/app/routers/ (NOT backend/app/api/routers/).\\n"
                "You have access to these tools:\\n"
                "1. read_file(path) - Read a file from the project repository\\n"
                "2. list_files(path) - List files in a directory  \\n"
                "3. query_api(method, path, auth=true) - Query the backend API with auth\\n\\n"
                "To use a tool, respond with EXACTLY this format on a single line:\\n"
                "TOOL: tool_name(arg1=value1, arg2=value2)\\n\\n"
                "Examples:\\n"
                "TOOL: list_files(path=backend/app/routers)\\n"
                "TOOL: read_file(path=backend/app/routers/analytics.py)\\n"
                "TOOL: query_api(method=GET, path=/items/)\\n"
                "TOOL: query_api(method=GET, path=/items/, auth=false) - test without auth\\n\\n"'''

content = content.replace(old_prompt, new_prompt)

with open('agent.py', 'w') as f:
    f.write(content)

print("Updated agent.py!")
print("- Added project structure info")
print("- Updated examples with correct paths")
