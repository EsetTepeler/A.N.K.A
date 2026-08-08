from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_lite_model: str = "gemini-2.5-flash-lite"

    # Altyapi
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    # Core
    anka_host: str = "0.0.0.0"
    anka_port: int = 8000
    anka_db_path: str = "./data/anka.db"

    # RAG
    anka_projects_root: str = "./projects"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    qdrant_collection: str = "anka_codebase"

    system_prompt: str = (
        "Sen A.N.K.A adinda kisisel bir yapay zeka asistanisin. "
        "Turkce konusursun, kisa ve net yanit verirsin. "
        "Elindeki araclari (tools) gerektiginde kullanirsin; "
        "bir araci kullanmadan once kullaniciya sormana gerek yok, "
        "SAFE sinifi araclar otomatik calisir. "
        "Kullanicinin kod projelerine dair sorularda search_codebase araciyla "
        "ilgili kod parcalarini bulup yanitini bu parcalara dayandirirsin; "
        "kod referansi verirken dosya yolu ve satir araligini belirtirsin."
    )


settings = Settings()
