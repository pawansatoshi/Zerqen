from __future__ import annotations
import pandas as pd

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


def validate_ohlcv(
    frame: pd.DataFrame,
    *,
    expected_interval: str | None = None,
    now: pd.Timestamp | None = None,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        return False, ("missing columns: " + ",".join(sorted(missing)),)
    if frame.empty:
        return False, ("empty dataset",)

    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        reasons.append("invalid timestamps")
    if timestamps.duplicated().any():
        reasons.append("duplicate timestamps")
    if not timestamps.is_monotonic_increasing:
        reasons.append("timestamps not monotonic")

    numeric = frame[list(REQUIRED_COLUMNS - {"timestamp"})].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        reasons.append("non-numeric OHLCV")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        reasons.append("non-positive price")
    if (numeric["volume"] < 0).any():
        reasons.append("negative volume")

    if not numeric.empty:
        bad_ohlc = (
            (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1))
            | (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1))
        )
        if bad_ohlc.any():
            reasons.append("invalid OHLC relationships")

    if expected_interval and not timestamps.isna().any() and len(timestamps) > 1:
        interval = pd.Timedelta(expected_interval)
        gaps = timestamps.diff().iloc[1:]
        if (gaps != interval).any():
            reasons.append("timestamp gaps or unexpected interval")

    if now is not None and not timestamps.isna().any():
        current = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else pd.Timestamp(now, tz="UTC")
        if (timestamps > current).any():
            reasons.append("future timestamps")

    return not reasons, tuple(reasons)
