#!/usr/bin/env python3
"""Fix auth parsing in agent.py"""

with open('agent.py', 'r') as f:
    content = f.read()

old_code = '''if "=" in arg:
                            key, value = arg.split("=", 1)
                            args[key.strip()] = value.strip().strip('"').strip("'")'''

new_code = '''if "=" in arg:
                            key, value = arg.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            # Convert auth string to boolean
                            if key == "auth":
                                value = value.lower() == "true"
                            args[key] = value'''

content = content.replace(old_code, new_code)

with open('agent.py', 'w') as f:
    f.write(content)

print("Fixed auth parsing!")
