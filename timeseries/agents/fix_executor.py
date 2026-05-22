import asyncio
from datetime import datetime
from typing import Any, Dict

from timeseries.state import TimeSeriesState as PrometheusState, ExperimentResult
from shared.llm.router import LLMRouter
from timeseries.config import MAX_RETRIES
from shared.execution.e2b_executor import E2BExecutor
from timeseries.agents.code_generator import code_generator_node

FIX_PROMPT_TEMPLATE = """You are fixing a broken time series forecasting Python script.

ORIGINAL SCRIPT:
{original_code}

FAILURE TYPE: {failure_type}

FIX INSTRUCTIONS:
{fix_instructions}

STDOUT FROM FAILED RUN:
{stdout}

STDERR FROM FAILED RUN:
{stderr}

Generate the corrected Python script. Apply the fix instructions precisely.
CRITICAL RULES:
- Always use chronological split (df.iloc[:split_idx] for train, df.iloc[split_idx:] for test) — NEVER random split
- Always use regression models only (XGBRegressor, LGBMRegressor, RandomForestRegressor, LinearRegression, Ridge)
- The script must print "FORECAST:[...]" before the final JSON metrics line
- Do not change anything that was working correctly.
Only return the Python code. No markdown, no backticks, no explanation."""


async def fix_executor_node(
    state: PrometheusState,
    experiment_result: ExperimentResult,
    diagnosis: Dict[str, str],
    architecture: Dict = None,
) -> ExperimentResult:
    retry_count = experiment_result.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        experiment_result["success"] = False
        state["debug_log"].append({
            "phase": "fix_executor",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "max_retries_exhausted",
            "failure_type": diagnosis.get("failure_type"),
            "experiment_id": experiment_result.get("experiment_id"),
        })
        return experiment_result

    fix_history = list(experiment_result.get("fix_history") or [])
    current_failure = diagnosis.get("failure_type")
    should_regenerate = (
        retry_count >= 1
        and fix_history
        and fix_history[-1].get("failure_type") == current_failure
        and architecture is not None
    )

    router = LLMRouter()

    if should_regenerate:
        state["debug_log"].append({
            "phase": "fix_executor",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "scratch_regeneration",
            "reason": f"failure_type '{current_failure}' repeated — discarding patched code",
            "experiment_id": experiment_result.get("experiment_id"),
            "retry_count": retry_count,
        })
        fixed_code = await code_generator_node(state, architecture)
    else:
        fix_prompt = FIX_PROMPT_TEMPLATE.format(
            original_code=experiment_result.get("generated_code", ""),
            failure_type=current_failure or "unknown",
            fix_instructions=diagnosis.get("fix_instructions", ""),
            stdout=experiment_result.get("stdout", "")[:2000],
            stderr=experiment_result.get("stderr", "")[:2000],
        )
        fixed_code = await router.call(
            task_type="code_fix",
            system_prompt="You are an expert Python ML engineer fixing a broken time series pipeline script.",
            user_message=fix_prompt,
        )

        fixed_code = fixed_code.strip()
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            fixed_code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    executor = E2BExecutor()
    exec_result = await executor.run(
        code=fixed_code,
        dataset_path=state["dataset_path"],
    )

    retry_count += 1
    fix_history.append({
        "retry": retry_count,
        "failure_type": diagnosis.get("failure_type"),
        "fix_applied": diagnosis.get("fix_instructions", "")[:200],
    })

    experiment_result["generated_code"] = fixed_code
    experiment_result["stdout"] = exec_result.stdout
    experiment_result["stderr"] = exec_result.stderr
    experiment_result["exit_code"] = exec_result.exit_code
    experiment_result["success"] = exec_result.success
    experiment_result["parsed_metrics"] = exec_result.parsed_metrics
    experiment_result["error_type"] = exec_result.error_type
    experiment_result["model_pkl_b64"] = exec_result.model_pkl_b64
    experiment_result["forecast_values"] = exec_result.forecast_values
    experiment_result["retry_count"] = retry_count
    experiment_result["fix_history"] = fix_history

    state["debug_log"].append({
        "phase": "fix_executor",
        "timestamp": datetime.utcnow().isoformat(),
        "experiment_id": experiment_result.get("experiment_id"),
        "retry_count": retry_count,
        "failure_type": diagnosis.get("failure_type"),
        "fix_success": exec_result.success,
    })

    return experiment_result
