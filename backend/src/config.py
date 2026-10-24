from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env dicari relatif ke folder backend/, jadi aman dijalanin dari folder mana pun
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # LLM — salah satu nama diterima
    llm_api_key: str = ""
    openai_api_key: str = ""        # alias lama, tetap didukung
    groq_api_key: str = ""          # alias lama, tetap didukung

    # Database
    database_url: str = "sqlite:///./agent.db"

    # Model LLM
    llm_model: str = "openai/gpt-oss-120b"
    llm_router_model: str = "openai/gpt-oss-20b"

    # CORS — origin yang diizinkan (pisahkan koma di .env)
    # Contoh: ALLOWED_ORIGINS=http://localhost:5173,https://myapp.com
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Auth. Wajib diisi pada production (termasuk Vercel).
    auth_secret: str = ""
    app_env: str = "development"
    allow_self_registration: bool = False

    def get_llm_api_key(self) -> str:
        """Kembalikan API key LLM dari salah satu variabel yang tersedia."""
        return self.llm_api_key or self.groq_api_key or self.openai_api_key or ""

    def get_allowed_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS dari string CSV menjadi list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
