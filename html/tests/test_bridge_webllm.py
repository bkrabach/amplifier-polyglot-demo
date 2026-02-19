"""Tests for the WebLLM integration in bridge.js.

Validates that bridge.js uses JSON Schema constrained decoding (response_format)
instead of native WebLLM function calling. The model outputs a discriminated
union: either {"type": "text", ...} or {"type": "tool_call", ...}.
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
        assert re.search(
            r"async\s+function\s+initWebLLM", bridge_js
        ), "initWebLLM must be an async function"

    def test_init_webllm_accepts_model_id(self, bridge_js):
        """initWebLLM must accept a modelId parameter."""
        match = re.search(
            r"async\s+function\s+initWebLLM\s*\(([^)]*)\)", bridge_js
        )
        assert match, "initWebLLM function signature not found"
        params = match.group(1)
        assert "modelId" in params, "initWebLLM must accept modelId parameter"

    def test_init_webllm_accepts_progress_callback(self, bridge_js):
        """initWebLLM must accept an onProgress callback parameter."""
        match = re.search(
            r"async\s+function\s+initWebLLM\s*\(([^)]*)\)", bridge_js
        )
        assert match, "initWebLLM function signature not found"
        params = match.group(1)
        assert "onProgress" in params, "initWebLLM must accept onProgress parameter"

    def test_init_webllm_imports_from_cdn(self, bridge_js):
        """initWebLLM must import WebLLM from the esm.run CDN."""
        assert "esm.run/@mlc-ai/web-llm" in bridge_js, (
            "WebLLM must be imported from https://esm.run/@mlc-ai/web-llm"
        )

    def test_init_webllm_creates_engine(self, bridge_js):
        """initWebLLM must call CreateMLCEngine to create the WebLLM engine."""
        assert "CreateMLCEngine" in bridge_js, (
            "initWebLLM must use CreateMLCEngine to create the engine"
        )

    def test_init_webllm_sets_global_engine(self, bridge_js):
        """initWebLLM must set webllmEngine (used by amplifier_llm_complete)."""
        assert "webllmEngine" in bridge_js, (
            "initWebLLM must set webllmEngine for amplifier_llm_complete to use"
        )


class TestConstrainedDecodingSchema:
    """Tests for the JSON Schema constrained decoding approach."""

    def test_has_build_tool_call_schema_function(self, bridge_js):
        """Must have a buildToolCallSchema function for the discriminated union."""
        assert re.search(
            r"function\s+buildToolCallSchema", bridge_js
        ), "Must define a buildToolCallSchema function"

    def test_schema_uses_oneof(self, bridge_js):
        """The schema must use oneOf for the discriminated union."""
        assert "oneOf" in bridge_js, (
            "Schema must use oneOf for text vs tool_call discrimination"
        )

    def test_schema_has_text_type(self, bridge_js):
        """The schema must define a text response type with const discriminator."""
        assert re.search(
            r"""const.*['"]text['"]""", bridge_js
        ) or re.search(
            r"""['"]text['"].*const""", bridge_js
        ), "Schema must have a const 'text' discriminator"

    def test_schema_has_tool_call_type(self, bridge_js):
        """The schema must define a tool_call type with const discriminator."""
        assert re.search(
            r"""const.*['"]tool_call['"]""", bridge_js
        ) or re.search(
            r"""['"]tool_call['"].*const""", bridge_js
        ), "Schema must have a const 'tool_call' discriminator"

    def test_schema_constrains_tool_names_via_enum(self, bridge_js):
        """Tool names must be constrained via enum in the schema."""
        assert "enum" in bridge_js, (
            "Schema must use enum to constrain valid tool names"
        )

    def test_schema_is_stringified(self, bridge_js):
        """The schema must be JSON.stringify'd (WebLLM requires string)."""
        assert re.search(
            r"JSON\.stringify\(.*[Ss]chema", bridge_js, re.DOTALL
        ), "Schema must be passed through JSON.stringify"


class TestAmplifierLlmComplete:
    """Tests for amplifier_llm_complete using constrained decoding."""

    def test_llm_complete_exists(self, bridge_js):
        """amplifier_llm_complete must be defined on window."""
        assert "amplifier_llm_complete" in bridge_js

    def test_llm_complete_is_async(self, bridge_js):
        """amplifier_llm_complete must be async."""
        assert re.search(
            r"amplifier_llm_complete\s*=\s*async", bridge_js
        ), "amplifier_llm_complete must be an async function"

    def test_llm_complete_checks_engine_initialized(self, bridge_js):
        """amplifier_llm_complete must check if webllmEngine is initialized."""
        assert re.search(
            r"webllmEngine", bridge_js
        ), "amplifier_llm_complete must check webllmEngine"

    def test_llm_complete_uses_response_format(self, bridge_js):
        """Must use response_format with json_object type."""
        assert "response_format" in bridge_js, (
            "Must use response_format for constrained decoding"
        )
        assert "json_object" in bridge_js, (
            "response_format type must be json_object"
        )

    def test_llm_complete_does_not_use_native_tool_calling(self, bridge_js):
        """Must NOT use params.tools or params.tool_choice."""
        assert "params.tools" not in bridge_js, (
            "Must not use params.tools (native function calling is broken)"
        )
        assert "params.tool_choice" not in bridge_js, (
            "Must not use params.tool_choice (native function calling is broken)"
        )

    def test_llm_complete_handles_text_response(self, bridge_js):
        """Must handle output.type === 'text' for text responses."""
        assert re.search(
            r"""output\.type\s*===?\s*['"]text['"]""", bridge_js
        ), "Must check output.type for 'text' responses"

    def test_llm_complete_handles_tool_call_response(self, bridge_js):
        """Must handle output.type === 'tool_call' for tool call responses."""
        assert re.search(
            r"""output\.type\s*===?\s*['"]tool_call['"]""", bridge_js
        ), "Must check output.type for 'tool_call' responses"

    def test_llm_complete_returns_tool_calls_array(self, bridge_js):
        """amplifier_llm_complete must return tool_calls in the response."""
        assert "tool_calls" in bridge_js, (
            "amplifier_llm_complete must return tool_calls"
        )

    def test_llm_complete_returns_json_string(self, bridge_js):
        """amplifier_llm_complete must return JSON.stringify'd results."""
        assert "JSON.stringify" in bridge_js, (
            "amplifier_llm_complete must return JSON-stringified results"
        )

    def test_llm_complete_handles_errors(self, bridge_js):
        """amplifier_llm_complete must have error handling."""
        assert "catch" in bridge_js, (
            "amplifier_llm_complete must have error handling"
        )

    def test_llm_complete_parses_request_json(self, bridge_js):
        """amplifier_llm_complete must parse the incoming requestJson."""
        assert "JSON.parse" in bridge_js, (
            "amplifier_llm_complete must parse the request JSON string"
        )

    def test_llm_complete_builds_system_prompt_with_tools(self, bridge_js):
        """Must build a system prompt that describes available tools."""
        assert (
            "toolDescriptions" in bridge_js or "Available tools" in bridge_js
        ), "Must build a system prompt with tool descriptions"

    def test_llm_complete_generates_tool_call_id(self, bridge_js):
        """Must generate a unique ID for tool calls."""
        assert re.search(
            r"call_.*random", bridge_js
        ), "Must generate a call_* ID for tool calls"


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
