# amplifier-polyglot-demo

Browser-based AI agent with tools in four programming languages (Rust, TypeScript, Python, Go) running entirely in the browser.

## Structure

- `rust/wasm-agent/` — WASM agent engine (brain that runs in browser)
- `rust/data-transform/` — Rust data_transform tool (compiled into WASM)
- `typescript/` — TypeScript web_research tool (Milestone 5)
- `python/` — Python code_analysis tool (Milestone 5)
- `go/` — Go document_builder tool (placeholder)
- `html/` — Browser demo (Milestone 7)

## Building

```bash
# Run data-transform tests
cargo test -p data-transform

# Build WASM agent
wasm-pack build rust/wasm-agent --target web --out-dir ../../html/pkg
```
