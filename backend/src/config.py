from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env dicari relatif ke folder backend/, jadi aman dijalanin dari folder mana pun
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # nama field = nama variabel .env (case-insensitive)
    openai_api_key: str = "dummy_key"   # isinya key Groq lo
    database_url: str = "sqlite:///./agent.db"
    model_path: str = "./models/model.pkl"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_router_model: str = ""


settings = Settings()