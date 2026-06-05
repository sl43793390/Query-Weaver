"""Query-Weaver — entry point.

Run with:
    python main.py
"""
from __future__ import annotations

import sys
import traceback


def main() -> int:
    # Ensure project root is on sys.path so `config` and `src` resolve
    # when running `python main.py` from any cwd.
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from src.core.logger import setup_logger
    setup_logger()

    try:
        from src.ui.main_window import MainWindow
    except ImportError as exc:  # pragma: no cover - missing deps
        msg = str(exc)
        hint = (
            "tkinter is part of the Python stdlib but is a separate install "
            "option — install it via your OS package manager or re-run the "
            "Python installer and tick 'tcl/tk and IDLE'."
            if "tkinter" in msg
            else "Run: pip install -r requirements.txt"
        )
        print(f"[FATAL] Missing dependency: {exc}\n{hint}", file=sys.stderr)
        return 2

    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
