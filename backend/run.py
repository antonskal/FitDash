"""Launcher.

    python run.py                 # start the API (+ serves frontend/dist if built)
    python run.py --demo          # seed demo data if the DB is empty, then start
    python run.py --demo --reset  # wipe and reseed demo data, then start
"""

from __future__ import annotations

import argparse
import random

import uvicorn

from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Seed offline demo data (no Garmin account needed)")
    parser.add_argument("--reset", action="store_true", help="With --demo: wipe existing rows before seeding")
    parser.add_argument("--days", type=int, default=365, help="With --demo: number of days to generate")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if args.demo:
        from app.db import get_db
        from app.demo.seed import seed

        db = get_db()
        has_rows = db.query_one("SELECT COUNT(*) AS n FROM daily_summaries")["n"] > 0
        if args.reset or not has_rows:
            print(f"[demo] seeding {args.days} days into {settings.resolved_db_path}")
            seed(db, args.days, reset=True, rng=random.Random(42))
        else:
            print("[demo] database already has data; skipping seed (use --reset to regenerate)")

    uvicorn.run("app.main:app", host=args.host or settings.host, port=args.port or settings.port,
                reload=args.reload, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
