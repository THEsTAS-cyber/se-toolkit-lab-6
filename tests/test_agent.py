"""
Regression tests for agent.py.

Tests that the agent outputs valid JSON with required fields and uses tools correctly.

Note: These tests require the LLM API to be available. Set LLM_API_BASE to a working
endpoint or skip tests if API is unreachable.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


# Skip tests if LLM API is not configured or unreachable
LLM_API_BASE = os.environ.get("LLM_API_BASE", "")
SKIP_REASON = "LLM API not available (set LLM_API_BASE or run on VM)"


def run_agent(question: str, env: dict | None = None) -> dict:
    """Run agent.py with a question and return parsed JSON output."""
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Merge environment variables
    test_env = os.environ.copy()
    if env:
        test_env.update(env)

    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
        env=test_env,
    )

    if result.returncode != 0 and not result.stdout:
        raise RuntimeError(f"Agent failed: {result.stderr}")

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Agent output is not valid JSON: {e}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        ) from e

    return output


@unittest.skipUnless(LLM_API_BASE, SKIP_REASON)
class TestAgent(unittest.TestCase):
    """Test cases for agent.py."""

    def test_agent_output_format(self):
        """
        Test that agent.py outputs valid JSON with required fields.

        Verifies:
        1. Output is valid JSON
        2. 'answer' field is present
        3. 'tool_calls' field is present
        """
        output = run_agent("What is 2+2?")

        self.assertIn("answer", output, f"Missing 'answer' field in output: {output}")
        self.assertIn("tool_calls", output, f"Missing 'tool_calls' field in output: {output}")
        self.assertIsInstance(output["answer"], str,
            f"'answer' should be string, got {type(output['answer'])}")
        self.assertIsInstance(output["tool_calls"], list,
            f"'tool_calls' should be list, got {type(output['tool_calls'])}")

    def test_merge_conflict_question(self):
        """
        Test that agent uses read_file for merge conflict question.

        Question: "How do you resolve a merge conflict?"
        Expected:
        - read_file in tool_calls
        - wiki/git-workflow.md in source or answer
        """
        output = run_agent("How do you resolve a merge conflict?")

        # Check required fields
        self.assertIn("answer", output, f"Missing 'answer' field: {output}")
        self.assertIn("source", output, f"Missing 'source' field: {output}")
        self.assertIn("tool_calls", output, f"Missing 'tool_calls' field: {output}")

        # Check that read_file was used
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        self.assertIn("read_file", tool_names,
            f"Expected 'read_file' in tool_calls, got: {tool_names}")

        # Check that source references wiki file
        source = output.get("source", "")
        answer = output.get("answer", "")
        combined = f"{source} {answer}".lower()

        self.assertTrue(
            "wiki" in combined or "git" in combined,
            f"Expected wiki/git reference in source or answer. Got source='{source}', answer='{answer}'"
        )

    def test_list_files_question(self):
        """
        Test that agent uses list_files for directory listing question.

        Question: "What files are in the wiki?"
        Expected:
        - list_files in tool_calls
        """
        output = run_agent("What files are in the wiki?")

        # Check required fields
        self.assertIn("answer", output, f"Missing 'answer' field: {output}")
        self.assertIn("tool_calls", output, f"Missing 'tool_calls' field: {output}")

        # Check that list_files was used
        tool_names = [tc.get("tool") for tc in output["tool_calls"]]
        self.assertIn("list_files", tool_names,
            f"Expected 'list_files' in tool_calls, got: {tool_names}")


class TestTools(unittest.TestCase):
    """Test tool implementations (no LLM required)."""

    def setUp(self):
        """Set up tools for testing."""
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        from agent import Tools
        self.tools = Tools(project_root)

    def test_read_file_exists(self):
        """Test reading an existing file."""
        content = self.tools.read_file("README.md")
        self.assertNotIn("Error", content, f"Failed to read README.md: {content}")
        self.assertTrue(len(content) > 0, "File content is empty")

    def test_read_file_not_found(self):
        """Test reading a non-existent file."""
        content = self.tools.read_file("nonexistent_file.md")
        self.assertIn("Error", content, "Should return error for non-existent file")

    def test_read_file_security(self):
        """Test path traversal protection."""
        content = self.tools.read_file("../../etc/passwd")
        self.assertIn("Error", content, "Should block path traversal")
        self.assertIn("Access denied", content, "Should mention access denied")

    def test_list_files_exists(self):
        """Test listing an existing directory."""
        listing = self.tools.list_files("wiki")
        self.assertNotIn("Error", listing, f"Failed to list wiki: {listing}")
        self.assertIn("git.md", listing, "Should contain git.md")

    def test_list_files_not_found(self):
        """Test listing a non-existent directory."""
        listing = self.tools.list_files("nonexistent_dir")
        self.assertIn("Error", listing, "Should return error for non-existent directory")

    def test_list_files_security(self):
        """Test path traversal protection."""
        listing = self.tools.list_files("../../etc")
        self.assertIn("Error", listing, "Should block path traversal")
        self.assertIn("Access denied", listing, "Should mention access denied")


if __name__ == "__main__":
    # Run tool tests first (no LLM required)
    print("Running tool tests (no LLM required)...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTools)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✓ All tool tests passed!")

    # Run agent tests if LLM is available
    if LLM_API_BASE:
        print("\nRunning agent tests (LLM required)...")
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAgent)
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
    else:
        print(f"\n⊘ Skipping agent tests: {SKIP_REASON}")
        print("  Set LLM_API_BASE to run agent tests, or run on the VM.")
