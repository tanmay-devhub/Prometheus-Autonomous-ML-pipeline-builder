import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from unittest.mock import AsyncMock, patch

from backend.agents.data_profiler import (
    _run_validation, _detect_leakage, _detect_imbalance, data_profiler_node
)
from backend.state import PrometheusState


def make_state(df: pd.DataFrame, task_type: str = "binary_classification", target: str = "target") -> PrometheusState:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        df.to_csv(f, index=False)
        path = f.name

    return {
        "job_id": "test",
        "user_description": "test",
        "dataset_path": path,
        "dataset_columns": df.columns.tolist(),
        "dataset_sample_rows": df.head(5).to_dict(orient="records"),
        "dataset_row_count": len(df),
        "task_type": task_type,
        "target_column": target,
        "evaluation_metric": "roc_auc",
        "domain_flags": [],
        "problem_analysis_raw": None,
        "problem_approved": True,
        "model_approved": False,
        "profile_report": None,
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
        "current_phase": "problem_approved",
        "error_message": None,
        "debug_log": [],
    }


def test_clean_dataset_no_block_warnings():
    df = pd.DataFrame({
        "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
        "feature2": ["a", "b", "c", "d", "e"],
        "target": [0, 1, 0, 1, 0],
    })
    warnings = _run_validation(df, "target")
    block_warnings = [w for w in warnings if w["severity"] == "block"]
    assert len(block_warnings) == 0


def test_high_null_column_generates_block_warning():
    df = pd.DataFrame({
        "feature1": [1.0, None, None, None, None, None, None, None, None, None],
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })
    warnings = _run_validation(df, "target")
    block_warnings = [w for w in warnings if w["severity"] == "block"]
    assert len(block_warnings) == 1
    assert "feature1" in block_warnings[0]["column"]


def test_leakage_detection_high_correlation():
    n = 100
    target = np.random.randint(0, 2, n).astype(float)
    leaky = target + np.random.normal(0, 0.001, n)

    df = pd.DataFrame({"leaky_feature": leaky, "normal_feature": np.random.randn(n), "target": target})
    leakage = _detect_leakage(df, "target")
    assert any("leaky_feature" in w for w in leakage)


def test_class_imbalance_detection():
    n_majority = 100
    n_minority = 5
    target = [0] * n_majority + [1] * n_minority
    df = pd.DataFrame({"feature": range(n_majority + n_minority), "target": target})
    detected, ratio = _detect_imbalance(df, "target")
    assert detected is True
    assert ratio < 0.1


@pytest.mark.asyncio
async def test_profiler_full_pipeline():
    df = pd.DataFrame({
        "age": [25, 30, 35, 40, 45],
        "income": [50000, 60000, 70000, 80000, 90000],
        "target": [0, 1, 0, 1, 0],
    })
    state = make_state(df)

    try:
        with patch("backend.agents.data_profiler.LLMRouter") as MockRouter:
            instance = MockRouter.return_value
            instance.call = AsyncMock(return_value="• Good data quality\n• No missing values")
            result = await data_profiler_node(state)

        assert result["profile_report"] is not None
        assert result["current_phase"] == "profiling_complete"
    finally:
        os.unlink(state["dataset_path"])
