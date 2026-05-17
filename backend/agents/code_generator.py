import json
import textwrap
from typing import Dict

from backend.state import PrometheusState
from backend.llm.router import LLMRouter

# ── Structural skeleton ────────────────────────────────────────────────────────
# Saves a plain dict {model, cat_encodings, num_medians, ...} — no sklearn
# Pipeline or ColumnTransformer, so the pkl loads across all sklearn versions.
SCRIPT_TEMPLATE = """\
import warnings
warnings.filterwarnings('ignore')
import sys
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
{extra_imports}

try:
    df = pd.read_csv(sys.argv[1])
    df = df.dropna(subset=['{target_column}'])

    X = df.drop(columns=['{target_column}'])
    y = df['{target_column}']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42{stratify_arg}
    )

    _cat_cols = X_train.select_dtypes(include=['object', 'category']).columns.tolist()
    _num_cols = X_train.select_dtypes(exclude=['object', 'category']).columns.tolist()

    # Build category encodings from training data only
    _cat_encodings = {{}}
    for _col in _cat_cols:
        X_train[_col] = X_train[_col].fillna('missing').astype(str)
        X_test[_col]  = X_test[_col].fillna('missing').astype(str)
        _vals = sorted(X_train[_col].unique())
        _cat_encodings[_col] = {{v: i for i, v in enumerate(_vals)}}
        X_train[_col] = X_train[_col].map(_cat_encodings[_col]).fillna(len(_vals)).astype(int)
        X_test[_col]  = X_test[_col].map(_cat_encodings[_col]).fillna(len(_vals)).astype(int)

    # Numeric NaN imputation with training medians
    _num_medians = {{}}
    for _col in _num_cols:
        _med = float(X_train[_col].median())
        _num_medians[_col] = _med
        X_train[_col] = X_train[_col].fillna(_med)
        X_test[_col]  = X_test[_col].fillna(_med)

    # --- model block ---
{model_block}
    # --- end model block ---

    model.fit(X_train, y_train)

    try:
        import pickle as _pkl, base64 as _b64
        _save = {{
            'model': model,
            'cat_encodings': _cat_encodings,
            'cat_cols': _cat_cols,
            'num_medians': _num_medians,
            'num_cols': _num_cols,
            'feature_names': list(X_train.columns),
        }}
        print(f"__MODEL_PKL__:{{_b64.b64encode(_pkl.dumps(_save)).decode('ascii')}}", flush=True)
    except Exception:
        pass

    y_pred = model.predict(X_test)
    {metric_line}

    print(json.dumps({{
        "metric_name": "{metric_name}",
        "metric_value": round(float(metric_value), 6),
        "model_type": "{model_type}",
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test))
    }}))

except Exception as e:
    print(json.dumps({{"error": True, "error_type": type(e).__name__, "error_message": str(e)}}))
"""

METRIC_CONFIG = {
    "roc_auc": {
        "imports": "from sklearn.metrics import roc_auc_score",
        "line": "metric_value = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])",
    },
    "r2": {
        "imports": "from sklearn.metrics import r2_score",
        "line": "metric_value = r2_score(y_test, y_pred)",
    },
    "rmse": {
        "imports": "from sklearn.metrics import mean_squared_error",
        "line": "metric_value = float(np.sqrt(mean_squared_error(y_test, y_pred)))",
    },
    "accuracy": {
        "imports": "from sklearn.metrics import accuracy_score",
        "line": "metric_value = accuracy_score(y_test, y_pred)",
    },
    "f1": {
        "imports": "from sklearn.metrics import f1_score",
        "line": "metric_value = f1_score(y_test, y_pred, average='weighted')",
    },
}

FALLBACK_BLOCKS = {
    "classifier": (
        "    from sklearn.ensemble import RandomForestClassifier\n"
        "    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')"
    ),
    "regressor": (
        "    from sklearn.ensemble import RandomForestRegressor\n"
        "    model = RandomForestRegressor(n_estimators=100, random_state=42)"
    ),
}

MODEL_BLOCK_PROMPT = """Write ONLY the model instantiation block for a Python ML script.

Architecture spec:
{arch_json}

Context:
- Task type: {task_type}
- Class imbalance detected: {imbalance}
- X_train, X_test are already encoded (all numeric, no NaN)
- The script calls model.fit(X_train, y_train) automatically after your block

Your block must:
1. Import the model class
2. Instantiate the model with the hyperparameters from the spec

Hard rules:
- Every line MUST begin with exactly 4 spaces
- Variable MUST be named exactly: model
- Only import from: sklearn, xgboost, lightgbm
- Do NOT call model.fit() — handled by the script
- Return ONLY the indented block — no markdown, no backticks, no explanation"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return raw


def _normalize_block(block: str) -> str:
    lines = textwrap.dedent(block).split("\n")
    return "\n".join("    " + ln if ln.strip() else "" for ln in lines)


def _validate_block(block: str) -> tuple[bool, str]:
    dedented = textwrap.dedent(block)
    try:
        compile(dedented, "<model_block>", "exec")
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    if "model" not in block:
        return False, "Block must assign a variable named 'model'"
    return True, ""


_MODEL_SENTINEL = "__PROMETHEUS_MODEL_BLOCK__"


def _build_script(model_block, target_column, metric, model_type, task_type):
    mc = METRIC_CONFIG.get(metric, METRIC_CONFIG["roc_auc"])
    stratify = ", stratify=y" if "classif" in task_type else ""
    template_with_sentinel = SCRIPT_TEMPLATE.replace("{model_block}", _MODEL_SENTINEL)
    formatted = template_with_sentinel.format(
        extra_imports=mc["imports"],
        target_column=target_column,
        stratify_arg=stratify,
        metric_line=mc["line"],
        metric_name=metric,
        model_type=model_type,
    )
    return formatted.replace(_MODEL_SENTINEL, _normalize_block(model_block))


async def code_generator_node(state: PrometheusState, architecture: Dict) -> str:
    router = LLMRouter()
    target_column = state["target_column"]
    task_type = state["task_type"]
    evaluation_metric = state["evaluation_metric"]
    imbalance = state["class_imbalance_detected"]
    model_type = architecture.get("model_type", "RandomForestClassifier")

    prompt = MODEL_BLOCK_PROMPT.format(
        arch_json=json.dumps(architecture, indent=2),
        task_type=task_type,
        imbalance=imbalance,
    )

    model_block = None
    for attempt in range(3):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=(
                "You are an expert Python ML engineer. "
                "Output only indented Python code (4-space indent). No markdown, no prose."
            ),
            user_message=prompt,
        )
        raw = _strip_fences(raw)
        ok, err = _validate_block(raw)
        if ok:
            model_block = raw
            break
        prompt = (
            f"Issue: {err}\n\nFix it. 4-space indent, variable named 'model', no fit() call.\n"
            f"Architecture: {json.dumps(architecture, indent=2)}\nReturn ONLY the block."
        )

    if model_block is None:
        fallback_key = "regressor" if "regress" in task_type else "classifier"
        model_block = FALLBACK_BLOCKS[fallback_key]

    return _build_script(
        model_block=model_block,
        target_column=target_column,
        metric=evaluation_metric,
        model_type=model_type,
        task_type=task_type,
    )
