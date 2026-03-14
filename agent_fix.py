#!/usr/bin/env python3
"""Fix agent.py - change auth default to True"""

with open('agent.py', 'r') as f:
    content = f.read()

# Change auth default from False to True
content = content.replace(
    'def query_api(self, method: str, path: str, body: Optional[str] = None, auth: bool = False)',
    'def query_api(self, method: str, path: str, body: Optional[str] = None, auth: bool = True)'
)

with open('agent.py', 'w') as f:
    f.write(content)

print("Fixed! auth default is now True")
