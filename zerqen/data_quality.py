from __future__ import annotations
import pandas as pd

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}

def validate_ohlcv(frame: pd.DataFrame) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        reasons.append("missing columns: " + ",".join(sorted(missing)))
        return False, tuple(reasons)
    if frame.empty:
        reasons.append("empty dataset")
    if frame["timestamp"].duplicated().any():
        reasons.append("duplicate timestamps")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        reasons.append("invalid timestamps")
    if not timestamps.is_monotonic_increasing:
        reasons.append("timestamps not monotonic")
    numeric = frame[list(REQUIRED_COLUMNS - {"timestamp"})].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        reasons.append("non-numeric OHLCV")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        reasons.append("non-positive price")
    if (numeric["volume"] < 0).any():
        reasons.append("negative volume")
    return not reasons, tuple(reasons)
