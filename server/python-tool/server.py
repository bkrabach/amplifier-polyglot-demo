"""gRPC server wrapping the code_analysis Python tool.

Implements the ToolService proto (GetSpec + Execute) for the
code_analysis module, making it callable from any gRPC client
(Python, Rust, Go, etc.).
"""
import grpc
import json
import sys
import os
from concurrent import futures

# Add paths where code_analysis might live:
# 1. Running locally from repo root: ../../python
# 2. Running inside Docker container: /app/python
_here = os.path.dirname(os.path.abspath(__file__))
for candidate in [
    os.path.join(_here, "..", "..", "python"),  # local dev
    "/app/python",                               # Docker container
]:
    candidate = os.path.abspath(candidate)
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

import amplifier_module_pb2
import amplifier_module_pb2_grpc


class CodeAnalysisService(amplifier_module_pb2_grpc.ToolServiceServicer):
    """Wraps the Python code_analysis tool as a gRPC ToolService."""

    def GetSpec(self, request, context):
        return amplifier_module_pb2.ToolSpec(
            name="code_analysis",
            description=(
                "Analyzes Python source code using the ast module. "
                "Computes complexity, extracts function signatures, "
                "and identifies structural patterns."
            ),
            parameters_json=json.dumps({
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["analyze", "complexity", "signatures"],
                        "description": "Analysis action to perform",
                    },
                    "code": {
                        "type": "string",
                        "description": "Python source code to analyze",
                    },
                },
                "required": ["code"],
            }),
        )

    def Execute(self, request, context):
        try:
            input_data = json.loads(request.input.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return amplifier_module_pb2.ToolExecuteResponse(
                success=False,
                error=f"Invalid JSON input: {e}",
            )

        from code_analysis import execute

        result = execute(input_data)

        if result.get("success", False):
            output = result.get("output", result)
            return amplifier_module_pb2.ToolExecuteResponse(
                success=True,
                output=json.dumps(output).encode("utf-8"),
                content_type="application/json",
            )
        else:
            return amplifier_module_pb2.ToolExecuteResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                content_type="application/json",
            )


def serve(port=50053):
    """Start the gRPC server on the given port."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    amplifier_module_pb2_grpc.add_ToolServiceServicer_to_server(
        CodeAnalysisService(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    print(f"Python code_analysis gRPC service listening on :{port}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="code_analysis gRPC server")
    parser.add_argument("--port", type=int, default=50053, help="Port to listen on")
    args = parser.parse_args()
    serve(port=args.port)
