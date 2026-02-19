"""Integration test for the polyglot gRPC services.

Tests both the Go document_builder and Python code_analysis
gRPC services by calling GetSpec and Execute on each.

Usage:
    # With docker compose running:
    docker compose up -d
    python3 server/test_polyglot.py
    docker compose down

    # Or with services started manually:
    python3 server/test_polyglot.py
"""
import grpc
import json
import sys
import os

# Add the python-tool directory so the generated stubs are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python-tool"))

from amplifier_module_pb2 import Empty, ToolExecuteRequest
from amplifier_module_pb2_grpc import ToolServiceStub


def test_service(name, port, test_input):
    """Test a single gRPC ToolService: GetSpec + Execute.

    Args:
        name: Display name for the service
        port: Port the service is listening on
        test_input: Dict to send as Execute input

    Returns:
        True if all checks pass, False otherwise
    """
    passed = True
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = ToolServiceStub(channel)

    # Test GetSpec
    try:
        spec = stub.GetSpec(Empty(), timeout=5)
        print(f"  [{name}] GetSpec: name={spec.name}, desc={spec.description[:60]}...")
        assert spec.name, f"GetSpec returned empty name for {name}"
        assert spec.description, f"GetSpec returned empty description for {name}"
        params = json.loads(spec.parameters_json)
        assert params.get("type") == "object", f"parameters_json is not a JSON Schema object for {name}"
        print(f"  [{name}] GetSpec: PASS")
    except Exception as e:
        print(f"  [{name}] GetSpec: FAIL — {e}")
        passed = False

    # Test Execute
    try:
        input_bytes = json.dumps(test_input).encode("utf-8")
        request = ToolExecuteRequest(input=input_bytes, content_type="application/json")
        response = stub.Execute(request, timeout=10)

        output = response.output.decode("utf-8") if response.output else ""
        print(f"  [{name}] Execute: success={response.success}, output_len={len(output)}")

        if response.success:
            parsed = json.loads(output)
            preview = json.dumps(parsed, indent=None)[:200]
            print(f"  [{name}] Output preview: {preview}...")
            print(f"  [{name}] Execute: PASS")
        else:
            print(f"  [{name}] Execute: FAIL — error={response.error}")
            passed = False
    except Exception as e:
        print(f"  [{name}] Execute: FAIL — {e}")
        passed = False

    channel.close()
    return passed


def main():
    all_passed = True

    # Test Go document_builder on :50052
    print("\n=== Testing Go document_builder on :50052 ===")
    go_input = {
        "template": "summary",
        "title": "Polyglot Test",
        "key_points": ["Point 1", "Point 2"],
        "conclusion": "Integration test passed.",
    }
    if not test_service("go-document-builder", 50052, go_input):
        all_passed = False

    # Test Python code_analysis on :50053
    print("\n=== Testing Python code_analysis on :50053 ===")
    py_input = {
        "action": "analyze",
        "code": "def hello(name: str) -> str:\n    return f'Hello {name}'",
    }
    if not test_service("python-code-analysis", 50053, py_input):
        all_passed = False

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("ALL POLYGLOT SERVICES WORKING!")
        return 0
    else:
        print("SOME SERVICES FAILED — see above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
