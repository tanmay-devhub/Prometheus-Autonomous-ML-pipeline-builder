import asyncio
from typing import Dict

from classification.state import ClassificationState, ExperimentResult
from classification.agents.code_generator import code_generator_node
from classification.agents.result_interpreter import result_interpreter_node
from classification.agents.failure_diagnostician import failure_diagnostician_node
from classification.agents.fix_executor import fix_executor_node
from classification.config import MAX_RETRIES
from shared.execution.e2b_executor import E2BExecutor
from classification.tracking.mlflow_tracker import MLflowTracker


async def _run_single_experiment(
    state: ClassificationState, architecture: Dict, experiment_id: str
) -> ExperimentResult:
    tracker = MLflowTracker()
    run_id = tracker.start_run(state["job_id"], architecture["name"])

    tracker.log_params(run_id, {
        "model_type": architecture.get("model_type", "unknown"),
        "architecture_name": architecture["name"],
        "job_id": state["job_id"],
        "retry_count": 0,
    })

    generated_code = await code_generator_node(state, architecture)
    tracker.log_code(run_id, generated_code)

    experiment_result: ExperimentResult = {
        "experiment_id": experiment_id,
        "architecture_name": architecture["name"],
        "generated_code": generated_code,
        "stdout": "",
        "stderr": "",
        "exit_code": -1,
        "parsed_metrics": {},
        "success": False,
        "retry_count": 0,
        "failure_type": None,
        "fix_history": [],
        "mlflow_run_id": run_id,
    }

    executor = E2BExecutor()
    exec_result = await executor.run(
        code=generated_code,
        dataset_path=state["dataset_path"],
    )

    experiment_result["stdout"] = exec_result.stdout
    experiment_result["stderr"] = exec_result.stderr
    experiment_result["exit_code"] = exec_result.exit_code
    experiment_result["success"] = exec_result.success
    experiment_result["parsed_metrics"] = exec_result.parsed_metrics
    experiment_result["error_type"] = exec_result.error_type
    experiment_result["model_pkl_b64"] = exec_result.model_pkl_b64

    for _ in range(MAX_RETRIES + 1):
        experiment_result = await result_interpreter_node(state, experiment_result)
        if experiment_result["success"]:
            break
        if experiment_result.get("retry_count", 0) >= MAX_RETRIES:
            break
        diagnosis = await failure_diagnostician_node(state, experiment_result)
        experiment_result = await fix_executor_node(state, experiment_result, diagnosis, architecture)
        tracker.log_fix_attempt(
            run_id,
            experiment_result["retry_count"],
            diagnosis["failure_type"],
            diagnosis["fix_instructions"],
        )

    metric = state["evaluation_metric"]
    metric_val = experiment_result["parsed_metrics"].get(metric, 0.0)
    tracker.log_metrics(run_id, {metric: float(metric_val) if metric_val == metric_val else 0.0})
    tracker.end_run(run_id, "FINISHED" if experiment_result["success"] else "FAILED")

    return experiment_result


async def parallel_experiments_node(state: ClassificationState) -> ClassificationState:
    architectures = state["architectures"]
    results = await asyncio.gather(
        _run_single_experiment(state, architectures[0], f"{state['job_id']}_exp_A"),
        _run_single_experiment(state, architectures[1], f"{state['job_id']}_exp_B"),
    )
    state["experiment_results"] = list(results)
    state["current_phase"] = "experiments_complete"
    return state
