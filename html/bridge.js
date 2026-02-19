// html/bridge.js
// JavaScript bridge layer — dispatches tool calls from the Rust WASM kernel
// to the appropriate language runtime.

const toolRegistry = {};

// Register tools from each language runtime
function registerTools() {
    // Rust tools are handled in-process by the WASM kernel.
    // This registry is only for tools that need the JS bridge.

    toolRegistry["web_research"] = {
        language: "TypeScript",
        execute: (input) => window.tsWebResearch(input),
    };

    toolRegistry["code_analysis"] = {
        language: "Python",
        execute: async (input) => {
            const pyodide = window.pyodideInstance;
            if (!pyodide) throw new Error("Pyodide not loaded");
            const inputJson = JSON.stringify(input).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
            const result = pyodide.runPython(`pyCodeAnalysis('${inputJson}')`);
            return JSON.parse(result);
        },
    };

    toolRegistry["document_builder"] = {
        language: "Go",
        execute: async (input) => {
            if (!window.goWasmReady) throw new Error("Go WASM not loaded");
            const resultStr = window.goDocumentBuilder(JSON.stringify(input));
            return JSON.parse(resultStr);
        },
    };
}

// The function called by the Rust WASM kernel via wasm-bindgen
window.amplifier_execute_tool = async function (name, inputJson) {
    const tool = toolRegistry[name];
    if (!tool) {
        return JSON.stringify({ success: false, error: `Unknown tool: ${name}` });
    }

    try {
        const input = JSON.parse(inputJson);
        updateToolUI(name, tool.language, "running");
        const result = await tool.execute(input);
        updateToolUI(name, tool.language, "complete");
        return JSON.stringify(typeof result === "string" ? JSON.parse(result) : result);
    } catch (e) {
        updateToolUI(name, tool.language, "error");
        return JSON.stringify({ success: false, error: e.message || String(e) });
    }
};

// The function called by the Rust WASM kernel for LLM completion
window.amplifier_llm_complete = async function (requestJson) {
    const request = JSON.parse(requestJson);
    if (!window.webllmEngine) {
        return JSON.stringify({ error: "WebLLM engine not loaded" });
    }

    try {
        const response = await window.webllmEngine.chat.completions.create({
            messages: request.messages,
            tools: request.tools?.map((t) => ({
                type: "function",
                function: {
                    name: t.name,
                    description: t.description,
                    parameters: t.parameters,
                },
            })),
            tool_choice: request.tools?.length ? "auto" : undefined,
        });

        const choice = response.choices[0];
        const content = choice.message.content || "";
        const tool_calls =
            choice.message.tool_calls?.map((tc) => ({
                id: tc.id,
                name: tc.function.name,
                arguments: JSON.parse(tc.function.arguments || "{}"),
            })) || [];

        return JSON.stringify({
            content: content,
            tool_calls: tool_calls,
            usage: response.usage
                ? {
                      input_tokens: response.usage.prompt_tokens,
                      output_tokens: response.usage.completion_tokens,
                      total_tokens: response.usage.total_tokens,
                  }
                : null,
        });
    } catch (e) {
        return JSON.stringify({ error: e.message || String(e) });
    }
};

// Event callback from the Rust WASM kernel
window.amplifier_on_event = function (eventType, dataJson) {
    console.log(`[Event] ${eventType}:`, dataJson);
    // The UI will hook into this for progress display
    if (window.onAmplifierEvent) {
        window.onAmplifierEvent(eventType, JSON.parse(dataJson));
    }
};

// UI update callback (implemented in the main HTML)
function updateToolUI(name, language, status) {
    if (window.onToolUpdate) {
        window.onToolUpdate(name, language, status);
    }
}

// Initialize when DOM is ready
if (typeof document !== "undefined") {
    registerTools();
}
