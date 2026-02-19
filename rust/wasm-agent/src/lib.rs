//! WASM agent engine — self-contained agent loop for browser execution.
//!
//! This is the brain that runs in the browser. It doesn't depend on
//! amplifier-core — it's a self-contained WASM module that uses
//! wasm-bindgen to bridge to JavaScript for LLM calls and non-Rust tools.
//!
//! Architecture:
//! - `execute_prompt` runs the agent loop: prompt → LLM → tool calls → iterate
//! - `data_transform` tool runs in-process (Rust WASM, no JS bridge overhead)
//! - All other tools route through `amplifier_execute_tool` JS bridge
//! - LLM calls go through `amplifier_llm_complete` JS bridge to WebLLM

use std::cell::RefCell;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use wasm_bindgen::prelude::*;

// ---------------------------------------------------------------------------
// Persistent conversation state — survives across execute_prompt calls
// ---------------------------------------------------------------------------

thread_local! {
    static MESSAGES: RefCell<Vec<Value>> = RefCell::new(Vec::new());
}

// ---------------------------------------------------------------------------
// JavaScript imports — these functions are provided by the HTML page at runtime
// ---------------------------------------------------------------------------

#[wasm_bindgen]
extern "C" {
    /// Call a tool by name with JSON input, returning JSON result string.
    /// Dispatches to the appropriate language runtime (TS, Python/Pyodide, Go WASM).
    #[wasm_bindgen(js_name = "amplifier_execute_tool")]
    async fn js_execute_tool(name: &str, input_json: &str) -> JsValue;

    /// Call the LLM (WebLLM) with a JSON request, returning JSON response string.
    #[wasm_bindgen(js_name = "amplifier_llm_complete")]
    async fn js_llm_complete(request_json: &str) -> JsValue;

    /// Emit an event to the browser UI (for progress/status updates).
    #[wasm_bindgen(js_name = "amplifier_on_event")]
    fn js_on_event(event_type: &str, data_json: &str);
}

// ---------------------------------------------------------------------------
// Tool spec — describes available tools for the LLM
// ---------------------------------------------------------------------------

/// Describes a tool available to the LLM.
#[derive(Serialize, Deserialize, Clone)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters: Value,
}

// ---------------------------------------------------------------------------
// Public helper — extract text from an LLM response message
// ---------------------------------------------------------------------------

/// Extract text content from an LLM response message.
///
/// Handles three content shapes:
/// - String: `{"content": "hello"}` → `"hello"`
/// - Array of blocks: `{"content": [{"text": "hello"}, ...]}` → concatenated text
/// - Null / missing: → `""`
pub fn extract_text(message: &Value) -> String {
    match message.get("content") {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Array(blocks)) => blocks
            .iter()
            .filter_map(|b| b.get("text").and_then(|t| t.as_str()))
            .collect::<Vec<_>>()
            .join(""),
        _ => String::new(),
    }
}

// ---------------------------------------------------------------------------
// WASM-exported functions
// ---------------------------------------------------------------------------

/// Get the kernel version.
#[wasm_bindgen]
pub fn kernel_version() -> String {
    "0.1.0-wasm".to_string()
}

/// Get the list of available tool specs as JSON.
#[wasm_bindgen]
pub fn get_tool_specs() -> String {
    let specs = json!([
        {
            "name": "data_transform",
            "description": "Process structured data — stats, filter, sort, validate, aggregate. Runs at native speed in Rust WASM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["stats", "filter", "sort", "validate", "aggregate"]},
                    "data": {"type": "array", "description": "Data to process"},
                    "field": {"type": "string", "description": "Field name for numeric operations"},
                    "where": {"type": "object", "description": "Filter clause: {field, op, value}"},
                    "compute": {"type": "array", "description": "Aggregate operations: sum, mean, min, max"},
                    "schema": {"type": "object", "description": "JSON Schema for validate operation"}
                },
                "required": ["operation"]
            }
        },
        {
            "name": "web_research",
            "description": "Search the web and fetch URL content. Uses browser-native fetch and DOMParser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["search", "fetch", "extract_links"]},
                    "query": {"type": "string"},
                    "url": {"type": "string"},
                    "max_length": {"type": "integer"}
                },
                "required": ["action"]
            }
        },
        {
            "name": "code_analysis",
            "description": "Analyze Python source code using the ast module. Computes complexity, extracts signatures, identifies patterns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["analyze", "complexity", "signatures"]},
                    "code": {"type": "string", "description": "Python source code to analyze"}
                },
                "required": ["action", "code"]
            }
        },
        {
            "name": "document_builder",
            "description": "Assemble structured Markdown documents with templates, tables, and citations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["build", "format_table", "add_citations"]},
                    "template": {"type": "string", "enum": ["research_report", "summary", "comparison"]},
                    "data": {"type": "object"}
                },
                "required": ["action"]
            }
        }
    ]);
    serde_json::to_string(&specs).unwrap()
}

/// Execute a single tool call.
///
/// `data_transform` runs in-process (Rust WASM); all others go through JS bridge.
#[wasm_bindgen]
pub async fn execute_tool(name: &str, input_json: &str) -> String {
    if name == "data_transform" {
        // Run natively in WASM — no JS bridge overhead
        match serde_json::from_str::<Value>(input_json) {
            Ok(input) => match data_transform::execute(&input) {
                Ok(result) => json!({"success": true, "output": result}).to_string(),
                Err(e) => json!({"success": false, "error": e}).to_string(),
            },
            Err(e) => json!({"success": false, "error": format!("Invalid JSON: {e}")}).to_string(),
        }
    } else {
        // Route through JavaScript bridge to the appropriate language runtime
        let result_js = js_execute_tool(name, input_json).await;
        result_js
            .as_string()
            .unwrap_or_else(|| json!({"success": false, "error": "JS bridge returned non-string"}).to_string())
    }
}

/// Clear the conversation history. Called from the UI to start a fresh conversation.
#[wasm_bindgen]
pub fn clear_history() {
    MESSAGES.with(|msgs| {
        msgs.borrow_mut().clear();
    });
}

/// Get the number of messages in the conversation history.
/// Exposed for testing and debugging.
#[wasm_bindgen]
pub fn get_history_length() -> usize {
    MESSAGES.with(|msgs| msgs.borrow().len())
}

/// Run the full agent loop: prompt → LLM → tool calls → iterate → response.
///
/// This is the main entry point called from JavaScript.
///
/// # Arguments
/// * `prompt` — The user's message
/// * `tools_json` — JSON array of ToolSpec objects describing available tools
/// * `max_iterations` — Maximum number of LLM↔tool round-trips (safety limit)
///
/// # Returns
/// The final text response from the agent, or an error message.
#[wasm_bindgen]
pub async fn execute_prompt(
    prompt: &str,
    tools_json: &str,
    max_iterations: u32,
) -> Result<String, JsValue> {
    let tools: Vec<ToolSpec> =
        serde_json::from_str(tools_json).map_err(|e| JsValue::from_str(&e.to_string()))?;

    // Add system prompt only on first call (when history is empty)
    MESSAGES.with(|msgs| {
        let mut messages = msgs.borrow_mut();
        if messages.is_empty() {
            messages.push(json!({
                "role": "system",
                "content": "You are a helpful research assistant. You have access to tools written in four programming languages (Rust, TypeScript, Python, Go). When the user asks you to research something, analyze code, process data, or generate a document, you MUST use the appropriate tools. For simple greetings or questions that don\u{27}t need tools, respond directly with plain text \u{2014} do NOT attempt to call tools for simple conversation."
            }));
        }
        messages.push(json!({
            "role": "user",
            "content": prompt
        }));
    });

    for iteration in 0..max_iterations {
        js_on_event(
            "iteration:start",
            &json!({"iteration": iteration}).to_string(),
        );

        // Build the LLM request with the full conversation history
        let request = MESSAGES.with(|msgs| {
            json!({
                "messages": *msgs.borrow(),
                "tools": tools,
            })
        });

        // Call the LLM via JavaScript bridge
        let response_js = js_llm_complete(&serde_json::to_string(&request).unwrap()).await;
        let response_str = response_js.as_string().unwrap_or_default();
        let response: Value = serde_json::from_str(&response_str)
            .map_err(|e| JsValue::from_str(&format!("Invalid LLM response: {e}")))?;

        // Add assistant message to persistent history
        MESSAGES.with(|msgs| {
            msgs.borrow_mut().push(response.clone());
        });

        // Check for tool calls
        let tool_calls = response.get("tool_calls").and_then(|tc| tc.as_array());

        if let Some(calls) = tool_calls {
            if calls.is_empty() {
                // No tool calls — return the text response
                return Ok(extract_text(&response));
            }

            for call in calls {
                let tool_name = call.get("name").and_then(|n| n.as_str()).unwrap_or("");
                let tool_args = call.get("arguments").unwrap_or(&Value::Null);
                let call_id = call.get("id").and_then(|id| id.as_str()).unwrap_or("");

                js_on_event(
                    "tool:execute",
                    &json!({
                        "tool": tool_name,
                        "iteration": iteration,
                    })
                    .to_string(),
                );

                // Execute: data_transform runs in WASM, others via JS bridge
                let result = if tool_name == "data_transform" {
                    let input_str = serde_json::to_string(tool_args).unwrap_or_default();
                    match serde_json::from_str::<Value>(&input_str) {
                        Ok(input) => match data_transform::execute(&input) {
                            Ok(r) => json!({"success": true, "output": r}).to_string(),
                            Err(e) => json!({"success": false, "error": e}).to_string(),
                        },
                        Err(e) => {
                            json!({"success": false, "error": format!("Invalid JSON: {e}")})
                                .to_string()
                        }
                    }
                } else {
                    let input_str = serde_json::to_string(tool_args).unwrap_or_default();
                    let result_js = js_execute_tool(tool_name, &input_str).await;
                    result_js.as_string().unwrap_or_else(|| "{}".to_string())
                };

                js_on_event(
                    "tool:result",
                    &json!({
                        "tool": tool_name,
                        "iteration": iteration,
                    })
                    .to_string(),
                );

                // Add tool result to persistent history
                MESSAGES.with(|msgs| {
                    msgs.borrow_mut().push(json!({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result,
                    }));
                });
            }
        } else {
            // No tool_calls field — return the text response
            return Ok(extract_text(&response));
        }
    }

    // Max iterations reached
    let last_text = MESSAGES.with(|msgs| {
        extract_text(msgs.borrow().last().unwrap_or(&Value::Null))
    });
    Ok(last_text)
}

// ---------------------------------------------------------------------------
// Tests — only the pure-Rust logic is testable without a browser
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn extract_text_from_string_content() {
        let msg = json!({"role": "assistant", "content": "Hello world"});
        assert_eq!(extract_text(&msg), "Hello world");
    }

    #[test]
    fn extract_text_from_null_content() {
        let msg = json!({"role": "assistant", "content": null});
        assert_eq!(extract_text(&msg), "");
    }

    #[test]
    fn extract_text_from_missing_content() {
        let msg = json!({"role": "assistant"});
        assert_eq!(extract_text(&msg), "");
    }

    #[test]
    fn extract_text_from_content_blocks() {
        let msg = json!({
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"}
            ]
        });
        assert_eq!(extract_text(&msg), "Hello world");
    }

    #[test]
    fn extract_text_from_empty_message() {
        let msg = json!({});
        assert_eq!(extract_text(&msg), "");
    }

    #[test]
    fn data_transform_executes_in_process() {
        // Verify data_transform crate is linked and callable
        let input = json!({
            "operation": "stats",
            "data": [{"value": 10}, {"value": 20}],
            "field": "value"
        });
        let result = data_transform::execute(&input).unwrap();
        assert_eq!(result["count"], 2);
        assert_eq!(result["sum"], 30.0);
    }

    #[test]
    fn kernel_version_is_set() {
        assert_eq!(kernel_version(), "0.1.0-wasm");
    }

    #[test]
    fn tool_specs_are_valid_json() {
        let specs_json = get_tool_specs();
        let specs: Vec<ToolSpec> = serde_json::from_str(&specs_json).unwrap();
        assert_eq!(specs.len(), 4);
        assert_eq!(specs[0].name, "data_transform");
        assert_eq!(specs[1].name, "web_research");
        assert_eq!(specs[2].name, "code_analysis");
        assert_eq!(specs[3].name, "document_builder");
    }

    #[test]
    fn clear_history_resets_message_state() {
        // After clearing, history should be empty
        clear_history();
        assert_eq!(get_history_length(), 0);
    }

    #[test]
    fn message_history_persists_across_calls_via_thread_local() {
        // Clear first to ensure clean state
        clear_history();
        assert_eq!(get_history_length(), 0);

        // Simulate what execute_prompt does: add messages to the thread-local
        MESSAGES.with(|msgs| {
            let mut messages = msgs.borrow_mut();
            messages.push(json!({"role": "system", "content": "You are a helper."}));
            messages.push(json!({"role": "user", "content": "Hello"}));
            messages.push(json!({"role": "assistant", "content": "Hi there!"}));
        });
        assert_eq!(get_history_length(), 3);

        // Simulate a second call - messages should still be there
        MESSAGES.with(|msgs| {
            let mut messages = msgs.borrow_mut();
            messages.push(json!({"role": "user", "content": "What did I say?"}));
        });
        assert_eq!(get_history_length(), 4);

        // Clear should reset
        clear_history();
        assert_eq!(get_history_length(), 0);
    }
}
