"""Tests for the WebLLM integration in bridge.js (Task 6.1).

Validates that bridge.js contains the required WebLLM provider functions
and correct structure for the Rust WASM kernel to call.
"""
import os
import re
import pytest

BRIDGE_PATH = os.path.join(os.path.dirname(__file__), "..", "bridge.js")


@pytest.fixture
def bridge_js():
    """Read bridge.js contents."""
    with open(BRIDGE_PATH) as f:
        return f.read()


class TestInitWebLLM:
    """Tests for the initWebLLM function."""

    def test_init_webllm_function_exists(self, bridge_js):
        """bridge.js must export an initWebLLM function."""
        assert "initWebLLM" in bridge_js, "initWebLLM function not found in bridge.js"

    def test_init_webllm_is_async(self, bridge_js):
        """initWebLLM must be async (returns a promise)."""
        assert re.search(r"async\s+function\s+initWebLLM", bridge_js), \
            "initWebLLM must be an async function"

    def test_init_webllm_accepts_model_id(self, bridge_js):
        """initWebLLM must accept a modelId parameter."""
        match = re.search(r"async\s+function\s+initWebLLM\s*\(([^)]*)\)", bridge_js)
        assert match, "initWebLLM function signature not found"
        params = match.group(1)
        assert "modelId" in params, "initWebLLM must accept modelId parameter"

    def test_init_webllm_accepts_progress_callback(self, bridge_js):
        """initWebLLM must accept an onProgress callback parameter."""
        match = re.search(r"async\s+function\s+initWebLLM\s*\(([^)]*)\)", bridge_js)
        assert match, "initWebLLM function signature not found"
        params = match.group(1)
        assert "onProgress" in params, "initWebLLM must accept onProgress parameter"

    def test_init_webllm_imports_from_cdn(self, bridge_js):
        """initWebLLM must import WebLLM from the esm.run CDN."""
        assert "esm.run/@mlc-ai/web-llm" in bridge_js, \
            "WebLLM must be imported from https://esm.run/@mlc-ai/web-llm"

    def test_init_webllm_creates_engine(self, bridge_js):
        """initWebLLM must call CreateMLCEngine to create the WebLLM engine."""
        assert "CreateMLCEngine" in bridge_js, \
            "initWebLLM must use CreateMLCEngine to create the engine"

    def test_init_webllm_sets_global_engine(self, bridge_js):
        """initWebLLM must set webllmEngine (used by amplifier_llm_complete)."""
        assert "webllmEngine" in bridge_js, \
            "initWebLLM must set webllmEngine for amplifier_llm_complete to use"


class TestAmplifierLlmComplete:
    """Tests for the amplifier_llm_complete function."""

    def test_llm_complete_exists(self, bridge_js):
        """amplifier_llm_complete must be defined on window."""
        assert "amplifier_llm_complete" in bridge_js

    def test_llm_complete_is_async(self, bridge_js):
        """amplifier_llm_complete must be async."""
        assert re.search(r"amplifier_llm_complete\s*=\s*async", bridge_js), \
            "amplifier_llm_complete must be an async function"

    def test_llm_complete_checks_engine_initialized(self, bridge_js):
        """amplifier_llm_complete must check if webllmEngine is initialized."""
        # Should have a guard checking webllmEngine exists
        assert re.search(r"webllmEngine", bridge_js), \
            "amplifier_llm_complete must check webllmEngine"

    def test_llm_complete_handles_tool_calls(self, bridge_js):
        """amplifier_llm_complete must handle tool_calls in the response."""
        assert "tool_calls" in bridge_js, \
            "amplifier_llm_complete must handle tool_calls"

    def test_llm_complete_converts_tools_to_openai_format(self, bridge_js):
        """Tools must be converted to OpenAI-compatible format with type: function."""
        assert '"function"' in bridge_js or "'function'" in bridge_js, \
            "Tools must use type: 'function' (OpenAI format)"

    def test_llm_complete_returns_json_string(self, bridge_js):
        """amplifier_llm_complete must return JSON.stringify'd results."""
        assert "JSON.stringify" in bridge_js, \
            "amplifier_llm_complete must return JSON-stringified results"

    def test_llm_complete_handles_errors(self, bridge_js):
        """amplifier_llm_complete must have error handling."""
        # Should have try/catch
        assert "catch" in bridge_js, \
            "amplifier_llm_complete must have error handling"

    def test_llm_complete_parses_request_json(self, bridge_js):
        """amplifier_llm_complete must parse the incoming requestJson."""
        assert "JSON.parse" in bridge_js, \
            "amplifier_llm_complete must parse the request JSON string"


class TestToolRegistry:
    """Tests that existing tool registry is preserved."""

    def test_tool_registry_exists(self, bridge_js):
        assert "toolRegistry" in bridge_js

    def test_web_research_registered(self, bridge_js):
        assert "web_research" in bridge_js

    def test_code_analysis_registered(self, bridge_js):
        assert "code_analysis" in bridge_js

    def test_document_builder_registered(self, bridge_js):
        assert "document_builder" in bridge_js

    def test_amplifier_execute_tool_exists(self, bridge_js):
        assert "amplifier_execute_tool" in bridge_js
