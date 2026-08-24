#!/usr/bin/env python3
"""Run the local-only Career Radar web panel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.panel import LOOPBACK_HOSTS, create_app  # noqa: E402


DEFAULT_DATABASE = ROOT / "career_radar.local.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Opportunity Inbox panel.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=_port, default=8765)
    arguments = parser.parse_args(argv)
    if arguments.host not in LOOPBACK_HOSTS:
        parser.error("--host must be a loopback address")
    try:
        import uvicorn

        app = create_app(
            db_path=arguments.db,
            root=ROOT,
            profile_path=arguments.profile,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    uvicorn.run(app, host=arguments.host, port=arguments.port, log_level="warning")
    return 0


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65_535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


if __name__ == "__main__":
    raise SystemExit(main())
