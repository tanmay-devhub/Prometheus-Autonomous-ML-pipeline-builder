import pytest
from unittest.mock import AsyncMock, patch
from execution.code_validator import validate_generated_code

COLUMNS = ["age", "income", "education", "target"]
TARGET = "target"

VALID_CODE = '''
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
import json
import sys

try:
    df = pd.read_csv(sys.argv[1])
    X = df[["age", "income", "education"]].fillna(0)
    y = df["target"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = GradientBoostingClassifier(n_estimators=100)
    model.fit(X_train, y_train)
    y_pred = model.predict_proba(X_test)[:, 1]
    metric_value = roc_auc_score(y_test, y_pred)
    print(json.dumps({"metric_name": "roc_auc", "metric_value": metric_value,
                      "model_type": "GradientBoostingClassifier",
                      "train_samples": len(X_train), "test_samples": len(X_test)}))
except Exception as e:
    print(json.dumps({"error": True, "error_type": type(e).__name__, "error_message": str(e)}))
'''

def test_valid_code_passes_all_checks():
    is_valid, failures = validate_generated_code(VALID_CODE, COLUMNS, TARGET)
    assert is_valid, f"Expected valid code but got failures: {failures}"


def test_wrong_column_name_caught():
    bad_code = VALID_CODE.replace('df[["age", "income", "education"]]', 'df[["age", "income", "nonexistent_col"]]')
    is_valid, failures = validate_generated_code(bad_code, COLUMNS, TARGET)
    assert not is_valid
    assert any("nonexistent_col" in f for f in failures)


def test_forbidden_import_caught():
    bad_code = "import requests\n" + VALID_CODE
    is_valid, failures = validate_generated_code(bad_code, COLUMNS, TARGET)
    assert not is_valid
    assert any("requests" in f for f in failures)


def test_missing_sys_argv_caught():
    bad_code = VALID_CODE.replace("sys.argv[1]", '"hardcoded_path.csv"')
    is_valid, failures = validate_generated_code(bad_code, COLUMNS, TARGET)
    assert not is_valid
    assert any("sys.argv[1]" in f for f in failures)


def test_missing_metric_value_caught():
    bad_code = VALID_CODE.replace("metric_value", "value")
    is_valid, failures = validate_generated_code(bad_code, COLUMNS, TARGET)
    assert not is_valid
    assert any("metric_value" in f for f in failures)


def test_syntax_error_caught():
    bad_code = "def broken(\n    pass"
    is_valid, failures = validate_generated_code(bad_code, COLUMNS, TARGET)
    assert not is_valid
    assert any("SyntaxError" in f for f in failures)
