# KORE AI - Internal AI Agent Workspace

KORE AI adalah prototype AI agent internal perusahaan yang membantu karyawan mengakses data operasional melalui chat. Sistem ini menggabungkan autentikasi karyawan, database lookup, RAG berbasis dokumen PDF, dan percakapan natural dalam satu workspace React.

Project ini cocok untuk portfolio, demo MVP, atau baseline pengembangan AI assistant internal perusahaan.

## Fitur Utama

- **Login karyawan** dengan ID karyawan dan password.
- **Password hashing** di backend memakai PBKDF2 + salt.
- **Session token** untuk mengamankan akses chat.
- **AI agent routing** untuk memilih sumber jawaban:
  - Database untuk data live karyawan.
  - RAG/PDF untuk kebijakan dan dokumen internal.
  - Conversation mode untuk sapaan, small talk, dan bantuan umum.
- **Konteks employee login**, sehingga pertanyaan seperti `sisa cuti saya berapa` memakai ID user yang sedang login.
- **RAG knowledge base** dari file PDF di `backend/data`.
- **Frontend chat workspace** dengan riwayat percakapan, copy/share/download session, dan UI KORE AI.

## Tech Stack

| Layer | Teknologi |
| --- | --- |
| Frontend | React, Vite, CSS |
| Backend | FastAPI, Python |
| Database | PostgreSQL via `psycopg` |
| RAG | PDF loader + lexical vector store |
| LLM | OpenAI-compatible client, Groq/OpenAI optional |
| Auth | Local backend auth, PBKDF2 password hashing, signed token |

## Struktur Project

```text
.
├── backend/
│   ├── api.py                    # FastAPI app, auth, routing, agent executor
│   ├── main.py                   # Local backend runner
│   ├── data/                     # PDF knowledge base
│   ├── src/
│   │   ├── database/             # Repository dan koneksi database
│   │   ├── rag/                  # Loader, chunking, retrieval, vector store
│   │   └── schemas.py            # Pydantic request/response schemas
│   └── tests/
├── frontend/
│   ├── src/App.jsx               # Main React UI
│   ├── src/backendClient.js      # API client
│   └── src/App.css               # Styling
└── README.md
```

## Cara Menjalankan

### 1. Backend

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
python main.py
```

Backend berjalan di:

```text
http://localhost:8000
```

### 2. Frontend

Buka terminal baru:

```bash
cd frontend
npm install
npm run dev
```

Frontend berjalan di:

```text
http://localhost:5173
```

## Menjalankan dengan Docker

Project menyediakan `Dockerfile` untuk backend dan frontend, serta `docker-compose.yml` untuk development.

```bash
docker compose up --build
```

Service yang berjalan:

| Service | URL |
| --- | --- |
| Backend | `http://localhost:8000` |
| Frontend | `http://localhost:5173` |

Catatan database:

- Compose ini tidak membuat database PostgreSQL baru.
- Jika PostgreSQL berjalan di host/laptop, `docker-compose.yml` sudah memakai default `host.docker.internal`.
- Jika konfigurasi database berbeda, override saat menjalankan compose:

```bash
DATABASE_URL=postgresql://user:password@host.docker.internal:55432/employee_agent docker compose up --build
```

- Jika backend dijalankan manual tanpa Docker, `localhost` tetap bisa dipakai sesuai setup lokal.

## Environment Variables

Buat file `backend/.env` dari contoh berikut:

```env
# LLM optional. Jika kosong, chat fallback tetap berjalan untuk beberapa intent.
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=openai/gpt-oss-120b
LLM_ROUTER_MODEL=

# Database PostgreSQL.
DATABASE_URL=postgresql://user:password@localhost:55432/employee_agent

# Optional. Jika kosong, backend membuat secret lokal di backend/.auth_secret.
AUTH_SECRET=
```

File sensitif seperti `.env`, `backend/auth_users.json`, dan `backend/.auth_secret` tidak boleh dicommit.

## Auth & Security

Implementasi auth saat ini dibuat untuk project pribadi/prototype:

- Password tidak disimpan di browser.
- Password di-hash di backend menggunakan PBKDF2 + salt.
- Frontend hanya menyimpan session token.
- Endpoint `/chat` membutuhkan `Authorization: Bearer <token>`.
- Backend mengambil `employee_id` dari token, bukan dari input bebas frontend.

Untuk production, disarankan menambahkan HTTPS, refresh token, rate limiting, audit log, role-based access control, dan database-backed user store.

## API Ringkas

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| `GET` | `/health` | Cek status backend dan knowledge base |
| `POST` | `/auth/register` | Daftar akun karyawan |
| `POST` | `/auth/login` | Login karyawan |
| `GET` | `/auth/session` | Validasi session token |
| `POST` | `/chat` | Chat utama AI agent |
| `GET` | `/debug/route` | Debug routing intent |

## Contoh Prompt Demo

### Database

```text
halo, saya mau cek cuti saya
```

```text
jabatan saya apa
```

### Follow-up Database

```text
sisa 8 ya
```

### RAG / Dokumen

```text
jelaskan syarat cuti
```

```text
kebijakan lembur gimana?
```

### Conversation

```text
ini jam berapa ya
```

```text
baik terimakasih
```

## Testing

Backend:

```bash
cd backend
../venv/bin/python -m pytest tests/test_api.py
```

Frontend build:

```bash
cd frontend
npm run build
```

## Status Project

Project ini sudah berada di level **AI agent prototype / internal data agent**. Agent dapat memilih jalur database, RAG, atau conversation berdasarkan intent user dan konteks login.

Masih perlu pengembangan lanjutan untuk menjadi production-ready:

- Role-based permission per jabatan.
- Deployment config yang lengkap.
- Observability dan audit log.
- Test coverage yang lebih luas.
- RAG dengan embeddings atau reranker model.
- User store production-ready.

## Catatan

Data dan dokumen di project ini digunakan untuk simulasi/demo. Jangan gunakan data pribadi atau data perusahaan nyata tanpa kontrol keamanan yang sesuai.
