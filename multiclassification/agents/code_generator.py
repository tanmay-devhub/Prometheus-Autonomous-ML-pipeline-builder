import json
import textwrap
from typing import Dict

from multiclassification.state import MultiClassState
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

    # Target encoding (multiclass — always LabelEncoder)
    _target_col = '{target_column}'
    _le_target = LabelEncoder()
    _le_target.fit(df[_target_col].astype(str))
    _class_names = _le_target.classes_.tolist()
    _label_to_int = {{label: int(i) for i, label in enumerate(_class_names)}}
    _int_to_label = {{str(int(i)): label for i, label in enumerate(_class_names)}}
    df[_target_col] = _le_target.transform(df[_target_col].astype(str))

    X = df.drop(columns=[_target_col])
    y = df[_target_col]
    _original_feature_columns = list(X.columns)

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError:
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
        'class_names':                    _class_names,
        'label_to_int':                   _label_to_int,
        'int_to_label':                   _int_to_label,
        'binary_encoders':                _binary_encoders,
        'multi_encoders':                 _multi_encoders,
        'num_medians':                    _num_medians,
        'original_feature_columns':       _original_feature_columns,
        'feature_columns_after_encoding': list(X_train.columns),
    }}

    # --- model block ---
{model_block}
    # --- end model block ---

    # Class balancing for multiclass
    _sample_weight = None
    try:
        if hasattr(model, 'class_weight'):
            model.set_params(class_weight='balanced')
        elif hasattr(model, 'is_unbalance'):
            model.set_params(is_unbalance=True)
        else:
            from sklearn.utils.class_weight import compute_sample_weight as _csw
            _sample_weight = _csw('balanced', y_train)
    except Exception:
        pass

    if _sample_weight is not None:
        model.fit(X_train, y_train, sample_weight=_sample_weight)
    else:
        model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    {metric_line}

    # Multiclass metrics
    from sklearn.metrics import accuracy_score as _acc_fn, f1_score as _f1_fn, classification_report as _cr_fn
    _accuracy = float(_acc_fn(y_test, y_pred))
    _f1_macro = float(_f1_fn(y_test, y_pred, average='macro', zero_division=0))
    _f1_weighted = float(_f1_fn(y_test, y_pred, average='weighted', zero_division=0))

    try:
        _report = _cr_fn(y_test, y_pred, output_dict=True, zero_division=0)
        _per_class_f1 = {{}}
        for _k, _v in _report.items():
            if _k in ('accuracy', 'macro avg', 'weighted avg'):
                continue
            try:
                _idx = int(_k)
                if _idx < len(_class_names):
                    _per_class_f1[_class_names[_idx]] = round(float(_v.get('f1-score', 0)), 4)
            except (ValueError, TypeError):
                if _k in _class_names:
                    _per_class_f1[_k] = round(float(_v.get('f1-score', 0)), 4)
    except Exception:
        _per_class_f1 = {{}}

    try:
        import pickle as _pkl, base64 as _b64
        _save = {{
            'model':            model,
            'encoding_map':     _encoding_map,
            'feature_names':    list(X_train.columns),
            'training_metrics': {{
                'accuracy':    round(_accuracy, 6),
                'f1_macro':    round(_f1_macro, 6),
                'f1_weighted': round(_f1_weighted, 6),
                'per_class_f1': _per_class_f1,
                'class_names': _class_names,
                'num_classes': len(_class_names),
            }},
        }}
        print(f"__MODEL_PKL__:{{_b64.b64encode(_pkl.dumps(_save)).decode('ascii')}}", flush=True)
    except Exception:
        pass

    print(json.dumps({{
        "metric_name":   "{metric_name}",
        "metric_value":  round(float(metric_value), 6),
        "accuracy":      round(_accuracy, 6),
        "f1_macro":      round(_f1_macro, 6),
        "f1_weighted":   round(_f1_weighted, 6),
        "num_classes":   len(_class_names),
        "class_names":   _class_names,
        "per_class_f1":  _per_class_f1,
        "model_type":    "{model_type}",
        "train_samples": int(len(X_train)),
        "test_samples":  int(len(X_test)),
    }}))

except Exception as e:
    print(json.dumps({{"error": True, "error_type": type(e).__name__, "error_message": str(e)}}))
"""

METRIC_CONFIG = {
    "f1_macro": {
        "imports": "from sklearn.metrics import f1_score",
        "line": "metric_value = f1_score(y_test, y_pred, average='macro', zero_division=0)",
    },
    "f1_weighted": {
        "imports": "from sklearn.metrics import f1_score",
        "line": "metric_value = f1_score(y_test, y_pred, average='weighted', zero_division=0)",
    },
    "accuracy": {
        "imports": "from sklearn.metrics import accuracy_score",
        "line": "metric_value = accuracy_score(y_test, y_pred)",
    },
    "log_loss": {
        "imports": "from sklearn.metrics import log_loss",
        "line": "metric_value = log_loss(y_test, model.predict_proba(X_test))",
    },
}

FALLBACK_BLOCK = (
    "    from sklearn.ensemble import RandomForestClassifier\n"
    "    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')"
)

MODEL_BLOCK_PROMPT = """Write ONLY the model instantiation block for a multiclass classification script.

Architecture spec:
{arch_json}

Context:
- Task type: multiclass_classification
- Number of classes: {num_classes}
- Class imbalance detected: {imbalance}
- X_train, X_test are already encoded (all numeric, no NaN)
- The script calls model.fit() automatically after your block

Your block must:
1. Import the model class
2. Instantiate the model with the hyperparameters from the spec

Multiclass-specific rules:
- LogisticRegression: set multi_class='multinomial', solver='lbfgs', max_iter=1000
- XGBClassifier: set objective='multi:softprob', num_class={num_classes}, eval_metric='mlogloss', use_label_encoder=False
- LGBMClassifier: set objective='multiclass', num_class={num_classes}, verbose=-1
- RandomForestClassifier / GradientBoostingClassifier: class_weight='balanced' handles imbalance
- Do NOT set class_weight on XGBClassifier or LGBMClassifier — script handles it

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
    mc = METRIC_CONFIG.get(metric, METRIC_CONFIG["f1_macro"])
    template_with_sentinel = SCRIPT_TEMPLATE.replace("{model_block}", _MODEL_SENTINEL)
    formatted = template_with_sentinel.format(
        extra_imports=mc["imports"],
        target_column=target_column,
        metric_line=mc["line"],
        metric_name=metric,
        model_type=model_type,
    )
    return formatted.replace(_MODEL_SENTINEL, _normalize_block(model_block))


async def code_generator_node(state: MultiClassState, architecture: Dict) -> str:
    router = LLMRouter()
    target_column = state["target_column"]
    evaluation_metric = state["evaluation_metric"]
    imbalance = state["class_imbalance_detected"]
    num_classes = state.get("num_classes", 3)
    model_type = architecture.get("model_type", "RandomForestClassifier")

    prompt = MODEL_BLOCK_PROMPT.format(
        arch_json=json.dumps(architecture, indent=2),
        num_classes=num_classes,
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
        model_block = FALLBACK_BLOCK

    return _build_script(
        model_block=model_block,
        target_column=target_column,
        metric=evaluation_metric,
        model_type=model_type,
    )
