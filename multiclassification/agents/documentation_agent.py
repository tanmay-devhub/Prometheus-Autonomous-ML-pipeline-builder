import json
import os
from datetime import datetime
from typing import Any, Dict

from multiclassification.state import MultiClassState
from shared.llm.router import LLMRouter
from shared.execution.e2b_executor import E2BExecutor

MODEL_CARD_PROMPT = """Generate a model card for this multiclass classification model. Use this exact markdown structure:

# Model Card: {model_type}

## Model Details
- **Task:** multiclass_classification ({num_classes} classes: {class_names})
- **Algorithm:** {model_type}
- **Target variable:** {target_column}
- **Evaluation metric:** {evaluation_metric}: {metric_value}
- **Accuracy:** {accuracy}
- **Training samples:** {train_samples}
- **Test samples:** {test_samples}

## Training Data
[Describe the dataset characteristics based on this profile: {profile_summary}]

## Performance
[Interpret the metric value in plain English — is this good, acceptable, or poor for a {num_classes}-class problem?
Mention any classes the model struggles with based on per-class F1: {per_class_f1}]

## Limitations
[List 3-5 specific limitations based on the data profile warnings and the number of classes]

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
    from sklearn.preprocessing import LabelEncoder
    import shap

    df = pd.read_csv(sys.argv[1])
    target_col = {target_col_repr}
    feature_cols = [c for c in df.columns if c != target_col]

    X = df[feature_cols].copy()
    y = df[target_col].copy()

    for col in X.select_dtypes(include=['object', 'category']).columns:
        X[col] = LabelEncoder().fit_transform(X[col].astype(str))

    X = X.fillna(X.median(numeric_only=True))

    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from xgboost import XGBClassifier
    from lightgbm import LGBMClassifier
    from sklearn.linear_model import LogisticRegression

    model_class = {model_class_repr}
    try:
        model = model_class()
        model.fit(X, y)
    except Exception:
        model = RandomForestClassifier(n_estimators=50, class_weight='balanced')
        model.fit(X, y)

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X[:100])
        if isinstance(shap_values, list):
            mean_abs = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
        else:
            mean_abs = np.abs(shap_values).mean(axis=0)
    except Exception:
        try:
            explainer = shap.LinearExplainer(model, X)
            shap_values = explainer.shap_values(X[:100])
            mean_abs = np.abs(shap_values).mean(axis=0)
        except Exception:
            mean_abs = np.zeros(len(feature_cols))

    top_indices = np.argsort(mean_abs)[::-1][:10]
    top_features = [
        {{"feature": feature_cols[i], "importance": float(mean_abs[i])}}
        for i in top_indices
    ]
    print(json.dumps(top_features))
except Exception as e:
    print(json.dumps([{{"error": str(e)}}]))
"""


async def documentation_agent_node(state: MultiClassState) -> MultiClassState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    profile = state.get("profile_report", {})
    metrics = winning.get("parsed_metrics", {})
    metric = state["evaluation_metric"]
    metric_value = metrics.get(metric, metrics.get("f1_macro", 0.0))
    model_type = winning.get("architecture_name", "ML Model")
    num_classes = state.get("num_classes", 0)
    class_names = state.get("class_names", [])
    per_class_f1 = metrics.get("per_class_f1", {})

    profile_summary = json.dumps({
        "row_count": profile.get("row_count"),
        "column_count": profile.get("column_count"),
        "warnings": [w["message"] for w in state.get("validation_warnings", [])[:5]],
        "llm_insights": profile.get("llm_interpretation", ""),
    })

    card_prompt = MODEL_CARD_PROMPT.format(
        model_type=model_type,
        num_classes=num_classes,
        class_names=", ".join(str(c) for c in class_names),
        target_column=state["target_column"],
        evaluation_metric=metric,
        metric_value=round(float(metric_value), 4),
        accuracy=round(float(metrics.get("accuracy", 0)), 4),
        train_samples=int(metrics.get("train_samples", 0)),
        test_samples=int(metrics.get("test_samples", 0)),
        per_class_f1=json.dumps(per_class_f1),
        profile_summary=profile_summary,
        user_description=state["user_description"],
    )

    model_card = await router.call(
        task_type="interpretation",
        system_prompt="You are an ML documentation expert writing a model card for a multiclass classifier.",
        user_message=card_prompt,
    )

    shap_script = SHAP_SCRIPT_TEMPLATE.format(
        target_col_repr=repr(state["target_column"]),
        model_class_repr=model_type,
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
                f"These are the top features driving predictions for a {num_classes}-class model "
                f"(classes: {class_names}):\n"
                f"{json.dumps(shap_features, indent=2)}\n\n"
                f"In plain English, explain what drives predictions for a non-technical stakeholder.\n"
                f"Reference the actual feature names and their relative importance.\n"
                f"Mention what each feature means for predicting different classes if possible.\n"
                f"Keep it under 150 words. Use simple language."
            )
            plain_explanation = await router.call(
                task_type="interpretation",
                system_prompt="You are an expert at explaining ML models to non-technical stakeholders.",
                user_message=shap_prompt,
            )
        except Exception:
            plain_explanation = f"The model achieved {metric} = {metric_value:.4f} across {num_classes} classes."

    state["model_card"] = model_card
    state["plain_english_explanation"] = plain_explanation
    state["shap_plot_path"] = None
    state["profile_report"]["shap_features"] = shap_features

    # Store per-class metrics in state
    state["per_class_metrics"] = per_class_f1

    state["debug_log"].append({
        "phase": "documentation_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "model_card_length": len(model_card),
        "shap_features_count": len(shap_features),
    })

    return state
