"""
api.py - KORE AI backend (FastAPI)

3 jalur jawaban:
  1. database -> data live (saldo cuti, profil pegawai, tiket) dari PostgreSQL
  2. rag      -> jawaban dari dokumen PDF (knowledge base)
  3. chat     -> ngobrol santai kayak teman (LLM, fallback ke jawaban template)

Env yang dipakai (taruh di .env):
  LLM_API_KEY       = kunci API Groq (atau GROQ_API_KEY / OPENAI_API_KEY; kosong = fallback template)
  LLM_BASE_URL      = opsional; otomatis ke Groq kalau key diawali gsk_
  LLM_MODEL         = model utama untuk jawaban chat
  LLM_ROUTER_MODEL  = opsional, model kecil buat klasifikasi jalur (hemat kuota)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.schemas import AuthLoginRequest, AuthRegisterRequest, AuthResponse, ChatRequest, ChatResponse
from src.database.connection import initialize_database
from src.database.repository import UserRepository
from src.rag.pipeline import get_rag_pipeline, run_rag_pipeline

try:
    from dotenv import load_dotenv

    # override=True: .env jadi sumber utama, gak ketiban env var lama di shell/venv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kore.api")

# ---------------------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------------------

DB_SOURCE = "SQLite" if os.getenv("DATABASE_URL", "").startswith("sqlite") else "PostgreSQL"
CHAT_SOURCE = "Conversation"
BACKEND_DIR = Path(__file__).resolve().parent
AUTH_USERS_FILE = BACKEND_DIR / "auth_users.json"
AUTH_SECRET_FILE = BACKEND_DIR / ".auth_secret"
AUTH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
PASSWORD_HASH_ITERATIONS = 210_000

RAG_TERMS = {
    "cuti", "wfh", "gaji", "lembur", "training", "dokumen", "pdf", "arunika",
    "pegawai", "karyawan", "insiden", "sla", "kebijakan", "saldo", "prioritas",
    "confidential", "restricted", "aturan", "prosedur", "ketentuan",
}

DB_TERMS = ["database", "db", "sql", "postgres", "postgresql", "data live"]
LEAVE_BALANCE_TERMS = ["sisa cuti", "saldo cuti", "cuti tersedia", "jatah cuti", "kuota cuti"]
# pertanyaan soal aturan/kebijakan -> jalur RAG (PDF), bukan database
POLICY_TERMS = [
    "aturan", "kebijakan", "prosedur", "dokumen", "pdf", "syarat", "ketentuan",
    "policy", "sla", "maksimal", "maksimum", "batas", "minimal", "minimum", "boleh",
]
# kata yang menandakan user minta data, bukan sekadar ngobrol
DATA_INTENT_TERMS = [
    "riwayat", "daftar", "tampilkan", "tunjukkan", "lihat", "liat", "list", "history",
    "rekap", "total", "status", "pengajuan", "berapa",
]
SELF_REFERENCE_TERMS = [
    "saya", "aku", "gua", "gue", "gw", "ku", "punya saya", "punya aku", "punya gua",
    "punya gue", "milik saya", "milik aku", "milik gua", "milik gue",
]
# minta daftar SEMUA karyawan (bukan satu orang spesifik) -> topik "employee_list"
EMPLOYEE_LIST_TERMS = [
    "data pegawai", "data karyawan", "profil pegawai", "profil karyawan",
    "nama pegawai", "nama karyawan", "daftar pegawai", "daftar karyawan",
    "semua pegawai", "semua karyawan", "list pegawai", "list karyawan",
    "siapa saja", "ada siapa",
]
TOPIC_KEYWORDS = {
    "overtime": ["lembur", "overtime"],
    "leave": ["cuti"],
    "ticket": ["tiket", "ticket", "helpdesk"],
    "wfh": ["wfh"],
    "reimbursement": ["reimburse", "reimbursement", "reimbursment"],
    "training": ["training", "pelatihan"],
    "attendance": ["absen", "absensi", "kehadiran", "attendance", "terlambat", "telat"],
    "asset": ["aset", "asset", "inventaris"],
    "employee": [
        "employee", "jabatan", "posisi", "divisi", "departemen", "bagian", "lokasi",
        "kantor", "kerja dimana", "atasan", "manager", "bergabung", "join",
    ],
}
TOPIC_ORDER = ["overtime", "leave", "ticket", "wfh", "reimbursement", "training",
               "attendance", "asset", "employee"]

ASK_NAME_PHRASES = [
    "nama saya siapa", "nama aku siapa", "namaku siapa",
    "nama gue siapa", "nama gua siapa",
]
NAME_PATTERNS = [
    r"\b(?:nama saya|nama aku|nama gue|nama gua|namaku|panggil saya|panggil aku|panggil gue|panggil gua)\s+(?:adalah\s+)?([A-Za-z]{2,20}(?:\s[A-Za-z]{2,20}){0,2})",
    r"\b(?:my name is|call me)\s+([A-Za-z]{2,20}(?:\s[A-Za-z]{2,20}){0,2})",
]
NAME_STOPWORDS = r"\b(?:dan|ya|nih|dong|tolong|inget|ingat|yang|mau|lagi|di|dari|karena|kok|sih)\b"

ROUTER_PROMPT = """Klasifikasikan pesan user ke SATU label:
- database: minta data live/spesifik orang (saldo cuti, riwayat lembur, absensi, tiket IT, reimburse, WFH, training, aset, profil pegawai), biasanya menyebut nama atau employee ID
- rag: tanya isi dokumen/kebijakan/prosedur/aturan perusahaan
- chat: ngobrol santai, curhat, sapaan, minta saran umum, pertanyaan umum di luar dokumen/data perusahaan

Percakapan sebelumnya:
{context}

Pesan user: {message}

Jawab hanya satu kata: database, rag, atau chat."""

CHAT_SYSTEM = (
    "Kamu Kore AI, AI assistant yang ngobrol santai kayak teman kerja. "
    "Pakai bahasa Indonesia santai, ikutin gaya bicara user, jawab singkat dan natural. "
    "Sistem ini punya 2 kemampuan lain yang ditangani terpisah: jawab dari dokumen PDF "
    "dan cek data dari database. Jangan pernah mengarang data internal perusahaan "
    "(cuti, gaji, pegawai, tiket, kebijakan). Kalau user nanya hal itu dan kamu gak punya "
    "datanya, bilang kamu bisa cek lewat dokumen/database dan minta detail "
    "(nama atau employee ID, dan mau data apa)."
)


# ---------------------------------------------------------------------------
# Lifespan & app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Server starting up...")
    initialize_database()
    pipeline = get_rag_pipeline()
    print(f"Knowledge base loaded: {pipeline.chunk_count} chunks from {pipeline.loaded_files}")
    yield
    print("Server shutting down...")


app = FastAPI(title="AI Agentic 1", version="v1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth lokal sederhana
# ---------------------------------------------------------------------------

def _employee_key(employee_id: str) -> str:
    return employee_id.strip().lower()


def _load_auth_users() -> dict:
    if not AUTH_USERS_FILE.exists():
        return {}
    try:
        return json.loads(AUTH_USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.exception("Gagal membaca auth_users.json")
        return {}


def _save_auth_users(users: dict):
    AUTH_USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


def _get_auth_secret() -> bytes:
    env_secret = os.getenv("AUTH_SECRET", "").strip()
    if env_secret:
        return env_secret.encode("utf-8")
    if AUTH_SECRET_FILE.exists():
        return AUTH_SECRET_FILE.read_bytes()
    secret = secrets.token_urlsafe(48).encode("utf-8")
    AUTH_SECRET_FILE.write_bytes(secret)
    return secret


def _hash_password(password: str, salt_b64: str | None = None):
    salt = base64.urlsafe_b64decode(salt_b64.encode("utf-8")) if salt_b64 else secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return {
        "salt": base64.urlsafe_b64encode(salt).decode("utf-8"),
        "hash": base64.urlsafe_b64encode(password_hash).decode("utf-8"),
        "iterations": PASSWORD_HASH_ITERATIONS,
    }


def _verify_password(password: str, user: dict) -> bool:
    stored = user.get("password") or {}
    salt = stored.get("salt")
    expected_hash = stored.get("hash")
    if not salt or not expected_hash:
        return False
    candidate = _hash_password(password, salt)["hash"]
    return hmac.compare_digest(candidate, expected_hash)


def _b64url_json(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_b64url_json(data: str) -> dict:
    padded = data + "=" * (-len(data) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))


def _make_auth_token(employee_id: str) -> str:
    payload = {
        "sub": employee_id,
        "exp": int(time.time()) + AUTH_TOKEN_TTL_SECONDS,
    }
    payload_part = _b64url_json(payload)
    signature = hmac.new(_get_auth_secret(), payload_part.encode("utf-8"), hashlib.sha256).digest()
    signature_part = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{payload_part}.{signature_part}"


def _read_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Session token tidak ada.")
    return authorization.split(" ", 1)[1].strip()


def _get_user_from_token(token: str) -> dict:
    try:
        payload_part, signature_part = token.split(".", 1)
        expected = hmac.new(_get_auth_secret(), payload_part.encode("utf-8"), hashlib.sha256).digest()
        padded_signature = signature_part + "=" * (-len(signature_part) % 4)
        signature = base64.urlsafe_b64decode(padded_signature.encode("utf-8"))
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = _decode_b64url_json(payload_part)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Session token tidak valid.") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Session token sudah kedaluwarsa.")

    user = _load_auth_users().get(_employee_key(payload.get("sub", "")))
    if not user:
        raise HTTPException(status_code=401, detail="Akun tidak ditemukan.")
    return user


def _auth_response(user: dict) -> AuthResponse:
    token = _make_auth_token(user["employee_id"])
    return AuthResponse(
        token=token,
        user={"employee_id": user["employee_id"], "display_name": user.get("display_name") or None},
    )


def _validate_auth_input(employee_id: str, password: str):
    if not employee_id.strip():
        raise HTTPException(status_code=400, detail="ID karyawan wajib diisi.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Kata sandi minimal 6 karakter.")


# ---------------------------------------------------------------------------
# Helper umum
# ---------------------------------------------------------------------------

def _has_any(text: str, terms) -> bool:
    """Cocokkan kata/frasa dengan batas kata (jadi 'cara' gak nyangkut di 'acara')."""
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _recent_context_text(recent_messages, limit: int = 6) -> str:
    items = []
    for item in (recent_messages or [])[-limit:]:
        content = (item.content or "").strip()
        if content:
            role = "User" if item.role == "user" else "AI"
            items.append(f"{role}: {content}")
    return "\n".join(items)


def _history_for_llm(recent_messages, limit: int = 6):
    items = []
    for item in (recent_messages or [])[-limit:]:
        content = (item.content or "").strip()
        if content:
            items.append({
                "role": "user" if item.role == "user" else "assistant",
                "content": content,
            })
    return items


# ---------------------------------------------------------------------------
# LLM (OpenAI-compatible). Kalau LLM_API_KEY kosong -> return None (pakai fallback)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_llm_client():
    api_key = (
        os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    )
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL") or None
    if not base_url and api_key.startswith("gsk_"):  # key Groq
        base_url = "https://api.groq.com/openai/v1"
    try:
        from openai import OpenAI

        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        logger.exception("Gagal membuat LLM client")
        return None


def llm_complete(
    system: str,
    messages: list,
    max_tokens: int = 400,
    temperature: float = 0.7,
    model: str | None = None,
    reasoning_effort: str | None = "low",
):
    """reasoning_effort: model gpt-oss di Groq "mikir" dulu sebelum jawab, dan proses
    mikir itu ikut makan max_tokens. "low" bikin dia dikit mikirnya, jadi token lebih
    banyak nyisa buat jawaban beneran. Set None kalau ganti ke model non-reasoning."""
    client = _get_llm_client()
    if client is None:
        return None
    try:
        kwargs = dict(
            model=model or os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            # max_completion_tokens (bukan max_tokens): buat model reasoning kayak
            # gpt-oss, token buat "mikir" ikut kepotong dari sini juga.
            max_completion_tokens=max_tokens,
        )
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        response = client.chat.completions.create(**kwargs)
        content = (response.choices[0].message.content or "").strip()
        if not content:
            finish = response.choices[0].finish_reason
            logger.warning("LLM balas kosong (finish_reason=%s, max_tokens=%s)", finish, max_tokens)
        return content or None
    except Exception:
        logger.exception("Panggilan LLM gagal")
        return None


# ---------------------------------------------------------------------------
# Memori nama user
# ---------------------------------------------------------------------------

def extract_name(message: str):
    text = message.strip()
    lower = text.lower()
    if "?" in text or len(text.split()) > 8:
        return None
    if any(phrase in lower for phrase in ASK_NAME_PHRASES):
        return None

    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        name = re.split(
            r"[,.!?]|" + NAME_STOPWORDS, match.group(1), maxsplit=1, flags=re.IGNORECASE
        )[0].strip()
        if name:
            return " ".join(part.capitalize() for part in name.split())
    return None


def get_name_memory_reply(message: str, user_name: str | None):
    lower = message.lower()
    if any(phrase in lower for phrase in ASK_NAME_PHRASES):
        if user_name:
            return {"reply": f"Nama kamu {user_name}. Aku masih ingat.", "source": "Conversation memory"}
        return {
            "reply": "Aku belum tahu nama kamu. Bilang aja misalnya: nama saya Celine.",
            "source": "Conversation memory",
        }

    detected = extract_name(message)
    if detected:
        return {"reply": f"Siap, aku ingat. Nama kamu {detected}.", "source": "Conversation memory"}
    return None


# ---------------------------------------------------------------------------
# Jalur DATABASE
# ---------------------------------------------------------------------------

_index_cache = {"at": 0.0, "ttl": 60, "ids": set(), "names": []}


def get_employee_index(repository):
    """Daftar employee_id + nama dari database (di-cache, supaya gak query tiap pesan)."""
    now = time.time()
    if now - _index_cache["at"] < _index_cache["ttl"]:
        return _index_cache

    ids, names, ttl = set(), [], 10  # kalau gagal, coba lagi 10 detik lagi
    fetch = getattr(repository, "list_employee_index", None) if repository else None
    if callable(fetch):
        try:
            rows = fetch()
            ids = {str(r["employee_id"]).upper() for r in rows}
            full_names = [r["full_name"] for r in rows if r.get("full_name")]
            candidates = set(full_names)
            for full_name in full_names:  # "Budi Santoso" -> juga dikenali lewat "Budi"
                first = full_name.split()[0]
                if len(first) >= 4:
                    candidates.add(first)
            names = sorted(candidates, key=len, reverse=True)  # nama panjang dicek dulu
            ttl = 60
        except Exception:
            logger.exception("list_employee_index gagal")

    _index_cache.update(at=now, ttl=ttl, ids=ids, names=names)
    return _index_cache


def find_identifier(message: str, repository) -> str:
    index = get_employee_index(repository)
    for token in re.findall(r"[A-Za-z0-9_\-]+", message):
        if token.upper() in index["ids"]:
            return token.upper()

    text = message.lower()
    for candidate in index["names"]:
        if re.search(rf"\b{re.escape(candidate.lower())}\b", text):
            return candidate
    return ""


def _normalize_employee_id(employee_id: str | None, repository) -> str:
    if not employee_id:
        return ""
    normalized = employee_id.strip().upper()
    if not normalized:
        return ""
    try:
        if normalized in get_employee_index(repository)["ids"]:
            return normalized
    except Exception:
        logger.exception("Validasi employee_id login gagal")
    return normalized


def _mentions_self(text: str) -> bool:
    return _has_any(text, SELF_REFERENCE_TERMS) or bool(re.search(r"\b[a-z]+ku\b", text))


def _can_use_login_employee(text: str) -> bool:
    if _mentions_self(text) or _has_any(text, LEAVE_BALANCE_TERMS):
        return True
    personal_topics = ["overtime", "leave", "wfh", "reimbursement", "training", "attendance", "asset"]
    return any(_has_any(text, TOPIC_KEYWORDS[topic]) for topic in personal_topics) or _has_any(
        text, TOPIC_KEYWORDS["employee"]
    )


_ID_LOOKUP_CUES = ["ada", "siapa", "apa", "gimana", "bagaimana", "berapa", "dimana", "di mana", "kapan"]


def detect_db_topic(text: str, identifier: str):
    """Sinyal untuk jalur database. Return nama topik atau None."""
    if _has_any(text, POLICY_TERMS):
        return None  # tanya aturan/kebijakan -> RAG

    wants_db = _has_any(text, DB_TERMS)
    data_intent = wants_db or bool(identifier) or _has_any(text, DATA_INTENT_TERMS)

    if _has_any(text, LEAVE_BALANCE_TERMS):
        return "leave"

    # kata "karyawan"/"pegawai" polos (gak harus persis "daftar karyawan" dll) sudah cukup
    # jadi sinyal soal data pegawai -> nama spesifik = profil, tanpa nama = daftar
    if re.search(r"\b(karyawan|pegawai)\b", text) or _has_any(text, EMPLOYEE_LIST_TERMS):
        return "employee" if identifier else "employee_list"

    for topic in TOPIC_ORDER:
        if not _has_any(text, TOPIC_KEYWORDS[topic]):
            continue
        if topic == "employee":
            if identifier:
                return "employee"
        elif data_intent:
            return topic

    if wants_db and identifier:
        return "employee"

    # nyebut nama/ID pegawai yang valid di kalimat pendek/pertanyaan -> anggap nanya orangnya
    if identifier and (len(text.split()) <= 6 or _has_any(text, _ID_LOOKUP_CUES) or "?" in text):
        return "employee"

    return None


_FILTER_STOPWORDS = r"\b(saja|aja|doang|dong|ya|nih|deh|kok|sih)\b\s*$"


def _extract_position_filter(text: str):
    """Tangkep frasa filter posisi/divisi dari kalimat, misal 'yang ai engineer' -> 'ai engineer'."""
    candidate = None
    match = re.search(r"\byang\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        candidate = match.group(1)
    else:
        match = re.search(
            r"\b(?:posisi|jabatan|divisi|departemen|bagian)\s+([a-z0-9 ]{2,40})",
            text, flags=re.IGNORECASE,
        )
        if match:
            candidate = match.group(1)
    if not candidate:
        return None
    candidate = re.sub(
        r"^(posisi|jabatan|divisi|departemen|bagian)\s+", "", candidate.strip(), flags=re.IGNORECASE
    )
    candidate = re.sub(_FILTER_STOPWORDS, "", candidate, flags=re.IGNORECASE).strip(" ?.!,")
    return candidate or None


def _d(value) -> str:
    return str(value) if value else "-"


def _t(value) -> str:
    return str(value)[:5] if value else "-"


def _rp(value) -> str:
    try:
        return "Rp" + f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return f"Rp{value}"


def _example_id(repository) -> str:
    ids = sorted(get_employee_index(repository)["ids"])
    return ids[0] if ids else "EMP-001"


def _ask_identifier(topic: str, repository):
    label = {
        "leave": "sisa cuti", "overtime": "riwayat lembur", "wfh": "riwayat WFH",
        "reimbursement": "riwayat reimburse", "training": "riwayat training",
        "attendance": "absensi", "asset": "aset", "employee": "profil pegawai",
    }.get(topic, "data")
    return {
        "reply": (
            "Bisa aku ambil dari database, tapi sebutkan employee ID atau nama lengkap "
            f"karyawannya dulu. Contoh: {label} {_example_id(repository)}."
        ),
        "source": DB_SOURCE,
    }


def _ask_disambiguation(matches):
    lines = [f"- {m['employee_id']}: {m['full_name']} ({m.get('department') or '-'})" for m in matches]
    return {
        "reply": "Ada beberapa karyawan yang cocok:\n" + "\n".join(lines)
        + "\nSebutkan employee ID atau nama lengkapnya ya.",
        "source": DB_SOURCE,
    }


def _format_employee_answer(emp, text: str) -> str:
    who = f"{emp['full_name']} ({emp['employee_id']})"
    if _has_any(text, ["jabatan", "posisi"]):
        return f"Jabatan {who} adalah {emp['position']} di departemen {emp.get('department') or '-'}."
    if _has_any(text, ["divisi", "departemen", "bagian"]):
        return f"{who} berada di departemen {emp.get('department') or '-'}."
    if _has_any(text, ["lokasi", "kantor", "kerja dimana"]):
        return f"Lokasi kerja {who} adalah {emp['work_location']}."
    if _has_any(text, ["atasan", "manager"]):
        return f"Atasan {who} adalah {emp.get('manager_name') or 'belum tercatat'}."
    if _has_any(text, ["bergabung", "join"]):
        return f"{who} bergabung pada {_d(emp['join_date'])}."
    return (
        "Data pegawai dari database:\n"
        f"- ID: {emp['employee_id']}\n"
        f"- Nama: {emp['full_name']}\n"
        f"- Jabatan: {emp['position']}\n"
        f"- Departemen: {emp.get('department') or '-'}\n"
        f"- Atasan: {emp.get('manager_name') or '-'}\n"
        f"- Lokasi kerja: {emp['work_location']}\n"
        f"- Status: {emp['employment_status']}\n"
        f"- Bergabung: {_d(emp['join_date'])}"
    )


def _extract_first_number(text: str):
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


def _is_leave_balance_confirmation(text: str) -> bool:
    compact = re.sub(r"[^a-z0-9\s]", "", text).strip()
    if _has_any(compact, ["riwayat", "pengajuan", "daftar", "history", "aturan", "kebijakan"]):
        return False
    return (
        _has_any(compact, ["berarti", "berati", "jadi", "sisa", "saldo", "iya", "ya", "bener", "benar"])
        and _extract_first_number(compact) is not None
    )


def get_database_reply(topic, identifier: str, message: str, repository):
    text = message.lower()

    if topic is None:
        return {
            "reply": (
                "Kayaknya ini soal data live. Sebutkan mau data apa (cuti, lembur, absensi, tiket IT, "
                "reimburse, WFH, training, aset, daftar karyawan, atau profil pegawai) dan employee ID / "
                "nama karyawannya kalau nanya orang tertentu."
            ),
            "source": DB_SOURCE,
        }
    if repository is None:
        return {"reply": "Koneksi ke database lagi bermasalah. Cek log backend.", "source": DB_SOURCE}

    def answer(reply: str, table: str):
        return {"reply": reply, "source": f"{DB_SOURCE}: {table}"}

    if topic == "employee_list":
        filter_text = _extract_position_filter(text)
        try:
            total = repository.count_employees(filter_text)
            rows = repository.list_employees(limit=20, filter_text=filter_text)
        except Exception as exc:
            logger.exception("Query daftar karyawan gagal")
            return {
                "reply": f"Query ke database gagal ({type(exc).__name__}). Cek log backend buat detailnya.",
                "source": DB_SOURCE,
            }
        label = f" dengan posisi/divisi mengandung '{filter_text}'" if filter_text else ""
        if filter_text and not rows:
            return answer(
                f"Gak ada karyawan yang posisi/divisinya cocok dengan '{filter_text}'. "
                "Coba cek ejaannya atau sebutkan nama divisi/posisi yang lebih umum.",
                "employees",
            )
        lines = [f"Ada {total} karyawan{label} di database. {len(rows)} nama pertama (urut abjad):"]
        lines += [
            f"- {r['employee_id']}: {r['full_name']}"
            + (f" ({r['department']})" if r.get("department") else "")
            + (f" - {r['position']}" if r.get("position") else "")
            for r in rows
        ]
        if total > len(rows):
            lines.append("Sebutkan nama atau employee ID buat lihat detail lengkapnya.")
        return answer("\n".join(lines), "employees")

    try:
        employee = None
        if identifier or topic != "ticket":  # tiket boleh tanpa nama (tampil tiket terbaru)
            if not identifier:
                return _ask_identifier(topic, repository)
            matches = repository.find_employees(identifier, limit=5)
            if not matches:
                return {
                    "reply": f"Aku belum menemukan karyawan '{identifier}' di database.",
                    "source": DB_SOURCE,
                }
            if len(matches) > 1:
                return _ask_disambiguation(matches)
            employee = matches[0]

        emp_id = employee["employee_id"] if employee else None
        who = f"{employee['full_name']} ({emp_id})" if employee else ""

        if topic == "employee":
            return answer(_format_employee_answer(employee, text), "employees")

        if topic == "leave":
            balance = repository.get_leave_balance(emp_id)
            if balance and _is_leave_balance_confirmation(text):
                remaining = int(balance["remaining_leave"])
                asked_number = _extract_first_number(text)
                if asked_number == remaining:
                    return answer(
                        f"Iya, benar. Berdasarkan database, sisa cuti kamu {remaining} hari.",
                        "leave_balances",
                    )
                return answer(
                    f"Di database yang tercatat sisa cuti kamu {remaining} hari, bukan {asked_number} hari.",
                    "leave_balances",
                )

            lines = [f"Data cuti dari database untuk {who}:"]
            if balance:
                lines += [
                    f"- Tahun: {balance['year']}",
                    f"- Kuota cuti: {balance['annual_quota']} hari",
                    f"- Cuti terpakai: {balance['used_leave']} hari",
                    f"- Menunggu persetujuan: {balance['pending_leave']} hari",
                    f"- Saldo tersedia: {balance['remaining_leave']} hari",
                ]
            else:
                lines.append("- Saldo cuti belum tercatat.")
            if _has_any(text, ["riwayat", "pengajuan", "daftar", "history"]):
                requests_ = repository.list_leave_requests(emp_id, limit=5)
                if requests_:
                    lines.append("Pengajuan terbaru:")
                    lines += [
                        f"- {_d(r['start_date'])} s/d {_d(r['end_date'])} "
                        f"({r['total_days']} hari) {r['leave_type']} [{r['status']}]"
                        for r in requests_
                    ]
            return answer("\n".join(lines), "leave_balances")

        if topic == "overtime":
            rows = repository.list_overtime(emp_id, limit=5)
            if not rows:
                return answer(f"Belum ada pengajuan lembur untuk {who} di database.", "overtime_requests")
            summary = repository.overtime_summary(emp_id)
            hours = round(float(summary["approved_minutes"]) / 60, 1)
            lines = [
                f"Riwayat lembur {who} dari database "
                f"(total {summary['total']} pengajuan, {hours} jam disetujui). 5 terbaru:"
            ]
            lines += [
                f"- {_d(r['overtime_date'])} {_t(r['start_time'])}-{_t(r['end_time'])} "
                f"({r['duration_minutes']} menit) [{r['status']}] {r['reason'] or ''}".rstrip()
                for r in rows
            ]
            return answer("\n".join(lines), "overtime_requests")

        if topic == "ticket":
            rows = repository.list_tickets(emp_id, limit=5)
            if not rows:
                return answer("Aku belum menemukan tiket yang cocok di database.", "it_tickets")
            title = f"Tiket IT {who}" if who else "Tiket IT terbaru"
            lines = [f"{title} dari database:"]
            lines += [
                f"- #{r['id']} [{r['priority']}/{r['status']}] {r['title']} ({r['category']})"
                + ("" if who else f" - {r['full_name']}")
                for r in rows
            ]
            return answer("\n".join(lines), "it_tickets")

        if topic == "wfh":
            rows = repository.list_wfh(emp_id, limit=5)
            if not rows:
                return answer(f"Belum ada pengajuan WFH untuk {who}.", "wfh_requests")
            lines = [f"Pengajuan WFH {who} dari database (5 terbaru):"]
            lines += [f"- {_d(r['wfh_date'])} [{r['status']}] {r['reason'] or ''}".rstrip() for r in rows]
            return answer("\n".join(lines), "wfh_requests")

        if topic == "reimbursement":
            rows = repository.list_reimbursements(emp_id, limit=5)
            if not rows:
                return answer(f"Belum ada reimbursement untuk {who}.", "reimbursements")
            lines = [f"Reimbursement {who} dari database (5 terbaru):"]
            lines += [
                f"- {_d(r['submitted_at'])[:10]} {r['category']} {_rp(r['amount'])} [{r['status']}] "
                f"{r['description'] or ''}".rstrip()
                for r in rows
            ]
            return answer("\n".join(lines), "reimbursements")

        if topic == "training":
            rows = repository.list_training(emp_id, limit=5)
            if not rows:
                return answer(f"Belum ada pengajuan training untuk {who}.", "training_requests")
            lines = [f"Pengajuan training {who} dari database:"]
            lines += [
                f"- {r['training_name']} ({r['provider']}) mulai {_d(r['start_date'])}, "
                f"biaya {_rp(r['cost'])} [{r['status']}]"
                for r in rows
            ]
            return answer("\n".join(lines), "training_requests")

        if topic == "attendance":
            rows = repository.attendance_summary(emp_id, last_n=30)
            if not rows:
                return answer(f"Belum ada data absensi untuk {who}.", "attendance")
            total = sum(r["jumlah"] for r in rows)
            late = sum(int(r["telat_menit"]) for r in rows)
            lines = [f"Absensi {who} ({total} hari tercatat terakhir):"]
            lines += [f"- {r['attendance_status']}: {r['jumlah']} hari" for r in rows]
            lines.append(f"Total keterlambatan: {late} menit")
            return answer("\n".join(lines), "attendance")

        if topic == "asset":
            rows = repository.list_assets(emp_id, limit=10)
            if not rows:
                return answer(f"Belum ada aset perusahaan atas nama {who}.", "company_assets")
            lines = [f"Aset perusahaan {who} dari database:"]
            lines += [
                f"- {r['asset_code']}: {r['asset_type']} {r['brand'] or ''} {r['model'] or ''} [{r['status']}]"
                for r in rows
            ]
            return answer("\n".join(lines), "company_assets")
    except Exception as exc:
        logger.exception("Query database gagal")
        return {
            "reply": f"Query ke database gagal ({type(exc).__name__}). Cek log backend buat detailnya.",
            "source": DB_SOURCE,
        }

    return {
        "reply": "Data itu belum bisa aku ambil dari database. Coba sebutkan lebih spesifik.",
        "source": DB_SOURCE,
    }


# ---------------------------------------------------------------------------
# Jalur CHAT
# ---------------------------------------------------------------------------

_GREETINGS = {"halo", "hai", "hi", "hello", "pagi", "siang", "malam", "permisi", "oy", "oi"}
_TEST_WORDS = {"test", "tes", "coba", "testing", "ping"}
_THANKS_TERMS = ["makasih", "terima kasih", "terimakasih", "thanks", "thank you", "thx"]
_TIME_TERMS = ["jam berapa", "pukul berapa", "waktu sekarang", "sekarang jam", "sekarang pukul"]
_CLOSING_TERMS = [*_THANKS_TERMS, "baik", "oke", "okee", "okei", "ok", "siap", "sip", "yaudah", "ya sudah"]
_SMALLTALK_PHRASES = [
    "apa kabar", "gimana kabar", "lagi apa", "lagi ngapain", "siapa kamu", "kamu siapa",
    "lu siapa", "bisa apa", "bantu apa", "fitur kamu", "kamu bisa ngapain", "lu bisa apa",
    "curhat", "temenin", "gabut", "bosen", "bosan", *_THANKS_TERMS, *_TIME_TERMS,
    "wkwk", "haha", "hehe", "lol",
    "capek", "lelah", "pusing", "stress", "stres", "sedih", "panik", "bingung",
    "error", "bug", "ga bisa", "gak bisa", "nggak bisa", "tidak bisa",
]


def _is_smalltalk(text: str) -> bool:
    compact = re.sub(r"[^a-z0-9\s]", "", text).strip()
    return compact in _GREETINGS or compact in _TEST_WORDS or _has_any(text, _SMALLTALK_PHRASES)


def _time_context():
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    hour = now.hour
    if 4 <= hour < 11:
        greeting = "pagi"
    elif 11 <= hour < 15:
        greeting = "siang"
    elif 15 <= hour < 18:
        greeting = "sore"
    else:
        greeting = "malam"
    return {"greeting": greeting, "clock": now.strftime("%H.%M"), "zone": "WIB"}


def _is_closing_smalltalk(text: str) -> bool:
    compact = re.sub(r"[^a-z0-9\s]", "", text).strip()
    if _extract_first_number(compact) is not None or _has_any(compact, ["sisa", "saldo", "berapa"]):
        return False
    return _has_any(compact, _CLOSING_TERMS)


def rule_based_chat(message: str, user_name: str | None = None):
    """Fallback kalau LLM belum dikonfigurasi."""
    text = message.lower().strip()
    compact = re.sub(r"[^a-z0-9\s]", "", text)
    name = f", {user_name}" if user_name else ""

    def reply(text_reply):
        return {"reply": text_reply, "source": "Casual conversation"}

    if compact in _GREETINGS:
        current = _time_context()
        return reply(
            f"Selamat {current['greeting']}{name}. Sekarang pukul {current['clock']} {current['zone']}. "
            "Mau cek data, tanya dokumen, atau ngobrol santai?"
        )
    if _has_any(text, _TIME_TERMS):
        current = _time_context()
        return reply(f"Sekarang pukul {current['clock']} {current['zone']}.")
    if _is_closing_smalltalk(text):
        return reply(f"Sama-sama{name}. Santai, kalau ada yang mau dicek lagi tinggal bilang.")
    if _has_any(text, ["apa kabar", "gimana kabar", "lagi apa", "lagi ngapain"]):
        return reply("Aku baik dan siap diajak ngobrol. Mau santai dulu atau langsung bahas dokumen/data?")
    if _has_any(text, ["siapa kamu", "kamu siapa", "lu siapa"]):
        return reply(f"Aku Koreai{name}, AI assistant di app ini. Bisa ngobrol, jawab dari PDF, dan cek data dari database.")
    if _has_any(text, ["bisa apa", "bantu apa", "fitur kamu", "kamu bisa ngapain", "lu bisa apa"]):
        return reply("Aku punya 3 mode: ngobrol santai, jawab dari dokumen PDF (RAG), dan cek data live dari database (cuti, pegawai, tiket).")
    if _has_any(text, ["curhat", "temenin", "gabut", "bosen", "bosan"]):
        return reply("Bisa banget. Cerita aja pelan-pelan, aku dengerin.")
    if _has_any(text, _THANKS_TERMS):
        return reply(f"Sama-sama{name}. Santai aja.")
    if compact in _TEST_WORDS:
        return reply("Masuk. Aku online dan bisa balas.")
    if _has_any(text, ["error", "bug", "ga bisa", "gak bisa", "nggak bisa", "tidak bisa"]):
        return reply(
            "Kita pecah masalahnya:\n"
            "1. Catat pesan error persisnya (console/terminal).\n"
            "2. Ulangi langkah yang bikin error.\n"
            "3. Cek frontend console kalau UI bermasalah, backend log kalau API bermasalah.\n"
            "4. Kirim error-nya ke aku, kita bedah bareng."
        )
    if _has_any(text, ["capek", "lelah", "pusing", "stress", "stres", "sedih", "panik", "bingung"]):
        return reply(
            "Aku paham. Coba pelan-pelan: tulis satu kalimat masalah paling beratnya, "
            "pisahin yang harus selesai sekarang vs nanti, lalu ambil satu langkah kecil 10 menit. "
            "Bagian mana yang paling bikin berat?"
        )
    return reply(
        "Aku belum nangkep maksudnya. Coba jelasin lebih spesifik, atau bilang mau ngobrol, "
        "tanya isi dokumen, atau cek data."
    )


def get_chat_reply(message: str, recent_messages, user_name: str | None):
    text = message.lower().strip()
    compact = re.sub(r"[^a-z0-9\s]", "", text).strip()
    if compact in _GREETINGS or _has_any(text, _TIME_TERMS) or _is_closing_smalltalk(text):
        return rule_based_chat(message, user_name)

    system = CHAT_SYSTEM + (f"\nNama user: {user_name}." if user_name else "")
    messages = _history_for_llm(recent_messages) + [{"role": "user", "content": message}]
    reply = llm_complete(system, messages)
    if reply:
        return {"reply": reply, "source": CHAT_SOURCE}
    return rule_based_chat(message, user_name)


# ---------------------------------------------------------------------------
# Jalur RAG
# ---------------------------------------------------------------------------

def _rag_query(message: str, recent_messages) -> str:
    """Pertanyaan lanjutan pendek digabung dengan pertanyaan user sebelumnya."""
    if len(message.split()) > 4:
        return message
    for item in reversed(recent_messages or []):
        if item.role == "user" and item.content.strip():
            return f"{item.content.strip()}. {message}"
    return message


def get_rag_reply(message: str, recent_messages):
    result = run_rag_pipeline(_rag_query(message, recent_messages))
    source = result.get("source") or "PDF knowledge base"
    if "pdf" not in source.lower():
        source = f"PDF: {source}"
    return {"reply": result["reply"], "source": source}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def classify_with_llm(message: str, recent_messages):
    context = _recent_context_text(recent_messages) or "-"
    prompt = ROUTER_PROMPT.format(context=context, message=message)
    label = llm_complete(
        "Kamu router intent. Jawab hanya satu kata.",
        [{"role": "user", "content": prompt}],
        max_tokens=40,
        temperature=0,
        model=os.getenv("LLM_ROUTER_MODEL") or None,  # model kecil & cepat khusus router
    )
    if not label:
        return None
    label = label.lower().strip(" .\n\"'`")
    for candidate in ("database", "rag", "chat"):
        if label.startswith(candidate):
            return candidate
    return None


def classify_with_rules(message: str) -> str:
    text = message.lower()
    words = set(re.findall(r"[a-z0-9]+", text))
    if words & RAG_TERMS:
        return "rag"
    if _is_smalltalk(text):
        return "chat"
    return "rag"  # default aman: cari di dokumen, bukan ngarang


def _topic_from_history(recent_messages, repository, limit: int = 8):
    """Cari topik database dari histori chat, dipakai buat pesan lanjutan/filter
    yang sendiri gak punya kata kunci topik."""
    for item in reversed((recent_messages or [])[-limit:]):
        content = (item.content or "").strip()
        source = (getattr(item, "source", None) or "").strip()
        if not content:
            continue
        combined = f"{source} {content}".lower()
        if "leave_balances" in combined or "data cuti dari database" in combined:
            return "leave"
        if "employees" in combined or "data pegawai dari database" in combined:
            return "employee"
        if "it_tickets" in combined or "tiket it" in combined:
            return "ticket"
        if "overtime_requests" in combined or "riwayat lembur" in combined:
            return "overtime"
        if "attendance" in combined or "absensi" in combined:
            return "attendance"
        if "company_assets" in combined or "aset perusahaan" in combined:
            return "asset"
        if "wfh_requests" in combined or "pengajuan wfh" in combined:
            return "wfh"
        if "reimbursements" in combined or "reimbursement" in combined:
            return "reimbursement"
        if "training_requests" in combined or "pengajuan training" in combined:
            return "training"

        if item.role != "user":
            continue
        text = content.lower()
        ident = find_identifier(content, repository)
        topic = detect_db_topic(text, ident)
        if topic:
            return topic
    return None


def _is_database_followup(text: str, recent_messages) -> bool:
    if not recent_messages:
        return False
    if _has_any(text, POLICY_TERMS):
        return False
    if _is_closing_smalltalk(text):
        return False
    compact = re.sub(r"[^a-z0-9\s]", "", text).strip()
    followup_cues = [
        "berarti", "berati", "jadi", "bener", "benar", "sisa", "saldo", "segitu",
    ]
    has_cue = _has_any(compact, followup_cues) or _extract_first_number(compact) is not None
    if not has_cue:
        return False
    return _topic_from_history(recent_messages, None, limit=4) is not None


def decide_route(message: str, recent_messages, employee_id: str | None = None):
    text = message.lower()
    if _is_smalltalk(text) or _is_closing_smalltalk(text):
        return {"route": "chat", "topic": None, "identifier": "", "repository": None}
    if _has_any(text, POLICY_TERMS):
        return {"route": "rag", "topic": None, "identifier": "", "repository": None}

    try:
        repository = UserRepository()
    except Exception:
        logger.exception("UserRepository gagal dibuat")
        repository = None

    detected_identifier = find_identifier(message, repository)
    login_identifier = _normalize_employee_id(employee_id, repository)
    identifier = detected_identifier or (login_identifier if _can_use_login_employee(text) else "")
    topic = detect_db_topic(text, identifier)
    if topic:
        return {"route": "database", "topic": topic, "identifier": identifier, "repository": repository}
    if _has_any(text, POLICY_TERMS):
        return {"route": "rag", "topic": None, "identifier": identifier, "repository": repository}
    if _is_smalltalk(text) or _is_closing_smalltalk(text):
        return {"route": "chat", "topic": None, "identifier": identifier, "repository": repository}

    history_topic = _topic_from_history(recent_messages, repository, limit=8)
    if login_identifier and history_topic and _is_database_followup(text, recent_messages):
        return {
            "route": "database",
            "topic": history_topic,
            "identifier": login_identifier,
            "repository": repository,
        }

    label = classify_with_llm(message, recent_messages) or classify_with_rules(message)
    if label == "database":
        # pesan ini gak punya kata kunci topik sendiri -> kemungkinan lanjutan/filter.
        # Nyisir balik pesan USER sebelumnya (bukan balasan AI yang lebih "berisik"),
        # satu-satu dari yang paling baru, sampe ketemu yang jelas nyebut topik data.
        topic = history_topic
    else:
        topic = None
    return {"route": label, "topic": topic, "identifier": identifier, "repository": repository}


# ---------------------------------------------------------------------------
# Agent executor
# ---------------------------------------------------------------------------

def _agent_step(thought: str, action: str, observation: str | None = None):
    return {"thought": thought, "action": action, "observation": observation}


def _summarize_observation(result: dict) -> str:
    source = result.get("source") or "Unknown source"
    reply = re.sub(r"\s+", " ", result.get("reply") or "").strip()
    if len(reply) > 180:
        reply = reply[:180].rsplit(" ", 1)[0] + "..."
    return f"{source}: {reply}" if reply else source


def _route_label(route: str, topic: str | None) -> str:
    if route == "database":
        return f"database.{topic or 'general'}"
    if route == "rag":
        return "rag.search_knowledge_base"
    return "conversation.respond"


def run_agent_executor(message: str, request: ChatRequest):
    """Executor ringan: plan -> tool -> observe -> final.

    Ini sengaja membungkus sistem lama, bukan menggantinya. Database, RAG, dan chat
    tetap memakai fungsi yang sudah ada, tapi sekarang ada jejak keputusan agent.
    """
    steps = [
        _agent_step(
            "Memahami tujuan user dan konteks sesi login.",
            "inspect_request",
            f"employee_id={request.employee_id or '-'}, recent_messages={len(request.recent_messages or [])}",
        )
    ]

    memory_reply = get_name_memory_reply(message, request.user_name)
    if memory_reply:
        steps.append(_agent_step(
            "Pertanyaan ini cukup dijawab dari memory percakapan.",
            "conversation_memory",
            _summarize_observation(memory_reply),
        ))
        return {**memory_reply, "agent_steps": steps}

    decision = decide_route(message, request.recent_messages, request.employee_id)
    route = decision["route"]
    topic = decision["topic"]
    identifier = decision["identifier"]
    logger.info("route=%s topic=%s identifier=%s | %s", route, topic, identifier, message[:80])

    steps.append(_agent_step(
        "Memilih tool paling cocok berdasarkan intent, kata kunci, histori, dan employee ID login.",
        _route_label(route, topic),
        f"identifier={identifier or '-'}",
    ))

    if route == "database":
        result = get_database_reply(topic, identifier, message, decision["repository"])
    elif route == "chat":
        result = get_chat_reply(message, request.recent_messages, request.user_name)
    else:
        result = get_rag_reply(message, request.recent_messages)

    steps.append(_agent_step(
        "Mengeksekusi tool dan membaca hasil observasi.",
        "observe_tool_result",
        _summarize_observation(result),
    ))
    steps.append(_agent_step(
        "Menyusun jawaban final dengan sumber aktif tanpa mengarang data internal.",
        "final_response",
        result.get("source") or "Unknown source",
    ))

    return {**result, "agent_steps": steps}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Hello from AI Agent API!"}


@app.get("/health")
def health_check():
    pipeline = get_rag_pipeline()
    return {
        "status": "ok",
        "llm_configured": _get_llm_client() is not None,
        "knowledge_base_files": pipeline.loaded_files,
        "knowledge_base_chunks": pipeline.chunk_count,
    }


@app.post("/auth/register", response_model=AuthResponse)
def register(request: AuthRegisterRequest):
    employee_id = request.employee_id.strip()
    password = request.password
    _validate_auth_input(employee_id, password)

    users = _load_auth_users()
    key = _employee_key(employee_id)
    if key in users:
        raise HTTPException(status_code=409, detail="ID karyawan sudah terdaftar.")

    user = {
        "employee_id": employee_id,
        "display_name": (request.display_name or "").strip(),
        "password": _hash_password(password),
        "created_at": int(time.time()),
    }
    users[key] = user
    _save_auth_users(users)
    return _auth_response(user)


@app.post("/auth/login", response_model=AuthResponse)
def login(request: AuthLoginRequest):
    employee_id = request.employee_id.strip()
    password = request.password
    _validate_auth_input(employee_id, password)

    user = _load_auth_users().get(_employee_key(employee_id))
    if not user or not _verify_password(password, user):
        raise HTTPException(status_code=401, detail="ID karyawan atau kata sandi salah.")
    return _auth_response(user)


@app.get("/auth/session", response_model=AuthResponse)
def session(authorization: str | None = Header(default=None)):
    user = _get_user_from_token(_read_bearer_token(authorization))
    return _auth_response(user)


@app.get("/debug/llm")
def debug_llm():
    """Ngetes panggilan LLM langsung, error aslinya ditampilkan (gak ke-swallow)."""
    client = _get_llm_client()
    if client is None:
        return {"llm_configured": False, "detail": "API key belum kebaca dari .env"}
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Balas dengan kata 'pong' saja."}],
            max_completion_tokens=500,
            reasoning_effort="low",
        )
        choice = response.choices[0]
        return {
            "ok": True,
            "model": model,
            "reply": choice.message.content,
            "finish_reason": choice.finish_reason,  # "length" = kehabisan token, "stop" = normal
            "usage": response.usage.model_dump() if response.usage else None,
        }
    except Exception as exc:
        return {"ok": False, "model": model, "error_type": type(exc).__name__, "error": str(exc)}


@app.get("/debug/route")
def debug_route(message: str):
    """Ngetes routing tanpa jalanin jawaban. Contoh: /debug/route?message=sisa cuti EMP-001"""
    decision = decide_route(message, [])
    return {k: v for k, v in decision.items() if k != "repository"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, authorization: str | None = Header(default=None)):
    """Endpoint utama: terima pertanyaan, jalankan agent executor, kembalikan jawaban."""
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Pesan kosong.")

    auth_user = _get_user_from_token(_read_bearer_token(authorization))
    request.employee_id = auth_user["employee_id"]
    if not request.user_name:
        request.user_name = auth_user.get("display_name") or auth_user["employee_id"]

    try:
        result = run_agent_executor(message, request)
    except RuntimeError as exc:
        logger.exception("Agent executor gagal saat menjalankan RAG pipeline")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        reply=result["reply"],
        source=result["source"],
        agent_steps=result.get("agent_steps", []),
    )
