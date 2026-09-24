# KORE AI

**Internal AI agent workspace untuk akses data operasional karyawan lewat chat.**

KORE AI menggabungkan autentikasi karyawan, pencarian data di database, tanya-jawab dokumen (RAG) berbasis PDF, dan percakapan natural dalam satu antarmuka. Agent memilih sendiri sumber jawaban yang paling sesuai untuk setiap pertanyaan, dan selalu menampilkan sumbernya.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)

> **Status:** prototype / MVP. Belum ditujukan untuk production. Lihat bagian [Roadmap](#roadmap).

---

## Daftar Isi

- [Fitur](#fitur)
- [Arsitektur](#arsitektur)
- [Tech Stack](#tech-stack)
- [Struktur Proyek](#struktur-proyek)
- [Memulai](#memulai)
- [Konfigurasi](#konfigurasi)
- [Menjalankan dengan Docker](#menjalankan-dengan-docker)
- [Referensi API](#referensi-api)
- [Contoh Penggunaan](#contoh-penggunaan)
- [Keamanan](#keamanan)
- [Pengujian](#pengujian)
- [Roadmap](#roadmap)
- [Catatan Data](#catatan-data)

---

## Fitur

**Autentikasi**
- Registrasi dan login dengan ID karyawan dan kata sandi.
- Kata sandi di-hash di backend (PBKDF2 + salt), tidak pernah disimpan di browser.
- Akses chat dilindungi session token bertanda tangan.

**AI agent**
- Routing intent otomatis ke tiga jalur jawaban:
  - **Database**: data langsung tentang karyawan, seperti cuti dan jabatan.
  - **RAG / PDF**: kebijakan dan dokumen internal.
  - **Conversation**: sapaan, obrolan ringan, dan bantuan umum.
- Sadar konteks login. Pertanyaan seperti "sisa cuti saya berapa" otomatis memakai ID karyawan yang sedang masuk.
- Mendukung pertanyaan lanjutan (follow-up) dalam satu percakapan.
- Setiap jawaban menyertakan sumber datanya.

**Antarmuka**
- Chat workspace dengan riwayat percakapan, pencarian sesi, dan ganti nama sesi.
- Salin, bagikan, dan unduh percakapan.
- Tema monokrom putih-hitam, responsif untuk desktop dan mobile.

## Arsitektur

```mermaid
flowchart LR
    U[Karyawan] --> F[Frontend<br/>React + Vite]
    F -->|Bearer token| B[Backend<br/>FastAPI]
    B --> R{Intent router}
    R -->|data karyawan| D[(PostgreSQL)]
    R -->|kebijakan & dokumen| G[RAG<br/>PDF knowledge base]
    R -->|obrolan umum| L[LLM]
    D --> A[Jawaban + sumber]
    G --> A
    L --> A
    A --> F
```

Backend mengambil `employee_id` dari token sesi, bukan dari input frontend. Karyawan hanya bisa mengakses data miliknya sendiri lewat jalur database.

## Tech Stack

| Layer | Teknologi |
| --- | --- |
| Frontend | React, Vite, CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL (`psycopg`) |
| RAG | PDF loader, chunking, lexical vector store |
| LLM | Klien kompatibel OpenAI (Groq atau OpenAI, opsional) |
| Auth | Autentikasi lokal, PBKDF2, token bertanda tangan |
| Infrastruktur | Docker, Docker Compose |

## Struktur Proyek

```
.
├── backend/
│   ├── api.py                # FastAPI app: auth, routing, agent executor
│   ├── main.py               # Entry point untuk menjalankan backend lokal
│   ├── data/                 # PDF knowledge base
│   ├── src/
│   │   ├── agents/           # Logika agent, prompt, dan state
│   │   ├── database/         # Koneksi dan repository
│   │   ├── rag/              # Loader, chunking, retrieval, vector store
│   │   ├── tools/            # Tool untuk cuti dan RAG
│   │   ├── config.py         # Konfigurasi aplikasi
│   │   └── schemas.py        # Skema request/response (Pydantic)
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Antarmuka utama
│   │   ├── App.css           # Styling
│   │   └── backendClient.js  # Klien API
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml
```

## Memulai

### Prasyarat

- Python 3.10 atau lebih baru
- Node.js 18 atau lebih baru
- PostgreSQL yang sudah berjalan dan bisa diakses
- (Opsional) API key LLM dari Groq atau OpenAI

### 1. Clone repositori

```bash
git clone https://github.com/Nikoardyan/kore-ai-agent.git
cd kore-ai-agent
```

### 2. Jalankan backend

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # lalu isi nilainya, lihat bagian Konfigurasi
python main.py
```

Backend berjalan di `http://localhost:8000`.

### 3. Jalankan frontend

Di terminal baru:

```bash
cd frontend
npm install
npm run dev
```

Frontend berjalan di `http://localhost:5173`.

### 4. Letakkan dokumen knowledge base

Taruh file PDF yang ingin dijadikan sumber jawaban di `backend/data/`.

## Konfigurasi

Salin `backend/.env.example` menjadi `backend/.env`, lalu isi nilainya.

| Variabel | Wajib | Keterangan |
| --- | --- | --- |
| `DATABASE_URL` | Ya | Connection string PostgreSQL, misalnya `postgresql://user:password@localhost:55432/employee_agent` |
| `LLM_API_KEY` | Tidak | API key LLM. Jika kosong, beberapa intent tetap dijawab lewat fallback |
| `LLM_BASE_URL` | Tidak | Endpoint LLM kompatibel OpenAI. Otomatis ke Groq jika key diawali `gsk_` |
| `LLM_MODEL` | Tidak | Model untuk menjawab. Default: `openai/gpt-oss-120b` |
| `LLM_ROUTER_MODEL` | Tidak | Model khusus untuk routing intent |
| `AUTH_SECRET` | Tidak | Secret penanda tangan token. Jika kosong, dibuat otomatis di `backend/.auth_secret` |

> File `.env`, `backend/auth_users.json`, dan `backend/.auth_secret` berisi data sensitif dan sudah masuk `.gitignore`. Jangan pernah di-commit.

## Menjalankan dengan Docker

```bash
docker compose up --build
```

| Service | URL |
| --- | --- |
| Backend | http://localhost:8000 |
| Frontend | http://localhost:5173 |

Beberapa catatan:

- Compose **tidak** membuat database PostgreSQL. Database harus sudah berjalan di host.
- Secara default backend di dalam container terhubung ke host lewat `host.docker.internal`.
- Untuk memakai konfigurasi database lain:

```bash
DATABASE_URL=postgresql://user:password@host.docker.internal:55432/employee_agent \
  docker compose up --build
```

## Referensi API

| Method | Endpoint | Auth | Fungsi |
| --- | --- | --- | --- |
| `GET` | `/health` | Tidak | Status backend dan knowledge base |
| `POST` | `/auth/register` | Tidak | Mendaftarkan akun karyawan |
| `POST` | `/auth/login` | Tidak | Login dan mendapatkan session token |
| `GET` | `/auth/session` | Ya | Memvalidasi session token |
| `POST` | `/chat` | Ya | Endpoint chat utama AI agent |
| `GET` | `/debug/route` | Tidak | Melihat hasil routing intent (untuk debugging) |

Endpoint yang butuh autentikasi memakai header:

```
Authorization: Bearer <token>
```

## Contoh Penggunaan

| Jalur | Contoh pertanyaan |
| --- | --- |
| Database | `halo, saya mau cek cuti saya` <br> `jabatan saya apa` |
| Follow-up | `sisa 8 ya` |
| Dokumen (RAG) | `jelaskan syarat cuti` <br> `kebijakan lembur gimana?` |
| Percakapan | `ini jam berapa ya` <br> `baik terimakasih` |

## Keamanan

Implementasi saat ini dibuat untuk prototype:

- Kata sandi di-hash dengan PBKDF2 + salt dan tidak disimpan di browser.
- Frontend hanya menyimpan session token.
- `/chat` mewajibkan token, dan backend menentukan `employee_id` dari token.
- File rahasia dan data login lokal dikecualikan dari git.

Untuk penggunaan production, tambahkan:

- HTTPS dan refresh token
- Rate limiting
- Audit log
- Role-based access control
- User store berbasis database

## Pengujian

Backend:

```bash
cd backend
../venv/bin/python -m pytest tests/test_api.py
```

Frontend (memastikan build berhasil):

```bash
cd frontend
npm run build
```

## Roadmap

- [ ] Role-based permission per jabatan
- [ ] Konfigurasi deployment yang lengkap
- [ ] Observability dan audit log
- [ ] Cakupan test yang lebih luas
- [ ] RAG dengan embeddings atau reranker
- [ ] User store untuk production
- [ ] Login OAuth (Google dan GitHub)

## Catatan Data

Data dan dokumen di proyek ini hanya untuk simulasi dan demo. Jangan memakai data pribadi atau data perusahaan sungguhan tanpa kontrol keamanan yang sesuai.
