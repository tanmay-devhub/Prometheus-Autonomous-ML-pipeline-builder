import json
import re
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import numpy as np

from multiclassification.state import MultiClassState
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
            warnings.append({
                "severity": "block",
                "message": f"Column '{col}' has {null_pct:.1f}% missing values",
                "column": col,
            })
        elif null_pct > 10:
            warnings.append({
                "severity": "warn",
                "message": f"Column '{col}' has {null_pct:.1f}% missing values",
                "column": col,
            })
        elif null_pct > 0:
            warnings.append({
                "severity": "info",
                "message": f"Column '{col}' has {null_pct:.1f}% missing values",
                "column": col,
            })
    return warnings


def _detect_leakage(df: pd.DataFrame, target_col: str) -> List[str]:
    leakage = []
    if target_col not in df.columns:
        return leakage

    leakage_name_patterns = ["target", "label", "output", "result", "prediction"]

    for col in df.columns:
        if col == target_col:
            continue
        col_lower = col.lower()
        if any(p in col_lower for p in leakage_name_patterns):
            leakage.append(f"Column '{col}' name suggests leakage (contains: {col_lower})")
            continue

        try:
            from sklearn.feature_selection import mutual_info_classif
            col_encoded = pd.Categorical(df[col]).codes
            target_encoded = pd.Categorical(df[target_col]).codes
            mi = mutual_info_classif(
                col_encoded.reshape(-1, 1), target_encoded, random_state=42
            )[0]
            max_entropy = np.log(max(df[col].nunique(), 2))
            normalized_mi = mi / max_entropy if max_entropy > 0 else 0
            if normalized_mi > 0.9:
                leakage.append(
                    f"Column '{col}' has normalized mutual information {normalized_mi:.3f} with target (possible leakage)"
                )
        except Exception:
            pass

    return leakage


def _detect_class_imbalance(df: pd.DataFrame, target_col: str):
    if target_col not in df.columns:
        return False, None, [], {}
    counts = df[target_col].value_counts()
    distribution = {str(k): int(v) for k, v in counts.items()}
    if len(counts) < 2:
        return False, None, [], distribution

    ratio = float(counts.max() / counts.min())
    imbalanced_classes = [str(cls) for cls, cnt in counts.items() if cnt < 30]

    if ratio > 5:
        return True, ratio, imbalanced_classes, distribution
    elif ratio > 2:
        return True, ratio, imbalanced_classes, distribution
    return False, ratio, imbalanced_classes, distribution


def _detect_pii(df: pd.DataFrame) -> List[Dict[str, str]]:
    pii_warnings = []
    pii_name_patterns = ["email", "phone", "ssn", "social_security", "address", "ip_address", "passport"]
    email_re = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    phone_re = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
    ssn_re = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    for col in df.columns:
        col_lower = col.lower()
        if any(p in col_lower for p in pii_name_patterns):
            pii_warnings.append({
                "severity": "warn",
                "message": f"Column '{col}' name suggests PII data",
                "column": col,
            })
            continue
        sample = df[col].dropna().astype(str).head(20)
        for val in sample:
            if email_re.search(val) or phone_re.search(val) or ssn_re.search(val):
                pii_warnings.append({
                    "severity": "warn",
                    "message": f"Column '{col}' contains what appears to be PII data",
                    "column": col,
                })
                break

    return pii_warnings


async def data_profiler_node(state: MultiClassState) -> MultiClassState:
    router = LLMRouter()
    df = pd.read_csv(state["dataset_path"])
    target_col = state.get("target_column", "")

    col_stats = _compute_column_stats(df)
    duplicate_count = int(df.duplicated().sum())
    duplicate_pct = round(duplicate_count / len(df) * 100, 2)

    target_distribution: Dict[str, Any] = {}
    if target_col in df.columns:
        counts = df[target_col].value_counts()
        target_distribution = {str(k): int(v) for k, v in counts.items()}

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

    imbalance_detected, imbalance_ratio, imbalanced_classes, class_distribution = (
        _detect_class_imbalance(df, target_col)
    )

    if imbalance_detected and imbalance_ratio is not None:
        severity = "block" if imbalance_ratio > 5 else "warn"
        validation_warnings.append({
            "severity": severity,
            "message": f"Class imbalance detected: max/min ratio = {imbalance_ratio:.1f}",
            "column": target_col,
        })

    # Flag classes with insufficient samples
    if target_col in df.columns:
        counts = df[target_col].value_counts()
        for cls, cnt in counts.items():
            if cnt < 30:
                validation_warnings.append({
                    "severity": "block",
                    "message": f"Class '{cls}' has only {cnt} samples (minimum 30 recommended)",
                    "column": target_col,
                })
            elif cnt < 100:
                validation_warnings.append({
                    "severity": "warn",
                    "message": f"Class '{cls}' has only {cnt} samples (100+ recommended for reliable training)",
                    "column": target_col,
                })

    pii_warnings = _detect_pii(df)
    validation_warnings.extend(pii_warnings)

    profile_json = json.dumps(profile, indent=2)
    llm_prompt = (
        f"Given this multiclass classification dataset profile, write 3-5 bullet points a data scientist would find useful.\n"
        f"Focus on: data quality, class balance, modeling challenges for {state.get('num_classes', '?')} classes.\n"
        f"Be specific and reference actual column names and numbers.\n"
        f"Keep each bullet under 20 words.\n"
        f"Profile: {profile_json}"
    )
    llm_interpretation = await router.call(
        task_type="interpretation",
        system_prompt="You are an expert data scientist providing concise dataset insights.",
        user_message=llm_prompt,
    )
    profile["llm_interpretation"] = llm_interpretation

    state["profile_report"] = profile
    state["validation_warnings"] = validation_warnings
    state["leakage_warnings"] = leakage_warnings
    state["class_imbalance_detected"] = imbalance_detected
    state["imbalance_ratio"] = imbalance_ratio
    state["imbalanced_classes"] = imbalanced_classes
    state["class_distribution"] = class_distribution
    state["current_phase"] = "profiling_complete"
    state["debug_log"].append({
        "phase": "data_profiler",
        "timestamp": datetime.utcnow().isoformat(),
        "validation_warning_count": len(validation_warnings),
        "leakage_warning_count": len(leakage_warnings),
        "imbalance_detected": imbalance_detected,
        "num_classes": state.get("num_classes"),
    })

    return state
