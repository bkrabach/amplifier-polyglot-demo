"""Tests for the Python code_analysis tool.

These tests verify the ast-based code analysis runs correctly
outside the browser (native Python), ensuring correctness before
it's loaded into Pyodide.
"""
import json
import sys
import os
import pytest

# Add parent directory to path so we can import code_analysis
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import code_analysis


# ---------------------------------------------------------------------------
# Test: execute() entry point
# ---------------------------------------------------------------------------

class TestExecuteEntryPoint:
    def test_execute_returns_dict(self):
        result = code_analysis.execute({"action": "analyze", "code": "x = 1"})
        assert isinstance(result, dict)

    def test_execute_requires_code(self):
        result = code_analysis.execute({"action": "analyze", "code": ""})
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_execute_unknown_action(self):
        result = code_analysis.execute({"action": "unknown", "code": "x = 1"})
        assert result["success"] is False
        assert "Unknown action" in result["error"]

    def test_execute_syntax_error_returns_graceful_fallback(self):
        """When code has syntax errors, return basic line metrics instead of failing."""
        result = code_analysis.execute({"action": "analyze", "code": "def foo(:"})
        assert result["success"] is True
        output = json.loads(result["output"])
        assert output["total_lines"] >= 1
        assert "non_empty_lines" in output
        assert "syntax_error" in output
        assert "note" in output
        assert "summary" in output
        assert output["functions"] == []
        assert output["classes"] == []
        assert output["imports"] == []

    def test_execute_syntax_error_multiline_fallback(self):
        """Syntax error fallback counts lines correctly for multi-line code."""
        bad_code = "x = 1\ny = 2\ndef broken(:\nz = 3\n"
        result = code_analysis.execute({"action": "analyze", "code": bad_code})
        assert result["success"] is True
        output = json.loads(result["output"])
        assert output["total_lines"] == 4
        assert output["non_empty_lines"] == 4

    def test_execute_entry_point_never_raises(self):
        """The execute entry point catches all exceptions and returns a dict."""
        # Even with bizarre input, execute should return a dict, never raise
        result = code_analysis.execute({"action": "analyze", "code": "x = 1"})
        assert isinstance(result, dict)
        assert "success" in result

    def test_execute_defaults_to_analyze(self):
        result = code_analysis.execute({"code": "x = 1"})
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Test: analyze action
# ---------------------------------------------------------------------------

class TestAnalyzeAction:
    SAMPLE_CODE = """
import os
from collections import Counter

class MyClass:
    def method_one(self, x: int) -> str:
        \"\"\"A method with a docstring.\"\"\"
        if x > 0:
            return str(x)
        return ""

    async def method_two(self):
        pass

def standalone(a, b, c):
    for i in range(a):
        if i > b:
            return c
    return 0
"""

    def test_analyze_finds_functions(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        assert result["success"] is True
        output = result["output"]
        func_names = [f["name"] for f in output["functions"]]
        assert "method_one" in func_names
        assert "method_two" in func_names
        assert "standalone" in func_names

    def test_analyze_finds_classes(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        output = result["output"]
        class_names = [c["name"] for c in output["classes"]]
        assert "MyClass" in class_names

    def test_analyze_finds_imports(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        output = result["output"]
        import_modules = [i["module"] for i in output["imports"]]
        assert "os" in import_modules
        assert "collections" in import_modules

    def test_analyze_includes_line_count(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        output = result["output"]
        assert output["line_count"] > 0

    def test_analyze_includes_summary(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        output = result["output"]
        assert "function_count" in output["summary"]
        assert "class_count" in output["summary"]
        assert output["summary"]["function_count"] == 3
        assert output["summary"]["class_count"] == 1

    def test_analyze_detects_async(self):
        result = code_analysis.execute({"action": "analyze", "code": self.SAMPLE_CODE})
        output = result["output"]
        async_funcs = [f for f in output["functions"] if f["async"]]
        assert len(async_funcs) == 1
        assert async_funcs[0]["name"] == "method_two"


# ---------------------------------------------------------------------------
# Test: complexity action
# ---------------------------------------------------------------------------

class TestComplexityAction:
    def test_complexity_basic(self):
        code = """
def simple():
    return 1

def complex_func(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                return i
    return 0
"""
        result = code_analysis.execute({"action": "complexity", "code": code})
        assert result["success"] is True
        output = result["output"]
        assert "simple" in output
        assert output["simple"]["complexity"] == 1
        assert output["simple"]["rating"] == "low"
        # complex_func has: base(1) + if(1) + for(1) + if(1) = 4
        assert output["complex_func"]["complexity"] >= 4

    def test_complexity_with_boolops(self):
        code = """
def multi_cond(a, b, c):
    if a and b or c:
        return True
    return False
"""
        result = code_analysis.execute({"action": "complexity", "code": code})
        output = result["output"]
        # base(1) + if(1) + (and adds 1, or adds 1) = 4
        assert output["multi_cond"]["complexity"] >= 3


# ---------------------------------------------------------------------------
# Test: signatures action
# ---------------------------------------------------------------------------

class TestSignaturesAction:
    def test_signatures_basic(self):
        code = """
def greet(name: str, times: int = 1) -> str:
    \"\"\"Greet someone.\"\"\"
    return name * times

async def fetch_data(url: str) -> dict:
    pass
"""
        result = code_analysis.execute({"action": "signatures", "code": code})
        assert result["success"] is True
        sigs = result["output"]
        assert len(sigs) == 2

        greet_sig = next(s for s in sigs if s["name"] == "greet")
        assert "name: str" in greet_sig["params"]
        assert "-> str" in greet_sig["return_type"]
        assert greet_sig["docstring"] == "Greet someone."
        assert greet_sig["async"] is False

        fetch_sig = next(s for s in sigs if s["name"] == "fetch_data")
        assert fetch_sig["async"] is True


# ---------------------------------------------------------------------------
# Test: pattern detection
# ---------------------------------------------------------------------------

class TestPatternDetection:
    def test_detects_recursion(self):
        code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        result = code_analysis.execute({"action": "analyze", "code": code})
        patterns = result["output"]["patterns"]
        pattern_types = [p["type"] for p in patterns]
        assert "recursion" in pattern_types

    def test_detects_comprehension(self):
        code = """
def make_list():
    return [x**2 for x in range(10)]
"""
        result = code_analysis.execute({"action": "analyze", "code": code})
        patterns = result["output"]["patterns"]
        pattern_types = [p["type"] for p in patterns]
        assert "comprehension" in pattern_types

    def test_detects_abstract_class(self):
        code = """
from abc import ABC

class Base(ABC):
    pass
"""
        result = code_analysis.execute({"action": "analyze", "code": code})
        patterns = result["output"]["patterns"]
        pattern_types = [p["type"] for p in patterns]
        assert "abstract_class" in pattern_types

    def test_detects_decorator(self):
        code = """
import functools

@functools.lru_cache
def cached(n):
    return n * 2
"""
        result = code_analysis.execute({"action": "analyze", "code": code})
        patterns = result["output"]["patterns"]
        pattern_types = [p["type"] for p in patterns]
        assert "decorator" in pattern_types


# ---------------------------------------------------------------------------
# Test: pyCodeAnalysis JSON entry point (for Pyodide bridge)
# ---------------------------------------------------------------------------

class TestPyCodeAnalysisEntryPoint:
    def test_pyCodeAnalysis_accepts_json_string(self):
        input_json = json.dumps({"action": "analyze", "code": "x = 1"})
        result_json = code_analysis.pyCodeAnalysis(input_json)
        result = json.loads(result_json)
        assert result["success"] is True

    def test_pyCodeAnalysis_accepts_dict(self):
        result_json = code_analysis.pyCodeAnalysis({"action": "analyze", "code": "x = 1"})
        result = json.loads(result_json)
        assert result["success"] is True

    def test_pyCodeAnalysis_returns_valid_json(self):
        input_json = json.dumps({"action": "complexity", "code": "def f(): pass"})
        result_json = code_analysis.pyCodeAnalysis(input_json)
        # Must be valid JSON
        result = json.loads(result_json)
        assert isinstance(result, dict)
