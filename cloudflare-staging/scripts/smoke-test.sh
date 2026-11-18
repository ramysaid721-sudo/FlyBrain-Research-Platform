#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:?Usage: bash scripts/smoke-test.sh https://worker.example.workers.dev}"
echo "== health =="
curl --fail-with-body --silent --show-error "$BASE_URL/health"
echo
echo "== initialize =="
curl --fail-with-body --silent --show-error -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"flybrain-smoke-test","version":"1.0"}}}' "$BASE_URL/mcp"
echo
echo "== tools/list =="
curl --fail-with-body --silent --show-error -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' "$BASE_URL/mcp"
echo
echo "== ask_flybrain =="
curl --fail-with-body --silent --show-error -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' --data '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ask_flybrain","arguments":{"question":"What is the relationship between FlyBrain-NOS and URCAL?"}}}' "$BASE_URL/mcp"
echo
echo "All HTTP smoke tests completed."
