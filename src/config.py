"""
Configurações centralizadas da aplicação.

Pydantic-settings carrega automaticamente de:
1. Variáveis de ambiente do sistema
2. Arquivo .env (menor prioridade)

Padrão Singleton com @lru_cache: a configuração é lida apenas
uma vez e reutilizada em toda a aplicação.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Diretório raiz do projeto (2 níveis acima deste arquivo)
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,   # MONGODB_URI e mongodb_uri são equivalentes
        extra="ignore"          # Ignora variáveis desconhecidas no .env
    )

    # ─── Aplicação ────────────────────────────────────────────
    app_name: str = "Motor de Busca Semântico"
    debug: bool = False

    # ─── MongoDB ──────────────────────────────────────────────
    mongodb_uri: str = "mongodb://admin:password123@localhost:27017"
    mongodb_db_name: str = "semantic_search"

    # ─── ElasticSearch ────────────────────────────────────────
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "documents"

    # ─── Embeddings ───────────────────────────────────────────
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # ─── Chunking ─────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 50


@lru_cache()  # Garante que Settings() é instanciado uma única vez
def get_settings() -> Settings:
    return Settings()


# Instância global — importe este objeto em outros módulos
settings = get_settings()
