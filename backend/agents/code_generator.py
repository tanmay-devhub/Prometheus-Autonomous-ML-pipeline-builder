import json
import textwrap
from typing import Dict

from backend.state import PrometheusState
from backend.llm.router import LLMRouter

SCRIPT_TEMPLATE = """\
import warnings
warnings.filterwarnings('ignore')
import sys
import re
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
{extra_imports}

def _safe_col(name):
    return re.sub(r'[^A-Za-z0-9_]', '_', str(name))

try:
    df = pd.read_csv(sys.argv[1])
    df = df.dropna(subset=['{target_column}'])

    # Fix numeric columns stored as strings
    for _col in df.columns:
        if df[_col].dtype == 'object':
            _conv = pd.to_numeric(df[_col], errors='coerce')
            if _conv.notna().mean() > 0.9:
                df[_col] = _conv

    # Encode target column (only if non-numeric)
    _target_col = '{target_column}'
    _target_mapping = {{}}
    _reverse_target_mapping = {{}}
    if not pd.api.types.is_numeric_dtype(df[_target_col]):
        _tvs = df[_target_col].dropna().unique()
        _sl  = [str(v).strip().lower() for v in _tvs]
        if set(_sl) <= {{'yes', 'no'}}:
            _target_mapping = {{str(v): (1 if str(v).strip().lower() == 'yes' else 0) for v in _tvs}}
        elif set(_sl) <= {{'true', 'false'}}:
            _target_mapping = {{str(v): (1 if str(v).strip().lower() == 'true' else 0) for v in _tvs}}
        else:
            _le_t = LabelEncoder()
            _le_t.fit(df[_target_col].astype(str))
            _target_mapping = {{str(c): int(i) for i, c in enumerate(_le_t.classes_)}}
        df[_target_col] = df[_target_col].astype(str).map(_target_mapping).astype(int)
        _reverse_target_mapping = {{int(v): k for k, v in _target_mapping.items()}}

    X = df.drop(columns=[_target_col])
    y = df[_target_col]
    _original_feature_columns = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42{stratify_arg}
    )

    # Binary string feature encoding (2 unique values)
    _binary_encoders = {{}}
    for _col in X_train.select_dtypes(include=['object', 'category']).columns.tolist():
        if X_train[_col].nunique() <= 2:
            _le = LabelEncoder()
            _vals = X_train[_col].fillna('missing').astype(str)
            _le.fit(_vals)
            _map = {{c: int(i) for i, c in enumerate(_le.classes_)}}
            _binary_encoders[_col] = {{'type': 'binary', 'mapping': _map, 'reverse': {{int(i): c for c, i in _map.items()}}}}
            X_train[_col] = _vals.map(_map).fillna(0).astype(int)
            X_test[_col]  = X_test[_col].fillna('missing').astype(str).map(_map).fillna(0).astype(int)

    # Multi-category one-hot encoding (>2 unique values)
    _multi_encoders = {{}}
    for _col in X_train.select_dtypes(include=['object', 'category']).columns.tolist():
        _cats  = X_train[_col].dropna().astype(str).unique().tolist()
        # fillna('nan') before astype(str) so NaN → "nan" consistently (avoids None/"" mismatch at predict time)
        _dt    = pd.get_dummies(X_train[_col].fillna('nan').astype(str), prefix=_col, drop_first=False)
        _dv    = pd.get_dummies(X_test[_col].fillna('nan').astype(str),  prefix=_col, drop_first=False)
        # Sanitize column names — XGBoost/LightGBM reject <, >, [, ], spaces, etc.
        _safe_names = {{c: _safe_col(c) for c in _dt.columns}}
        # Map sanitized column name → original category value for correct reverse lookup
        _col_to_category = {{_safe_col(c): c[len(_col)+1:] for c in _dt.columns}}
        _dt.rename(columns=_safe_names, inplace=True)
        _dv.rename(columns=_safe_names, inplace=True)
        _ecols = _dt.columns.tolist()
        _multi_encoders[_col] = {{'type': 'onehot', 'encoded_columns': _ecols, 'categories': _cats, 'col_to_category': _col_to_category}}
        X_train = pd.concat([X_train.drop(columns=[_col]), _dt], axis=1)
        X_test  = pd.concat([X_test.drop(columns=[_col]),  _dv.reindex(columns=_ecols, fill_value=0)], axis=1)

    # Numeric NaN imputation with training medians
    _num_medians = {{}}
    for _col in X_train.select_dtypes(exclude=['object', 'category']).columns.tolist():
        _med = float(X_train[_col].median())
        _num_medians[_col] = _med
        X_train[_col] = X_train[_col].fillna(_med)
        X_test[_col]  = X_test[_col].fillna(_med)

    _encoding_map = {{
        'target_column':                  _target_col,
        'target_mapping':                 _target_mapping,
        'reverse_target_mapping':         _reverse_target_mapping,
        'binary_encoders':                _binary_encoders,
        'multi_encoders':                 _multi_encoders,
        'num_medians':                    _num_medians,
        'original_feature_columns':       _original_feature_columns,
        'feature_columns_after_encoding': list(X_train.columns),
    }}

    # --- model block ---
{model_block}
    # --- end model block ---

    # Enforce class balance regardless of what the model block set
    _sample_weight = None
    if '{task_type}' == 'binary_classification':
        _y_int = y_train.astype(int)
        _n_neg = max(int((_y_int == 0).sum()), 1)
        _n_pos = max(int((_y_int == 1).sum()), 1)
        try:
            if hasattr(model, 'scale_pos_weight'):
                model.set_params(scale_pos_weight=_n_neg / _n_pos)
            elif hasattr(model, 'class_weight'):
                model.set_params(class_weight='balanced')
            else:
                from sklearn.utils.class_weight import compute_sample_weight as _csw
                _sample_weight = _csw('balanced', y_train)
        except Exception:
            pass

    if _sample_weight is not None:
        model.fit(X_train, y_train, sample_weight=_sample_weight)
    else:
        model.fit(X_train, y_train)

    try:
        import pickle as _pkl, base64 as _b64
        _save = {{
            'model':         model,
            'encoding_map':  _encoding_map,
            'feature_names': list(X_train.columns),
        }}
        print(f"__MODEL_PKL__:{{_b64.b64encode(_pkl.dumps(_save)).decode('ascii')}}", flush=True)
    except Exception:
        pass

    y_pred = model.predict(X_test)
    {metric_line}

    print(json.dumps({{
        "metric_name":   "{metric_name}",
        "metric_value":  round(float(metric_value), 6),
        "model_type":    "{model_type}",
        "train_samples": int(len(X_train)),
        "test_samples":  int(len(X_test)),
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
    "mae": {
        "imports": "from sklearn.metrics import mean_absolute_error",
        "line": "metric_value = mean_absolute_error(y_test, y_pred)",
    },
    "accuracy": {
        "imports": "from sklearn.metrics import accuracy_score",
        "line": "metric_value = accuracy_score(y_test, y_pred)",
    },
    "f1": {
        "imports": "from sklearn.metrics import f1_score",
        "line": "metric_value = f1_score(y_test, y_pred, average='weighted')",
    },
    "pr_auc": {
        "imports": "from sklearn.metrics import average_precision_score",
        "line": "metric_value = average_precision_score(y_test, model.predict_proba(X_test)[:, 1])",
    },
    "log_loss": {
        "imports": "from sklearn.metrics import log_loss",
        "line": "metric_value = log_loss(y_test, model.predict_proba(X_test))",
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
- The script calls model.fit() automatically after your block

Your block must:
1. Import the model class
2. Instantiate the model with the hyperparameters from the spec

Class balancing rules (MANDATORY for binary_classification):
- RandomForestClassifier / LogisticRegression / LGBMClassifier: set class_weight='balanced'
- XGBClassifier: the script handles scale_pos_weight automatically — do NOT set it here
- GradientBoostingClassifier: the script handles sample_weight automatically — do NOT set it here

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
        task_type=task_type,
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
