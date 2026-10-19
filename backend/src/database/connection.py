"""
connection.py - koneksi ke PostgreSQL (docker-compose: employee-agent-db)

Tabel sudah dibuat & diisi oleh service `seed` di proyek
employee_ai_agent_database (docker compose --profile seed run --rm seed).
File ini cuma menyediakan koneksi, bukan membuat skema.
"""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from src.config import settings


def _to_psycopg_conninfo(database_url: str) -> str:
    """psycopg gak kenal dialect suffix SQLAlchemy (postgresql+psycopg://), jadi dibuang."""
    database_url = (database_url or "").strip()
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError(
            "DATABASE_URL harus diawali postgresql:// atau postgresql+psycopg://, "
            f"sekarang: {database_url!r}"
        )
    return database_url


@contextmanager
def get_db_connection():
    """Dipakai sebagai: `with get_db_connection() as connection: connection.execute(...)`."""
    conninfo = _to_psycopg_conninfo(settings.database_url)
    connection = psycopg.connect(conninfo, row_factory=dict_row)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def initialize_database():
    """Mengecek koneksi ke Postgres dan memastikan tabel app_users tersedia."""
    db_url = getattr(settings, "database_url", "")
    if not db_url or not db_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        return
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS app_users (
                        employee_id VARCHAR(64) PRIMARY KEY,
                        display_name VARCHAR(128),
                        role VARCHAR(32) DEFAULT 'employee',
                        password_hash TEXT,
                        password_salt TEXT,
                        created_at BIGINT
                    );
                """)
    except Exception as exc:
        import logging
        logging.getLogger("kore.db").warning("Database belum terhubung: %s", exc)