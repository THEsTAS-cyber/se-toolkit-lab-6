"""
Regression tests for agent.py.

Tests that the agent outputs valid JSON with 'answer' and 'tool_calls' fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_output_format():
    """
    Test that agent.py outputs valid JSON with required fields.
    
    Runs agent.py as a subprocess and verifies:
    1. Output is valid JSON
    2. 'answer' field is present
    3. 'tool_calls' field is present
    """
    # Path to agent.py
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"
    
    # Run agent with a simple question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Agent output is not valid JSON: {e}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        ) from e
    
    # Check required fields
    assert "answer" in output, f"Missing 'answer' field in output: {output}"
    assert "tool_calls" in output, f"Missing 'tool_calls' field in output: {output}"
    
    # Verify types
    assert isinstance(output["answer"], str), \
        f"'answer' should be string, got {type(output['answer'])}"
    assert isinstance(output["tool_calls"], list), \
        f"'tool_calls' should be list, got {type(output['tool_calls'])}"
    
    print(f"✓ Test passed: answer='{output['answer'][:50]}...'")


if __name__ == "__main__":
    test_agent_output_format()
    print("All tests passed!")
