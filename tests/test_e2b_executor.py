import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass

from execution.e2b_executor import E2BExecutor, ExecutionResult

VALID_CODE = """
import json, sys
print(json.dumps({"metric_name": "roc_auc", "metric_value": 0.85,
                  "model_type": "LogisticRegression",
                  "train_samples": 700, "test_samples": 180}))
"""

SYNTAX_ERROR_CODE = """
def broken(:
    pass
"""

BAD_FORMAT_CODE = """
import sys
print("This is not JSON on the last line")
"""


def make_mock_sandbox(stdout: str = "", stderr: str = "", exit_code: int = 0):
    sandbox = MagicMock()
    sandbox.files.write = MagicMock()
    install_result = MagicMock()
    install_result.exit_code = 0
    run_result = MagicMock()
    run_result.stdout = stdout
    run_result.stderr = stderr
    run_result.exit_code = exit_code
    sandbox.commands.run = MagicMock(side_effect=[install_result, run_result])
    sandbox.kill = MagicMock()
    return sandbox


@pytest.mark.asyncio
async def test_valid_code_success():
    valid_output = '{"metric_name": "roc_auc", "metric_value": 0.85, "model_type": "LR", "train_samples": 700, "test_samples": 180}'
    mock_sandbox = make_mock_sandbox(stdout=valid_output)

    with patch("execution.e2b_executor.Sandbox", return_value=mock_sandbox):
        with patch("builtins.open", MagicMock()):
            executor = E2BExecutor()
            result = await executor.run(VALID_CODE, "fake_dataset.csv")

    assert result.success is True
    assert result.parsed_metrics.get("roc_auc") == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_syntax_error_in_output():
    error_output = '{"error": true, "error_type": "SyntaxError", "error_message": "invalid syntax"}'
    mock_sandbox = make_mock_sandbox(stdout=error_output, exit_code=1)

    with patch("execution.e2b_executor.Sandbox", return_value=mock_sandbox):
        with patch("builtins.open", MagicMock()):
            executor = E2BExecutor()
            result = await executor.run(SYNTAX_ERROR_CODE, "fake_dataset.csv")

    assert result.success is False
    assert result.error_type == "SyntaxError"


@pytest.mark.asyncio
async def test_bad_json_format_output_parse_error():
    mock_sandbox = make_mock_sandbox(stdout="This is not JSON on the last line", exit_code=0)

    with patch("execution.e2b_executor.Sandbox", return_value=mock_sandbox):
        with patch("builtins.open", MagicMock()):
            executor = E2BExecutor()
            result = await executor.run(BAD_FORMAT_CODE, "fake_dataset.csv")

    assert result.success is False
    assert result.error_type == "OutputParseError"
