#!/usr/bin/env python3
"""
Council Skill - Database Initialization Script

Initializes the Council Memory database with the full schema.
Auto-initializes on first use with clear logging.

Usage:
    python init_db.py
    python init_db.py --force
    python init_db.py --check
"""

import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

# Import path resolver for skill-root awareness
try:
    from lib.path_resolver import (
        SKILL_ROOT,
        MEMORY_DB_PATH,
        MEMORY_DATA_DIR,
        MEMORY_INIT_SCHEMA,
        MEMORY_CONFIG_DIR,
        MEMORY_SETTINGS_PATH
    )
except ImportError:
    # Fallback if running directly from memory/ directory
    SKILL_ROOT = Path(__file__).parent.parent
    MEMORY_DIR = SKILL_ROOT / "memory"
    MEMORY_DATA_DIR = MEMORY_DIR / "data"
    MEMORY_DB_PATH = MEMORY_DATA_DIR / "council_memory.db"
    MEMORY_MIGRATIONS_DIR = MEMORY_DIR / "migrations"
    MEMORY_INIT_SCHEMA = MEMORY_MIGRATIONS_DIR / "init_schema.sql"
    MEMORY_CONFIG_DIR = MEMORY_DIR / "config"
    MEMORY_SETTINGS_PATH = MEMORY_CONFIG_DIR / "memory_settings.json"


def check_database_exists(db_path: Path) -> bool:
    """Check if database file exists and is valid."""
    if not db_path.exists():
        return False

    # Try to open and query the database
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Consider it valid if it has at least one table
        return len(tables) > 0
    except sqlite3.DatabaseError:
        return False


def initialize_database(db_path: Path, schema_path: Path, force: bool = False) -> bool:
    """
    Initialize the Council Memory database.

    Args:
        db_path: Path where the database should be created
        schema_path: Path to the SQL schema file
        force: Overwrite existing database

    Returns:
        bool: True if initialization succeeded
    """
    # Check if database already exists
    if not force and check_database_exists(db_path):
        print(f"Database already exists: {db_path}")
        print("Use --force to overwrite")
        return False

    # Verify schema file exists
    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}", file=sys.stderr)
        return False

    # Create data directory
    MEMORY_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Backup existing database if forcing
    if force and db_path.exists():
        backup_path = db_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        print(f"Backing up existing database to: {backup_path}")
        db_path.rename(backup_path)

    # Read schema
    print(f"Reading schema from: {schema_path}")
    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: Failed to read schema: {e}", file=sys.stderr)
        return False

    # Create database
    print(f"Creating database at: {db_path}")
    try:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(schema_sql)
        conn.commit()

        # Verify creation
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"Successfully created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")

        conn.close()
        return True

    except Exception as e:
        print(f"ERROR: Failed to create database: {e}", file=sys.stderr)
        # Clean up partial database
        if db_path.exists():
            db_path.unlink()
        return False


def verify_config_files():
    """Verify that configuration files exist."""
    print("\nVerifying configuration files...")

    required_files = [
        (MEMORY_SETTINGS_PATH, "Memory settings"),
    ]

    all_exist = True
    for file_path, description in required_files:
        if file_path.exists():
            print(f"  ✓ {description}: {file_path}")
        else:
            print(f"  ✗ {description} missing: {file_path}")
            all_exist = False

    return all_exist


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize Council Memory Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Initialize if not exists
  %(prog)s --force            # Overwrite existing database
  %(prog)s --check            # Check if database exists
        """
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing database (creates backup first)"
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if database exists, don't create"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Council Memory Database Initialization")
    print("=" * 60)
    print(f"Skill Root: {SKILL_ROOT}")
    print(f"Database: {MEMORY_DB_PATH}")
    print(f"Schema: {MEMORY_INIT_SCHEMA}")
    print("=" * 60)

    # Check-only mode
    if args.check:
        if check_database_exists(MEMORY_DB_PATH):
            print("✓ Database exists and is valid")
            sys.exit(0)
        else:
            print("✗ Database does not exist or is invalid")
            sys.exit(1)

    # Initialize database
    success = initialize_database(
        db_path=MEMORY_DB_PATH,
        schema_path=MEMORY_INIT_SCHEMA,
        force=args.force
    )

    if success:
        print("\n" + "=" * 60)
        print("✓ Database initialization complete")
        print("=" * 60)

        # Verify config files
        verify_config_files()

        print("\nThe Council Memory system is ready to use.")
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Database initialization failed")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
