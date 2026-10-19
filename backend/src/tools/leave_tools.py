"""
leave_tools.py - Tool untuk mengambil data cuti karyawan dari database.

FIX dari versi sebelumnya:
- Sebelumnya hanya dummy yang selalu return 12. Sekarang mengambil data nyata
  dari database via UserRepository.
- Fungsi ini digunakan oleh sistem agent sebagai tool yang reusable.
"""

import logging

logger = logging.getLogger("kore.tools.leave")


def get_leave_balance(employee_id: str) -> dict | None:
    """
    Mengambil saldo cuti karyawan dari database.

    Args:
        employee_id: ID karyawan (misal: EMP-001)

    Returns:
        Dict berisi year, annual_quota, used_leave, pending_leave, remaining_leave
        atau None jika data tidak ditemukan.
    """
    if not employee_id:
        logger.warning("get_leave_balance dipanggil tanpa employee_id")
        return None
    try:
        from src.database.repository import UserRepository
        repo = UserRepository()
        return repo.get_leave_balance(employee_id)
    except Exception:
        logger.exception("Gagal mengambil saldo cuti untuk %s", employee_id)
        return None


def list_leave_requests(employee_id: str, limit: int = 5) -> list:
    """
    Mengambil riwayat pengajuan cuti karyawan dari database.

    Args:
        employee_id: ID karyawan
        limit: Jumlah maksimum data yang dikembalikan

    Returns:
        List dict berisi start_date, end_date, total_days, leave_type, status
    """
    if not employee_id:
        return []
    try:
        from src.database.repository import UserRepository
        repo = UserRepository()
        return repo.list_leave_requests(employee_id, limit=limit)
    except Exception:
        logger.exception("Gagal mengambil riwayat cuti untuk %s", employee_id)
        return []
