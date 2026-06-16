"""Command-line entry for the student account system.

Launch from the project root, mirroring ``student_main.py``::

    uv run python student_account_platform/account_main.py

The project root is prepended to ``sys.path`` so that uvicorn's reload
subprocess can still import the top-level ``student_account_platform``
package, even when this file is invoked by path (which otherwise puts only
this package's own directory on ``sys.path``).
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "student_account_platform.web:app",
        host="127.0.0.1",
        port=8002,
        reload=True,
    )
