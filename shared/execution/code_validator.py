import ast
from typing import List, Tuple

ALLOWED_TOP_LEVEL_IMPORTS = {
    "pandas", "numpy", "sklearn", "xgboost", "lightgbm",
    "scipy", "json", "sys", "os", "warnings", "re",
}


def _get_import_roots(tree: ast.AST) -> List[str]:
    roots = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.append(node.module.split(".")[0])
    return roots


def _extract_subscript_strings(tree: ast.AST) -> List[str]:
    strings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            slice_node = node.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                strings.append(slice_node.value)
            elif isinstance(slice_node, ast.List):
                for elt in slice_node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        strings.append(elt.value)
    return strings


def validate_generated_code(
    code: str, dataset_columns: List[str], target_column: str
) -> Tuple[bool, List[str]]:
    failures = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        failures.append(f"SyntaxError: {e}")
        return False, failures

    import_roots = _get_import_roots(tree)
    bad_imports = [r for r in import_roots if r not in ALLOWED_TOP_LEVEL_IMPORTS]
    if bad_imports:
        failures.append(
            f"Forbidden imports detected: {bad_imports}. "
            f"Only these are allowed: {sorted(ALLOWED_TOP_LEVEL_IMPORTS)}"
        )

    used_strings = _extract_subscript_strings(tree)
    all_valid_columns = set(dataset_columns) | {target_column, "target"}
    bad_columns = [s for s in used_strings if s not in all_valid_columns and len(s) > 0]
    if bad_columns:
        failures.append(
            f"Code references columns not in dataset: {bad_columns}. "
            f"Valid columns: {dataset_columns}"
        )

    if target_column and target_column not in code:
        failures.append(
            f"Target column '{target_column}' does not appear in the generated code."
        )

    if "sys.argv[1]" not in code:
        failures.append("Code must load the dataset from sys.argv[1] but 'sys.argv[1]' was not found.")

    if "metric_value" not in code:
        failures.append(
            "Code does not contain 'metric_value' — the final JSON output format is missing."
        )

    return len(failures) == 0, failures
