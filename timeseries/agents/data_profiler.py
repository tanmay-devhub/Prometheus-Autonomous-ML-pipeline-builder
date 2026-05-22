import json
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import numpy as np

from timeseries.state import TimeSeriesState as PrometheusState
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


def _check_stationarity(series: pd.Series) -> tuple[bool, float]:
    """ADF test. Returns (is_stationary, p_value)."""
    try:
        from statsmodels.tsa.stattools import adfuller
        result = adfuller(series.dropna(), autolag="AIC")
        p_value = float(result[1])
        return p_value < 0.05, p_value
    except Exception:
        return True, 0.0  # Assume stationary on failure


def _detect_trend(series: pd.Series) -> tuple[bool, float]:
    """Linear regression R² > 0.3 → trend detected."""
    try:
        from sklearn.linear_model import LinearRegression
        x = np.arange(len(series)).reshape(-1, 1)
        y = series.values
        mask = ~np.isnan(y)
        if mask.sum() < 10:
            return False, 0.0
        model = LinearRegression().fit(x[mask], y[mask])
        r2 = float(model.score(x[mask], y[mask]))
        return r2 > 0.3, r2
    except Exception:
        return False, 0.0


def _detect_seasonality(series: pd.Series, frequency: str) -> tuple[bool, float]:
    """Autocorrelation at seasonal lag > 0.5 → seasonality."""
    try:
        lag_map = {"hourly": 24, "daily": 7, "weekly": 4, "monthly": 12}
        lag = lag_map.get(frequency, 7)
        if len(series) <= lag * 2:
            return False, 0.0
        clean = series.dropna()
        autocorr = float(clean.autocorr(lag=lag))
        if np.isnan(autocorr):
            return False, 0.0
        return abs(autocorr) > 0.5, autocorr
    except Exception:
        return False, 0.0


def _check_gaps(dates: pd.Series, frequency: str) -> List[str]:
    """Check for missing time periods."""
    warnings = []
    try:
        freq_map = {"hourly": "H", "daily": "D", "weekly": "W", "monthly": "ME"}
        pandas_freq = freq_map.get(frequency, "D")
        expected = pd.date_range(start=dates.min(), end=dates.max(), freq=pandas_freq)
        missing_count = len(expected) - len(dates)
        if missing_count > 0:
            warnings.append(f"Time series has {missing_count} missing {frequency} periods")
    except Exception:
        pass
    return warnings


async def data_profiler_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    df = pd.read_csv(state["dataset_path"])
    date_col = state.get("date_column", "")
    target_col = state.get("target_column", "")
    frequency = state.get("frequency", "daily")

    # Step 1: Sort by date column
    gap_warnings = []
    if date_col in df.columns:
        try:
            df[date_col] = pd.to_datetime(df[date_col])
            if not df[date_col].is_monotonic_increasing:
                df = df.sort_values(date_col).reset_index(drop=True)
                state["debug_log"].append({
                    "phase": "data_profiler",
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "sorted_by_date",
                })

            # Check for duplicate timestamps
            dup_dates = int(df[date_col].duplicated().sum())
            if dup_dates > 0:
                gap_warnings.append(f"Dataset has {dup_dates} duplicate timestamps — this may cause issues")

            # Check for gaps
            gap_warnings.extend(_check_gaps(df[date_col], frequency))
        except Exception:
            pass

    # Step 2: Statistical profiling
    col_stats = _compute_column_stats(df)
    duplicate_count = int(df.duplicated().sum())

    target_stats: Dict[str, Any] = {}
    is_stationary = True
    has_trend = False
    has_seasonality = False
    adf_p_value = 0.0
    trend_r2 = 0.0
    seasonality_autocorr = 0.0

    if target_col in df.columns and pd.api.types.is_numeric_dtype(df[target_col]):
        series = df[target_col].dropna()
        target_stats = {
            "min": float(series.min()),
            "max": float(series.max()),
            "mean": float(series.mean()),
            "std": float(series.std()),
            "count": int(len(series)),
        }

        is_stationary, adf_p_value = _check_stationarity(series)
        has_trend, trend_r2 = _detect_trend(series)
        has_seasonality, seasonality_autocorr = _detect_seasonality(series, frequency)

    # Time span info
    time_span_info = {}
    if date_col in df.columns:
        try:
            dates = pd.to_datetime(df[date_col])
            time_span_info = {
                "first_date": str(dates.min().date()),
                "last_date": str(dates.max().date()),
                "total_periods": len(df),
                "frequency": frequency,
            }
        except Exception:
            pass

    profile = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_count": duplicate_count,
        "columns": col_stats,
        "target_distribution": target_stats,
        "time_span": time_span_info,
        "is_stationary": is_stationary,
        "has_trend": has_trend,
        "has_seasonality": has_seasonality,
        "adf_p_value": round(adf_p_value, 4),
        "trend_r2": round(trend_r2, 4),
        "seasonality_autocorr": round(float(seasonality_autocorr) if seasonality_autocorr else 0.0, 4),
    }

    # Step 3: Validation warnings
    validation_warnings = []
    for col in df.columns:
        null_pct = df[col].isnull().sum() / len(df) * 100
        if null_pct > 50:
            validation_warnings.append({
                "severity": "block",
                "message": f"Column '{col}' has {null_pct:.1f}% missing values",
                "column": col,
            })
        elif null_pct > 10:
            validation_warnings.append({
                "severity": "warn",
                "message": f"Column '{col}' has {null_pct:.1f}% missing values",
                "column": col,
            })

    for w in gap_warnings:
        validation_warnings.append({"severity": "warn", "message": w, "column": date_col})

    if len(df) < 50:
        validation_warnings.append({
            "severity": "warn",
            "message": f"Dataset has only {len(df)} rows — time series models need at least 50 data points",
            "column": "",
        })

    # Step 4: LLM interpretation of TS properties
    ts_summary = {
        "row_count": len(df),
        "date_column": date_col,
        "target_column": target_col,
        "frequency": frequency,
        "is_stationary": is_stationary,
        "has_trend": has_trend,
        "has_seasonality": has_seasonality,
        "target_stats": target_stats,
        "time_span": time_span_info,
        "warnings": [w["message"] for w in validation_warnings[:5]],
    }

    llm_prompt = (
        f"Given these time series properties, write 3-5 bullet observations a data scientist would find useful.\n"
        f"Focus on: stationarity implications, trend direction, seasonality patterns, data quality, modeling recommendations.\n"
        f"Be specific and reference actual values.\n"
        f"Keep each bullet under 25 words.\n"
        f"Properties: {json.dumps(ts_summary, indent=2)}"
    )
    llm_interpretation = await router.call(
        task_type="interpretation",
        system_prompt="You are an expert time series analyst providing concise dataset insights.",
        user_message=llm_prompt,
    )
    profile["llm_interpretation"] = llm_interpretation

    # Update state
    state["profile_report"] = profile
    state["validation_warnings"] = validation_warnings
    state["leakage_warnings"] = []
    state["is_stationary"] = is_stationary
    state["has_trend"] = has_trend
    state["has_seasonality"] = has_seasonality
    state["current_phase"] = "profiling_complete"
    state["debug_log"].append({
        "phase": "data_profiler",
        "timestamp": datetime.utcnow().isoformat(),
        "is_stationary": is_stationary,
        "has_trend": has_trend,
        "has_seasonality": has_seasonality,
        "validation_warning_count": len(validation_warnings),
    })

    return state
