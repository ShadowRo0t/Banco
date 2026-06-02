from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Configurations
    API_TITLE: str = "Banco - API de Clasificación de Incidentes"
    API_DESCRIPTION: str = (
        "API para la clasificación automática en tiempo real de prioridades y "
        "categorías de solicitudes de clientes mediante un LLM local y LangChain."
    )
    API_VERSION: str = "1.0.0"
    APP_ENV: str = "development"

    # Ollama LLM Configurations
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    LLM_TIMEOUT_SECONDS: float = 10.0

    # Operational Thresholds
    LATENCY_THRESHOLD_MS: float = 5000.0  # Umbral de alerta para tiempo de respuesta

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
