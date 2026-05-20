import json
from datetime import datetime
from typing import Any, Dict

from classification.state import ClassificationState as PrometheusState, ExperimentResult
from shared.llm.router import LLMRouter


async def result_interpreter_node(
    state: PrometheusState, experiment_result: ExperimentResult
) -> ExperimentResult:
    if not experiment_result["success"]:
        # Pass directly to failure diagnostician — no LLM call needed here
        return experiment_result

    router = LLMRouter()
    metrics = experiment_result["parsed_metrics"]
    metric_name = state["evaluation_metric"]
    metric_value = metrics.get(metric_name, list(metrics.values())[0] if metrics else 0)
    model_type = metrics.get("model_type", experiment_result.get("architecture_name", "unknown"))

    prompt = (
        f"An ML experiment completed with these results:\n"
        f"Metric: {metric_name} = {metric_value}\n"
        f"Model type: {model_type}\n"
        f"Training samples: {metrics.get('train_samples', 'unknown')}\n"
        f"Test samples: {metrics.get('test_samples', 'unknown')}\n"
        f"Task type: {state['task_type']}\n"
        f"Expected metric: {state['evaluation_metric']}\n\n"
        f"In one sentence, assess whether this result is:\n"
        f'- "good": metric is strong for this task type\n'
        f'- "acceptable": metric is reasonable but has room for improvement\n'
        f'- "poor": metric suggests the model is not learning well\n'
        f'- "suspicious": metric is suspiciously perfect (possible leakage) or impossibly bad\n\n'
        f'Return JSON: {{"assessment": "good|acceptable|poor|suspicious", "reason": "<one sentence>"}}'
    )

    raw = await router.call(
        task_type="interpretation",
        system_prompt="You are an ML expert assessing experiment results.",
        user_message=prompt,
    )

    try:
        assessment = json.loads(raw.strip())
        experiment_result["failure_type"] = (
            "suspicious_metric" if assessment.get("assessment") == "suspicious"
            else ("poor_metric" if assessment.get("assessment") == "poor" else None)
        )
        if experiment_result["failure_type"] in ("suspicious_metric", "poor_metric"):
            experiment_result["success"] = False
    except json.JSONDecodeError:
        pass

    return experiment_result
