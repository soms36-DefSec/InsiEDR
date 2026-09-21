from __future__ import annotations

import argparse
import sys

from server.storage.postgres_storage import PostgresStorage


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Run InsiEDR database migrations")
	parser.add_argument("--dsn", default=None, help="PostgreSQL DSN; falls back to INSIEDR_DATABASE_DSN/DATABASE_DSN")
	return parser


def main(argv: list[str] | None = None) -> int:
	args = build_parser().parse_args(argv)
	storage = PostgresStorage(args.dsn)
	storage.ensure_migrations()
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))
