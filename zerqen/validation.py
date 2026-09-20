from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class Split:
    train: pd.DataFrame
    test: pd.DataFrame

def chronological_split(frame: pd.DataFrame, train_fraction: float = 0.7) -> Split:
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    cut = int(len(frame) * train_fraction)
    if cut < 1 or cut >= len(frame):
        raise ValueError("frame is too small for requested split")
    return Split(frame.iloc[:cut].copy(), frame.iloc[cut:].copy())

def rolling_walk_forward(
    frame: pd.DataFrame,
    train_size: int,
    test_size: int,
    step: int | None = None,
) -> list[Split]:
    if train_size <= 0 or test_size <= 0:
        raise ValueError("train_size and test_size must be positive")
    step = step or test_size
    splits = []
    start = 0
    while start + train_size + test_size <= len(frame):
        train = frame.iloc[start:start + train_size].copy()
        test = frame.iloc[start + train_size:start + train_size + test_size].copy()
        splits.append(Split(train, test))
        start += step
    return splits
