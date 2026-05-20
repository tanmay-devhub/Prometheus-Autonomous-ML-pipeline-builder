import json
from datetime import datetime
from typing import Any, Dict, List

from regression.state import RegressionState, ExperimentResult
from shared.llm.router import LLMRouter


async def model_selector_node(state: RegressionState) -> RegressionState:
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
        state["current_phase"] = "awaiting_model_approval"
        return state

    a = successful[0]
    b = successful[1]
    metric = state["evaluation_metric"]

    def metric_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get(metric, 0.0)

    def rmse_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get("rmse", float("inf"))

    def mae_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get("mae", float("inf"))

    def r2_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get("r2", -999.0)

    prompt = (
        f"Two regression experiments completed. Select the winner.\n\n"
        f"Experiment A — {a['architecture_name']}:\n"
        f"  RMSE: {rmse_val(a):.4f}\n"
        f"  MAE: {mae_val(a):.4f}\n"
        f"  R2: {r2_val(a):.4f}\n"
        f"  Retry count: {a.get('retry_count', 0)}\n\n"
        f"Experiment B — {b['architecture_name']}:\n"
        f"  RMSE: {rmse_val(b):.4f}\n"
        f"  MAE: {mae_val(b):.4f}\n"
        f"  R2: {r2_val(b):.4f}\n"
        f"  Retry count: {b.get('retry_count', 0)}\n\n"
        f"Primary metric: {metric} (for regression: lower RMSE and MAE are better, higher R2 is better)\n"
        f"Consider all three metrics and retry count (fewer = more robust).\n"
        f"Note which model had better R2 even if RMSE is slightly higher.\n"
        f'Return JSON: {{"winner": "A"|"B", "justification": "<2 sentences referencing specific numbers>"}}'
    )

    raw = await router.call(
        task_type="complex_decision",
        system_prompt="You are an ML expert selecting the best regression model from two experiments.",
        user_message=prompt,
    )

    try:
        decision = json.loads(raw.strip())
        winner_key = decision.get("winner", "A")
        winner = a if winner_key == "A" else b
        justification = decision.get("justification", "Selected based on metric performance.")
    except json.JSONDecodeError:
        # Fallback: pick by primary metric (lower RMSE/MAE is better, higher R2 is better)
        if metric == "r2":
            winner = a if r2_val(a) >= r2_val(b) else b
        else:
            winner = a if metric_val(a) <= metric_val(b) else b
        justification = (
            f"Automatically selected '{winner['architecture_name']}' with "
            f"RMSE={rmse_val(winner):.4f}, MAE={mae_val(winner):.4f}, R2={r2_val(winner):.4f}."
        )

    state["winning_experiment"] = winner
    state["winning_justification"] = justification
    state["current_phase"] = "awaiting_model_approval"

    state["debug_log"].append({
        "phase": "model_selector",
        "timestamp": datetime.utcnow().isoformat(),
        "winner": winner["architecture_name"],
        "justification": justification,
    })

    return state
