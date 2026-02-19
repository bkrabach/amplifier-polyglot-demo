"""Tests for the Cache API polyfill and secure context fixes.

Validates that:
1. cache-polyfill.js exists with correct in-memory fallback
2. template.html has secure context check in boot()
3. build.py inlines the polyfill BEFORE other scripts
4. bridge.js has WebGPU guard in initWebLLM
5. README documents the local server requirement
"""

import os
import re
import sys

import pytest

HTML_DIR = os.path.join(os.path.dirname(__file__), "..")
ROOT_DIR = os.path.join(HTML_DIR, "..")
sys.path.insert(0, HTML_DIR)

POLYFILL_PATH = os.path.join(HTML_DIR, "cache-polyfill.js")
TEMPLATE_PATH = os.path.join(HTML_DIR, "template.html")
BRIDGE_PATH = os.path.join(HTML_DIR, "bridge.js")
README_PATH = os.path.join(ROOT_DIR, "README.md")


# ---- Fixtures ----


@pytest.fixture
def polyfill_js():
    """Read cache-polyfill.js contents."""
    with open(POLYFILL_PATH) as f:
        return f.read()


@pytest.fixture
def template_html():
    """Read template.html contents."""
    with open(TEMPLATE_PATH) as f:
        return f.read()


@pytest.fixture
def bridge_js():
    """Read bridge.js contents."""
    with open(BRIDGE_PATH) as f:
        return f.read()


@pytest.fixture
def readme_md():
    """Read README.md contents."""
    with open(README_PATH) as f:
        return f.read()


@pytest.fixture(scope="module")
def assembled_html():
    """Build the assembled HTML for end-to-end checks."""
    from build import assemble_html

    return assemble_html(root_dir=ROOT_DIR, go_wasm_available=False)


# ---- Fix 1: cache-polyfill.js ----


class TestCachePolyfillFile:
    """cache-polyfill.js provides an in-memory Cache API fallback."""

    def test_polyfill_file_exists(self):
        assert os.path.exists(POLYFILL_PATH), "cache-polyfill.js must exist"

    def test_polyfill_is_es5_no_arrow_functions(self, polyfill_js):
        """Must use ES5-compatible syntax - no arrow functions."""
        lines = polyfill_js.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            assert "=>" not in line, (
                f"Arrow function found on line {i}: {line.strip()}"
            )

    def test_polyfill_is_es5_no_class_syntax(self, polyfill_js):
        """Must use ES5-compatible syntax - no class keyword."""
        assert not re.search(
            r"\bclass\s+\w+", polyfill_js
        ), "Must not use class syntax (ES5 compatibility)"

    def test_polyfill_provides_caches_global(self, polyfill_js):
        """Must install window.caches as a fallback."""
        assert "window.caches" in polyfill_js

    def test_polyfill_has_fake_cache_storage(self, polyfill_js):
        """Must implement CacheStorage-like open/has/delete/keys/match."""
        for method in ["open", "has", "delete", "keys", "match"]:
            assert (
                f".prototype.{method}" in polyfill_js
                or f'"{method}"' in polyfill_js
            ), f"FakeCacheStorage must implement {method}"

    def test_polyfill_has_fake_cache(self, polyfill_js):
        """Must implement Cache-like match/put/add/addAll/delete/keys."""
        for method in ["match", "put", "add", "addAll", "delete", "keys"]:
            assert method in polyfill_js, f"FakeCache must implement {method}"

    def test_polyfill_detects_blocked_cache_api(self, polyfill_js):
        """Must probe the real Cache API and fall back if blocked."""
        assert "__probe__" in polyfill_js or "caches.open" in polyfill_js

    def test_polyfill_logs_warning(self, polyfill_js):
        """Must warn the user that models will re-download."""
        assert "console.warn" in polyfill_js

    def test_polyfill_is_iife(self, polyfill_js):
        """Must be wrapped in an IIFE to avoid polluting global scope."""
        assert "(function" in polyfill_js
        assert "})();" in polyfill_js or "}())" in polyfill_js


# ---- Fix 2: Secure context check in boot() ----


class TestSecureContextCheck:
    """template.html boot() must check for secure context."""

    def test_template_has_secure_context_check(self, template_html):
        """boot() must check window.isSecureContext."""
        assert "isSecureContext" in template_html, (
            "boot() must check isSecureContext for file:// detection"
        )

    def test_secure_context_check_shows_http_guidance(self, template_html):
        """Must tell users to use http:// when on file://."""
        assert "http://" in template_html or "http.server" in template_html, (
            "Must guide users to serve via HTTP"
        )

    def test_secure_context_check_is_early_in_boot(self, template_html):
        """The isSecureContext check must appear before initWebLLM call."""
        sc_pos = template_html.find("isSecureContext")
        webllm_pos = template_html.find("initWebLLM")
        assert sc_pos != -1, "isSecureContext not found"
        assert webllm_pos != -1, "initWebLLM not found"
        assert sc_pos < webllm_pos, (
            "isSecureContext check must come before initWebLLM"
        )


# ---- Fix 3: build.py inlines polyfill ----


class TestBuildPolyfillInlining:
    """build.py must inline cache-polyfill.js before other scripts."""

    def test_template_has_polyfill_placeholder(self, template_html):
        """template.html must have a placeholder for the polyfill."""
        assert "Cache API polyfill" in template_html

    def test_assembled_html_contains_polyfill(self, assembled_html):
        """Assembled output must contain the polyfill code."""
        assert "installCachePolyfill" in assembled_html or "FakeCache" in assembled_html

    def test_polyfill_before_webllm_import(self, assembled_html):
        """Polyfill must appear BEFORE any WebLLM import in the output."""
        polyfill_pos = assembled_html.find("installCachePolyfill")
        if polyfill_pos == -1:
            polyfill_pos = assembled_html.find("FakeCache")
        webllm_pos = assembled_html.find("esm.run/@mlc-ai/web-llm")
        assert polyfill_pos != -1, "Polyfill code not found in assembled HTML"
        assert webllm_pos != -1, "WebLLM import not found in assembled HTML"
        assert polyfill_pos < webllm_pos, (
            "Polyfill must appear before WebLLM import"
        )

    def test_polyfill_before_go_wasm_exec(self, assembled_html):
        """Polyfill must appear BEFORE Go wasm_exec.js in the output."""
        polyfill_pos = assembled_html.find("installCachePolyfill")
        if polyfill_pos == -1:
            polyfill_pos = assembled_html.find("FakeCache")
        # Go wasm_exec.js is the first placeholder replacement
        go_wasm_pos = assembled_html.find("Go WASM")
        assert polyfill_pos != -1, "Polyfill code not found in assembled HTML"
        assert polyfill_pos < go_wasm_pos, (
            "Polyfill must appear before Go WASM runtime"
        )

    def test_no_polyfill_placeholder_remains(self, assembled_html):
        """The polyfill placeholder must be replaced."""
        assert "<!-- PLACEHOLDER: Cache API polyfill -->" not in assembled_html


# ---- Fix 4: WebGPU guard in bridge.js ----


class TestWebGPUGuard:
    """bridge.js initWebLLM must check for WebGPU availability."""

    def test_init_webllm_checks_navigator_gpu(self, bridge_js):
        """initWebLLM must check navigator.gpu before loading WebLLM."""
        assert "navigator.gpu" in bridge_js, (
            "initWebLLM must check navigator.gpu availability"
        )

    def test_webgpu_check_throws_helpful_error(self, bridge_js):
        """Must throw a descriptive error when WebGPU is missing."""
        assert "WebGPU" in bridge_js, (
            "Error message must mention WebGPU"
        )


# ---- Fix 5: README update ----


class TestReadmeUpdate:
    """README.md must document the local server requirement."""

    def test_readme_mentions_http_server(self, readme_md):
        """README must mention running a local HTTP server."""
        assert "http.server" in readme_md or "localhost" in readme_md

    def test_readme_mentions_file_protocol_limitation(self, readme_md):
        """README must explain that file:// won't work."""
        assert "file://" in readme_md, (
            "README must explain file:// protocol limitation"
        )

    def test_readme_mentions_cache_api(self, readme_md):
        """README must mention Cache API as a reason for HTTP requirement."""
        assert "Cache API" in readme_md or "cache" in readme_md.lower()

    def test_readme_has_running_section(self, readme_md):
        """README must have a section about running the demo."""
        assert "Running" in readme_md or "running" in readme_md
