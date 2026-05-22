import json
from datetime import datetime
from typing import Any, Dict

from timeseries.state import TimeSeriesState as PrometheusState, ExperimentResult
from shared.llm.router import LLMRouter


async def result_interpreter_node(
    state: PrometheusState, experiment_result: ExperimentResult
) -> ExperimentResult:
    if not experiment_result["success"]:
        return experiment_result

    metrics = experiment_result["parsed_metrics"]
    rmse = metrics.get("rmse", metrics.get("metric_value", 0))
    mae = metrics.get("mae", 0)
    mape = metrics.get("mape", 0)
    train_samples = metrics.get("train_samples", 0)
    test_samples = metrics.get("test_samples", 0)
    model_type = metrics.get("model_type", experiment_result.get("architecture_name", "unknown"))

    # Rule-based assessment using MAPE (most intuitive)
    if mape > 0:
        if mape < 10:
            assessment = "good"
            reason = f"MAPE {mape:.1f}% is excellent for time series forecasting."
        elif mape < 20:
            assessment = "good"
            reason = f"MAPE {mape:.1f}% is acceptable for time series forecasting."
        elif mape < 30:
            assessment = "acceptable"
            reason = f"MAPE {mape:.1f}% is marginal — the model captures the trend but has notable error."
        else:
            assessment = "poor"
            reason = f"MAPE {mape:.1f}% is too high — the model is not forecasting well."
    else:
        # Fallback to RMSE as % of mean target
        target_mean = metrics.get("target_mean", 1.0) or 1.0
        if target_mean and rmse > 0:
            rmse_pct = (rmse / abs(target_mean)) * 100
            if rmse_pct < 15:
                assessment = "good"
                reason = f"RMSE is {rmse_pct:.1f}% of target mean — excellent."
            elif rmse_pct < 25:
                assessment = "good"
                reason = f"RMSE is {rmse_pct:.1f}% of target mean — acceptable."
            elif rmse_pct < 35:
                assessment = "acceptable"
                reason = f"RMSE is {rmse_pct:.1f}% of target mean — marginal performance."
            else:
                assessment = "poor"
                reason = f"RMSE is {rmse_pct:.1f}% of target mean — poor forecasting quality."
        else:
            assessment = "acceptable"
            reason = "Unable to assess relative error — treating as acceptable."

    # Flag insufficient test period
    if test_samples < 30:
        experiment_result.setdefault("failure_type", None)
        # Don't fail, just warn in debug log

    if assessment == "poor":
        experiment_result["failure_type"] = "poor_metric"
        experiment_result["success"] = False
    elif assessment == "suspicious" if mape == 0 and rmse == 0 else False:
        experiment_result["failure_type"] = "suspicious_metric"
        experiment_result["success"] = False

    return experiment_result
