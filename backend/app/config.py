"""
Central configuration for OpsAgent-X.

Everything here is overridable via environment variables (or a .env file in
the backend/ directory). See ../.env.example at the project root for the
full list with sane defaults.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"

    # --- LLM Engine: DeepSeek-V4 Flash via NVIDIA NIM (OpenAI-compatible) ---
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-ai/deepseek-v4-flash"

    # Illustrative $ / 1K tokens per reasoning mode, shown on the dashboard's
    # cost panel. Tune these against your actual NIM / self-hosted billing.
    TOKEN_COST_PER_1K: dict[str, float] = {
        "non_think": 0.0002,
        "think_high": 0.0006,
        "think_max": 0.0014,
    }

    # --- Redis: LangGraph checkpoints, semantic cache, live event pub/sub ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- MongoDB: incidents, audit trail, compliance history ---
    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DB_NAME: str = "opsagentx"

    # --- Kubernetes / Prometheus (read-only tooling for LogAnalyst) ---
    K8S_IN_CLUSTER: bool = False
    K8S_KUBECONFIG: str | None = None
    PROMETHEUS_URL: str = "http://prometheus.monitoring.svc.cluster.local:9090"
    # Hard allow-list: LogAnalyst can only read logs from these namespaces,
    # regardless of what the model asks for.
    ALLOWED_NAMESPACES: list[str] = ["staging", "default"]

    # --- Git (CodeFixer commits patches to a feature branch here) ---
    GIT_REPO_PATH: str = "/repo"
    GITHUB_TOKEN: str = ""

    # --- ArgoCD (final deploy step, after human approval) ---
    ARGOCD_SERVER: str = ""
    ARGOCD_TOKEN: str = ""

    # --- Safety constraints ---
    MAX_RETRIES: int = 2
    REQUIRE_HUMAN_APPROVAL: bool = True

    # --- CORS ---
    FRONTEND_ORIGIN: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
