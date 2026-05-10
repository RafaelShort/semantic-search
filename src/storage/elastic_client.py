"""
Cliente ElasticSearch para indexação e busca semântica.

O ElasticSearch será usado para dois tipos de busca:
┌────────────────────────────────────────────────────────────┐
│ 1. BM25 (keyword search)                                    │
│    Campo: content (type: text)                              │
│    Como funciona: analisa frequência de termos              │
│                                                             │
│ 2. kNN (semantic search)                                    │
│    Campo: content_embedding (type: dense_vector)            │
│    Como funciona: mede similaridade entre vetores           │
│                                                             │
│ 3. Híbrida = BM25 + kNN combinados                         │
└────────────────────────────────────────────────────────────┘
"""

from loguru import logger
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, BulkIndexError

from src.config import settings


class ElasticSearchClient:
    """
    Gerencia conexão e operações no ElasticSearch.

    Uso:
        es_client.connect()
        es_client.create_index()
        es_client.bulk_index(chunks_with_embeddings)
    """

    # ─────────────────────────────────────────────────────────
    # Mapeamento do Índice
    # Define a estrutura e comportamento de cada campo
    # ─────────────────────────────────────────────────────────
    INDEX_MAPPINGS = {
        "properties": {
            # Texto principal — analisado para busca full-text (BM25)
            "content": {
                "type": "text",
                "analyzer": "portuguese_custom",
                "fields": {
                    # Subcampo keyword: para filtragem exata e ordenação
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            # Vetor de embedding — habilita busca semântica (kNN)
            "content_embedding": {
                "type": "dense_vector",
                "dims": 384,             # Dimensão do all-MiniLM-L6-v2
                "index": True,           # OBRIGATÓRIO para kNN aproximado
                "similarity": "cosine"   # Métrica: cosine similarity
            },
            # Referência ao documento original no MongoDB
            "document_id":    {"type": "keyword"},
            "mongo_chunk_id": {"type": "keyword"},
            # Origem do documento (caminho, URL, etc.)
            "source":         {"type": "keyword"},
            # Posição do chunk dentro do documento
            "chunk_index":    {"type": "integer"},
            # Metadados flexíveis (título, autor, data, etc.)
            "metadata": {
                "type": "object",
                "dynamic": True  # Aceita campos não definidos
            }
        }
    }

    INDEX_SETTINGS = {
        "number_of_shards":   1,   # 1 shard para desenvolvimento
        "number_of_replicas": 0,   # 0 réplicas para desenvolvimento
        "analysis": {
            # Analisador customizado para Português
            "analyzer": {
                "portuguese_custom": {
                    "type":      "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "portuguese_stop",
                        "portuguese_stemmer",
                        "asciifolding"  # Remove acentos na indexação
                    ]
                }
            },
            "filter": {
                "portuguese_stop": {
                    "type":      "stop",
                    "stopwords": "_portuguese_"  # Remove: de, do, da, e, para...
                },
                "portuguese_stemmer": {
                    "type":     "stemmer",
                    "language": "portuguese"  # Reduz palavras ao radical
                }
            }
        }
    }

    def __init__(self):
        self._client: Elasticsearch | None = None

    # ─────────────────────────────────────────────────────────
    # Conexão
    # ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Conecta ao ElasticSearch e exibe informações da versão."""
        try:
            self._client = Elasticsearch(
                settings.elasticsearch_url,
                request_timeout=15,
                retry_on_timeout=True,
                max_retries=3
            )
            info = self._client.info()
            version = info["version"]["number"]
            cluster = info["cluster_name"]
            logger.info(
                f"✅ ElasticSearch conectado | "
                f"v{version} | Cluster: '{cluster}'"
            )
        except Exception as exc:
            logger.error(f"❌ Falha ao conectar ao ElasticSearch: {exc}")
            raise

    @property
    def client(self) -> Elasticsearch:
        if self._client is None:
            raise RuntimeError(
                "ElasticSearch não conectado. Chame connect() primeiro."
            )
        return self._client

    @property
    def index_name(self) -> str:
        return settings.elasticsearch_index

    # ─────────────────────────────────────────────────────────
    # Gerenciamento do Índice
    # ─────────────────────────────────────────────────────────

    def create_index(self, force_recreate: bool = False) -> None:
        """
        Cria o índice no ElasticSearch com o mapeamento definido.

        Args:
            force_recreate: Se True, deleta e recria (perde todos os dados!)
        """
        index_name = self.index_name
        exists = self.client.indices.exists(index=index_name)

        if exists:
            if force_recreate:
                self.client.indices.delete(index=index_name)
                logger.warning(f"🗑️  Índice '{index_name}' deletado (force_recreate=True)")
            else:
                logger.info(f"ℹ️  Índice '{index_name}' já existe — nenhuma ação necessária")
                return

        self.client.indices.create(
            index=index_name,
            mappings=self.INDEX_MAPPINGS,
            settings=self.INDEX_SETTINGS
        )
        logger.info(f"✅ Índice '{index_name}' criado com sucesso")

    def delete_index(self) -> None:
        """Remove o índice completamente. Use com cuidado!"""
        index_name = self.index_name
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            logger.warning(f"🗑️  Índice '{index_name}' deletado")

    # ─────────────────────────────────────────────────────────
    # Indexação de Documentos
    # ─────────────────────────────────────────────────────────

    def index_chunk(self, chunk_data: dict) -> str:
        """
        Indexa um único chunk (útil para testes).

        Args:
            chunk_data: Dict com 'content', 'content_embedding' e metadados

        Returns:
            ID do documento no ElasticSearch
        """
        response = self.client.index(
            index=self.index_name,
            document=chunk_data,
            refresh="wait_for"  # Aguarda até estar disponível para busca
        )
        return response["_id"]

    def bulk_index(self, chunks: list[dict]) -> tuple[int, int]:
        """
        Indexa múltiplos chunks com a Bulk API.

        Por que Bulk API?
        → 1 request HTTP para N documentos (muito mais eficiente)
        → Até 10x mais rápido que indexações individuais
        → Recomendado para qualquer volume > 10 documentos

        Args:
            chunks: Lista de dicts com content, content_embedding e metadados

        Returns:
            Tuple (sucessos, falhas)
        """
        if not chunks:
            return 0, 0

        # Formata os chunks no formato esperado pelo bulk helper
        actions = [
            {
                "_index":  self.index_name,
                "_source": chunk
            }
            for chunk in chunks
        ]

        try:
            success_count, errors = bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True,
                chunk_size=500
            )
            error_count = len(errors)

            logger.info(
                f"✅ Bulk index concluído | "
                f"Sucesso: {success_count} | Erros: {error_count}"
            )

            if errors:
                logger.warning(f"⚠️  Erros no bulk index: {errors[:3]}")

            return success_count, error_count

        except BulkIndexError as exc:
            logger.error(f"❌ Erro crítico no bulk index: {exc}")
            raise

    # ─────────────────────────────────────────────────────────
    # Busca  ← NOVO
    # ─────────────────────────────────────────────────────────

    def search(self, query: dict, size: int = 10) -> dict:
        """
        Executa uma busca no ElasticSearch.

        Suporta qualquer query DSL do ElasticSearch:
        - kNN (busca semântica por vetor)
        - multi_match (busca por palavras-chave BM25)
        - bool (combinações complexas)

        Args:
            query: Query no formato DSL do ElasticSearch
            size:  Número máximo de resultados

        Returns:
            Resposta bruta do ElasticSearch com hits
        """
        try:
            response = self.client.search(
                index=self.index_name,
                body=query,
                size=size,
            )
            # Compatibilidade com diferentes versões do cliente ES
            return response.body if hasattr(response, "body") else dict(response)

        except Exception as exc:
            logger.error(f"❌ Erro na busca: {exc}")
            return {"hits": {"hits": []}}

    # ─────────────────────────────────────────────────────────
    # Estatísticas
    # ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Retorna estatísticas do índice."""
        try:
            index_name = self.index_name

            if not self.client.indices.exists(index=index_name):
                return {"docs_count": 0, "store_size_bytes": 0, "store_size_mb": 0.0}

            stats  = self.client.indices.stats(index=index_name)
            totals = stats["indices"][index_name]["total"]

            return {
                "docs_count":       totals["docs"]["count"],
                "docs_deleted":     totals["docs"]["deleted"],
                "store_size_bytes": totals["store"]["size_in_bytes"],
                "store_size_mb":    round(totals["store"]["size_in_bytes"] / 1_048_576, 2)
            }
        except Exception as exc:
            logger.error(f"❌ Erro ao obter stats do ES: {exc}")
            return {"docs_count": 0, "store_size_bytes": 0, "store_size_mb": 0.0}


# ─────────────────────────────────────────────────────────────
# Instância global — Singleton Pattern
# Use: from src.storage.elastic_client import es_client
# ─────────────────────────────────────────────────────────────
es_client = ElasticSearchClient()
