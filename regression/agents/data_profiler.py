import json
import re
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import numpy as np

from regression.state import RegressionState
from shared.llm.router import LLMRouter


def _compute_column_stats(df: pd.DataFrame) -> List[Dict[str, Any]]:
    stats = []
    for col in df.columns:
        col_data = df[col]
        null_count = int(col_data.isnull().sum())
        null_pct = round(null_count / len(df) * 100, 2)
        unique_count = int(col_data.nunique())
        dtype = str(col_data.dtype)

        entry: Dict[str, Any] = {
            "column": col,
            "dtype": dtype,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
        }
        if pd.api.types.is_numeric_dtype(col_data):
            entry["min"] = float(col_data.min()) if not col_data.isnull().all() else None
            entry["max"] = float(col_data.max()) if not col_data.isnull().all() else None
            entry["mean"] = float(col_data.mean()) if not col_data.isnull().all() else None
            entry["std"] = float(col_data.std()) if not col_data.isnull().all() else None
            entry["skewness"] = float(col_data.skew()) if not col_data.isnull().all() else None
        else:
            top5 = col_data.value_counts().head(5).to_dict()
            entry["top_values"] = {str(k): int(v) for k, v in top5.items()}
        stats.append(entry)
    return stats


def _run_validation(df: pd.DataFrame, target_col: str) -> List[Dict[str, str]]:
    warnings = []
    for col in df.columns:
        null_pct = df[col].isnull().sum() / len(df) * 100
        if null_pct > 50:
            warnings.append({"severity": "block", "message": f"Column '{col}' has {null_pct:.1f}% missing values", "column": col})
        elif null_pct > 10:
            warnings.append({"severity": "warn", "message": f"Column '{col}' has {null_pct:.1f}% missing values", "column": col})
        elif null_pct > 0:
            warnings.append({"severity": "info", "message": f"Column '{col}' has {null_pct:.1f}% missing values", "column": col})
    return warnings


def _detect_leakage(df: pd.DataFrame, target_col: str) -> List[str]:
    leakage = []
    if target_col not in df.columns:
        return leakage

    target = df[target_col]
    leakage_name_patterns = ["target", "label", "output", "result", "prediction"]

    for col in df.columns:
        if col == target_col:
            continue
        col_lower = col.lower()
        if any(p in col_lower for p in leakage_name_patterns):
            leakage.append(f"Column '{col}' name suggests leakage (contains: {col_lower})")
            continue
        try:
            if pd.api.types.is_numeric_dtype(df[col]) and pd.api.types.is_numeric_dtype(target):
                corr = df[col].corr(target)
                if corr is not None and not np.isnan(corr) and abs(corr) > 0.95:
                    leakage.append(f"Column '{col}' has Pearson correlation {corr:.3f} with target (possible leakage)")
        except Exception:
            pass

    return leakage


async def data_profiler_node(state: RegressionState) -> RegressionState:
    router = LLMRouter()
    df = pd.read_csv(state["dataset_path"])
    target_col = state.get("target_column", "")

    col_stats = _compute_column_stats(df)
    duplicate_count = int(df.duplicated().sum())
    duplicate_pct = round(duplicate_count / len(df) * 100, 2)

    target_distribution: Dict[str, Any] = {}
    if target_col in df.columns:
        target_distribution = {
            "min": float(df[target_col].min()),
            "max": float(df[target_col].max()),
            "mean": float(df[target_col].mean()),
            "std": float(df[target_col].std()),
            "skewness": float(df[target_col].skew()),
            "median": float(df[target_col].median()),
        }

    profile = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_count": duplicate_count,
        "duplicate_pct": duplicate_pct,
        "columns": col_stats,
        "target_distribution": target_distribution,
    }

    validation_warnings = _run_validation(df, target_col)
    leakage_warnings = _detect_leakage(df, target_col)

    # Check for log transform recommendation
    if target_col in df.columns:
        skewness = abs(df[target_col].skew())
        if skewness > 1.5:
            validation_warnings.append({
                "severity": "info",
                "message": f"Target column '{target_col}' is heavily skewed (skewness={skewness:.2f}). "
                           "A log transform may improve model performance.",
                "column": target_col,
            })

    profile_json = json.dumps(profile, indent=2)
    llm_prompt = (
        f"Given this regression dataset profile, write 3-5 bullet points a data scientist would find useful.\n"
        f"Focus on: data quality, target distribution, potential modeling challenges, skewness.\n"
        f"Be specific and reference actual column names and numbers.\n"
        f"Keep each bullet under 25 words.\n"
        f"Profile: {profile_json}"
    )
    llm_interpretation = await router.call(
        task_type="interpretation",
        system_prompt="You are an expert data scientist providing concise dataset insights for a regression task.",
        user_message=llm_prompt,
    )
    profile["llm_interpretation"] = llm_interpretation

    state["profile_report"] = profile
    state["validation_warnings"] = validation_warnings
    state["leakage_warnings"] = leakage_warnings
    state["class_imbalance_detected"] = False
    state["imbalance_ratio"] = None
    state["current_phase"] = "profiling_complete"
    state["debug_log"].append({
        "phase": "data_profiler",
        "timestamp": datetime.utcnow().isoformat(),
        "validation_warning_count": len(validation_warnings),
        "leakage_warning_count": len(leakage_warnings),
    })

    return state
