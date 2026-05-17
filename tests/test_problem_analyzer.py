import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agents.problem_analyzer import problem_analyzer_node
from backend.state import PrometheusState


def make_state(**kwargs) -> PrometheusState:
    base: PrometheusState = {
        "job_id": "test-job",
        "user_description": "Predict survival on the Titanic",
        "dataset_path": "demo_datasets/titanic.csv",
        "dataset_columns": ["PassengerId", "Survived", "Pclass", "Name", "Sex", "Age"],
        "dataset_sample_rows": [{"PassengerId": 1, "Survived": 0, "Pclass": 3, "Name": "Smith", "Sex": "male", "Age": 22}],
        "dataset_row_count": 891,
        "task_type": None,
        "target_column": None,
        "evaluation_metric": None,
        "domain_flags": [],
        "problem_analysis_raw": None,
        "problem_approved": False,
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
        "current_phase": "initializing",
        "error_message": None,
        "debug_log": [],
    }
    base.update(kwargs)
    return base


VALID_RESPONSE = json.dumps({
    "task_type": "binary_classification",
    "target_column": "Survived",
    "evaluation_metric": "roc_auc",
    "confidence": 0.95,
    "reasoning": "User wants to predict survival (0/1), which is binary classification.",
    "domain_flags": [],
    "alternative_target": "",
    "warnings": [],
})


@pytest.mark.asyncio
async def test_valid_analysis():
    state = make_state()
    with patch("backend.agents.problem_analyzer.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.call = AsyncMock(return_value=VALID_RESPONSE)
        result = await problem_analyzer_node(state)

    assert result["task_type"] == "binary_classification"
    assert result["target_column"] == "Survived"
    assert result["evaluation_metric"] == "roc_auc"
    assert result["current_phase"] == "awaiting_problem_approval"


@pytest.mark.asyncio
async def test_invalid_json_then_valid():
    state = make_state()
    call_count = 0

    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "This is not JSON!!!"
        return VALID_RESPONSE

    with patch("backend.agents.problem_analyzer.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.call = mock_call
        result = await problem_analyzer_node(state)

    assert result["task_type"] == "binary_classification"
    assert result["target_column"] == "Survived"
    assert call_count == 2


@pytest.mark.asyncio
async def test_wrong_target_column_then_correct():
    state = make_state()
    wrong_response = json.dumps({
        "task_type": "binary_classification",
        "target_column": "NonExistentColumn",
        "evaluation_metric": "roc_auc",
        "confidence": 0.9,
        "reasoning": "Test",
        "domain_flags": [],
        "alternative_target": "",
        "warnings": [],
    })
    call_count = 0

    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return wrong_response
        return VALID_RESPONSE

    with patch("backend.agents.problem_analyzer.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.call = mock_call
        result = await problem_analyzer_node(state)

    assert result["target_column"] == "Survived"
    assert call_count == 2
