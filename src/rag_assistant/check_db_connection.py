"""Check the RDS PostgreSQL connection and enable the pgvector extension."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Missing required .env settings: {names}")

    try:
        port = int(os.getenv("PGPORT", "5432"))
    except ValueError as exc:
        raise SystemExit("PGPORT must be a valid integer") from exc

    connection_options = {
        "host": os.environ["PGHOST"],
        "port": port,
        "dbname": os.environ["PGDATABASE"],
        "user": os.environ["PGUSER"],
        "password": os.environ["PGPASSWORD"],
        "sslmode": os.getenv("PGSSLMODE", "require"),
        "connect_timeout": 10,
    }

    try:
        with psycopg.connect(**connection_options) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except psycopg.Error as exc:
        raise SystemExit(
            "RDS connection or pgvector extension setup failed. "
            "Check the endpoint, network access, credentials, SSL settings, "
            f"and extension permissions. PostgreSQL reported: {exc}"
        ) from exc

    print("Connected to RDS and ensured the vector extension is installed.")


if __name__ == "__main__":
    main()
