import math
from typing import Any


def clean_value(v: Any) -> Any:
    """Replace NaN/Inf floats with None for JSON serialization."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def clean_row(row: dict) -> dict:
    return {k: clean_value(v) for k, v in row.items()}
