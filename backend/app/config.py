"""All settings, read from environment variables or backend/.env (SRS Section 9, NFR-SEC-01).

Defaults let the app start offline with no keys: TF-IDF router, console SMS, SQLite.
Secrets are SecretStr, so they never appear in logs or error messages by accident.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain import policies

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


LLM_NAMES = ("gemini", "groq", "openrouter")  # LLM_ORDER


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app
    app_env: Literal["dev", "demo"] = "dev"
    public_url: str = "http://localhost:8000"
    frontend_origins: str = "http://localhost:5173"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'ekcall.db').as_posix()}"

    # --- LLM (FR-AGT-16, FR-AGT-18)
    llm_backend: Literal["gemini", "ollama", "hybrid"] = "gemini"
    gemini_api_keys: SecretStr = SecretStr("")
    gemini_model_main: str = ""
    gemini_model_fast: str = ""
    gemini_model_fallback: str = ""  # tried once when the model is overloaded (503) or out of quota
    gemini_budget_s: float = Field(0.0, ge=0)  # most seconds per Gemini request in total; 0 = no limit
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    # Order of the cloud LLMs: the first answers, each next one only when all before it are unavailable.
    # Names: gemini, groq, openrouter. One without its API key is skipped.
    llm_order: str = "gemini,groq,openrouter"
    # Groq (any OpenAI-compatible API). Empty key: off.
    groq_api_keys: SecretStr = SecretStr("")  # key1,key2 (the next key on 429/401/403)
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # OpenRouter (a ":free" model). Empty key: off.
    openrouter_api_keys: SecretStr = SecretStr("")  # key1,key2
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- router + retrieval (FR-AGT-02, 03, 05)
    router_backend: Literal["tfidf", "banglabert", "llm"] = "tfidf"
    router_model_dir: Path = BACKEND_DIR / "data" / "models" / "router"
    tfidf_model_path: Path = BACKEND_DIR / "data" / "models" / "tfidf_router.joblib"
    router_confidence_threshold: float = Field(policies.ROUTER_CONFIDENCE_THRESHOLD, gt=0, lt=1)
    retrieval_min_score: float = Field(policies.RETRIEVAL_MIN_SCORE, gt=0, lt=1)
    embed_model: str = "intfloat/multilingual-e5-small"
    embed_cache_dir: Path = BACKEND_DIR / "data" / "models" / "e5"
    chroma_dir: Path = BACKEND_DIR / "data" / "chroma"
    chroma_host: str = ""  # set (e.g. localhost) to use the Chroma server instead of chroma_dir
    chroma_port: int = 8001
    services_file: Path = BACKEND_DIR / "data" / "services.yaml"
    voice_fast_mode: bool = True
    agent_engine: Literal["langgraph", "stub"] = "langgraph"  # stub: fixed answer, no keys needed
    preload_models: bool = False  # True in .env.example: load models in the background at startup

    # --- Twilio (FR-CALL)
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_number: str = ""
    stt_language: str = "bn-BD"
    tts_voice: str = "Google.bn-IN-Standard-A"
    tts_language: str = "bn-IN"
    missed_call_mode: bool = False
    validate_twilio_signature: bool = False

    # --- SMS (FR-SMS-03)
    sms_backend: Literal["console", "textbee"] = "console"
    textbee_api_key: SecretStr = SecretStr("")
    textbee_device_id: str = ""

    # --- security + privacy (FR-ADM-05, NFR-PRIV-01)
    admin_token: SecretStr = SecretStr("")
    admin_session_hours: float = Field(default=8, gt=0, le=72)  # how long an admin login lasts
    phone_hash_salt: SecretStr = SecretStr("")

    # ------------------------------------------------------------ derived values

    @property
    def frontend_origin_list(self) -> list[str]:
        return _split(self.frontend_origins)

    @property
    def gemini_key_list(self) -> list[str]:
        return _split(self.gemini_api_keys.get_secret_value())

    @property
    def groq_key_list(self) -> list[str]:
        return _split(self.groq_api_keys.get_secret_value())

    @property
    def openrouter_key_list(self) -> list[str]:
        return _split(self.openrouter_api_keys.get_secret_value())

    @property
    def llm_order_list(self) -> list[str]:
        return [name.lower() for name in _split(self.llm_order)]

    @property
    def cloud_llm_summary(self) -> str:
        """The cloud LLMs that will be used, in LLM_ORDER, e.g. "gemini (m, fast m) -> groq (m)".

        Only providers with an API key (and models) are listed, like the chain the container builds.
        """
        parts: list[str] = []
        gemini_set = bool(self.gemini_key_list and self.gemini_model_main and self.gemini_model_fast)
        for name in dict.fromkeys(self.llm_order_list):
            if name == "gemini" and gemini_set:
                extra = f", 2nd {self.gemini_model_fallback}" if self.gemini_model_fallback else ""
                parts.append(f"gemini ({self.gemini_model_main}, fast {self.gemini_model_fast}{extra})")
            elif name == "groq" and self.groq_key_list and self.groq_model:
                parts.append(f"groq ({self.groq_model})")
            elif name == "openrouter" and self.openrouter_key_list and self.openrouter_model:
                parts.append(f"openrouter ({self.openrouter_model})")
        return " -> ".join(parts) or "none configured"

    @property
    def llm_summary(self) -> str:
        """LLM_BACKEND with the models behind it, for the startup log and evaluation reports."""
        if self.llm_backend == "ollama":
            return f"ollama ({self.ollama_model})"
        if self.llm_backend == "hybrid":
            return f"hybrid: fast jobs on ollama ({self.ollama_model}), main jobs on {self.cloud_llm_summary}"
        return self.cloud_llm_summary

    def config_warnings(self) -> list[str]:
        """Problems worth logging at startup. The app still starts; the affected feature fails politely."""
        warnings: list[str] = []
        unknown = [n for n in self.llm_order_list if n not in LLM_NAMES]
        if unknown:
            warnings.append(f"LLM_ORDER has unknown names {unknown}; known: {', '.join(LLM_NAMES)}")
        if self.llm_backend in ("gemini", "hybrid"):
            if not self.gemini_key_list:
                warnings.append(f"LLM_BACKEND={self.llm_backend} but GEMINI_API_KEYS is empty")
            if not (self.gemini_model_main and self.gemini_model_fast):
                warnings.append("GEMINI_MODEL_MAIN / GEMINI_MODEL_FAST are not set")
        if self.sms_backend == "textbee" and not (
            self.textbee_api_key.get_secret_value() and self.textbee_device_id
        ):
            warnings.append("SMS_BACKEND=textbee but TEXTBEE_API_KEY / TEXTBEE_DEVICE_ID are missing")
        if not self.phone_hash_salt.get_secret_value():
            warnings.append("PHONE_HASH_SALT is empty: phone hashes in question_logs are weak")
        if self.app_env == "demo":
            if not self.admin_token.get_secret_value():
                warnings.append("APP_ENV=demo but ADMIN_TOKEN is empty: the admin dashboard is closed (503)")
            if not self.validate_twilio_signature:
                warnings.append("APP_ENV=demo but VALIDATE_TWILIO_SIGNATURE=false")
        return warnings


@lru_cache
def get_settings() -> Settings:
    """The one Settings object for the running app (read once)."""
    return Settings()
