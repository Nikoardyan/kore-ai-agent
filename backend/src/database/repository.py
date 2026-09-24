"""
repository.py - query ke PostgreSQL (database employee_agent)

Semua method dipanggil dari api.py (get_database_reply). Nama field yang
dikembalikan sengaja disamakan dengan nama kolom aslinya di database supaya
gampang dilacak, kecuali yang memang perlu di-join (department, manager_name).
"""

from src.database.connection import get_db_connection


class UserRepository:
    # -- index nama/ID untuk deteksi identifier di pesan user -----------------

    def list_employee_index(self):
        query = "SELECT employee_id, full_name FROM employees ORDER BY full_name"
        with get_db_connection() as connection:
            rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    # -- profil pegawai ---------------------------------------------------

    def find_employees(self, identifier: str, limit: int = 5):
        query = """
            SELECT
                e.employee_id,
                e.full_name,
                e.position,
                e.work_location,
                e.employment_status,
                e.join_date,
                d.name AS department,
                m.full_name AS manager_name
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
            LEFT JOIN employees m ON m.employee_id = e.manager_id
            WHERE e.employee_id ILIKE %s OR e.full_name ILIKE %s
            ORDER BY e.full_name
            LIMIT %s
        """
        like = f"%{identifier}%"
        with get_db_connection() as connection:
            rows = connection.execute(query, (like, like, limit)).fetchall()
        return [dict(row) for row in rows]

    def list_employees(self, limit: int = 20, filter_text: str | None = None):
        """filter_text: cocok ke posisi ATAU nama departemen (substring, case-insensitive)."""
        query = """
            SELECT e.employee_id, e.full_name, e.position, d.name AS department
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
        """
        params: list = []
        if filter_text:
            query += " WHERE e.position ILIKE %s OR d.name ILIKE %s"
            params += [f"%{filter_text}%", f"%{filter_text}%"]
        query += " ORDER BY e.full_name LIMIT %s"
        params.append(limit)
        with get_db_connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def count_employees(self, filter_text: str | None = None) -> int:
        query = """
            SELECT COUNT(*) AS total
            FROM employees e
            LEFT JOIN departments d ON d.id = e.department_id
        """
        params: list = []
        if filter_text:
            query += " WHERE e.position ILIKE %s OR d.name ILIKE %s"
            params += [f"%{filter_text}%", f"%{filter_text}%"]
        with get_db_connection() as connection:
            row = connection.execute(query, tuple(params)).fetchone()
        return row["total"] if row else 0

    # -- cuti ---------------------------------------------------------------

    def get_leave_balance(self, employee_id: str):
        query = """
            SELECT year, annual_quota, used_leave, pending_leave, remaining_leave
            FROM leave_balances
            WHERE employee_id = %s
            ORDER BY year DESC
            LIMIT 1
        """
        with get_db_connection() as connection:
            row = connection.execute(query, (employee_id,)).fetchone()
        return dict(row) if row else None

    def list_leave_requests(self, employee_id: str, limit: int = 5):
        query = """
            SELECT start_date, end_date, total_days, leave_type, status
            FROM leave_requests
            WHERE employee_id = %s
            ORDER BY start_date DESC
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]

    # -- lembur ---------------------------------------------------------------

    def list_overtime(self, employee_id: str, limit: int = 5):
        query = """
            SELECT overtime_date, start_time, end_time, duration_minutes, status, reason
            FROM overtime_requests
            WHERE employee_id = %s
            ORDER BY overtime_date DESC
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def overtime_summary(self, employee_id: str):
        query = """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(duration_minutes) FILTER (WHERE lower(status) = 'approved'), 0) AS approved_minutes
            FROM overtime_requests
            WHERE employee_id = %s
        """
        with get_db_connection() as connection:
            row = connection.execute(query, (employee_id,)).fetchone()
        return dict(row) if row else {"total": 0, "approved_minutes": 0}

    # -- tiket IT ---------------------------------------------------------------

    def list_tickets(self, employee_id: str | None = None, limit: int = 5):
        base = """
            SELECT t.id, t.category, t.priority, t.title, t.description,
                   t.status, t.created_at, e.full_name
            FROM it_tickets t
            JOIN employees e ON e.employee_id = t.employee_id
        """
        params: list = []
        if employee_id:
            base += " WHERE t.employee_id = %s"
            params.append(employee_id)
        base += " ORDER BY t.created_at DESC LIMIT %s"
        params.append(limit)
        with get_db_connection() as connection:
            rows = connection.execute(base, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    # -- WFH ---------------------------------------------------------------

    def list_wfh(self, employee_id: str, limit: int = 5):
        query = """
            SELECT wfh_date, status, reason
            FROM wfh_requests
            WHERE employee_id = %s
            ORDER BY wfh_date DESC
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]

    # -- reimbursement ---------------------------------------------------------------

    def list_reimbursements(self, employee_id: str, limit: int = 5):
        query = """
            SELECT submitted_at, category, amount, status, description
            FROM reimbursements
            WHERE employee_id = %s
            ORDER BY submitted_at DESC
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]

    # -- training ---------------------------------------------------------------

    def list_training(self, employee_id: str, limit: int = 5):
        query = """
            SELECT training_name, provider, start_date, cost, status
            FROM training_requests
            WHERE employee_id = %s
            ORDER BY start_date DESC
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]

    # -- absensi ---------------------------------------------------------------

    def attendance_summary(self, employee_id: str, last_n: int = 30):
        query = """
            SELECT
                attendance_status,
                COUNT(*) AS jumlah,
                COALESCE(SUM(late_minutes), 0) AS telat_menit
            FROM (
                SELECT attendance_status, late_minutes
                FROM attendance
                WHERE employee_id = %s
                ORDER BY attendance_date DESC
                LIMIT %s
            ) recent
            GROUP BY attendance_status
            ORDER BY jumlah DESC
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, last_n)).fetchall()
        return [dict(row) for row in rows]

    # -- aset perusahaan ---------------------------------------------------------------

    def list_assets(self, employee_id: str, limit: int = 10):
        query = """
            SELECT asset_code, asset_type, brand, model, status
            FROM company_assets
            WHERE employee_id = %s
            ORDER BY assigned_at DESC NULLS LAST
            LIMIT %s
        """
        with get_db_connection() as connection:
            rows = connection.execute(query, (employee_id, limit)).fetchall()
        return [dict(row) for row in rows]