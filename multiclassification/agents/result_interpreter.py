import json
from datetime import datetime
from typing import Any, Dict

from multiclassification.state import MultiClassState, ExperimentResult
from shared.llm.router import LLMRouter


async def result_interpreter_node(
    state: MultiClassState, experiment_result: ExperimentResult
) -> ExperimentResult:
    if not experiment_result["success"]:
        return experiment_result

    router = LLMRouter()
    metrics = experiment_result["parsed_metrics"]
    metric_name = state["evaluation_metric"]
    metric_value = metrics.get(metric_name, metrics.get("f1_macro", list(metrics.values())[0] if metrics else 0))
    model_type = metrics.get("model_type", experiment_result.get("architecture_name", "unknown"))

    f1_macro = float(metrics.get("f1_macro", metric_value))
    accuracy = float(metrics.get("accuracy", 0))
    num_classes = int(metrics.get("num_classes", state.get("num_classes", 0)))
    per_class_f1 = metrics.get("per_class_f1", {})

    # Rule-based assessment using multiple signals
    struggling_classes = [cls for cls, f1 in per_class_f1.items() if isinstance(f1, (int, float)) and f1 < 0.5]

    if f1_macro >= 0.85 and accuracy >= 0.85:
        assessment = "good"
        reason = f"f1_macro={f1_macro:.3f} and accuracy={accuracy:.3f} are strong for {num_classes}-class problem"
    elif f1_macro >= 0.70:
        assessment = "acceptable"
        reason = f"f1_macro={f1_macro:.3f} is reasonable but has room for improvement"
    elif f1_macro < 0.40:
        assessment = "poor"
        reason = f"f1_macro={f1_macro:.3f} suggests the model is not learning well across all {num_classes} classes"
    elif f1_macro > 0.99 and num_classes > 2:
        assessment = "suspicious"
        reason = f"f1_macro={f1_macro:.3f} is suspiciously perfect for a {num_classes}-class problem — possible leakage"
    else:
        # LLM decides
        prompt = (
            f"An ML multiclass classification experiment completed with these results:\n"
            f"f1_macro = {f1_macro}\n"
            f"accuracy = {accuracy}\n"
            f"f1_weighted = {metrics.get('f1_weighted', 'unknown')}\n"
            f"num_classes = {num_classes}\n"
            f"per_class_f1 = {json.dumps(per_class_f1)}\n"
            f"Model type: {model_type}\n"
            f"Training samples: {metrics.get('train_samples', 'unknown')}\n"
            f"Test samples: {metrics.get('test_samples', 'unknown')}\n\n"
            f"In one sentence, assess whether this result is:\n"
            f'- "good": metric is strong for this multiclass task\n'
            f'- "acceptable": metric is reasonable but has room for improvement\n'
            f'- "poor": metric suggests the model is not learning well\n'
            f'- "suspicious": metric is suspiciously perfect (possible leakage) or impossibly bad\n\n'
            f'Return JSON: {{"assessment": "good|acceptable|poor|suspicious", "reason": "<one sentence>"}}'
        )

        raw = await router.call(
            task_type="interpretation",
            system_prompt="You are an ML expert assessing multiclass experiment results.",
            user_message=prompt,
        )

        try:
            parsed = json.loads(raw.strip())
            assessment = parsed.get("assessment", "acceptable")
            reason = parsed.get("reason", "")
        except json.JSONDecodeError:
            assessment = "acceptable"
            reason = ""

    experiment_result["failure_type"] = (
        "suspicious_metric" if assessment == "suspicious"
        else ("poor_metric" if assessment == "poor" else None)
    )
    if experiment_result["failure_type"] in ("suspicious_metric", "poor_metric"):
        experiment_result["success"] = False

    if struggling_classes and experiment_result["success"]:
        experiment_result.setdefault("warnings", [])
        experiment_result["warnings"] = [f"Struggling classes (f1 < 0.5): {', '.join(struggling_classes)}"]

    return experiment_result
