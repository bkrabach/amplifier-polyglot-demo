# Amplifier Polyglot Demo

A single HTML file containing an AI agent with tools in four programming languages,
running entirely in your browser.

## The Demo

Open `html/amplifier-polyglot-agent.html` in Chrome 113+ and ask the agent to research a topic.
The agent uses:

- **Rust** (WASM) — data transformation and statistics at native speed
- **TypeScript** — web search and page fetching via browser APIs
- **Python** (Pyodide) — code analysis using the ast module
- **Go** (WASM) — structured document generation

Each language is chosen because it's genuinely the best fit for that capability.

### Running the Demo

The demo requires a local web server (WebLLM needs `http://` for WebGPU and Cache API):

```bash
cd html/
python -m http.server 8080
# Open http://localhost:8080/amplifier-polyglot-agent.html
```

**Note:** Opening the HTML file directly (`file://`) won't work — the Cache API and WebGPU shader caching require a secure context.

## Building

```bash
# Prerequisites: Rust, wasm-pack
# Optional: Go (for document_builder tool)

# Quick build (skip Go if not installed)
./html/build.sh --no-go

# Full build (requires Go installed + document-builder-go repo)
./html/build.sh

# Or use the Python build script directly
python3 html/build.py --no-go

# Output: html/amplifier-polyglot-agent.html (~322KB without Go, ~20-25MB with Go)
```

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Rust | 1.70+ | Kernel + data_transform compiled to WASM |
| wasm-pack | 0.12+ | Builds Rust → WASM with JS bindings |
| Python 3 | 3.10+ | Runs the build script |
| Go | 1.21+ | *(Optional)* Compiles document_builder to WASM |

### Building from scratch

```bash
# 1. Build the Rust WASM agent (if pkg/ doesn't exist)
wasm-pack build rust/wasm-agent --target web --out-dir ../../html/pkg

# 2. Run the assembly script
python3 html/build.py --no-go

# 3. Open in browser
# (on Linux) xdg-open html/amplifier-polyglot-agent.html
# (on macOS) open html/amplifier-polyglot-agent.html
```

## Requirements

- Chrome 113+ or Edge 113+ (WebGPU required for local LLM)
- ~4GB GPU memory (for Phi-3.5-mini model)
- First load downloads ~2-4GB model (cached by browser after that)

## Architecture

```
Browser
├── Rust WASM kernel (orchestrator + context + data_transform tool)
├── TypeScript tool (web_research — DuckDuckGo + fetch)
├── Python tool (code_analysis — Pyodide + ast module)
├── Go WASM tool (document_builder — text/template)
├── JavaScript bridge (dispatches tool calls to the right runtime)
└── WebLLM provider (Phi-3.5-mini via WebGPU)
```

The Rust WASM kernel runs the agent loop (prompt → LLM → tool calls → iterate → response).
When it needs to call a tool:

- **data_transform** executes in-process in Rust WASM (no bridge overhead)
- **web_research** routes through the JS bridge to TypeScript
- **code_analysis** routes through the JS bridge to Python/Pyodide
- **document_builder** routes through the JS bridge to Go WASM

The LLM runs locally in the browser via WebLLM + WebGPU — no API keys needed.

## Project Structure

```
amplifier-polyglot-demo/
├── rust/
│   ├── wasm-agent/        ← WASM kernel + agent loop + JS bridge imports
│   └── data-transform/    ← Rust data processing tool (stats, filter, sort, validate)
├── typescript/
│   └── web-research.ts    ← Browser web research tool (DuckDuckGo + fetch + DOMParser)
├── python/
│   ├── code_analysis.py   ← AST-based code analyzer (complexity, signatures, patterns)
│   └── tests/             ← Python tool tests
├── go/                    ← (document builder built from separate repo)
├── html/
│   ├── template.html      ← UI template with placeholder comments
│   ├── bridge.js          ← JavaScript glue layer + WebLLM integration
│   ├── build.py           ← Python assembly script
│   ├── build.sh           ← Shell wrapper (builds WASM then assembles)
│   ├── pkg/               ← wasm-pack output (Rust WASM + JS glue)
│   ├── tests/             ← Build + E2E tests (134 tests total)
│   └── amplifier-polyglot-agent.html  ← OUTPUT (single file)
├── Cargo.toml             ← Rust workspace
└── README.md
```

## How It Works

The build script (`html/build.py`) reads `html/template.html` and replaces six
placeholder comments with inlined content:

1. **Go WASM runtime** — `wasm_exec.js` from the Go toolchain
2. **Go WASM binary** — base64-encoded `document_builder.wasm`
3. **TypeScript tools** — `web-research.ts` with type annotations stripped
4. **Python code** — `code_analysis.py` embedded as a JS string constant
5. **JavaScript bridge** — `bridge.js` inlined
6. **Rust WASM** — base64-encoded `.wasm` + modified JS glue (no ES modules)

The boot sequence initializes runtimes in order:
Rust WASM → Go WASM → TypeScript → Pyodide (CDN) → WebLLM (CDN + model download)

## Testing

```bash
# Run all tests (134 total)
python3 -m pytest html/tests/ -v

# Run just the build script tests
python3 -m pytest html/tests/test_build.py -v

# Run end-to-end tests
python3 -m pytest html/tests/test_e2e_build.py -v

# Run Rust tests
cargo test --workspace
```

## Notes

- The Go WASM build requires Go installed and the
  [document-builder-go](https://github.com/bkrabach/amplifier-module-tool-document-builder-go)
  repo cloned locally. If Go is unavailable, the HTML works with 3 languages instead of 4.
- The base64 encoding makes the file ~33% larger than the raw WASM binaries.
- Pyodide (~20MB) downloads from CDN on first use — it's not embedded in the HTML.
- WebLLM model (~2-4GB) downloads from CDN on first use and is cached by the browser.
- The assembled HTML file is fully self-contained — no server required.
