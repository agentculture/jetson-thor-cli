"""Entry point for ``python -m jetson_thor``."""

from __future__ import annotations

import sys

from jetson_thor.cli import main

if __name__ == "__main__":
    sys.exit(main())
