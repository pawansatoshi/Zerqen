import pandas as pd

def assert_chronological(frame: pd.DataFrame, timestamp_column: str = "timestamp") -> None:
    if timestamp_column not in frame:
        raise ValueError(f"missing {timestamp_column}")
    ts = pd.to_datetime(frame[timestamp_column], utc=True)
    if ts.duplicated().any():
        raise ValueError("duplicate timestamps detected")
    if not ts.is_monotonic_increasing:
        raise ValueError("timestamps must be strictly increasing")

def assert_no_future_columns(
    frame: pd.DataFrame,
    allowed: set[str] | None = None,
) -> None:
    allowed = allowed or {"timestamp", "open", "high", "low", "close", "volume"}
    forbidden = [c for c in frame.columns if c not in allowed and c.endswith(("_future", "_lead"))]
    if forbidden:
        raise ValueError(f"future-looking columns detected: {forbidden}")
