"""MultiPost entry point.

Usage:
    python app.py            -> desktop UI (PySide6)
    python app.py --cli ...  -> headless helpers (see multipost/cli.py)
"""

import sys

if "--cli" in sys.argv:
    sys.argv.remove("--cli")
    from multipost.cli import main
    raise SystemExit(main(sys.argv[1:]))

from multipost.ui import run

if __name__ == "__main__":
    run()
