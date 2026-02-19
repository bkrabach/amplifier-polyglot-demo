#!/usr/bin/env python3
"""Build script for the Amplifier Polyglot Demo.

Assembles a single HTML file from template.html by replacing
placeholder comments with inlined content from each language's
source files and WASM binaries.

Usage:
    python3 html/build.py              # Build with defaults
    python3 html/build.py --no-go      # Skip Go WASM (if Go not installed)
"""

import base64
import os
import re


def strip_typescript_types(ts_source: str) -> str:
    """Strip TypeScript type annotations to produce valid JavaScript.

    Handles: interface blocks, parameter types, return types,
    variable type annotations, 'as any' casts, catch type annotations.
    """
    lines = ts_source.split("\n")
    result_lines = []
    in_interface = False
    brace_depth = 0

    for line in lines:
        stripped = line.strip()

        # Skip interface declarations (multi-line blocks)
        if re.match(r"^interface\s+\w+", stripped):
            in_interface = True
            brace_depth = 0

        if in_interface:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0 and "{" in line:
                in_interface = False
            elif brace_depth <= 0:
                in_interface = False
            continue

        # Strip 'as any' casts: (window as any) -> (window)
        line = re.sub(r"\bas\s+any\b", "", line)

        # Strip catch type annotations: catch (e: any) -> catch (e)
        line = re.sub(r"catch\s*\(\s*(\w+)\s*:\s*\w+\s*\)", r"catch (\1)", line)

        # Strip variable type annotations: const x: Type = -> const x =
        # Be careful not to strip object property types in literals
        line = re.sub(
            r"((?:const|let|var)\s+\w+)\s*:\s*[\w<>\[\]|&\s]+\s*=", r"\1 =", line
        )

        # Strip function return types: ): ReturnType { -> ) {
        line = re.sub(r"\)\s*:\s*[\w<>\[\]|&\s]+\s*\{", ") {", line)

        # Strip parameter type annotations in function signatures
        # Match function declarations and strip types from params
        def strip_param_types(match):
            prefix = match.group(1)  # async function name(
            params_str = match.group(2)
            suffix = match.group(3)  # )

            # Strip type annotations from each parameter
            params = []
            for param in params_str.split(","):
                param = param.strip()
                if not param:
                    continue
                # Remove type annotation: name: Type -> name
                # Also handle optional params: name?: Type -> name
                param = re.sub(r"\s*\??\s*:\s*[\w<>\[\]|&\s\"']+$", "", param)
                # Handle default values with types: name: Type = default
                param = re.sub(r"\s*:\s*[\w<>\[\]|&\s\"']+(\s*=)", r"\1", param)
                params.append(param)

            return prefix + ", ".join(params) + suffix

        line = re.sub(
            r"((?:async\s+)?function\s+\w+\s*\()([^)]*?)(\))",
            strip_param_types,
            line,
        )

        # Also handle arrow function params and method params with types
        # e.g., (t: any) => -> (t) =>
        line = re.sub(r"\((\w+)\s*:\s*\w+\)", r"(\1)", line)

        result_lines.append(line)

    return "\n".join(result_lines)


def embed_python_as_js_string(py_source: str) -> str:
    """Embed Python source as a JavaScript string constant in a script tag.

    Uses a JS template literal (backtick string), escaping backticks
    and ${} interpolation markers in the Python source.
    """
    # Escape backticks and ${} for JS template literal
    escaped = py_source.replace("\\", "\\\\")
    escaped = escaped.replace("`", "\\`")
    escaped = escaped.replace("${", "\\${")

    return f"<script>\nconst pyCodeAnalysisSource = `{escaped}`;\n</script>"


def make_inline_wasm_glue(js_glue: str) -> str:
    """Modify wasm-pack generated JS glue for inline (non-module) use.

    Removes ES module export/import syntax so the code works in a
    regular <script> tag inside the single HTML file.
    """
    # Remove export keywords from function declarations
    result = re.sub(r"^export\s+function\s+", "function ", js_glue, flags=re.MULTILINE)
    result = re.sub(
        r"^export\s+async\s+function\s+", "async function ", result, flags=re.MULTILINE
    )

    # Remove export { ... } lines
    result = re.sub(r"^export\s*\{[^}]*\}\s*;?\s*$", "", result, flags=re.MULTILINE)

    # Remove import.meta.url references (replace with empty/null)
    result = re.sub(
        r"module_or_path\s*=\s*new\s+URL\([^)]*import\.meta\.url[^)]*\)\s*;",
        "// URL auto-detection removed for inline use",
        result,
    )

    return result


def _read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()


def _read_binary(path: str) -> bytes:
    """Read a binary file and return its contents."""
    with open(path, "rb") as f:
        return f.read()


def _base64_encode(data: bytes) -> str:
    """Base64 encode binary data to a string."""
    return base64.b64encode(data).decode("ascii")


def assemble_html(
    root_dir: str,
    go_wasm_available: bool = False,
    go_wasm_dir: str | None = None,
) -> str:
    """Assemble the single HTML file from template + inlined assets.

    Args:
        root_dir: Path to the amplifier-polyglot-demo root directory
        go_wasm_available: Whether Go WASM binary is available
        go_wasm_dir: Path to directory containing document_builder.wasm
                     and wasm_exec.js

    Returns:
        The assembled HTML string with all placeholders replaced.
    """
    html_dir = os.path.join(root_dir, "html")
    template_path = os.path.join(html_dir, "template.html")

    # Read template
    html = _read_file(template_path)

    # --- 1. Go WASM runtime (wasm_exec.js) ---
    if go_wasm_available and go_wasm_dir:
        wasm_exec_path = os.path.join(go_wasm_dir, "wasm_exec.js")
        go_runtime = f"<script>\n{_read_file(wasm_exec_path)}\n</script>"
    else:
        go_runtime = (
            "<script>\n"
            "// Go WASM not available — document_builder tool disabled\n"
            "console.warn('Go WASM runtime not included in this build');\n"
            "</script>"
        )
    html = html.replace(
        "<!-- PLACEHOLDER: Go WASM runtime (wasm_exec.js) -->",
        go_runtime,
    )

    # --- 2. Go WASM binary (base64) ---
    if go_wasm_available and go_wasm_dir:
        go_wasm_path = os.path.join(go_wasm_dir, "document_builder.wasm")
        go_wasm_b64 = _base64_encode(_read_binary(go_wasm_path))
        go_binary = f'<script id="go-wasm-b64" type="text/plain">{go_wasm_b64}</script>'
    else:
        go_binary = (
            '<script id="go-wasm-b64" type="text/plain">'
            "<!-- Go WASM not available -->"
            "</script>"
        )
    html = html.replace(
        "<!-- PLACEHOLDER: Go WASM binary (base64) -->",
        go_binary,
    )

    # --- 3. TypeScript tools (strip types for browser) ---
    ts_path = os.path.join(root_dir, "typescript", "web-research.ts")
    ts_source = _read_file(ts_path)
    ts_js = strip_typescript_types(ts_source)
    ts_block = f"<script>\n{ts_js}\n</script>"
    html = html.replace(
        "<!-- PLACEHOLDER: TypeScript tools (web-research.js) -->",
        ts_block,
    )

    # --- 4. Python code_analysis.py (as JS string for Pyodide) ---
    py_path = os.path.join(root_dir, "python", "code_analysis.py")
    py_source = _read_file(py_path)
    py_block = embed_python_as_js_string(py_source)
    html = html.replace(
        "<!-- PLACEHOLDER: Python code_analysis.py (as string for Pyodide) -->",
        py_block,
    )

    # --- 5. JavaScript bridge (bridge.js) ---
    bridge_path = os.path.join(html_dir, "bridge.js")
    bridge_js = _read_file(bridge_path)
    bridge_block = f"<script>\n{bridge_js}\n</script>"
    html = html.replace(
        "<!-- PLACEHOLDER: JavaScript bridge (bridge.js) -->",
        bridge_block,
    )

    # --- 6. Rust WASM binary (base64) + inlined JS glue ---
    pkg_dir = os.path.join(html_dir, "pkg")
    wasm_path = os.path.join(pkg_dir, "wasm_agent_bg.wasm")
    glue_path = os.path.join(pkg_dir, "wasm_agent.js")

    rust_wasm_b64 = _base64_encode(_read_binary(wasm_path))
    rust_glue = _read_file(glue_path)
    rust_glue_inline = make_inline_wasm_glue(rust_glue)

    rust_block = (
        f'<script id="rust-wasm-b64" type="text/plain">{rust_wasm_b64}</script>\n'
        f"<script>\n{rust_glue_inline}\n</script>"
    )
    html = html.replace(
        "<!-- PLACEHOLDER: Rust WASM binary (base64 from wasm-pack) -->",
        rust_block,
    )

    # --- 7. Inject boot sequence initialization code ---
    # Replace placeholder comments in the boot() function with actual init code
    html = _inject_boot_code(html, go_wasm_available)

    return html


def _inject_boot_code(html: str, go_wasm_available: bool) -> str:
    """Inject actual initialization code into the boot() function.

    Replaces the placeholder comments in boot() with real code that:
    - Decodes base64 Rust WASM and initializes via initSync
    - Optionally decodes and runs Go WASM
    - Loads Pyodide from CDN and runs the Python code
    - Sets up window.wasmAgent
    """
    # Rust WASM init
    rust_init = """
            // Decode and initialize Rust WASM kernel
            const rustWasmB64 = document.getElementById('rust-wasm-b64').textContent;
            const rustWasmBytes = Uint8Array.from(atob(rustWasmB64), c => c.charCodeAt(0));
            initSync(rustWasmBytes);
            window.wasmAgent = { execute_prompt, get_tool_specs, execute_tool, kernel_version };
            console.log('Rust WASM kernel loaded, version:', kernel_version());"""

    html = html.replace(
        "            // WASM init happens here (injected by build script)",
        rust_init,
    )

    # Go WASM init
    if go_wasm_available:
        go_init = """
            // Decode and initialize Go WASM document builder
            const goWasmB64 = document.getElementById('go-wasm-b64').textContent;
            const goWasmBytes = Uint8Array.from(atob(goWasmB64), c => c.charCodeAt(0));
            const go = new Go();
            const goResult = await WebAssembly.instantiate(goWasmBytes, go.importObject);
            go.run(goResult.instance);
            console.log('Go WASM document builder loaded');"""
    else:
        go_init = """
            // Go WASM not available — skipping document_builder
            window.goWasmReady = false;
            console.warn('Go WASM not included — document_builder tool disabled');"""

    html = html.replace(
        "            // Go WASM init happens here (injected by build script)",
        go_init,
    )

    # Pyodide init
    pyodide_init = """
            // Load Pyodide from CDN and run the code_analysis module
            const pyodideScript = document.createElement('script');
            pyodideScript.src = 'https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js';
            document.head.appendChild(pyodideScript);
            await new Promise((resolve, reject) => {
                pyodideScript.onload = resolve;
                pyodideScript.onerror = reject;
            });
            const pyodide = await loadPyodide();
            await pyodide.runPythonAsync(pyCodeAnalysisSource);
            window.pyodideInstance = pyodide;
            console.log('Pyodide loaded with code_analysis module');"""

    html = html.replace(
        "            // Pyodide loading happens here (injected by build script)",
        pyodide_init,
    )

    return html


def main():
    """CLI entry point: build the assembled HTML file."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build the Amplifier Polyglot Demo HTML"
    )
    parser.add_argument(
        "--no-go",
        action="store_true",
        help="Skip Go WASM (if Go is not installed)",
    )
    parser.add_argument(
        "--go-wasm-dir",
        type=str,
        default=None,
        help="Directory containing document_builder.wasm and wasm_exec.js",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Root directory of the amplifier-polyglot-demo repo",
    )
    args = parser.parse_args()

    # Determine root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = args.root or os.path.dirname(script_dir)

    go_wasm_available = not args.no_go and args.go_wasm_dir is not None
    go_wasm_dir = args.go_wasm_dir

    print("=== Assembling Amplifier Polyglot Demo ===")
    print(f"Root: {root_dir}")
    print(f"Go WASM: {'enabled' if go_wasm_available else 'disabled'}")

    html = assemble_html(
        root_dir=root_dir,
        go_wasm_available=go_wasm_available,
        go_wasm_dir=go_wasm_dir,
    )

    # Write output
    out_path = os.path.join(root_dir, "html", "amplifier-polyglot-agent.html")
    with open(out_path, "w") as f:
        f.write(html)

    size_bytes = os.path.getsize(out_path)
    size_kb = size_bytes / 1024
    size_mb = size_bytes / (1024 * 1024)

    print("\n=== Build complete ===")
    print(f"Output: {out_path}")
    if size_mb >= 1:
        print(f"Size: {size_mb:.1f} MB ({size_bytes:,} bytes)")
    else:
        print(f"Size: {size_kb:.1f} KB ({size_bytes:,} bytes)")


if __name__ == "__main__":
    main()
