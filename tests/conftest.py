from __future__ import annotations

import os
import tempfile
from pathlib import Path


_test_root = Path(tempfile.mkdtemp(prefix="miaobi-tests-"))
os.environ["MIAOBI_DATABASE_URL"] = f"sqlite:///{_test_root / 'miaobi.db'}"
os.environ["MIAOBI_STORAGE_ROOT"] = str(_test_root / "uploads")
