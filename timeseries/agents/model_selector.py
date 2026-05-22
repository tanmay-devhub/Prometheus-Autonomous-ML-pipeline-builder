import json
from datetime import datetime
from typing import Any, Dict, List

from timeseries.state import TimeSeriesState as PrometheusState, ExperimentResult
from shared.llm.router import LLMRouter


async def model_selector_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    successful = [r for r in state["experiment_results"] if r.get("success")]

    if not successful:
        state["error_message"] = "All experiments failed. See debug log for details."
        state["current_phase"] = "failed"
        return state

    if len(successful) == 1:
        winner = successful[0]
        state["winning_experiment"] = winner
        state["winning_justification"] = (
            f"Only experiment '{winner['architecture_name']}' completed successfully."
        )
        # Store forecast values from winner
        state["forecast_values"] = winner.get("forecast_values") or \
            winner.get("parsed_metrics", {}).get("forecast_values")
        state["train_cutoff_date"] = winner.get("parsed_metrics", {}).get("train_end_date")
        state["test_cutoff_date"] = winner.get("parsed_metrics", {}).get("test_end_date")
        state["current_phase"] = "awaiting_model_approval"
        return state

    # Two successful experiments — compare by RMSE (lower is better for time series)
    a = successful[0]
    b = successful[1]
    metric = state.get("evaluation_metric", "rmse")

    def metric_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get(metric, float("inf"))

    def mape_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get("mape", 0.0)

    prompt = (
        f"Two time series forecasting experiments completed. Select the winner.\n\n"
        f"Experiment A — {a['architecture_name']}:\n"
        f"  RMSE = {metric_val(a):.4f}\n"
        f"  MAE = {a['parsed_metrics'].get('mae', 'N/A')}\n"
        f"  MAPE = {mape_val(a):.2f}%\n"
        f"  Train period: {a['parsed_metrics'].get('train_start_date', 'N/A')} to {a['parsed_metrics'].get('train_end_date', 'N/A')}\n"
        f"  Test period: {a['parsed_metrics'].get('test_start_date', 'N/A')} to {a['parsed_metrics'].get('test_end_date', 'N/A')}\n"
        f"  Retry count: {a.get('retry_count', 0)}\n\n"
        f"Experiment B — {b['architecture_name']}:\n"
        f"  RMSE = {metric_val(b):.4f}\n"
        f"  MAE = {b['parsed_metrics'].get('mae', 'N/A')}\n"
        f"  MAPE = {mape_val(b):.2f}%\n"
        f"  Train period: {b['parsed_metrics'].get('train_start_date', 'N/A')} to {b['parsed_metrics'].get('train_end_date', 'N/A')}\n"
        f"  Test period: {b['parsed_metrics'].get('test_start_date', 'N/A')} to {b['parsed_metrics'].get('test_end_date', 'N/A')}\n"
        f"  Retry count: {b.get('retry_count', 0)}\n\n"
        f"Task type: timeseries\n"
        f"Primary metric: {metric} (LOWER IS BETTER)\n\n"
        f"Select the winner. Consider: RMSE (lower=better), MAPE (lower=better), retry count (fewer=more robust).\n"
        f'Return JSON: {{"winner": "A"|"B", "justification": "<2 sentences mentioning MAPE and train/test date ranges>"}}'
    )

    raw = await router.call(
        task_type="complex_decision",
        system_prompt="You are an ML expert selecting the best time series forecasting model.",
        user_message=prompt,
    )

    try:
        decision = json.loads(raw.strip())
        winner_key = decision.get("winner", "A")
        winner = a if winner_key == "A" else b
        justification = decision.get("justification", "Selected based on metric performance.")
    except json.JSONDecodeError:
        # Lower RMSE wins
        winner = a if metric_val(a) <= metric_val(b) else b
        justification = (
            f"Automatically selected '{winner['architecture_name']}' with "
            f"RMSE = {metric_val(winner):.4f} and MAPE = {mape_val(winner):.2f}%."
        )

    state["winning_experiment"] = winner
    state["winning_justification"] = justification

    # Store forecast values and date ranges from winner
    state["forecast_values"] = winner.get("forecast_values") or \
        winner.get("parsed_metrics", {}).get("forecast_values")
    state["train_cutoff_date"] = winner.get("parsed_metrics", {}).get("train_end_date")
    state["test_cutoff_date"] = winner.get("parsed_metrics", {}).get("test_end_date")

    state["current_phase"] = "awaiting_model_approval"

    state["debug_log"].append({
        "phase": "model_selector",
        "timestamp": datetime.utcnow().isoformat(),
        "winner": winner["architecture_name"],
        "justification": justification,
    })

    return state
