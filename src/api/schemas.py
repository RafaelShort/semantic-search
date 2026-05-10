"""
Schemas Pydantic — define a estrutura de request e response da API.

Por que usar schemas?
    - Validação automática dos dados de entrada
    - Documentação automática no Swagger UI
    - Serialização/desserialização automática
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Requests (entrada)
# ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Schema de requisição de busca."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Texto da busca",
        examples=["como funciona machine learning"]
    )
    mode: str = Field(
        default="hybrid",
        description="Modo de busca: hybrid | semantic | keyword",
        examples=["hybrid"]
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de resultados (1-20)"
    )
    semantic_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Peso da busca semântica (0.0 a 1.0)"
    )
    keyword_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Peso da busca por palavras-chave (0.0 a 1.0)"
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Score mínimo para incluir resultado"
    )
    rerank: bool = Field(
        default=True,
        description="Aplicar reranking nos resultados"
    )
    deduplicate: bool = Field(
        default=True,
        description="Remover resultados duplicados"
    )


class IngestRequest(BaseModel):
    """Schema para ingestão de URL via API."""

    url: str = Field(
        ...,
        description="URL para ingerir",
        examples=["https://exemplo.com/artigo"]
    )


# ─────────────────────────────────────────────────────────────
# Responses (saída)
# ─────────────────────────────────────────────────────────────

class SearchResultItem(BaseModel):
    """Um item de resultado de busca."""

    chunk_id:    str
    content:     str
    source:      str
    score:       float
    chunk_index: int
    search_type: str
    metadata:    dict = {}


class SearchResponse(BaseModel):
    """Response completo de uma busca."""

    query:        str
    mode:         str
    total_results: int
    results:      list[SearchResultItem]
    time_ms:      float


class IngestResponse(BaseModel):
    """Response de ingestão de documento."""

    success:     bool
    document_id: Optional[str] = None
    message:     str
    chunks_count: Optional[int] = None


class HealthResponse(BaseModel):
    """Response do health check."""

    status:        str
    mongodb:       bool
    elasticsearch: bool
    version:       str = "1.0.0"


class StatsResponse(BaseModel):
    """Response de estatísticas do sistema."""

    total_documents:     int
    processed_documents: int
    total_chunks:        int
    indexed_chunks:      int
    pending_chunks:      int
    es_docs_count:       int
    es_index_size_mb:    float
