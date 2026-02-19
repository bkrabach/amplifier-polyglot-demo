#!/bin/bash
# test-polyglot.sh — Start services, run integration tests, tear down.
#
# Usage:
#   ./server/test-polyglot.sh          # Full lifecycle
#   ./server/test-polyglot.sh --no-down  # Leave services running after test
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
NO_DOWN=false

for arg in "$@"; do
    case "$arg" in
        --no-down) NO_DOWN=true ;;
    esac
done

cleanup() {
    if [ "$NO_DOWN" = false ]; then
        echo ""
        echo "=== Tearing down docker compose ==="
        cd "$ROOT" && docker compose down 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "=== Building and starting polyglot services ==="
cd "$ROOT"
docker compose up -d --build

echo ""
echo "=== Waiting for services to be ready ==="
# Wait for Go service on :50052
for i in $(seq 1 30); do
    if python3 -c "
import grpc, sys
sys.path.insert(0, '$ROOT/server/python-tool')
from amplifier_module_pb2 import Empty
from amplifier_module_pb2_grpc import ToolServiceStub
try:
    ch = grpc.insecure_channel('localhost:50052')
    ToolServiceStub(ch).GetSpec(Empty(), timeout=2)
    print('  Go service ready on :50052')
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
        break
    fi
    echo "  Waiting for Go service... ($i/30)"
    sleep 2
done

# Wait for Python service on :50053
for i in $(seq 1 30); do
    if python3 -c "
import grpc, sys
sys.path.insert(0, '$ROOT/server/python-tool')
from amplifier_module_pb2 import Empty
from amplifier_module_pb2_grpc import ToolServiceStub
try:
    ch = grpc.insecure_channel('localhost:50053')
    ToolServiceStub(ch).GetSpec(Empty(), timeout=2)
    print('  Python service ready on :50053')
    sys.exit(0)
except:
    sys.exit(1)
" 2>/dev/null; then
        break
    fi
    echo "  Waiting for Python service... ($i/30)"
    sleep 2
done

echo ""
echo "=== Running integration tests ==="
python3 "$ROOT/server/test_polyglot.py"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=== Integration tests PASSED ==="
else
    echo ""
    echo "=== Integration tests FAILED ==="
    echo "Docker compose logs:"
    docker compose logs --tail=20 2>/dev/null || true
fi

exit $EXIT_CODE
