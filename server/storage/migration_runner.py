from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable
from datetime import datetime, timezone


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    in_dollar = False

    i = 0
    while i < len(sql_text):
        char = sql_text[i]
        
        # Check for $$
        if char == '$' and i + 1 < len(sql_text) and sql_text[i+1] == '$' and not in_single and not in_double:
            in_dollar = not in_dollar
            current.append('$')
            current.append('$')
            i += 2
            continue

        if char == "'" and not in_double and not in_dollar:
            in_single = not in_single
        elif char == '"' and not in_single and not in_dollar:
            in_double = not in_double
        elif char == ";" and not in_single and not in_double and not in_dollar:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue
            
        current.append(char)
        i += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def run_sql_script(connection, sql_text: str) -> int:
    cursor = connection.cursor()
    count = 0
    is_sqlite = connection.__class__.__module__.startswith("sqlite3")
    try:
        for statement in split_sql_statements(sql_text):
            if not is_sqlite:
                statement = statement.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            
            if not statement.strip():
                continue
                
            try:
                cursor.execute(statement)
                count += 1
            except Exception as e:
                # psycopg2 raises ProgrammingError for statements that only contain comments
                if "empty query" in str(e).lower():
                    continue
                raise
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return count


def apply_migration_file(connection_factory: Callable[[], object], migration_path: str | Path) -> int:
    path = Path(migration_path)
    sql_text = path.read_text(encoding="utf-8")
    connection = connection_factory()
    return run_sql_script(connection, sql_text)


def apply_migrations_dir(connection_factory: Callable[[], object], migrations_dir: str | Path) -> int:
    """Apply all SQL files in a directory in sorted order.

    Files ending with `_pg.sql` are only applied when the connection is not SQLite.
    Returns the total number of statements executed across all files.
    """
    dirp = Path(migrations_dir)
    if not dirp.exists() or not dirp.is_dir():
        return 0
    total = 0
    # sort files to ensure deterministic ordering (001_..., 002_...)
    files = sorted([p for p in dirp.iterdir() if p.is_file() and p.suffix == '.sql'])

    # Determine DB flavor by opening a connection briefly
    probe_conn = connection_factory()
    try:
        is_sqlite = probe_conn.__class__.__module__.startswith("sqlite3")
    finally:
        try:
            probe_conn.close()
        except Exception:
            pass

    # Ensure a schema_migrations table exists so we can track applied migrations
    conn = connection_factory()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Build set of already applied migrations
    conn = connection_factory()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT name FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        except Exception:
            applied = set()
        finally:
            cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for path in files:
        name = path.name
        if name.endswith("_pg.sql") and is_sqlite:
            # skip Postgres-only migration on sqlite demo
            continue
        if name in applied:
            continue

        sql_text = path.read_text(encoding="utf-8")
        # execute migration in its own connection
        connection = connection_factory()
        try:
            total += run_sql_script(connection, sql_text)
        finally:
            try:
                connection.close()
            except Exception:
                pass

        # record migration as applied
        record_conn = connection_factory()
        try:
            cur = record_conn.cursor()
            try:
                # placeholder differs between sqlite and psycopg2
                module_name = record_conn.__class__.__module__
                placeholder = "?" if module_name.startswith("sqlite3") else "%s"
                applied_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                cur.execute(
                    f"INSERT INTO schema_migrations (name, applied_at) VALUES ({placeholder}, {placeholder})",
                    (name, applied_at),
                )
                record_conn.commit()
            finally:
                cur.close()
        finally:
            try:
                record_conn.close()
            except Exception:
                pass

    return total
