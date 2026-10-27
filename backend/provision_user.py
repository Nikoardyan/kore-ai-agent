"""Provision akun KORE AI dari terminal admin.

Contoh:
  python provision_user.py EMP-003 --role hr

Skrip ini dimaksudkan untuk dijalankan oleh admin dengan DATABASE_URL yang sudah benar,
bukan diekspos sebagai endpoint HTTP.
"""

import argparse
import getpass
import os
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

# Preserve the caller's database target before api.py loads backend/.env with
# override=True. This lets an admin run this script with Vercel's production
# environment without accidentally provisioning against the local database.
provision_database_url = os.getenv("DATABASE_URL")

from api import _hash_password
from src.config import settings
from src.database.connection import get_db_connection
from src.database.repository import UserRepository

if provision_database_url:
    settings.database_url = provision_database_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat akun pengguna yang sudah terdaftar di HR database.")
    parser.add_argument("employee_id")
    parser.add_argument("--role", choices=("employee", "hr", "admin"), default="employee")
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Gunakan DATABASE_URL dari file environment tertentu, misalnya .env.production.local.",
    )
    parser.add_argument(
        "--database-url-prompt",
        action="store_true",
        help="Minta DATABASE_URL secara tersembunyi, misalnya untuk secret Vercel yang tidak bisa ditarik.",
    )
    args = parser.parse_args()

    if args.env_file and args.database_url_prompt:
        parser.error("Pilih --env-file atau --database-url-prompt, jangan keduanya.")

    if args.env_file:
        if not args.env_file.is_file():
            parser.error(f"File environment tidak ditemukan: {args.env_file}")
        production_database_url = dotenv_values(args.env_file).get("DATABASE_URL")
        if not production_database_url or not production_database_url.startswith(
            ("postgresql://", "postgresql+psycopg://", "postgres://")
        ):
            parser.error(
                f"{args.env_file} tidak berisi DATABASE_URL PostgreSQL yang dapat dibaca. "
                "Secret Vercel bisa berupa placeholder; gunakan --database-url-prompt."
            )
        settings.database_url = production_database_url

    if args.database_url_prompt:
        production_database_url = getpass.getpass("Production DATABASE_URL (input tersembunyi): ").strip()
        if not production_database_url.startswith(
            ("postgresql://", "postgresql+psycopg://", "postgres://")
        ):
            parser.error("DATABASE_URL harus berupa URL PostgreSQL.")
        settings.database_url = production_database_url

    employee = UserRepository().get_employee_by_id(args.employee_id.strip())
    if not employee:
        print("Employee ID tidak ditemukan di tabel employees.", file=sys.stderr)
        return 1

    password = getpass.getpass("Password baru (minimal 12 karakter): ")
    confirmation = getpass.getpass("Ulangi password: ")
    if len(password) < 12 or password != confirmation:
        print("Password harus sama dan minimal 12 karakter.", file=sys.stderr)
        return 1

    password_data = _hash_password(password)
    with get_db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO app_users (employee_id, display_name, role, password_hash, password_salt, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (employee_id) DO NOTHING
            RETURNING employee_id
            """,
            (
                employee["employee_id"], employee["full_name"], args.role,
                password_data["hash"], password_data["salt"], int(time.time()),
            ),
        ).fetchone()

    if not row:
        print("Akun sudah ada; gunakan prosedur reset password yang terotorisasi.", file=sys.stderr)
        return 1
    print(f"Akun {employee['employee_id']} dengan role {args.role} berhasil dibuat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
