from pathlib import Path
import pandas as pd

REQUIRED = {"timestamp", "open", "high", "low", "close", "volume"}

def load_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    return frame.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
