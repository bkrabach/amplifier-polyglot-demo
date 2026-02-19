"""Tests for the Python gRPC code_analysis service."""
import json
import sys
import os
import pytest

# Add the server directory to path so we can import the service module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Add the python directory so code_analysis is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "python"))


def test_server_module_importable():
    """server.py is importable and has CodeAnalysisService."""
    import server
    assert hasattr(server, "CodeAnalysisService")
    assert hasattr(server, "serve")


def test_get_spec_returns_correct_name():
    """GetSpec returns tool spec with name='code_analysis'."""
    import server
    service = server.CodeAnalysisService()
    spec = service.GetSpec(request=None, context=None)
    assert spec.name == "code_analysis"


def test_get_spec_returns_valid_parameters_json():
    """GetSpec returns valid JSON Schema in parameters_json."""
    import server
    service = server.CodeAnalysisService()
    spec = service.GetSpec(request=None, context=None)
    params = json.loads(spec.parameters_json)
    assert params["type"] == "object"
    assert "code" in params["properties"]


def test_get_spec_has_description():
    """GetSpec returns a non-empty description."""
    import server
    service = server.CodeAnalysisService()
    spec = service.GetSpec(request=None, context=None)
    assert len(spec.description) > 10


def test_execute_analyze_action():
    """Execute with analyze action returns function/class info."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({
        "action": "analyze",
        "code": "def hello():\n    return 'world'"
    }).encode("utf-8")

    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is True
    output = json.loads(response.output.decode("utf-8"))
    assert "functions" in output
    assert any(f["name"] == "hello" for f in output["functions"])


def test_execute_complexity_action():
    """Execute with complexity action returns complexity ratings."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({
        "action": "complexity",
        "code": "def simple(): pass\ndef complex_fn(x):\n    if x > 0:\n        for i in range(x):\n            if i % 2 == 0:\n                pass"
    }).encode("utf-8")

    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is True
    output = json.loads(response.output.decode("utf-8"))
    assert "simple" in output
    assert "complex_fn" in output


def test_execute_signatures_action():
    """Execute with signatures action returns function signatures."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({
        "action": "signatures",
        "code": "def greet(name: str) -> str:\n    return f'Hello {name}'"
    }).encode("utf-8")

    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is True
    output = json.loads(response.output.decode("utf-8"))
    assert len(output) == 1
    assert output[0]["name"] == "greet"
    assert "str" in output[0]["params"][0]


def test_execute_invalid_json():
    """Execute with invalid JSON returns error response."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    request = ToolExecuteRequest(input=b"not json", content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is False
    assert len(response.error) > 0


def test_execute_missing_code():
    """Execute without code field returns error."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({"action": "analyze"}).encode("utf-8")
    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is False
    assert "code" in response.error.lower() or "required" in response.error.lower()


def test_execute_syntax_error_code():
    """Execute with invalid Python code returns error."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({
        "action": "analyze",
        "code": "def broken(:\n    pass"
    }).encode("utf-8")
    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.success is False
    assert "syntax" in response.error.lower() or "error" in response.error.lower()


def test_response_content_type():
    """Execute response has application/json content_type."""
    import server
    from amplifier_module_pb2 import ToolExecuteRequest

    service = server.CodeAnalysisService()
    input_data = json.dumps({
        "action": "analyze",
        "code": "x = 1"
    }).encode("utf-8")
    request = ToolExecuteRequest(input=input_data, content_type="application/json")
    response = service.Execute(request, context=None)

    assert response.content_type == "application/json"
