"""Create a clean database directly as bot.db."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from db.models import Base


def create_clean_database(database_path: str = "bot.db") -> None:
    """
    Create or replace a clean SQLite database directly.
    This DELETES the existing database and creates a fresh one.
    """
    path = Path(database_path)

    # Delete old database if it exists
    if path.exists():
        print(f"🗑️ Deleting old database: {path}")
        path.unlink()

    # Create new database with all tables
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    engine.dispose()

    # Verify tables
    with sqlite3.connect(path) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]

    print(f"✅ Created clean database: {path.resolve()}")
    print(f"📊 Tables: {', '.join(tables)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a clean database directly as bot.db")
    parser.add_argument(
        "database_path",
        nargs="?",
        default="bot.db",
        help="Path to the database file (default: bot.db)"
    )
    args = parser.parse_args()
    create_clean_database(args.database_path)
