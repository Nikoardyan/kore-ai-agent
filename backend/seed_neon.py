"""
seed_neon.py - Script untuk membuat tabel & mengisi data sample ke Neon (cloud PostgreSQL).

Cara pakai:
  export NEON_DATABASE_URL="postgresql://neondb_owner:XXXX@ep-xxx.neon.tech/employee_agent?sslmode=require"
  python3 seed_neon.py

Script ini idempotent: bisa dijalankan berkali-kali tanpa duplikasi data
(menggunakan IF NOT EXISTS dan ON CONFLICT).
"""

import os
import sys

try:
    import psycopg
except ImportError:
    print("❌ psycopg belum terinstall. Jalankan: pip install psycopg[binary]")
    sys.exit(1)


DATABASE_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("❌ Set environment variable NEON_DATABASE_URL dulu!")
    print('   export NEON_DATABASE_URL="postgresql://user:pass@host/dbname?sslmode=require"')
    sys.exit(1)


# ---------------------------------------------------------------------------
# DDL - Tabel
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    # Departments
    """
    CREATE TABLE IF NOT EXISTS departments (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Employees
    """
    CREATE TABLE IF NOT EXISTS employees (
        employee_id VARCHAR(20) PRIMARY KEY,
        full_name VARCHAR(100) NOT NULL,
        position VARCHAR(100),
        department_id INT REFERENCES departments(id),
        work_location VARCHAR(100) DEFAULT 'Jakarta HQ',
        employment_status VARCHAR(30) DEFAULT 'Active',
        join_date DATE,
        manager_id VARCHAR(20) REFERENCES employees(employee_id),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Leave balances
    """
    CREATE TABLE IF NOT EXISTS leave_balances (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        year INT NOT NULL,
        annual_quota INT DEFAULT 12,
        used_leave INT DEFAULT 0,
        pending_leave INT DEFAULT 0,
        remaining_leave INT DEFAULT 12,
        UNIQUE(employee_id, year)
    )
    """,
    # Leave requests
    """
    CREATE TABLE IF NOT EXISTS leave_requests (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        start_date DATE,
        end_date DATE,
        total_days INT,
        leave_type VARCHAR(50),
        status VARCHAR(30) DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Overtime requests
    """
    CREATE TABLE IF NOT EXISTS overtime_requests (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        overtime_date DATE,
        start_time TIME,
        end_time TIME,
        duration_minutes INT,
        status VARCHAR(30) DEFAULT 'Pending',
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # IT tickets
    """
    CREATE TABLE IF NOT EXISTS it_tickets (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        category VARCHAR(50),
        priority VARCHAR(20) DEFAULT 'Medium',
        title VARCHAR(200),
        description TEXT,
        status VARCHAR(30) DEFAULT 'Open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # WFH requests
    """
    CREATE TABLE IF NOT EXISTS wfh_requests (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        wfh_date DATE,
        status VARCHAR(30) DEFAULT 'Pending',
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Reimbursements
    """
    CREATE TABLE IF NOT EXISTS reimbursements (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        category VARCHAR(50),
        amount DECIMAL(12,2),
        status VARCHAR(30) DEFAULT 'Pending',
        description TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Training requests
    """
    CREATE TABLE IF NOT EXISTS training_requests (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        training_name VARCHAR(200),
        provider VARCHAR(100),
        start_date DATE,
        cost DECIMAL(12,2),
        status VARCHAR(30) DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Attendance
    """
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        attendance_date DATE,
        attendance_status VARCHAR(30) DEFAULT 'Present',
        check_in TIME,
        check_out TIME,
        late_minutes INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # Company assets
    """
    CREATE TABLE IF NOT EXISTS company_assets (
        id SERIAL PRIMARY KEY,
        employee_id VARCHAR(20) REFERENCES employees(employee_id),
        asset_code VARCHAR(50),
        asset_type VARCHAR(50),
        brand VARCHAR(50),
        model VARCHAR(100),
        status VARCHAR(30) DEFAULT 'Active',
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


# ---------------------------------------------------------------------------
# Seed Data
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    (1, "Engineering"),
    (2, "Human Resources"),
    (3, "Finance"),
    (4, "Marketing"),
    (5, "Operations"),
]

EMPLOYEES = [
    ("EMP-001", "Niko Demo", "AI Engineer", 1, "Jakarta HQ", "Active", "2023-03-15", None, "niko@arunika.co.id"),
    ("EMP-002", "Celine Zafirameka", "Data Scientist", 1, "Jakarta HQ", "Active", "2023-06-01", "EMP-001", "celine@arunika.co.id"),
    ("EMP-003", "Budi Santoso", "HR Manager", 2, "Jakarta HQ", "Active", "2022-01-10", None, "budi@arunika.co.id"),
    ("EMP-004", "Sari Dewi", "Finance Analyst", 3, "Jakarta HQ", "Active", "2023-09-01", None, "sari@arunika.co.id"),
    ("EMP-005", "Andi Pratama", "Marketing Lead", 4, "Bandung Office", "Active", "2022-07-20", None, "andi@arunika.co.id"),
    ("EMP-006", "Rina Wulandari", "DevOps Engineer", 1, "Jakarta HQ", "Active", "2023-11-01", "EMP-001", "rina@arunika.co.id"),
    ("EMP-007", "Dimas Arya", "Operations Staff", 5, "Surabaya Office", "Active", "2024-01-15", None, "dimas@arunika.co.id"),
    ("EMP-008", "Putri Ayu", "HR Staff", 2, "Jakarta HQ", "Active", "2024-02-01", "EMP-003", "putri@arunika.co.id"),
    ("EMP-009", "Fajar Hidayat", "Backend Developer", 1, "Jakarta HQ", "Active", "2023-04-01", "EMP-001", "fajar@arunika.co.id"),
    ("EMP-010", "Maya Sari", "UI/UX Designer", 4, "Jakarta HQ", "Active", "2023-08-15", "EMP-005", "maya@arunika.co.id"),
]

LEAVE_BALANCES = [
    ("EMP-001", 2026, 12, 5, 0, 7),
    ("EMP-002", 2026, 12, 3, 1, 8),
    ("EMP-003", 2026, 12, 8, 0, 4),
    ("EMP-004", 2026, 12, 2, 2, 8),
    ("EMP-005", 2026, 12, 6, 0, 6),
    ("EMP-006", 2026, 12, 1, 0, 11),
    ("EMP-007", 2026, 12, 0, 0, 12),
    ("EMP-008", 2026, 12, 4, 1, 7),
    ("EMP-009", 2026, 12, 3, 0, 9),
    ("EMP-010", 2026, 12, 7, 0, 5),
]

LEAVE_REQUESTS = [
    ("EMP-001", "2026-06-10", "2026-06-12", 3, "Annual Leave", "Approved"),
    ("EMP-001", "2026-09-05", "2026-09-06", 2, "Annual Leave", "Approved"),
    ("EMP-002", "2026-07-15", "2026-07-17", 3, "Annual Leave", "Approved"),
    ("EMP-002", "2026-10-20", "2026-10-20", 1, "Sick Leave", "Pending"),
    ("EMP-003", "2026-03-01", "2026-03-05", 5, "Annual Leave", "Approved"),
    ("EMP-003", "2026-08-10", "2026-08-12", 3, "Annual Leave", "Approved"),
]

OVERTIME_REQUESTS = [
    ("EMP-001", "2026-10-01", "18:00", "21:00", 180, "Approved", "Deploy model ke production"),
    ("EMP-001", "2026-10-10", "19:00", "22:00", 180, "Pending", "Hotfix bug di API"),
    ("EMP-002", "2026-09-28", "18:00", "20:30", 150, "Approved", "Analisis data quarterly"),
    ("EMP-006", "2026-10-05", "17:00", "21:00", 240, "Approved", "Setup Kubernetes cluster"),
    ("EMP-009", "2026-10-12", "18:30", "22:00", 210, "Pending", "Refactor payment service"),
]

IT_TICKETS = [
    ("EMP-001", "Software", "High", "Akses GPU server down", "GPU server tidak bisa diakses sejak pagi", "Open"),
    ("EMP-002", "Hardware", "Medium", "Monitor kedua flickering", "Monitor LG 27 inci flickering tiap 30 menit", "In Progress"),
    ("EMP-004", "Network", "Low", "WiFi lantai 3 lambat", "Speed test cuma 5 Mbps, biasanya 50 Mbps", "Open"),
    ("EMP-007", "Software", "High", "SAP error saat input PO", "Error code 500 saat submit purchase order", "Resolved"),
    ("EMP-009", "Access", "Medium", "Request akses staging DB", "Butuh akses read ke staging database", "Open"),
]

WFH_REQUESTS = [
    ("EMP-001", "2026-10-14", "Approved", "Fokus coding di rumah"),
    ("EMP-001", "2026-10-15", "Approved", "Lanjut sprint review"),
    ("EMP-002", "2026-10-16", "Pending", "Dokter visit pagi"),
    ("EMP-006", "2026-10-14", "Approved", "Monitor deployment dari rumah"),
    ("EMP-009", "2026-10-17", "Rejected", "Melebihi kuota WFH bulan ini"),
]

REIMBURSEMENTS = [
    ("EMP-001", "Transport", 150000, "Approved", "Grab ke client meeting"),
    ("EMP-001", "Meal", 85000, "Approved", "Makan siang dengan client"),
    ("EMP-003", "Transport", 200000, "Approved", "Taksi ke kantor cabang"),
    ("EMP-005", "Marketing", 500000, "Pending", "Cetak brosur campaign Q4"),
    ("EMP-010", "Software", 300000, "Approved", "Figma Pro subscription 1 bulan"),
]

TRAINING_REQUESTS = [
    ("EMP-001", "Advanced LLM Fine-tuning", "Coursera", "2026-11-01", 0, "Approved"),
    ("EMP-002", "Machine Learning Operations", "DataCamp", "2026-11-15", 500000, "Pending"),
    ("EMP-003", "Leadership & Management", "HR Academy", "2026-10-20", 750000, "Approved"),
    ("EMP-006", "AWS Solutions Architect", "AWS Training", "2026-12-01", 1500000, "Pending"),
]

ATTENDANCE_DATA = [
    ("EMP-001", "2026-10-14", "Present", "08:55", "18:05", 0),
    ("EMP-001", "2026-10-15", "Present", "09:10", "18:00", 10),
    ("EMP-001", "2026-10-16", "Present", "08:45", "18:30", 0),
    ("EMP-001", "2026-10-17", "Present", "09:25", "18:00", 25),
    ("EMP-001", "2026-10-18", "WFH", "09:00", "17:30", 0),
    ("EMP-002", "2026-10-14", "Present", "08:50", "17:55", 0),
    ("EMP-002", "2026-10-15", "Present", "08:30", "18:10", 0),
    ("EMP-002", "2026-10-16", "Sick", None, None, 0),
    ("EMP-002", "2026-10-17", "Present", "09:00", "18:00", 0),
    ("EMP-002", "2026-10-18", "Present", "08:40", "17:50", 0),
    ("EMP-003", "2026-10-14", "Present", "08:00", "17:00", 0),
    ("EMP-003", "2026-10-15", "Present", "08:15", "17:30", 0),
    ("EMP-003", "2026-10-16", "Present", "07:55", "17:00", 0),
]

COMPANY_ASSETS = [
    ("EMP-001", "AST-001", "Laptop", "MacBook", "Pro 14 M3 Pro", "Active"),
    ("EMP-001", "AST-002", "Monitor", "LG", "27UK850 4K", "Active"),
    ("EMP-002", "AST-003", "Laptop", "MacBook", "Air M2", "Active"),
    ("EMP-003", "AST-004", "Laptop", "Lenovo", "ThinkPad X1 Carbon", "Active"),
    ("EMP-006", "AST-005", "Laptop", "MacBook", "Pro 16 M3 Max", "Active"),
    ("EMP-006", "AST-006", "Monitor", "Dell", "U2723QE 4K", "Active"),
    ("EMP-009", "AST-007", "Laptop", "MacBook", "Pro 14 M3", "Active"),
    ("EMP-010", "AST-008", "Tablet", "Apple", "iPad Pro 12.9", "Active"),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"🔗 Connecting to: {DATABASE_URL[:50]}...")
    
    conn = psycopg.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # 1. Create tables
    print("\n📋 Creating tables...")
    for ddl in DDL_STATEMENTS:
        cur.execute(ddl)
    conn.commit()
    print("   ✅ All tables created")
    
    # 2. Seed departments
    print("\n🏢 Seeding departments...")
    for dept_id, name in DEPARTMENTS:
        cur.execute(
            "INSERT INTO departments (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (dept_id, name),
        )
    # Reset sequence
    cur.execute("SELECT setval('departments_id_seq', (SELECT COALESCE(MAX(id),0) FROM departments))")
    conn.commit()
    print(f"   ✅ {len(DEPARTMENTS)} departments")
    
    # 3. Seed employees (2 passes: first without manager_id, then update)
    print("\n👤 Seeding employees...")
    for emp in EMPLOYEES:
        cur.execute(
            """INSERT INTO employees (employee_id, full_name, position, department_id,
               work_location, employment_status, join_date, manager_id, email)
               VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s)
               ON CONFLICT (employee_id) DO UPDATE SET
                 full_name=EXCLUDED.full_name, position=EXCLUDED.position,
                 department_id=EXCLUDED.department_id, work_location=EXCLUDED.work_location,
                 employment_status=EXCLUDED.employment_status, join_date=EXCLUDED.join_date,
                 email=EXCLUDED.email""",
            (emp[0], emp[1], emp[2], emp[3], emp[4], emp[5], emp[6], emp[8]),
        )
    conn.commit()
    # Update manager_id
    for emp in EMPLOYEES:
        if emp[7]:
            cur.execute(
                "UPDATE employees SET manager_id=%s WHERE employee_id=%s",
                (emp[7], emp[0]),
            )
    conn.commit()
    print(f"   ✅ {len(EMPLOYEES)} employees")
    
    # 4. Seed leave balances
    print("\n🏖️  Seeding leave balances...")
    for lb in LEAVE_BALANCES:
        cur.execute(
            """INSERT INTO leave_balances (employee_id, year, annual_quota, used_leave, pending_leave, remaining_leave)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (employee_id, year) DO UPDATE SET
                 annual_quota=EXCLUDED.annual_quota, used_leave=EXCLUDED.used_leave,
                 pending_leave=EXCLUDED.pending_leave, remaining_leave=EXCLUDED.remaining_leave""",
            lb,
        )
    conn.commit()
    print(f"   ✅ {len(LEAVE_BALANCES)} leave balances")
    
    # 5. Seed leave requests
    print("\n📝 Seeding leave requests...")
    cur.execute("DELETE FROM leave_requests")
    for lr in LEAVE_REQUESTS:
        cur.execute(
            """INSERT INTO leave_requests (employee_id, start_date, end_date, total_days, leave_type, status)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            lr,
        )
    conn.commit()
    print(f"   ✅ {len(LEAVE_REQUESTS)} leave requests")
    
    # 6. Seed overtime requests
    print("\n⏰ Seeding overtime requests...")
    cur.execute("DELETE FROM overtime_requests")
    for ot in OVERTIME_REQUESTS:
        cur.execute(
            """INSERT INTO overtime_requests (employee_id, overtime_date, start_time, end_time, duration_minutes, status, reason)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            ot,
        )
    conn.commit()
    print(f"   ✅ {len(OVERTIME_REQUESTS)} overtime requests")
    
    # 7. Seed IT tickets
    print("\n🎫 Seeding IT tickets...")
    cur.execute("DELETE FROM it_tickets")
    for tk in IT_TICKETS:
        cur.execute(
            """INSERT INTO it_tickets (employee_id, category, priority, title, description, status)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            tk,
        )
    conn.commit()
    print(f"   ✅ {len(IT_TICKETS)} IT tickets")
    
    # 8. Seed WFH requests
    print("\n🏠 Seeding WFH requests...")
    cur.execute("DELETE FROM wfh_requests")
    for wfh in WFH_REQUESTS:
        cur.execute(
            """INSERT INTO wfh_requests (employee_id, wfh_date, status, reason)
               VALUES (%s,%s,%s,%s)""",
            wfh,
        )
    conn.commit()
    print(f"   ✅ {len(WFH_REQUESTS)} WFH requests")
    
    # 9. Seed reimbursements
    print("\n💰 Seeding reimbursements...")
    cur.execute("DELETE FROM reimbursements")
    for rb in REIMBURSEMENTS:
        cur.execute(
            """INSERT INTO reimbursements (employee_id, category, amount, status, description)
               VALUES (%s,%s,%s,%s,%s)""",
            rb,
        )
    conn.commit()
    print(f"   ✅ {len(REIMBURSEMENTS)} reimbursements")
    
    # 10. Seed training requests
    print("\n📚 Seeding training requests...")
    cur.execute("DELETE FROM training_requests")
    for tr in TRAINING_REQUESTS:
        cur.execute(
            """INSERT INTO training_requests (employee_id, training_name, provider, start_date, cost, status)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            tr,
        )
    conn.commit()
    print(f"   ✅ {len(TRAINING_REQUESTS)} training requests")
    
    # 11. Seed attendance
    print("\n📊 Seeding attendance...")
    cur.execute("DELETE FROM attendance")
    for att in ATTENDANCE_DATA:
        cur.execute(
            """INSERT INTO attendance (employee_id, attendance_date, attendance_status, check_in, check_out, late_minutes)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            att,
        )
    conn.commit()
    print(f"   ✅ {len(ATTENDANCE_DATA)} attendance records")
    
    # 12. Seed company assets
    print("\n🖥️  Seeding company assets...")
    cur.execute("DELETE FROM company_assets")
    for asset in COMPANY_ASSETS:
        cur.execute(
            """INSERT INTO company_assets (employee_id, asset_code, asset_type, brand, model, status)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            asset,
        )
    conn.commit()
    print(f"   ✅ {len(COMPANY_ASSETS)} company assets")
    
    # Verify
    print("\n" + "=" * 50)
    print("🎉 SEED COMPLETE! Verifikasi:")
    tables = [
        "departments", "employees", "leave_balances", "leave_requests",
        "overtime_requests", "it_tickets", "wfh_requests", "reimbursements",
        "training_requests", "attendance", "company_assets",
    ]
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"   {table}: {count} rows")
    
    cur.close()
    conn.close()
    print("\n✅ Database siap dipakai di cloud!")
    print(f"\nSet DATABASE_URL di Vercel Environment Variables:")
    print(f"   {DATABASE_URL[:60]}...")


if __name__ == "__main__":
    main()
