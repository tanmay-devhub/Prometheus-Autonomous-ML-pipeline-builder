import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.state import PrometheusState, ExperimentResult
from backend.agents.failure_diagnostician import failure_diagnostician_node
from backend.agents.fix_executor import fix_executor_node
from execution.e2b_executor import ExecutionResult


def make_state() -> PrometheusState:
    return {
        "job_id": "test-debug",
        "user_description": "Predict target",
        "dataset_path": "demo_datasets/titanic.csv",
        "dataset_columns": ["PassengerId", "Pclass", "Sex", "Age", "Survived"],
        "dataset_sample_rows": [],
        "dataset_row_count": 891,
        "task_type": "binary_classification",
        "target_column": "Survived",
        "evaluation_metric": "roc_auc",
        "domain_flags": [],
        "problem_analysis_raw": None,
        "problem_approved": True,
        "model_approved": False,
        "profile_report": {},
        "validation_warnings": [],
        "leakage_warnings": [],
        "class_imbalance_detected": False,
        "imbalance_ratio": None,
        "architectures": [],
        "experiment_results": [],
        "current_retry_count": 0,
        "winning_experiment": None,
        "winning_justification": None,
        "model_card": None,
        "shap_plot_path": None,
        "generated_endpoint_code": None,
        "generated_requirements": None,
        "plain_english_explanation": None,
        "current_phase": "experiments",
        "error_message": None,
        "debug_log": [],
    }


def make_experiment(error_type: str = "column_error", stderr: str = "KeyError: 'wrong_column'") -> ExperimentResult:
    return {
        "experiment_id": "test-exp",
        "architecture_name": "test_arch",
        "generated_code": "import pandas as pd\ndf = pd.read_csv(sys.argv[1])\nprint(df['wrong_column'])",
        "stdout": "",
        "stderr": stderr,
        "exit_code": 1,
        "parsed_metrics": {},
        "success": False,
        "retry_count": 0,
        "failure_type": error_type,
        "fix_history": [],
        "mlflow_run_id": None,
    }


@pytest.mark.asyncio
async def test_column_error_identified():
    state = make_state()
    exp = make_experiment(error_type=None, stderr="KeyError: 'wrong_column'")

    with patch("backend.agents.failure_diagnostician.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.call = AsyncMock(return_value='{"failure_type": "column_error"}')
        diagnosis = await failure_diagnostician_node(state, exp)

    assert diagnosis["failure_type"] == "column_error"
    assert "column names available" in diagnosis["fix_instructions"]


@pytest.mark.asyncio
async def test_max_retries_exhausted():
    state = make_state()
    exp = make_experiment()
    exp["retry_count"] = 3  # at max retries

    with patch("backend.agents.fix_executor.LLMRouter") as MockRouter:
        with patch("backend.agents.fix_executor.E2BExecutor") as MockExecutor:
            diagnosis = {"failure_type": "column_error", "fix_strategy": "column_error", "fix_instructions": "Fix columns"}
            result = await fix_executor_node(state, exp, diagnosis)

    assert result["success"] is False
    assert any(e.get("action") == "max_retries_exhausted" for e in state["debug_log"])


@pytest.mark.asyncio
async def test_fix_succeeds_on_retry():
    state = make_state()
    exp = make_experiment(error_type="column_error")
    exp["retry_count"] = 0

    fixed_code = """
import warnings
warnings.filterwarnings('ignore')
import pandas as pd, numpy as np, json, sys
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score

try:
    df = pd.read_csv(sys.argv[1])
    X = df[["Pclass", "Age"]].fillna(0)
    y = df["Survived"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    m = LogisticRegression()
    m.fit(X_train, y_train)
    v = roc_auc_score(y_test, m.predict_proba(X_test)[:, 1])
    print(json.dumps({"metric_name": "roc_auc", "metric_value": v, "model_type": "LR",
                      "train_samples": len(X_train), "test_samples": len(X_test)}))
except Exception as e:
    print(json.dumps({"error": True, "error_type": type(e).__name__, "error_message": str(e)}))
"""

    mock_exec_result = ExecutionResult(
        stdout='{"metric_name": "roc_auc", "metric_value": 0.78, "model_type": "LR", "train_samples": 712, "test_samples": 179}',
        stderr="",
        exit_code=0,
        success=True,
        parsed_metrics={"roc_auc": 0.78},
        error_type=None,
        error_message=None,
        execution_time_seconds=2.0,
    )

    diagnosis = {"failure_type": "column_error", "fix_strategy": "column_error", "fix_instructions": "Fix column names"}

    with patch("backend.agents.fix_executor.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.call = AsyncMock(return_value=fixed_code)
        with patch("backend.agents.fix_executor.E2BExecutor") as MockExecutor:
            mock_e2b = MockExecutor.return_value
            mock_e2b.run = AsyncMock(return_value=mock_exec_result)
            result = await fix_executor_node(state, exp, diagnosis)

    assert result["success"] is True
    assert result["retry_count"] == 1
    assert len(result["fix_history"]) == 1
