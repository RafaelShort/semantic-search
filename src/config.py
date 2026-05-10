"""
Configurações centralizadas da aplicação.

Padrão Singleton com @lru_cache: a configuração é lida apenas
uma vez e reutilizada em toda a aplicação.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Diretório raiz do projeto
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,   
        extra="ignore"          
    )

    # Aplicação
    app_name: str = "Motor de Busca Semântico"
    debug: bool = False

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "semantic_search"

    # ElasticSearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "documents"

    # Embeddings
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 50


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Instância global — importe este objeto em outros módulos
settings = get_settings()
