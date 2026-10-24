"""Skema minimal yang wajib ada agar aplikasi dapat mulai di database PostgreSQL kosong."""

OPERATIONAL_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS departments (
        id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS employees (
        employee_id VARCHAR(20) PRIMARY KEY, full_name VARCHAR(100) NOT NULL,
        position VARCHAR(100), department_id INT REFERENCES departments(id),
        work_location VARCHAR(100) DEFAULT 'Jakarta HQ', employment_status VARCHAR(30) DEFAULT 'Active',
        join_date DATE, manager_id VARCHAR(20) REFERENCES employees(employee_id),
        email VARCHAR(100), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS leave_balances (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), year INT NOT NULL,
        annual_quota INT DEFAULT 12, used_leave INT DEFAULT 0, pending_leave INT DEFAULT 0,
        remaining_leave INT DEFAULT 12, UNIQUE(employee_id, year)
    )""",
    """CREATE TABLE IF NOT EXISTS leave_requests (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), start_date DATE,
        end_date DATE, total_days INT, leave_type VARCHAR(50), status VARCHAR(30) DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS overtime_requests (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), overtime_date DATE,
        start_time TIME, end_time TIME, duration_minutes INT, status VARCHAR(30) DEFAULT 'Pending',
        reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS it_tickets (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), category VARCHAR(50),
        priority VARCHAR(20) DEFAULT 'Medium', title VARCHAR(200), description TEXT,
        status VARCHAR(30) DEFAULT 'Open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS wfh_requests (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), wfh_date DATE,
        status VARCHAR(30) DEFAULT 'Pending', reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS reimbursements (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), category VARCHAR(50),
        amount DECIMAL(12,2), status VARCHAR(30) DEFAULT 'Pending', description TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS training_requests (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), training_name VARCHAR(200),
        provider VARCHAR(100), start_date DATE, cost DECIMAL(12,2), status VARCHAR(30) DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), attendance_date DATE,
        attendance_status VARCHAR(30) DEFAULT 'Present', check_in TIME, check_out TIME,
        late_minutes INT DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS company_assets (
        id SERIAL PRIMARY KEY, employee_id VARCHAR(20) REFERENCES employees(employee_id), asset_code VARCHAR(50),
        asset_type VARCHAR(50), brand VARCHAR(50), model VARCHAR(100), status VARCHAR(30) DEFAULT 'Active',
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS app_users (
        employee_id VARCHAR(64) PRIMARY KEY, display_name VARCHAR(128), role VARCHAR(32) DEFAULT 'employee',
        password_hash TEXT NOT NULL, password_salt TEXT NOT NULL, created_at BIGINT NOT NULL
    )""",
]
