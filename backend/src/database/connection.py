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
    """Skema & data sudah disiapkan lewat `docker compose --profile seed`.
    Di sini cuma mengecek koneksi ke Postgres hidup saat server start,
    supaya error konfigurasi ketahuan langsung, bukan pas ada chat masuk."""
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")