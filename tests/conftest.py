import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_frame(closes, volume=1_000_000.0, end="2026-09-25"):
    idx = pd.bdate_range(end=end, periods=len(closes))
    c = pd.Series(np.asarray(closes, dtype=float), index=idx)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
                         "Volume": np.full(len(c), volume)})


@pytest.fixture
def frame():
    return make_frame


@pytest.fixture
def trending_up():
    return make_frame(np.linspace(50, 100, 300))


@pytest.fixture
def trending_down():
    return make_frame(np.linspace(100, 50, 300))
