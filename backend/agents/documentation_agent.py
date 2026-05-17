import json
import os
from datetime import datetime
from typing import Any, Dict

from backend.state import PrometheusState
from backend.llm.router import LLMRouter
from execution.e2b_executor import E2BExecutor

MODEL_CARD_PROMPT = """Generate a model card for this ML model. Use this exact markdown structure:

# Model Card: {model_type}

## Model Details
- **Task:** {task_type}
- **Algorithm:** {model_type}
- **Target variable:** {target_column}
- **Evaluation metric:** {evaluation_metric}: {metric_value}
- **Training samples:** {train_samples}
- **Test samples:** {test_samples}

## Training Data
[Describe the dataset characteristics based on this profile: {profile_summary}]

## Performance
[Interpret the metric value in plain English — is this good, acceptable, or poor for this type of problem?]

## Limitations
[List 3-5 specific limitations based on the data profile warnings and the model type]

## Intended Use
[Describe appropriate use cases for this model based on the problem description: {user_description}]

## How Not To Use
[List 2-3 misuse cases or situations where this model should not be trusted]"""

SHAP_SCRIPT_TEMPLATE = """
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import json
import sys

try:
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    import shap

    df = pd.read_csv(sys.argv[1])
    target_col = {target_col_repr}
    feature_cols = [c for c in df.columns if c != target_col]

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    # Encode categoricals
    for col in X.select_dtypes(include=['object', 'category']).columns:
        X[col] = LabelEncoder().fit_transform(X[col].astype(str))

    X = X.fillna(X.median(numeric_only=True))

    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
    from xgboost import XGBClassifier, XGBRegressor
    from lightgbm import LGBMClassifier, LGBMRegressor
    from sklearn.linear_model import LogisticRegression, Ridge

    model_class = {model_class_repr}
    try:
        model = model_class()
        model.fit(X, y)
    except Exception:
        model = GradientBoostingClassifier(n_estimators=50) if {is_classification} else GradientBoostingRegressor(n_estimators=50)
        model.fit(X, y)

    try:
        explainer = shap.TreeExplainer(model)
    except Exception:
        explainer = shap.LinearExplainer(model, X)

    shap_values = explainer.shap_values(X[:100])
    if isinstance(shap_values, list):
        shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    top_indices = np.argsort(mean_abs_shap)[::-1][:10]
    top_features = [
        {{"feature": feature_cols[i], "importance": float(mean_abs_shap[i])}}
        for i in top_indices
    ]
    print(json.dumps(top_features))
except Exception as e:
    print(json.dumps([{{"error": str(e)}}]))
"""


async def documentation_agent_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    profile = state.get("profile_report", {})
    metrics = winning.get("parsed_metrics", {})
    metric = state["evaluation_metric"]
    metric_value = metrics.get(metric, 0.0)
    model_type = winning.get("architecture_name", "ML Model")

    # Step 1: Model card
    profile_summary = json.dumps({
        "row_count": profile.get("row_count"),
        "column_count": profile.get("column_count"),
        "warnings": [w["message"] for w in state.get("validation_warnings", [])[:5]],
        "llm_insights": profile.get("llm_interpretation", ""),
    })

    card_prompt = MODEL_CARD_PROMPT.format(
        model_type=model_type,
        task_type=state["task_type"],
        target_column=state["target_column"],
        evaluation_metric=metric,
        metric_value=round(metric_value, 4),
        train_samples=int(metrics.get("train_samples", 0)),
        test_samples=int(metrics.get("test_samples", 0)),
        profile_summary=profile_summary,
        user_description=state["user_description"],
    )

    model_card = await router.call(
        task_type="interpretation",
        system_prompt="You are an ML documentation expert writing a model card.",
        user_message=card_prompt,
    )

    # Step 2: SHAP
    is_classification = state["task_type"] == "binary_classification"
    shap_script = SHAP_SCRIPT_TEMPLATE.format(
        target_col_repr=repr(state["target_column"]),
        model_class_repr=model_type,
        is_classification=str(is_classification),
    )

    executor = E2BExecutor()
    shap_result = await executor.run(
        code=shap_script,
        dataset_path=state["dataset_path"],
    )

    shap_features = []
    plain_explanation = ""
    if shap_result.success:
        try:
            stdout_lines = [l.strip() for l in shap_result.stdout.strip().split("\n") if l.strip()]
            shap_features = json.loads(stdout_lines[-1])

            shap_prompt = (
                f"These are the top features driving predictions for this model:\n"
                f"{json.dumps(shap_features, indent=2)}\n\n"
                f"In plain English, explain what drives predictions for a non-technical stakeholder.\n"
                f"Reference the actual feature names and their relative importance.\n"
                f"Keep it under 150 words. Use simple language."
            )
            plain_explanation = await router.call(
                task_type="interpretation",
                system_prompt="You are an expert at explaining ML models to non-technical stakeholders.",
                user_message=shap_prompt,
            )
        except Exception:
            plain_explanation = f"The model achieved {metric} = {metric_value:.4f} on the test set."

    state["model_card"] = model_card
    state["plain_english_explanation"] = plain_explanation
    state["shap_plot_path"] = None  # SHAP data stored in profile, PNG generation optional
    state["profile_report"]["shap_features"] = shap_features

    state["debug_log"].append({
        "phase": "documentation_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "model_card_length": len(model_card),
        "shap_features_count": len(shap_features),
    })

    return state
