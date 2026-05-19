#!/usr/bin/env python3
"""
CloudVault single entry — starts API + web UI together.
Usage (from repo root):
  python run.py
Then open http://127.0.0.1:8000/

Optional auto-reload on code changes:
  python run.py --reload
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")


def main() -> None:
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)

    import uvicorn

    reload = "--reload" in sys.argv
    kwargs = dict(
        app="app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=reload,
    )
    if reload:
        kwargs["reload_dirs"] = [BACKEND]

    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()
