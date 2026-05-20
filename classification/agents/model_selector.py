import json
from datetime import datetime
from typing import Any, Dict, List

from classification.state import ClassificationState as PrometheusState, ExperimentResult
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
        state["current_phase"] = "awaiting_model_approval"
        return state

    # Two successful experiments — use Gemini to decide
    a = successful[0]
    b = successful[1]
    metric = state["evaluation_metric"]

    def metric_val(exp: ExperimentResult) -> float:
        return exp["parsed_metrics"].get(metric, 0.0)

    prompt = (
        f"Two ML experiments completed. Select the winner.\n\n"
        f"Experiment A — {a['architecture_name']}:\n"
        f"  Metric: {metric} = {metric_val(a)}\n"
        f"  Model: {a.get('architecture_name', 'unknown')}\n"
        f"  Retry count: {a.get('retry_count', 0)}\n\n"
        f"Experiment B — {b['architecture_name']}:\n"
        f"  Metric: {metric} = {metric_val(b)}\n"
        f"  Model: {b.get('architecture_name', 'unknown')}\n"
        f"  Retry count: {b.get('retry_count', 0)}\n\n"
        f"Task type: {state['task_type']}\n"
        f"Primary metric: {metric}\n\n"
        f"Select the winner. Consider: metric value, model simplicity, retry count (fewer = more robust), assessment.\n"
        f'Return JSON: {{"winner": "A"|"B", "justification": "<2 sentences referencing specific numbers>"}}'
    )

    raw = await router.call(
        task_type="complex_decision",
        system_prompt="You are an ML expert selecting the best model from two experiments.",
        user_message=prompt,
    )

    try:
        decision = json.loads(raw.strip())
        winner_key = decision.get("winner", "A")
        winner = a if winner_key == "A" else b
        justification = decision.get("justification", "Selected based on metric performance.")
    except json.JSONDecodeError:
        winner = a if metric_val(a) >= metric_val(b) else b
        justification = (
            f"Automatically selected '{winner['architecture_name']}' with "
            f"{metric} = {metric_val(winner):.4f}."
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
