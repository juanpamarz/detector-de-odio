"""Configuración centralizada y tipada (pydantic-settings).

Todas las credenciales se leen de variables de entorno o de `.env`; nunca se
escriben en el código. Los secretos usan `SecretStr` para que no aparezcan en
logs ni en `repr()`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Aplicación -------------------------------------------------------
    app_env: Literal["local", "production"] = "local"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # --- Persistencia y mensajería ---------------------------------------
    database_url: str = "postgresql+psycopg://centinela:centinela@localhost:5432/centinela"
    # Cola de trabajo:
    #   celery -> RabbitMQ/Redis + workers Celery (docker compose, VM)
    #   qstash -> Upstash QStash empuja cada tarea a /api/internal/tasks/* (serverless, Vercel)
    queue_backend: Literal["celery", "qstash"] = "celery"
    broker_url: str = "amqp://guest:guest@localhost:5672//"
    qstash_url: str = "https://qstash.upstash.io"
    qstash_token: SecretStr | None = None
    qstash_current_signing_key: SecretStr | None = None
    qstash_next_signing_key: SecretStr | None = None
    qstash_retries: int = 3
    # Vercel define VERCEL=1; en serverless se usa NullPool y sin sentencias preparadas.
    auto_migrate: bool = False
    serverless: bool = Field(default=False, validation_alias=AliasChoices("SERVERLESS", "VERCEL"))

    # --- Seguridad --------------------------------------------------------
    jwt_secret: SecretStr = SecretStr("cambia-esto-en-produccion-con-32+caracteres")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    first_admin_email: str | None = None
    first_admin_password: SecretStr | None = None
    first_admin_name: str = "Administrador"

    # --- Telegram ---------------------------------------------------------
    telegram_bot_token: SecretStr | None = None
    telegram_webhook_secret: SecretStr | None = None
    public_base_url: str | None = None  # p. ej. https://centinela-api.vercel.app

    # --- Proveedores NLP (todos con capa gratuita) -------------------------
    # Orden = prioridad. Se consultan los primeros NLP_ENSEMBLE_SIZE disponibles; si uno
    # falla (límite, caída, clave inválida) se pasa al siguiente de la lista.
    nlp_providers: str = "groq,cerebras,openrouter,edenai"
    nlp_fallback_providers: str = "heuristic"
    nlp_strategy: Literal["ensemble", "cascade"] = "ensemble"
    nlp_ensemble_size: int = Field(default=2, ge=1, le=6)
    # Tras fallar, un proveedor se salta durante este tiempo (circuit breaker).
    provider_cooldown_seconds: int = 120
    nlp_timeout_seconds: float = 12.0
    nlp_max_attempts: int = 4

    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b,llama-3.1-8b-instant,qwen/qwen3.8-27b"
    cerebras_api_key: SecretStr | None = None
    cerebras_model: str = "gpt-oss-120b,llama3.1-8b"
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "google/gemma-4-26b-a4b-it:free,nvidia/nemotron-3.5-lightning:free"
    edenai_api_key: SecretStr | None = None
    # Eden AI cobra de tu saldo de créditos: va al final de la cadena.
    edenai_model: str = "cohere/command-a-03-2025"

    # Pesos del ensamble (proveedor -> peso). Los ausentes valen 1.0.
    provider_weights: str = "groq:1.0,cerebras:1.0,openrouter:0.9,edenai:1.0,heuristic:0.5"

    # --- Política de moderación ------------------------------------------
    toxicity_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    identity_hate_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    crisis_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    hard_block_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    # Advertencias antes de expulsar del grupo. 0 = nunca expulsar (solo borra y advierte).
    max_warnings: int = Field(default=5, ge=0)
    allow_republish: bool = True
    store_crisis_text: bool = False
    crisis_support_message: str = (
        "Hola {name}. Leímos tu mensaje en el grupo y nos importa cómo estás.\n\n"
        "No estás solo/a. Hay personas que pueden escucharte sin juzgarte, gratis y a cualquier hora:\n"
        "- Línea de la Vida (México): 800 911 2000\n"
        "- Emergencias: 911\n\n"
        "Si puedes, habla también con alguien de confianza."
    )

    @field_validator(
        "groq_api_key", "cerebras_api_key", "openrouter_api_key", "edenai_api_key", "telegram_bot_token", "telegram_webhook_secret", "first_admin_password",
        "qstash_token", "qstash_current_signing_key", "qstash_next_signing_key", mode="before",
    )
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        # Una variable vacía en .env (GROQ_API_KEY=) significa "no configurado".
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _jwt_secret_default(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "cambia-esto-en-produccion-con-32+caracteres"
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app_env == "production" and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET debe tener al menos 32 caracteres en producción")
        if self.queue_backend == "qstash" and not (self.qstash_token and self.public_base_url):
            raise ValueError("QUEUE_BACKEND=qstash requiere QSTASH_TOKEN y PUBLIC_BASE_URL")
        return self

    @field_validator("database_url")
    @classmethod
    def _normalize_driver(cls, value: str) -> str:
        # Neon y otros servicios entregan postgresql://; forzamos el driver psycopg 3.
        if value.startswith("postgres://"):
            value = "postgresql://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def primary_provider_names(self) -> list[str]:
        return [p.strip() for p in self.nlp_providers.split(",") if p.strip()]

    @property
    def fallback_provider_names(self) -> list[str]:
        return [p.strip() for p in self.nlp_fallback_providers.split(",") if p.strip()]

    @property
    def provider_weight_map(self) -> dict[str, float]:
        weights: dict[str, float] = {}
        for pair in self.provider_weights.split(","):
            if ":" in pair:
                name, raw = pair.split(":", 1)
                weights[name.strip()] = float(raw)
        return weights


@lru_cache
def get_settings() -> Settings:
    return Settings()
