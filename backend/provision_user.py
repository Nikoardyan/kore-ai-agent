"""Provision akun KORE AI dari terminal admin.

Contoh:
  python provision_user.py EMP-003 --role hr

Skrip ini dimaksudkan untuk dijalankan oleh admin dengan DATABASE_URL yang sudah benar,
bukan diekspos sebagai endpoint HTTP.
"""

import argparse
import getpass
import sys
import time

from api import _hash_password
from src.database.connection import get_db_connection
from src.database.repository import UserRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Buat akun pengguna yang sudah terdaftar di HR database.")
    parser.add_argument("employee_id")
    parser.add_argument("--role", choices=("employee", "hr", "admin"), default="employee")
    args = parser.parse_args()

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
