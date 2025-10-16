from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

root_str = str(ROOT)
src_str = str(SRC)

if root_str not in sys.path:
    sys.path.insert(0, root_str)

if src_str not in sys.path:
    sys.path.insert(0, src_str)
