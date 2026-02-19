"""Code analysis tool using Python's ast module.

Runs in the browser via Pyodide. Called from the JavaScript bridge.
Uses ast.NodeVisitor for structural analysis of Python source code.
"""
import ast
import json


def execute(input_dict):
    """Execute a code analysis action.

    Args:
        input_dict: Dict with 'action' and 'code' keys

    Returns:
        Dict with success, output, error keys. Never raises exceptions.
    """
    try:
        return _execute_inner(input_dict)
    except Exception as e:
        # Catch-all: never let the tool return an unhandled exception
        code = input_dict.get("code", "") if isinstance(input_dict, dict) else ""
        lines = code.splitlines() if code else []
        return {
            "success": True,
            "output": json.dumps({
                "functions": [],
                "classes": [],
                "imports": [],
                "patterns": [],
                "total_lines": len(lines),
                "non_empty_lines": len([l for l in lines if l.strip()]),
                "error": str(e),
                "note": "Unexpected error during analysis, showing basic metrics only",
                "summary": f"{len(lines)} lines (error during analysis, basic metrics only)"
            })
        }


def _execute_inner(input_dict):
    """Inner implementation of execute — may raise exceptions."""
    action = input_dict.get("action", "analyze")
    code = input_dict.get("code", "")

    if not code:
        return {"success": False, "error": "code is required"}

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        # Fallback: return basic line-count analysis instead of failing
        lines = code.splitlines()
        return {
            "success": True,
            "output": json.dumps({
                "functions": [],
                "classes": [],
                "imports": [],
                "patterns": [],
                "total_lines": len(lines),
                "non_empty_lines": len([l for l in lines if l.strip()]),
                "syntax_error": str(e),
                "note": "Code had syntax issues, showing basic metrics only",
                "summary": f"{len(lines)} lines (syntax error in parsing, basic analysis only)"
            })
        }

    try:
        if action == "analyze":
            return {"success": True, "output": full_analysis(tree, code)}
        elif action == "complexity":
            return {"success": True, "output": compute_complexity(tree)}
        elif action == "signatures":
            return {"success": True, "output": extract_signatures(tree)}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def full_analysis(tree, code):
    """Complete structural analysis of Python source code."""
    visitor = AnalysisVisitor()
    visitor.visit(tree)

    return {
        "functions": visitor.functions,
        "classes": visitor.classes,
        "imports": visitor.imports,
        "complexity": compute_complexity(tree),
        "patterns": detect_patterns(tree),
        "line_count": len(code.splitlines()),
        "summary": {
            "function_count": len(visitor.functions),
            "class_count": len(visitor.classes),
            "import_count": len(visitor.imports),
        },
    }


def compute_complexity(tree):
    """Compute cyclomatic complexity for each function."""
    results = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1  # Base complexity
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp)):
                    complexity += 1
                elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
                elif isinstance(child, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(child, (ast.With, ast.AsyncWith)):
                    complexity += 1

            results[node.name] = {
                "complexity": complexity,
                "rating": (
                    "low" if complexity <= 5 else "medium" if complexity <= 10 else "high"
                ),
                "line": node.lineno,
            }

    return results


def extract_signatures(tree):
    """Extract function signatures with type hints."""
    signatures = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = []
            for arg in node.args.args:
                param = arg.arg
                if arg.annotation:
                    param += f": {ast.unparse(arg.annotation)}"
                params.append(param)

            return_type = ""
            if node.returns:
                return_type = f"-> {ast.unparse(node.returns)}"

            docstring = ast.get_docstring(node) or ""

            signatures.append(
                {
                    "name": node.name,
                    "params": params,
                    "return_type": return_type.strip(),
                    "async": isinstance(node, ast.AsyncFunctionDef),
                    "docstring": docstring[:200],
                    "line": node.lineno,
                    "decorators": [ast.unparse(d) for d in node.decorator_list],
                }
            )

    return signatures


def detect_patterns(tree):
    """Detect common code patterns."""
    patterns = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check for recursion
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Name) and child.func.id == node.name:
                        patterns.append(
                            {
                                "type": "recursion",
                                "function": node.name,
                                "line": child.lineno,
                            }
                        )

        # Check for comprehensions / generators
        if isinstance(
            node, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)
        ):
            patterns.append({"type": "comprehension", "line": node.lineno})

        # Check for Protocol/ABC usage
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in (
                    "Protocol",
                    "ABC",
                    "ABCMeta",
                ):
                    patterns.append(
                        {
                            "type": "abstract_class",
                            "class": node.name,
                            "line": node.lineno,
                        }
                    )

        # Check for decorator usage
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.decorator_list
        ):
            for dec in node.decorator_list:
                patterns.append(
                    {"type": "decorator", "function": node.name, "line": node.lineno}
                )

    return patterns


class AnalysisVisitor(ast.NodeVisitor):
    """Collects structural information from an AST."""

    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []

    def visit_FunctionDef(self, node):
        self.functions.append(
            {
                "name": node.name,
                "line": node.lineno,
                "async": False,
                "args": len(node.args.args),
            }
        )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.functions.append(
            {
                "name": node.name,
                "line": node.lineno,
                "async": True,
                "args": len(node.args.args),
            }
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append(
            {
                "name": node.name,
                "line": node.lineno,
                "bases": [ast.unparse(b) for b in node.bases],
                "methods": sum(
                    1
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ),
            }
        )
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({"module": alias.name, "line": node.lineno})
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.imports.append({"module": node.module or "", "line": node.lineno})
        self.generic_visit(node)


# For Pyodide: register the execute function globally
def pyCodeAnalysis(input_json):
    """Entry point called from the JavaScript bridge."""
    input_dict = json.loads(input_json) if isinstance(input_json, str) else input_json
    result = execute(input_dict)
    return json.dumps(result)
