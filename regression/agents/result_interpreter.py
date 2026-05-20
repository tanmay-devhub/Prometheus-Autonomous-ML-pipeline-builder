import json
from datetime import datetime
from typing import Any, Dict

from regression.state import RegressionState, ExperimentResult
from shared.llm.router import LLMRouter


async def result_interpreter_node(
    state: RegressionState, experiment_result: ExperimentResult
) -> ExperimentResult:
    if not experiment_result["success"]:
        return experiment_result

    router = LLMRouter()
    metrics = experiment_result["parsed_metrics"]
    metric_name = state["evaluation_metric"]
    metric_value = metrics.get(metric_name, list(metrics.values())[0] if metrics else 0)
    target_mean = state.get("target_mean") or 1.0

    r2          = metrics.get("r2", None)
    rmse_pct    = metrics.get("rmse_pct_of_mean", None)
    within_20   = metrics.get("within_20_pct", None)

    # Rule-based quality assessment using all available metrics
    assessment = "acceptable"
    reason = ""

    # Prefer r2 + within_20 signals when available (they're metric-agnostic)
    if r2 is not None and within_20 is not None:
        if r2 > 0.85 and within_20 >= 70:
            assessment = "good"
            reason = f"R²={r2:.3f}, {within_20:.0f}% within 20% tolerance — strong model."
        elif r2 < 0:
            assessment = "suspicious"
            reason = f"R²={r2:.3f} — negative R² means the model is worse than a constant predictor."
        elif r2 < 0.4 and within_20 < 40:
            assessment = "poor"
            reason = f"R²={r2:.3f}, only {within_20:.0f}% within 20% tolerance — model is not learning well."
        elif rmse_pct is not None and rmse_pct > 30 and r2 < 0.6:
            assessment = "poor"
            reason = f"RMSE is {rmse_pct:.1f}% of target mean and R²={r2:.3f} — insufficient accuracy."
        elif r2 > 0.7 or within_20 >= 55:
            assessment = "good"
            reason = f"R²={r2:.3f}, {within_20:.0f}% within 20% tolerance."
        else:
            assessment = "acceptable"
            reason = f"R²={r2:.3f}, {within_20:.0f}% within 20% tolerance — acceptable but room to improve."
    elif metric_name == "rmse" and rmse_pct is not None:
        if rmse_pct < 15:
            assessment = "good"
            reason = f"RMSE is {rmse_pct:.1f}% of target mean — strong performance."
        elif rmse_pct < 30:
            assessment = "acceptable"
            reason = f"RMSE is {rmse_pct:.1f}% of target mean — acceptable."
        else:
            assessment = "poor"
            reason = f"RMSE is {rmse_pct:.1f}% of target mean — model is not generalising well."
    elif metric_name == "r2" and r2 is not None:
        if r2 > 0.8:
            assessment = "good"
            reason = f"R²={r2:.4f} — strong variance explained."
        elif r2 > 0.6:
            assessment = "acceptable"
            reason = f"R²={r2:.4f} — acceptable."
        elif r2 < 0:
            assessment = "suspicious"
            reason = f"R²={r2:.4f} — negative R², worse than predicting the mean."
        else:
            assessment = "poor"
            reason = f"R²={r2:.4f} — explains less than 60% of variance."
    else:
        # MAE with no other signals — fall back to LLM
        prompt = (
            f"Regression experiment results:\n"
            f"  MAE={metric_value}, target mean={target_mean}, target std={state.get('target_std', 'unknown')}\n"
            f"  R²={r2}, RMSE% of mean={rmse_pct}, within-20%={within_20}\n"
            f"  Model: {metrics.get('model_type', 'unknown')}, samples: {metrics.get('train_samples')}\n\n"
            f"Assess as good / acceptable / poor / suspicious.\n"
            f'Return JSON: {{"assessment": "good|acceptable|poor|suspicious", "reason": "<one sentence>"}}'
        )
        raw = await router.call(
            task_type="interpretation",
            system_prompt="You are an ML expert assessing regression experiment quality.",
            user_message=prompt,
        )
        try:
            llm_assessment = json.loads(raw.strip())
            assessment = llm_assessment.get("assessment", "acceptable")
            reason = llm_assessment.get("reason", "")
        except json.JSONDecodeError:
            pass

    experiment_result["failure_type"] = (
        "suspicious_metric" if assessment == "suspicious"
        else ("poor_metric" if assessment == "poor" else None)
    )
    if experiment_result["failure_type"] in ("suspicious_metric", "poor_metric"):
        experiment_result["success"] = False

    return experiment_result
