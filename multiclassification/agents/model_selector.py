import json
from datetime import datetime
from typing import Any, Dict, List

from multiclassification.state import MultiClassState, ExperimentResult
from shared.llm.router import LLMRouter


async def model_selector_node(state: MultiClassState) -> MultiClassState:
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
        return float(exp["parsed_metrics"].get(metric, exp["parsed_metrics"].get("f1_macro", 0.0)))

    def per_class_summary(exp: ExperimentResult) -> str:
        pcf = exp["parsed_metrics"].get("per_class_f1", {})
        if not pcf or not isinstance(pcf, dict):
            return "N/A"
        return ", ".join(f"{cls}={v:.3f}" for cls, v in list(pcf.items())[:4])

    prompt = (
        f"Two multiclass classification experiments completed. Select the winner.\n\n"
        f"Experiment A — {a['architecture_name']}:\n"
        f"  Metric: {metric} = {metric_val(a):.4f}\n"
        f"  f1_macro = {a['parsed_metrics'].get('f1_macro', 'unknown')}\n"
        f"  accuracy = {a['parsed_metrics'].get('accuracy', 'unknown')}\n"
        f"  Per-class F1: {per_class_summary(a)}\n"
        f"  Retry count: {a.get('retry_count', 0)}\n\n"
        f"Experiment B — {b['architecture_name']}:\n"
        f"  Metric: {metric} = {metric_val(b):.4f}\n"
        f"  f1_macro = {b['parsed_metrics'].get('f1_macro', 'unknown')}\n"
        f"  accuracy = {b['parsed_metrics'].get('accuracy', 'unknown')}\n"
        f"  Per-class F1: {per_class_summary(b)}\n"
        f"  Retry count: {b.get('retry_count', 0)}\n\n"
        f"Task type: multiclass_classification\n"
        f"Number of classes: {state.get('num_classes', '?')}\n"
        f"Primary metric: {metric}\n\n"
        f"Select the winner. Consider: f1_macro, per-class F1 balance, retry count.\n"
        f"Mention which class each model struggled with most if known.\n"
        f'Return JSON: {{"winner": "A"|"B", "justification": "<2 sentences referencing specific numbers and struggling classes>"}}'
    )

    raw = await router.call(
        task_type="complex_decision",
        system_prompt="You are an ML expert selecting the best multiclass model from two experiments.",
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
