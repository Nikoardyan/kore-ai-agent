"""
main.py - jalanin server:  python main.py
Taruh di folder root project (sejajar dengan api.py dan folder src/).
"""

import uvicorn
from dotenv import load_dotenv

load_dotenv()  # baca .env (API key Groq, DATABASE_URL, dll) sebelum server start

if __name__ == "__main__":
    # "api:app" = variabel `app` di dalam file api.py
    # reload=True: server auto-restart kalau kode diubah (khusus development)
    # host 127.0.0.1 = hanya bisa diakses dari laptop lo sendiri (lebih aman).
    # Ganti ke "0.0.0.0" kalau perlu diakses dari device lain di jaringan yang sama.
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)