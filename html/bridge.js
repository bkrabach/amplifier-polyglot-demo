// html/bridge.js
// JavaScript bridge layer — dispatches tool calls from the Rust WASM kernel
// to the appropriate language runtime.
//
// Uses JSON Schema constrained decoding (response_format) instead of native
// WebLLM function calling. The model outputs a discriminated union:
//   {"type": "text", "content": "..."} or {"type": "tool_call", "name": "...", "arguments": {...}}

// --- WebLLM Provider Integration ---

let webllmEngine = null;

/**
 * Initialize the WebLLM engine with a given model.
 * Called during the boot sequence to load the AI model into the browser.
 *
 * @param {string} modelId - The WebLLM model identifier (e.g. "Qwen3-4B-q4f16_1-MLC")
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

// --- JSON Schema for Constrained Decoding ---

/**
 * Build a oneOf JSON schema for constrained decoding.
 * The model MUST output either a text response or a tool call — XGrammar
 * enforces this at the token level.
 *
 * @param {Array} tools - Array of tool specs with name, description, parameters
 * @returns {string} JSON-stringified schema
 */
function buildToolCallSchema(tools) {
    var toolCallSchema = {
        oneOf: [
            {
                type: "object",
                properties: {
                    type: { type: "string", const: "text" },
                    content: { type: "string" }
                },
                required: ["type", "content"]
            },
            {
                type: "object",
                properties: {
                    type: { type: "string", const: "tool_call" },
                    name: { type: "string", enum: tools.map(function(t) { return t.name; }) },
                    arguments: { type: "object" }
                },
                required: ["type", "name", "arguments"]
            }
        ]
    };
    return JSON.stringify(toolCallSchema);
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

// The function called by the Rust WASM kernel for LLM completion.
// Uses JSON Schema constrained decoding — NOT native function calling.
window.amplifier_llm_complete = async function (requestJson) {
    if (!webllmEngine) {
        return JSON.stringify({ error: "WebLLM not initialized" });
    }

    try {
        var request = JSON.parse(requestJson);
        var messages = request.messages || [];
        
        // Convert messages for WebLLM compatibility:
        // - 'tool' role → 'user' role with "[Tool result from X]" prefix
        // - assistant messages with tool_calls → plain assistant with text about the call
        messages = messages.map(function(m) {
            if (m.role === "tool") {
                var toolName = m.tool_call_id || "unknown";
                var content = typeof m.content === "string" ? m.content : JSON.stringify(m.content);
                return { role: "user", content: "[Tool result from " + toolName + "]: " + content };
            }
            if (m.role === "assistant" && m.tool_calls && m.tool_calls.length > 0) {
                var callDescs = m.tool_calls.map(function(tc) {
                    return "Called " + tc.name + " with " + JSON.stringify(tc.arguments);
                }).join("; ");
                return { role: "assistant", content: callDescs };
            }
            return { role: m.role, content: typeof m.content === "string" ? m.content : JSON.stringify(m.content || "") };
        });
        var tools = request.tools || [];

        // Build tool descriptions for the system prompt
        var toolDescriptions = tools.map(function(t) {
            return "- " + t.name + ": " + t.description +
                   "\n  Parameters: " + JSON.stringify(t.parameters);
        }).join("\n");

        // Build or replace the system message with tool descriptions and format instructions
        var hasSystemMsg = messages.length > 0 && messages[0].role === "system";
        var systemContent;

        if (tools.length > 0) {
            systemContent = "You are a helpful assistant with access to tools. " +
                "When the user's request requires using a tool, respond with a tool_call. " +
                "When you can answer directly, respond with text. " +
                "You MUST respond with valid JSON matching the required schema.\n\n" +
                "Available tools:\n" + toolDescriptions + "\n\n" +
                "Response format:\n" +
                "For text: {\"type\": \"text\", \"content\": \"your response\"}\n" +
                "For tool use: {\"type\": \"tool_call\", \"name\": \"tool_name\", \"arguments\": {\"param\": \"value\"}}";
        } else {
            systemContent = "You are a helpful assistant. " +
                "Respond with valid JSON: {\"type\": \"text\", \"content\": \"your response\"}";
        }

        // Replace or prepend system message
        if (hasSystemMsg) {
            messages = messages.slice();  // Don't mutate original
            messages[0] = { role: "system", content: systemContent };
        } else {
            messages = [{ role: "system", content: systemContent }].concat(messages);
        }

        // Build the schema for constrained decoding
        var schema;
        if (tools.length > 0) {
            schema = buildToolCallSchema(tools);
        } else {
            schema = JSON.stringify({
                type: "object",
                properties: {
                    type: { type: "string", const: "text" },
                    content: { type: "string" }
                },
                required: ["type", "content"]
            });
        }

        var completionParams = {
            stream: false,
            messages: messages,
            temperature: request.temperature || 0.7,
            max_tokens: request.max_tokens || 2048,
            response_format: {
                type: "json_object",
                schema: schema
            }
        };

        var completion = await webllmEngine.chat.completions.create(completionParams);
        var output = JSON.parse(completion.choices[0].message.content || "{}");

        if (output.type === "tool_call") {
            // Convert to the format the Rust kernel expects
            return JSON.stringify({
                role: "assistant",
                content: "",
                tool_calls: [{
                    id: "call_" + Math.random().toString(36).substr(2, 9),
                    name: output.name,
                    arguments: output.arguments || {}
                }]
            });
        } else if (output.type === "text" || !output.type) {
            // Text response (explicit check + fallback for safety)
            return JSON.stringify({
                role: "assistant",
                content: output.content || "",
                tool_calls: []
            });
        }

    } catch (e) {
        console.error("WebLLM error:", e);
        // Try to extract any useful text from the error
        if (e.message && e.message.includes("parsing outputMessage")) {
            var match = e.message.match(/Got outputMessage: ([\s\S]*?)(?:Got error:|$)/);
            var text = match ? match[1].trim() : "I encountered an error processing your request.";
            return JSON.stringify({
                role: "assistant",
                content: text,
                tool_calls: []
            });
        }
        return JSON.stringify({
            role: "assistant",
            content: "Error: " + e.message,
            tool_calls: []
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
