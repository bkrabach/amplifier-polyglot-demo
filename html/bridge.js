// html/bridge.js
// JavaScript bridge layer — dispatches tool calls from the Rust WASM kernel
// to the appropriate language runtime.

// --- WebLLM Provider Integration ---

let webllmEngine = null;

/**
 * Initialize the WebLLM engine with a given model.
 * Called during the boot sequence to load the AI model into the browser.
 *
 * @param {string} modelId - The WebLLM model identifier (e.g. "Phi-3.5-mini-instruct-q4f16_1-MLC")
 * @param {function} onProgress - Optional callback for download/init progress updates
 * @returns {Promise} The initialized WebLLM engine
 */
async function initWebLLM(modelId, onProgress) {
    // Guard: WebGPU required
    if (!navigator.gpu) {
        throw new Error('WebGPU not available. Use Chrome 113+, Edge 113+, or Safari 18+.');
    }

    const { CreateMLCEngine } = await import("https://esm.run/@mlc-ai/web-llm");
    webllmEngine = await CreateMLCEngine(modelId, {
        initProgressCallback: function(progress) {
            if (onProgress) onProgress(progress);
        }
    });
    window.webllmEngine = webllmEngine;
    return webllmEngine;
}

// --- Tool Registry ---

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
    if (!webllmEngine) {
        return JSON.stringify({ error: "WebLLM not initialized" });
    }

    try {
        const request = JSON.parse(requestJson);

        // Convert messages to OpenAI-compatible format (WebLLM uses this)
        const messages = request.messages || [];

        // Convert tool specs to OpenAI tool format
        const tools = (request.tools || []).map((t) => ({
            type: "function",
            function: {
                name: t.name,
                description: t.description,
                parameters:
                    typeof t.parameters === "string"
                        ? JSON.parse(t.parameters)
                        : t.parameters,
            },
        }));

        const params = {
            messages: messages,
            temperature: request.temperature || 0.7,
            max_tokens: request.max_tokens || 4096,
        };

        // Only include tools if we have them
        if (tools.length > 0) {
            params.tools = tools;
            params.tool_choice = "auto";
        }

        const completion = await webllmEngine.chat.completions.create(params);

        // Convert to the format the Rust kernel expects
        const choice = completion.choices[0];
        const response = {
            role: "assistant",
            content: choice.message.content || "",
            tool_calls: (choice.message.tool_calls || []).map((tc) => ({
                id: tc.id,
                name: tc.function.name,
                arguments: JSON.parse(tc.function.arguments || "{}"),
            })),
        };

        return JSON.stringify(response);
    } catch (e) {
        // Handle ToolCallOutputParseError — model responded with plain text
        // instead of a tool call JSON. Extract the text and return it.
        if (e.message && e.message.includes("parsing outputMessage for function calling")) {
            var match = e.message.match(/Got outputMessage: ([\s\S]*?)(?:Got error:|$)/);
            var text = match ? match[1].trim() : String(e);
            console.warn("WebLLM: model responded with text instead of tool call, returning as content");
            return JSON.stringify({
                role: "assistant",
                content: text,
                tool_calls: [],
            });
        }
        console.error("WebLLM error:", e);
        return JSON.stringify({
            role: "assistant",
            content: "Error: " + e.message,
            tool_calls: [],
        });
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
