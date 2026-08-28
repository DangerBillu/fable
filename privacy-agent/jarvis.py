#!/usr/bin/env python3
"""
FABLE / J.A.R.V.I.S. CLI Runner
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fable

if __name__ == "__main__":
    fable.main()
