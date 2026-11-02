#!/usr/bin/env python3
"""Entry point for the lead finder CLI. See backend/app/cli.py or run with --help."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cli import main  # noqa: E402

raise SystemExit(main())
