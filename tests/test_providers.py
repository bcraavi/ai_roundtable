"""Tests for the provider registry and agent configuration."""

import os
import unittest
from unittest.mock import patch

from ai_roundtable._providers import (
    parse_agent_spec,
    resolve_agents,
    validate_agents,
    AgentConfig,
)
from ai_roundtable._types import RoundtableError


class TestParseAgentSpec(unittest.TestCase):
    """Tests for parsing agent specification strings."""

    def test_simple_provider(self):
        provider, model = parse_agent_spec("claude")
        self.assertEqual(provider, "claude")
        self.assertIsNone(model)

    def test_provider_with_model(self):
        provider, model = parse_agent_spec("ollama:codellama")
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "codellama")

    def test_whitespace_stripped(self):
        provider, model = parse_agent_spec(" claude ")
        self.assertEqual(provider, "claude")

    def test_case_insensitive(self):
        provider, model = parse_agent_spec("CLAUDE")
        self.assertEqual(provider, "claude")

    def test_provider_model_whitespace(self):
        provider, model = parse_agent_spec("ollama : llama3")
        self.assertEqual(provider, "ollama")
        self.assertEqual(model, "llama3")


class TestResolveAgents(unittest.TestCase):
    """Tests for resolving agent specifications to configs."""

    def test_default_agents(self):
        agents = resolve_agents(None)
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0].name, "Claude")
        self.assertEqual(agents[1].name, "Codex")

    def test_custom_agents(self):
        agents = resolve_agents(["claude", "gemini"])
        self.assertEqual(len(agents), 2)
        self.assertEqual(agents[0].name, "Claude")
        self.assertEqual(agents[1].name, "Gemini")

    def test_minimum_two_agents(self):
        with self.assertRaises(RoundtableError):
            resolve_agents(["claude"])

    def test_duplicate_agents_rejected(self):
        with self.assertRaises(RoundtableError):
            resolve_agents(["claude", "claude"])

    def test_ollama_provider(self):
        agents = resolve_agents(["claude", "ollama:codellama"])
        self.assertEqual(agents[1].name, "Ollama/codellama")
        self.assertIn("ollama", agents[1].cmd[0])
        self.assertIn("codellama", agents[1].cmd)

    def test_ollama_default_model(self):
        agents = resolve_agents(["claude", "ollama:llama3"])
        self.assertEqual(agents[1].name, "Ollama/llama3")

    def test_generic_provider(self):
        agents = resolve_agents(["claude", "mycli"])
        self.assertEqual(agents[1].name, "Mycli")

    def test_generic_provider_with_model(self):
        agents = resolve_agents(["claude", "mycli:mymodel"])
        self.assertEqual(agents[1].name, "Mycli/mymodel")

    def test_three_agents(self):
        agents = resolve_agents(["claude", "codex", "gemini"])
        self.assertEqual(len(agents), 3)

    def test_env_override_for_claude(self):
        agents = resolve_agents(["claude", "codex"])
        # Claude should have env_overrides to remove CLAUDECODE
        self.assertIsNotNone(agents[0].env_overrides)
        self.assertIn("CLAUDECODE", agents[0].env_overrides)

    def test_each_agent_gets_unique_color(self):
        agents = resolve_agents(["claude", "codex", "gemini"])
        colors = [a.color_code for a in agents]
        self.assertEqual(len(set(colors)), 3)

    def test_env_var_override_command(self):
        with patch.dict(os.environ, {"ROUNDTABLE_GEMINI_CMD": "/custom/gemini"}):
            agents = resolve_agents(["claude", "gemini"])
            self.assertEqual(agents[1].cmd[0], "/custom/gemini")

    def test_opencode_provider(self):
        agents = resolve_agents(["claude", "opencode"])
        self.assertEqual(agents[1].name, "OpenCode")
        self.assertIn("opencode", agents[1].cmd[0])

    def test_amazon_q_provider(self):
        agents = resolve_agents(["claude", "q"])
        self.assertEqual(agents[1].name, "Amazon Q")
        self.assertIn("q", agents[1].cmd[0])
        self.assertIn("chat", agents[1].cmd)

    def test_copilot_provider(self):
        agents = resolve_agents(["claude", "copilot"])
        self.assertEqual(agents[1].name, "Copilot")
        self.assertIn("gh", agents[1].cmd[0])
        self.assertIn("copilot", agents[1].cmd)

    def test_aider_provider(self):
        agents = resolve_agents(["claude", "aider"])
        self.assertEqual(agents[1].name, "Aider")
        self.assertIn("--message", agents[1].cmd)

    def test_all_builtin_providers(self):
        """All built-in providers should resolve without error."""
        for provider in ["claude", "codex", "gemini", "opencode", "aider", "q", "copilot"]:
            agents = resolve_agents(["claude", provider] if provider != "claude" else ["claude", "codex"])
            self.assertEqual(len(agents), 2)


class TestValidateAgents(unittest.TestCase):
    """Tests for agent CLI validation."""

    def test_missing_tool_raises(self):
        agents = [
            AgentConfig(name="FakeTool", agent_key="fake", cmd=["nonexistent_tool_xyz123"],
                         color_code=""),
            AgentConfig(name="FakeTool2", agent_key="fake2", cmd=["nonexistent_tool_abc456"],
                         color_code=""),
        ]
        with self.assertRaises(RoundtableError) as ctx:
            validate_agents(agents)
        self.assertIn("nonexistent_tool_xyz123", str(ctx.exception))

    @patch('ai_roundtable._providers.shutil.which')
    def test_resolves_absolute_paths(self, mock_which):
        mock_which.return_value = "/usr/bin/claude"
        agents = [
            AgentConfig(name="Claude", agent_key="claude", cmd=["claude", "-p", "-"],
                         color_code=""),
            AgentConfig(name="Codex", agent_key="codex", cmd=["codex", "exec", "-"],
                         color_code=""),
        ]
        mock_which.side_effect = ["/usr/bin/claude", "/usr/bin/codex"]
        resolved = validate_agents(agents)
        self.assertEqual(resolved[0].cmd[0], "/usr/bin/claude")
        self.assertEqual(resolved[1].cmd[0], "/usr/bin/codex")


if __name__ == "__main__":
    unittest.main()
