"""Tests for the browser chat UI template (Task 6.2).

Validates that template.html contains the required UI structure,
boot sequence, chat interface, and integration points.
"""
import os
import re
import pytest

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "template.html")


@pytest.fixture
def template_html():
    """Read template.html contents."""
    with open(TEMPLATE_PATH) as f:
        return f.read()


class TestHTMLStructure:
    """Tests for basic HTML document structure."""

    def test_is_valid_html5(self, template_html):
        assert "<!DOCTYPE html>" in template_html

    def test_has_html_lang(self, template_html):
        assert '<html lang="en">' in template_html

    def test_has_charset_meta(self, template_html):
        assert 'charset="UTF-8"' in template_html

    def test_has_viewport_meta(self, template_html):
        assert "viewport" in template_html

    def test_has_title(self, template_html):
        assert "<title>" in template_html
        assert "Amplifier" in template_html or "Polyglot" in template_html

    def test_has_style_section(self, template_html):
        assert "<style>" in template_html

    def test_has_body(self, template_html):
        assert "<body>" in template_html


class TestChatInterface:
    """Tests for the chat message interface."""

    def test_has_messages_container(self, template_html):
        """Must have a messages container for chat bubbles."""
        assert 'id="messages"' in template_html

    def test_has_input_field(self, template_html):
        """Must have a text input for the user to type messages."""
        assert 'id="input"' in template_html

    def test_has_send_button(self, template_html):
        """Must have a send button."""
        assert 'id="send"' in template_html

    def test_input_starts_disabled(self, template_html):
        """Input should start disabled (enabled after boot completes)."""
        # The input element should have disabled attribute
        input_match = re.search(r'<input[^>]*id="input"[^>]*>', template_html)
        assert input_match, "Input element not found"
        assert "disabled" in input_match.group(0), \
            "Input should start disabled until boot completes"

    def test_send_button_starts_disabled(self, template_html):
        """Send button should start disabled."""
        btn_match = re.search(r'<button[^>]*id="send"[^>]*>', template_html)
        assert btn_match, "Send button not found"
        assert "disabled" in btn_match.group(0), \
            "Send button should start disabled until boot completes"

    def test_has_welcome_message(self, template_html):
        """Should show a welcome message with tool descriptions."""
        assert "Welcome" in template_html or "welcome" in template_html

    def test_welcome_mentions_four_languages(self, template_html):
        """Welcome message should mention Rust, TypeScript, Python, Go."""
        assert "Rust" in template_html
        assert "TypeScript" in template_html
        assert "Python" in template_html
        assert "Go" in template_html


class TestLanguageBadges:
    """Tests for language badge styling."""

    def test_has_rust_badge(self, template_html):
        assert "badge" in template_html and "rust" in template_html.lower()

    def test_has_typescript_badge(self, template_html):
        assert "badge" in template_html and ("ts" in template_html or "typescript" in template_html.lower())

    def test_has_python_badge(self, template_html):
        assert "badge" in template_html and "python" in template_html.lower()

    def test_has_go_badge(self, template_html):
        assert "badge" in template_html and "go" in template_html.lower()


class TestProgressAndStatus:
    """Tests for the boot progress and status bar."""

    def test_has_status_bar(self, template_html):
        """Must have a status bar showing boot/runtime progress."""
        assert 'id="status"' in template_html or 'class="status-bar"' in template_html

    def test_has_status_text(self, template_html):
        """Must have a status text element."""
        assert 'id="status-text"' in template_html

    def test_has_progress_indicator(self, template_html):
        """Must have a progress bar or indicator."""
        assert 'id="progress"' in template_html or "progress" in template_html


class TestBootSequence:
    """Tests for the boot sequence JavaScript."""

    def test_has_boot_function(self, template_html):
        """Must define a boot() function."""
        assert re.search(r"(async\s+)?function\s+boot\s*\(", template_html), \
            "Must define a boot() function"

    def test_boot_loads_webllm(self, template_html):
        """Boot sequence must call initWebLLM."""
        assert "initWebLLM" in template_html, \
            "Boot must call initWebLLM to load the AI model"

    def test_boot_uses_phi_model(self, template_html):
        """Boot must load the Phi-3.5-mini model by default."""
        assert "Phi-3.5-mini-instruct" in template_html or "Phi-3" in template_html, \
            "Boot must use the Phi-3.5-mini model"

    def test_has_set_status_function(self, template_html):
        """Must have a setStatus function for progress updates."""
        assert "setStatus" in template_html


class TestEventHandlers:
    """Tests for UI event handlers."""

    def test_send_message_handler(self, template_html):
        """Must have a sendMessage function."""
        assert "sendMessage" in template_html

    def test_enter_key_sends(self, template_html):
        """Enter key should trigger send."""
        assert "Enter" in template_html

    def test_click_sends(self, template_html):
        """Click on send button should trigger send."""
        assert "click" in template_html

    def test_add_message_function(self, template_html):
        """Must have an addMessage function for rendering messages."""
        assert "addMessage" in template_html


class TestToolVisualization:
    """Tests for tool call visualization in the UI."""

    def test_has_tool_call_styling(self, template_html):
        """Must have CSS for tool-call visualization."""
        assert "tool-call" in template_html

    def test_tool_language_mapping(self, template_html):
        """Must map tool names to their languages."""
        assert "data_transform" in template_html
        assert "web_research" in template_html
        assert "code_analysis" in template_html
        assert "document_builder" in template_html

    def test_get_tool_language_function(self, template_html):
        """Must have a function to get tool language from name."""
        assert "getToolLanguage" in template_html


class TestMarkdownRendering:
    """Tests for basic markdown rendering."""

    def test_has_render_markdown_function(self, template_html):
        """Must have a renderMarkdown function."""
        assert "renderMarkdown" in template_html

    def test_renders_bold(self, template_html):
        """Markdown renderer must convert bold markers to <b> tags."""
        # The renderer uses a regex like /\*\*(.+?)\*\*/g -> '<b>$1</b>'
        assert "<b>" in template_html, "Markdown renderer must produce <b> bold tags"


class TestPlaceholders:
    """Tests for build script integration points."""

    def test_has_placeholder_comments(self, template_html):
        """Must have PLACEHOLDER comments for build script injection."""
        assert "PLACEHOLDER" in template_html, \
            "Template must have PLACEHOLDER comments for the build script (Milestone 7)"

    def test_dark_theme(self, template_html):
        """Must use a dark theme."""
        # Check for dark background colors
        assert re.search(r"background:\s*#1[0-9a-f]{5}", template_html) or \
               re.search(r"background:\s*#0[0-9a-f]{5}", template_html), \
            "Must use a dark theme (dark background color)"
