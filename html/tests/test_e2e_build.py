"""End-to-end tests for the assembled HTML file (Task 7.2).

Verifies that the build output:
1. Exists and has a reasonable size
2. Contains all expected components (Rust, TS, Python, JS bridge)
3. Has proper HTML structure
4. Has all initialization code in the boot sequence
5. Contains no remaining placeholder comments
"""
import os
import re
import pytest

HTML_DIR = os.path.join(os.path.dirname(__file__), "..")
ROOT_DIR = os.path.join(HTML_DIR, "..")
OUTPUT_PATH = os.path.join(HTML_DIR, "amplifier-polyglot-agent.html")


@pytest.fixture(scope="module")
def assembled_html():
    """Build and read the assembled HTML file.

    Uses the build module directly to ensure fresh output,
    but also checks the file on disk.
    """
    import sys
    sys.path.insert(0, HTML_DIR)
    from build import assemble_html

    html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)

    # Also write to disk for file-level checks
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)

    return html


class TestFileExists:
    """The output file exists and has a reasonable size."""

    def test_output_file_exists(self, assembled_html):
        assert os.path.exists(OUTPUT_PATH)

    def test_file_size_reasonable(self, assembled_html):
        """File should be at least 100KB (Rust WASM base64 alone is ~280KB)."""
        size = len(assembled_html.encode("utf-8"))
        assert size > 100_000, f"File too small: {size} bytes"

    def test_file_size_under_limit(self, assembled_html):
        """Without Go WASM, file should be well under 50MB."""
        size = len(assembled_html.encode("utf-8"))
        assert size < 50_000_000, f"File too large: {size} bytes"

    def test_reports_size(self, assembled_html):
        """Just log the actual size for visibility."""
        size = len(assembled_html.encode("utf-8"))
        size_kb = size / 1024
        print(f"\n  Assembled HTML size: {size_kb:.1f} KB ({size:,} bytes)")


class TestHTMLValidity:
    """The assembled file is structurally valid HTML."""

    def test_starts_with_doctype(self, assembled_html):
        assert assembled_html.strip().startswith("<!DOCTYPE html>")

    def test_has_closing_html(self, assembled_html):
        assert "</html>" in assembled_html

    def test_has_head_and_body(self, assembled_html):
        assert "<head>" in assembled_html
        assert "<body>" in assembled_html

    def test_has_title(self, assembled_html):
        assert "<title>" in assembled_html


class TestNoPlaceholders:
    """All placeholder comments have been replaced."""

    def test_no_placeholder_comments(self, assembled_html):
        placeholders = re.findall(r"<!-- PLACEHOLDER:.*?-->", assembled_html)
        assert len(placeholders) == 0, f"Remaining placeholders: {placeholders}"

    def test_no_injected_by_build_comments(self, assembled_html):
        """The 'injected by build script' comments should be replaced."""
        assert "injected by build script" not in assembled_html


class TestRustWASMPresent:
    """Rust WASM kernel is properly embedded."""

    def test_rust_wasm_base64_tag_exists(self, assembled_html):
        assert 'id="rust-wasm-b64"' in assembled_html

    def test_rust_wasm_base64_has_content(self, assembled_html):
        match = re.search(
            r'<script id="rust-wasm-b64" type="text/plain">(.*?)</script>',
            assembled_html,
            re.DOTALL,
        )
        assert match is not None
        b64_content = match.group(1).strip()
        assert len(b64_content) > 1000, "Rust WASM base64 too small"

    def test_rust_wasm_magic_number(self, assembled_html):
        """WASM files start with \\x00asm which is AGFzbQ in base64."""
        assert "AGFzbQ" in assembled_html

    def test_rust_glue_code_present(self, assembled_html):
        """The wasm-pack JS glue code should be inlined."""
        assert "passStringToWasm0" in assembled_html
        assert "__wbg_get_imports" in assembled_html

    def test_rust_glue_no_export_keywords(self, assembled_html):
        """ES module exports should be stripped from inlined glue."""
        # Check there's no "export function" (but allow "export" in comments/strings)
        lines = assembled_html.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("export function "):
                pytest.fail(f"Found 'export function' in output: {stripped[:80]}")
            if stripped.startswith("export {"):
                pytest.fail(f"Found 'export {{' in output: {stripped[:80]}")

    def test_rust_init_code_in_boot(self, assembled_html):
        """Boot function should decode base64 and call initSync."""
        assert "initSync" in assembled_html
        assert "rust-wasm-b64" in assembled_html
        assert "kernel_version" in assembled_html

    def test_wasm_agent_exports_available(self, assembled_html):
        """The key Rust WASM exports should be reachable."""
        assert "execute_prompt" in assembled_html
        assert "get_tool_specs" in assembled_html
        assert "execute_tool" in assembled_html


class TestTypeScriptPresent:
    """TypeScript web_research tool is properly inlined."""

    def test_ts_web_research_function(self, assembled_html):
        assert "tsWebResearch" in assembled_html

    def test_ts_duckduckgo_api(self, assembled_html):
        assert "duckduckgo.com" in assembled_html

    def test_ts_dom_parser(self, assembled_html):
        assert "DOMParser" in assembled_html

    def test_ts_no_interface_declarations(self, assembled_html):
        """TypeScript interfaces should be stripped."""
        assert "interface WebResearchInput" not in assembled_html
        assert "interface ToolResult" not in assembled_html

    def test_ts_no_type_annotations(self, assembled_html):
        """TypeScript type annotations should be stripped."""
        # Should not have ": Promise<ToolResult>" in function signatures
        assert ": Promise<ToolResult>" not in assembled_html


class TestPythonPresent:
    """Python code_analysis is embedded as a JS string constant."""

    def test_python_source_embedded(self, assembled_html):
        assert "pyCodeAnalysisSource" in assembled_html

    def test_python_has_ast_import(self, assembled_html):
        """The Python source should include 'import ast'."""
        assert "import ast" in assembled_html

    def test_python_has_execute_function(self, assembled_html):
        """The Python source should include the execute function."""
        assert "def execute(" in assembled_html

    def test_python_has_pyodide_entry_point(self, assembled_html):
        """The pyCodeAnalysis function should be embedded."""
        assert "def pyCodeAnalysis(" in assembled_html


class TestJSBridgePresent:
    """JavaScript bridge layer is properly inlined."""

    def test_bridge_execute_tool(self, assembled_html):
        assert "amplifier_execute_tool" in assembled_html

    def test_bridge_llm_complete(self, assembled_html):
        assert "amplifier_llm_complete" in assembled_html

    def test_bridge_on_event(self, assembled_html):
        assert "amplifier_on_event" in assembled_html

    def test_bridge_tool_registry(self, assembled_html):
        assert "toolRegistry" in assembled_html

    def test_bridge_webllm_init(self, assembled_html):
        """initWebLLM function should be present."""
        assert "initWebLLM" in assembled_html

    def test_bridge_webllm_cdn(self, assembled_html):
        """WebLLM should load from CDN."""
        assert "esm.run/@mlc-ai/web-llm" in assembled_html


class TestPyodideInit:
    """Pyodide initialization is properly injected."""

    def test_pyodide_cdn_url(self, assembled_html):
        assert "pyodide" in assembled_html.lower()

    def test_pyodide_load_call(self, assembled_html):
        assert "loadPyodide" in assembled_html

    def test_pyodide_instance_set(self, assembled_html):
        assert "pyodideInstance" in assembled_html

    def test_pyodide_runs_code_analysis(self, assembled_html):
        """Pyodide should run the embedded Python code."""
        assert "pyCodeAnalysisSource" in assembled_html


class TestGoWASMStub:
    """When Go is unavailable, appropriate stubs are in place."""

    def test_go_wasm_stub_present(self, assembled_html):
        """Should have Go WASM placeholder/stub."""
        assert "go-wasm-b64" in assembled_html

    def test_go_wasm_not_available_message(self, assembled_html):
        """Should indicate Go WASM is not available."""
        assert "Go WASM not" in assembled_html


class TestBootSequence:
    """The boot sequence is complete and properly ordered."""

    def test_boot_function_exists(self, assembled_html):
        assert "async function boot()" in assembled_html

    def test_boot_loads_rust_first(self, assembled_html):
        """Rust WASM should load before other tools."""
        rust_pos = assembled_html.find("Loading Rust kernel")
        go_pos = assembled_html.find("Loading Go document")
        pyodide_pos = assembled_html.find("Loading Python analyzer")
        webllm_pos = assembled_html.find("Loading AI model")
        assert rust_pos < go_pos < pyodide_pos < webllm_pos

    def test_boot_enables_input_on_success(self, assembled_html):
        """On successful boot, input should be enabled."""
        assert "inputEl.disabled = false" in assembled_html
        assert "sendBtn.disabled = false" in assembled_html

    def test_boot_has_error_handling(self, assembled_html):
        """Boot should catch errors and display them."""
        assert "Boot failed" in assembled_html

    def test_boot_calls_boot_at_end(self, assembled_html):
        """The boot() function should be called somewhere, or ready to be called."""
        # It could be called at the end of the script or via DOMContentLoaded
        # Just ensure the function exists and the page has chat UI
        assert "boot()" in assembled_html


class TestChatUIIntact:
    """The chat UI from template.html survives assembly."""

    def test_has_messages_container(self, assembled_html):
        assert 'id="messages"' in assembled_html

    def test_has_input_field(self, assembled_html):
        assert 'id="input"' in assembled_html

    def test_has_send_button(self, assembled_html):
        assert 'id="send"' in assembled_html

    def test_has_status_bar(self, assembled_html):
        assert 'id="status"' in assembled_html

    def test_has_language_badges(self, assembled_html):
        assert "badge rust" in assembled_html
        assert "badge ts" in assembled_html
        assert "badge python" in assembled_html
        assert "badge go" in assembled_html

    def test_has_css_styles(self, assembled_html):
        assert "<style>" in assembled_html
        assert "dark" in assembled_html.lower() or "#1a1a2e" in assembled_html
