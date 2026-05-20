import json
import textwrap
from typing import Dict

from regression.state import RegressionState
from shared.llm.router import LLMRouter

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

    # Target column is continuous — never encode it
    _target_col = '{target_column}'
    _target_log_transformed = False

    # Check for log transform (skewness > 1.5)
    _target_skew = float(df[_target_col].skew())
    if _target_skew > 1.5 and (df[_target_col] > 0).all():
        df[_target_col] = np.log1p(df[_target_col])
        _target_log_transformed = True

    X = df.drop(columns=[_target_col])
    y = df[_target_col]
    _original_feature_columns = list(X.columns)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
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
        _dt    = pd.get_dummies(X_train[_col].fillna('nan').astype(str), prefix=_col, drop_first=False)
        _dv    = pd.get_dummies(X_test[_col].fillna('nan').astype(str),  prefix=_col, drop_first=False)
        _safe_names = {{c: _safe_col(c) for c in _dt.columns}}
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
        'target_mapping':                 {{}},
        'reverse_target_mapping':         {{}},
        'binary_encoders':                _binary_encoders,
        'multi_encoders':                 _multi_encoders,
        'num_medians':                    _num_medians,
        'original_feature_columns':       _original_feature_columns,
        'feature_columns_after_encoding': list(X_train.columns),
        'target_log_transformed':         _target_log_transformed,
    }}

    # --- model block ---
{model_block}
    # --- end model block ---

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    # If log-transformed, reverse for metric computation
    if _target_log_transformed:
        y_pred_orig = np.expm1(y_pred)
        y_test_orig = np.expm1(y_test)
    else:
        y_pred_orig = y_pred
        y_test_orig = y_test

    {metric_line}

    from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
    _mae  = float(mean_absolute_error(y_test_orig, y_pred_orig))
    _r2   = float(r2_score(y_test_orig, y_pred_orig))
    _rmse = float(np.sqrt(mean_squared_error(y_test_orig, y_pred_orig)))

    # Tolerance-based success metrics
    _tmean = float(np.abs(y_test_orig).mean()) if len(y_test_orig) > 0 else 1.0
    _rmse_pct = round(float(_rmse / _tmean * 100), 2) if _tmean > 0 else 0.0

    def _wtol(_yt, _yp, _t):
        _a = np.abs(np.array(_yt, dtype=float))
        _v = _a > 1e-9
        if not _v.any():
            return 0.0
        _err = np.abs(np.array(_yp, dtype=float)[_v] - np.array(_yt, dtype=float)[_v]) / _a[_v]
        return round(float((_err <= _t).mean() * 100), 2)

    _w10 = _wtol(y_test_orig, y_pred_orig, 0.10)
    _w15 = _wtol(y_test_orig, y_pred_orig, 0.15)
    _w20 = _wtol(y_test_orig, y_pred_orig, 0.20)

    try:
        import pickle as _pkl, base64 as _b64
        _save = {{
            'model':         model,
            'encoding_map':  _encoding_map,
            'feature_names': list(X_train.columns),
            'training_metrics': {{
                'mae':              round(_mae, 4),
                'r2':               round(_r2,  4),
                'rmse':             round(_rmse, 4),
                'rmse_pct_of_mean': _rmse_pct,
                'within_10_pct':    _w10,
                'within_15_pct':    _w15,
                'within_20_pct':    _w20,
                'target_mean':      round(_tmean, 4),
            }},
        }}
        print(f"__MODEL_PKL__:{{_b64.b64encode(_pkl.dumps(_save)).decode('ascii')}}", flush=True)
    except Exception:
        pass

    print(json.dumps({{
        "metric_name":          "{metric_name}",
        "metric_value":         round(float(metric_value), 6),
        "mae":                  round(_mae, 6),
        "r2":                   round(_r2,  6),
        "rmse":                 round(_rmse, 6),
        "rmse_pct_of_mean":     _rmse_pct,
        "within_10_pct":        _w10,
        "within_15_pct":        _w15,
        "within_20_pct":        _w20,
        "target_mean":          round(_tmean, 4),
        "model_type":           "{model_type}",
        "train_samples":        int(len(X_train)),
        "test_samples":         int(len(X_test)),
        "target_log_transformed": _target_log_transformed,
    }}))

except Exception as e:
    import traceback
    print(json.dumps({{"error": True, "error_type": type(e).__name__, "error_message": str(e)}}))
"""

METRIC_CONFIG = {
    "rmse": {
        "imports": "from sklearn.metrics import mean_squared_error",
        "line": "metric_value = float(np.sqrt(mean_squared_error(y_test_orig, y_pred_orig)))",
    },
    "mae": {
        "imports": "from sklearn.metrics import mean_absolute_error",
        "line": "metric_value = float(mean_absolute_error(y_test_orig, y_pred_orig))",
    },
    "r2": {
        "imports": "from sklearn.metrics import r2_score",
        "line": "metric_value = float(r2_score(y_test_orig, y_pred_orig))",
    },
}

FALLBACK_BLOCK = (
    "    from sklearn.ensemble import RandomForestRegressor\n"
    "    model = RandomForestRegressor(n_estimators=100, random_state=42)"
)

MODEL_BLOCK_PROMPT = """Write ONLY the model instantiation block for a Python ML regression script.

Architecture spec:
{arch_json}

Context:
- Task type: regression
- X_train, X_test are already encoded (all numeric, no NaN)
- The script calls model.fit() automatically after your block
- NEVER use class_weight, scale_pos_weight, or any classification-specific param

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


def _build_script(model_block, target_column, metric, model_type):
    mc = METRIC_CONFIG.get(metric, METRIC_CONFIG["rmse"])
    template_with_sentinel = SCRIPT_TEMPLATE.replace("{model_block}", _MODEL_SENTINEL)
    formatted = template_with_sentinel.format(
        extra_imports=mc["imports"],
        target_column=target_column,
        metric_line=mc["line"],
        metric_name=metric,
        model_type=model_type,
    )
    return formatted.replace(_MODEL_SENTINEL, _normalize_block(model_block))


async def code_generator_node(state: RegressionState, architecture: Dict) -> str:
    router = LLMRouter()
    target_column = state["target_column"]
    evaluation_metric = state["evaluation_metric"]
    model_type = architecture.get("model_type", "RandomForestRegressor")

    prompt = MODEL_BLOCK_PROMPT.format(
        arch_json=json.dumps(architecture, indent=2),
    )

    model_block = None
    for attempt in range(3):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=(
                "You are an expert Python ML engineer writing regression model code. "
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
        model_block = FALLBACK_BLOCK

    return _build_script(
        model_block=model_block,
        target_column=target_column,
        metric=evaluation_metric,
        model_type=model_type,
    )
