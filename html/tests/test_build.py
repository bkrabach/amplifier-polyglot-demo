"""Tests for the build script (Task 7.1).

Validates that build.py can assemble the single HTML file from
template.html by replacing placeholders with inlined content.
"""
import os
import sys
import re
import pytest

# Add the html directory to the path so we can import build
HTML_DIR = os.path.join(os.path.dirname(__file__), "..")
ROOT_DIR = os.path.join(HTML_DIR, "..")
sys.path.insert(0, HTML_DIR)

TEMPLATE_PATH = os.path.join(HTML_DIR, "template.html")


class TestBuildModuleExists:
    """The build module is importable and has the expected API."""

    def test_build_module_importable(self):
        import build
        assert hasattr(build, "assemble_html")

    def test_build_has_strip_typescript_types(self):
        import build
        assert hasattr(build, "strip_typescript_types")

    def test_build_has_embed_python_as_js_string(self):
        import build
        assert hasattr(build, "embed_python_as_js_string")

    def test_build_has_make_inline_wasm_glue(self):
        import build
        assert hasattr(build, "make_inline_wasm_glue")


class TestTypeScriptStripping:
    """TypeScript type annotations are stripped for browser compatibility."""

    def test_strips_interface_declarations(self):
        from build import strip_typescript_types
        ts = "interface Foo {\n    bar: string;\n    baz?: number;\n}\nfunction hello() { return 1; }"
        js = strip_typescript_types(ts)
        assert "interface" not in js
        assert "function hello()" in js

    def test_strips_type_annotations_from_params(self):
        from build import strip_typescript_types
        ts = "function greet(name: string, age: number): void {"
        js = strip_typescript_types(ts)
        assert "function greet(name, age)" in js
        assert ": string" not in js
        assert ": number" not in js
        assert ": void" not in js

    def test_strips_return_type_promise(self):
        from build import strip_typescript_types
        ts = "async function search(q: string): Promise<ToolResult> {"
        js = strip_typescript_types(ts)
        assert ": Promise<ToolResult>" not in js
        assert "async function search(q)" in js

    def test_strips_as_any_casts(self):
        from build import strip_typescript_types
        ts = "(window as any).tsWebResearch = tsWebResearch;"
        js = strip_typescript_types(ts)
        assert "as any" not in js
        assert "window" in js

    def test_strips_catch_type_annotation(self):
        from build import strip_typescript_types
        ts = "} catch (e: any) {"
        js = strip_typescript_types(ts)
        assert ": any" not in js
        assert "} catch (e) {" in js

    def test_strips_variable_type_annotations(self):
        from build import strip_typescript_types
        ts = "const results: any = {"
        js = strip_typescript_types(ts)
        assert ": any = " not in js

    def test_preserves_template_literals(self):
        from build import strip_typescript_types
        ts = "const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json`;"
        js = strip_typescript_types(ts)
        assert "encodeURIComponent(query)" in js

    def test_real_web_research_file_strips_cleanly(self):
        """The actual web-research.ts should strip without breaking."""
        from build import strip_typescript_types
        ts_path = os.path.join(ROOT_DIR, "typescript", "web-research.ts")
        with open(ts_path) as f:
            ts_content = f.read()
        js = strip_typescript_types(ts_content)
        assert "interface WebResearchInput" not in js
        assert "interface ToolResult" not in js
        assert "async function tsWebResearch" in js
        assert "window" in js


class TestPythonEmbedding:
    """Python source is embedded as a JavaScript string constant."""

    def test_embeds_as_script_tag(self):
        from build import embed_python_as_js_string
        py = 'def hello():\n    return "world"'
        result = embed_python_as_js_string(py)
        assert "<script" in result
        assert "pyCodeAnalysisSource" in result
        assert "hello" in result

    def test_escapes_backticks(self):
        from build import embed_python_as_js_string
        py = 'x = f"`test`"'
        result = embed_python_as_js_string(py)
        assert "\\`" in result

    def test_escapes_dollar_braces(self):
        from build import embed_python_as_js_string
        py = 'x = "${y}"'
        result = embed_python_as_js_string(py)
        assert "\\${" in result


class TestWasmGlueInlining:
    """The wasm-pack JS glue is modified for inline use (no ES modules)."""

    def test_removes_export_keywords(self):
        from build import make_inline_wasm_glue
        js = 'export function foo() { return 1; }\nexport { initSync, __wbg_init as default };'
        result = make_inline_wasm_glue(js)
        assert "export function" not in result
        assert "export {" not in result
        assert "function foo()" in result

    def test_removes_import_meta_url(self):
        from build import make_inline_wasm_glue
        js = "module_or_path = new URL('wasm_agent_bg.wasm', import.meta.url);"
        result = make_inline_wasm_glue(js)
        assert "import.meta.url" not in result


class TestAssembleHTML:
    """The assemble_html function replaces placeholders correctly."""

    def test_replaces_go_wasm_runtime_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: Go WASM runtime" not in html

    def test_replaces_go_wasm_binary_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: Go WASM binary" not in html

    def test_replaces_typescript_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: TypeScript tools" not in html
        assert "tsWebResearch" in html

    def test_replaces_python_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: Python code_analysis" not in html
        assert "pyCodeAnalysisSource" in html

    def test_replaces_bridge_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: JavaScript bridge" not in html
        assert "amplifier_execute_tool" in html

    def test_replaces_rust_wasm_placeholder(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER: Rust WASM binary" not in html
        assert "rust-wasm-b64" in html

    def test_no_placeholders_remain(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "<!-- PLACEHOLDER:" not in html

    def test_rust_wasm_base64_present(self):
        """The Rust WASM binary should be base64-encoded inline."""
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert 'id="rust-wasm-b64"' in html
        # Base64 of wasm magic number \x00asm => AGFzbQ
        assert "AGFzbQ" in html

    def test_boot_function_has_rust_init(self):
        """The boot function should have actual Rust WASM init code."""
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "rust-wasm-b64" in html
        assert "initSync" in html

    def test_boot_function_has_pyodide_init(self):
        """The boot function should have Pyodide loading code."""
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "loadPyodide" in html
        assert "pyodideInstance" in html

    def test_output_is_valid_html(self):
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_go_unavailable_shows_stub(self):
        """When Go WASM is not available, a stub message should appear."""
        from build import assemble_html
        html = assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)
        assert "Go WASM not available" in html or "goWasmReady" in html
