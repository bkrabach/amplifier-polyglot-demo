//! Data transformation tool — JSON validation, stats, filtering, sorting.
//!
//! Compiled into the WASM binary alongside the kernel.
//! Processes structured data at near-native speed.

use serde_json::{json, Value};

/// Execute a data transform operation.
///
/// Operations: stats, filter, sort, validate, aggregate.
pub fn execute(input: &Value) -> Result<Value, String> {
    let operation = input
        .get("operation")
        .and_then(|v| v.as_str())
        .ok_or("Missing 'operation' field")?;

    match operation {
        "stats" => compute_stats(input),
        "filter" => filter_data(input),
        "sort" => sort_data(input),
        "validate" => validate_schema(input),
        "aggregate" => aggregate_data(input),
        _ => Err(format!(
            "Unknown operation: {operation}. Use: stats, filter, sort, validate, aggregate"
        )),
    }
}

fn compute_stats(input: &Value) -> Result<Value, String> {
    let data = input
        .get("data")
        .and_then(|v| v.as_array())
        .ok_or("'data' must be an array")?;

    let field = input
        .get("field")
        .and_then(|v| v.as_str())
        .unwrap_or("value");

    let values: Vec<f64> = data
        .iter()
        .filter_map(|item| {
            // Handle plain numbers: [10, 20, 30]
            if let Some(n) = item.as_f64() {
                return Some(n);
            }
            // Handle objects with a field: [{"value": 10}, {"score": 20}]
            item.get(field).and_then(|v| v.as_f64())
        })
        .collect();

    if values.is_empty() {
        return Ok(json!({"count": 0, "sum": 0, "mean": 0, "min": 0, "max": 0}));
    }

    let count = values.len() as f64;
    let sum: f64 = values.iter().sum();
    let mean = sum / count;
    let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let variance: f64 = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / count;
    let std_dev = variance.sqrt();

    Ok(json!({
        "count": count as i64,
        "sum": sum,
        "mean": mean,
        "min": min,
        "max": max,
        "std_dev": std_dev,
    }))
}

fn filter_data(input: &Value) -> Result<Value, String> {
    let data = input
        .get("data")
        .and_then(|v| v.as_array())
        .ok_or("'data' must be an array")?;

    let where_clause = input
        .get("where")
        .ok_or("'where' clause is required for filter operation")?;

    let field = where_clause
        .get("field")
        .and_then(|v| v.as_str())
        .ok_or("'where.field' is required")?;
    let op = where_clause
        .get("op")
        .and_then(|v| v.as_str())
        .ok_or("'where.op' is required")?;
    let threshold = where_clause
        .get("value")
        .and_then(|v| v.as_f64())
        .ok_or("'where.value' must be a number")?;

    let filtered: Vec<&Value> = data
        .iter()
        .filter(|item| {
            let val = item.get(field).and_then(|v| v.as_f64()).unwrap_or(0.0);
            match op {
                ">" => val > threshold,
                ">=" => val >= threshold,
                "<" => val < threshold,
                "<=" => val <= threshold,
                "==" => (val - threshold).abs() < f64::EPSILON,
                "!=" => (val - threshold).abs() >= f64::EPSILON,
                _ => false,
            }
        })
        .collect();

    Ok(json!({
        "data": filtered,
        "count": filtered.len(),
        "original_count": data.len(),
    }))
}

fn sort_data(input: &Value) -> Result<Value, String> {
    let data = input
        .get("data")
        .and_then(|v| v.as_array())
        .ok_or("'data' must be an array")?;

    let field = input
        .get("field")
        .and_then(|v| v.as_str())
        .ok_or("'field' is required for sort operation")?;

    let descending = input
        .get("descending")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let mut sorted: Vec<Value> = data.clone();
    sorted.sort_by(|a, b| {
        let va = a.get(field).and_then(|v| v.as_f64()).unwrap_or(0.0);
        let vb = b.get(field).and_then(|v| v.as_f64()).unwrap_or(0.0);
        if descending {
            vb.partial_cmp(&va).unwrap_or(std::cmp::Ordering::Equal)
        } else {
            va.partial_cmp(&vb).unwrap_or(std::cmp::Ordering::Equal)
        }
    });

    Ok(json!({"data": sorted, "count": sorted.len()}))
}

fn validate_schema(input: &Value) -> Result<Value, String> {
    let data = input.get("data").ok_or("'data' is required for validate")?;
    let schema = input
        .get("schema")
        .ok_or("'schema' is required for validate")?;

    let schema_type = schema
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("any");
    let mut errors: Vec<String> = Vec::new();

    match schema_type {
        "object" => {
            if !data.is_object() {
                errors.push(format!("Expected object, got {}", type_name(data)));
            } else if let Some(required) = schema.get("required").and_then(|v| v.as_array()) {
                for req in required {
                    if let Some(field_name) = req.as_str() {
                        if data.get(field_name).is_none() {
                            errors.push(format!("Missing required field: {field_name}"));
                        }
                    }
                }
            }
        }
        "array" => {
            if !data.is_array() {
                errors.push(format!("Expected array, got {}", type_name(data)));
            }
        }
        "string" => {
            if !data.is_string() {
                errors.push(format!("Expected string, got {}", type_name(data)));
            }
        }
        "number" | "integer" => {
            if !data.is_number() {
                errors.push(format!("Expected number, got {}", type_name(data)));
            }
        }
        _ => {}
    }

    Ok(json!({
        "valid": errors.is_empty(),
        "errors": errors,
        "error_count": errors.len(),
    }))
}

fn aggregate_data(input: &Value) -> Result<Value, String> {
    let data = input
        .get("data")
        .and_then(|v| v.as_array())
        .ok_or("'data' must be an array")?;

    let compute = input
        .get("compute")
        .and_then(|v| v.as_array())
        .ok_or("'compute' must be an array of operation names")?;

    let field = input
        .get("field")
        .and_then(|v| v.as_str())
        .unwrap_or("value");

    let values: Vec<f64> = data
        .iter()
        .filter_map(|item| {
            // Handle plain numbers: [10, 20, 30]
            if let Some(n) = item.as_f64() {
                return Some(n);
            }
            // Handle objects with a field: [{"value": 10}, {"score": 20}]
            item.get(field).and_then(|v| v.as_f64())
        })
        .collect();

    let mut result = serde_json::Map::new();
    result.insert("count".into(), json!(values.len()));

    for op in compute {
        if let Some(op_name) = op.as_str() {
            match op_name {
                "sum" => {
                    result.insert("sum".into(), json!(values.iter().sum::<f64>()));
                }
                "mean" => {
                    let mean = if values.is_empty() {
                        0.0
                    } else {
                        values.iter().sum::<f64>() / values.len() as f64
                    };
                    result.insert("mean".into(), json!(mean));
                }
                "min" => {
                    result.insert(
                        "min".into(),
                        json!(values.iter().cloned().fold(f64::INFINITY, f64::min)),
                    );
                }
                "max" => {
                    result.insert(
                        "max".into(),
                        json!(values.iter().cloned().fold(f64::NEG_INFINITY, f64::max)),
                    );
                }
                _ => {}
            }
        }
    }

    Ok(Value::Object(result))
}

fn type_name(v: &Value) -> &str {
    match v {
        Value::Null => "null",
        Value::Bool(_) => "boolean",
        Value::Number(_) => "number",
        Value::String(_) => "string",
        Value::Array(_) => "array",
        Value::Object(_) => "object",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn stats_basic() {
        let result = execute(&json!({
            "operation": "stats",
            "data": [{"value": 10}, {"value": 20}, {"value": 30}],
            "field": "value"
        }))
        .unwrap();
        assert_eq!(result["count"], 3);
        assert_eq!(result["sum"], 60.0);
        assert_eq!(result["mean"], 20.0);
        assert_eq!(result["min"], 10.0);
        assert_eq!(result["max"], 30.0);
    }

    #[test]
    fn filter_greater_than() {
        let result = execute(&json!({
            "operation": "filter",
            "data": [{"x": 5}, {"x": 15}, {"x": 25}],
            "where": {"field": "x", "op": ">", "value": 10}
        }))
        .unwrap();
        assert_eq!(result["count"], 2);
    }

    #[test]
    fn sort_ascending() {
        let result = execute(&json!({
            "operation": "sort",
            "data": [{"v": 30}, {"v": 10}, {"v": 20}],
            "field": "v"
        }))
        .unwrap();
        let sorted = result["data"].as_array().unwrap();
        assert_eq!(sorted[0]["v"], 10);
        assert_eq!(sorted[2]["v"], 30);
    }

    #[test]
    fn validate_required_field_missing() {
        let result = execute(&json!({
            "operation": "validate",
            "data": {"name": "test"},
            "schema": {"type": "object", "required": ["name", "version"]}
        }))
        .unwrap();
        assert_eq!(result["valid"], false);
        assert_eq!(result["error_count"], 1);
    }

    #[test]
    fn validate_passes() {
        let result = execute(&json!({
            "operation": "validate",
            "data": {"name": "test", "version": 3},
            "schema": {"type": "object", "required": ["name", "version"]}
        }))
        .unwrap();
        assert_eq!(result["valid"], true);
    }

    #[test]
    fn aggregate_sum_and_mean() {
        let result = execute(&json!({
            "operation": "aggregate",
            "data": [{"v": 10}, {"v": 20}, {"v": 30}],
            "field": "v",
            "compute": ["sum", "mean", "min", "max"]
        }))
        .unwrap();
        assert_eq!(result["sum"], 60.0);
        assert_eq!(result["mean"], 20.0);
    }

    #[test]
    fn unknown_operation_returns_error() {
        let result = execute(&json!({"operation": "unknown_op"}));
        assert!(result.is_err());
    }

    #[test]
    fn stats_plain_number_array() {
        let input = json!({
            "operation": "stats",
            "data": [10, 20, 30, 40, 50]
        });
        let result = execute(&input).unwrap();
        assert_eq!(result["count"], 5);
        assert_eq!(result["sum"], 150.0);
        assert_eq!(result["mean"], 30.0);
        assert_eq!(result["min"], 10.0);
        assert_eq!(result["max"], 50.0);
    }

}
