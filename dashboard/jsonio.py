"""JSON helpers: make numpy/pandas values serialisable and read/write files."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


def clean(v, ndigits: int = 4):
    """NaN/inf -> None, numpy scalars -> python, floats rounded, recursively."""
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, ndigits)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, dict):
        return {k: clean(x, ndigits) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x, ndigits) for x in v]
    return v


def write_json(path: Path, obj, compact: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kw = {"separators": (",", ":")} if compact else {"indent": 1}
    path.write_text(json.dumps(clean(obj), ensure_ascii=False, **kw), encoding="utf-8")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
