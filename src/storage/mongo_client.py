"""
Cliente MongoDB para persistência de documentos e chunks.

Responsabilidades:
- Armazenar documentos brutos (PDF, TXT, URLs, etc.)
- Armazenar chunks de texto processados
- Controlar quais documentos já foram indexados (deduplicação)
- Rastrear quais chunks já foram enviados ao ElasticSearch

Coleções MongoDB:
┌─────────────────────────────────────────────────────┐
│ documents  → Documento completo + metadados          │
│ chunks     → Pedaços do documento prontos para busca │
└─────────────────────────────────────────────────────┘
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from loguru import logger
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from src.config import settings


class MongoDBClient:
    """
    Gerencia conexão e operações no MongoDB.

    Uso:
        mongo_client.connect()
        doc_id = mongo_client.save_document(source="file.pdf", content="...")
        mongo_client.disconnect()
    """

    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    # ─────────────────────────────────────────────────────────
    # Conexão
    # ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Conecta ao MongoDB e verifica a conexão via ping."""
        try:
            self._client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5_000,  # 5s de timeout
                connectTimeoutMS=5_000
            )
            # Ping real para verificar se o servidor responde
            self._client.admin.command("ping")
            self._db = self._client[settings.mongodb_db_name]
            logger.info(
                f"✅ MongoDB conectado | DB: '{settings.mongodb_db_name}'"
            )
        except Exception as exc:
            logger.error(f"❌ Falha ao conectar ao MongoDB: {exc}")
            raise

    def disconnect(self) -> None:
        """Fecha a conexão com o MongoDB."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("🔌 MongoDB desconectado")

    def _ensure_connected(self) -> None:
        if self._db is None:
            raise RuntimeError(
                "MongoDB não conectado. Chame connect() primeiro."
            )

    # ─────────────────────────────────────────────────────────
    # Índices (otimizam a velocidade das queries)
    # ─────────────────────────────────────────────────────────

    def create_indexes(self) -> None:
        """
        Cria índices para otimizar consultas.

        Índices criados:
        - documents.hash (unique)  → evita duplicatas
        - documents.source         → busca por origem
        - documents.created_at     → ordenação cronológica
        - chunks.document_id       → busca de chunks por documento
        - chunks.indexed_in_es     → controle de indexação no ES
        """
        self._ensure_connected()

        # Índices na coleção 'documents'
        self.documents.create_index("hash", unique=True, sparse=True)
        self.documents.create_index("source")
        self.documents.create_index("created_at")

        # Índices na coleção 'chunks'
        self.chunks.create_index("document_id")
        self.chunks.create_index("indexed_in_es")
        self.chunks.create_index([("document_id", 1), ("chunk_index", 1)])

        logger.info("✅ Índices MongoDB criados")

    # ─────────────────────────────────────────────────────────
    # Collections (propriedades para acesso fácil)
    # ─────────────────────────────────────────────────────────

    @property
    def documents(self) -> Collection:
        self._ensure_connected()
        return self._db["documents"]

    @property
    def chunks(self) -> Collection:
        self._ensure_connected()
        return self._db["chunks"]

    # ─────────────────────────────────────────────────────────
    # Operações em Documents
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(content: str) -> str:
        """
        Gera hash SHA-256 do conteúdo.

        Usado para deduplicação: se o hash já existe no banco,
        o documento já foi processado anteriormente.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def document_exists(self, content_hash: str) -> bool:
        """Verifica se um documento já foi processado."""
        return self.documents.find_one({"hash": content_hash}) is not None

    def save_document(
        self,
        source: str,
        content: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Salva um documento bruto no MongoDB.

        Args:
            source:   Origem (caminho do arquivo, URL, etc.)
            content:  Conteúdo textual extraído
            metadata: Informações extras (tipo, tamanho, autor, etc.)

        Returns:
            ID do documento (string do ObjectId)
        """
        content_hash = self._compute_hash(content)

        # Deduplicação: retorna o ID existente se já foi processado
        if self.document_exists(content_hash):
            existing = self.documents.find_one({"hash": content_hash})
            logger.warning(f"⚠️  Documento já existe: {source}")
            return str(existing["_id"])

        document = {
            "source":      source,
            "content":     content,
            "hash":        content_hash,
            "metadata":    metadata or {},
            "chunks_count": 0,             # Atualizado após chunking
            "created_at":  datetime.now(timezone.utc),
            "processed":   False           # True após embedding + indexação
        }

        result = self.documents.insert_one(document)
        doc_id = str(result.inserted_id)
        logger.info(f"📄 Documento salvo | ID: {doc_id} | Origem: {source}")
        return doc_id

    def update_document(self, document_id: str, update_data: dict) -> None:
        """Atualiza campos de um documento."""
        self.documents.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": update_data}
        )

    def get_all_documents(self) -> list[dict]:
        """Retorna todos os documentos (sem o conteúdo bruto para economizar memória)."""
        return list(self.documents.find(
            {},
            {"content": 0}  # Exclui o campo content da resposta
        ))

    # ─────────────────────────────────────────────────────────
    # Operações em Chunks
    # ─────────────────────────────────────────────────────────

    def save_chunks(self, chunks: list[dict]) -> list[str]:
        """
        Salva múltiplos chunks no MongoDB.

        Cada chunk representa um pedaço de texto do documento,
        pronto para ser embedding-ado e indexado no ElasticSearch.

        Args:
            chunks: Lista de dicts com 'content', 'document_id',
                    'chunk_index', e opcionalmente 'metadata'

        Returns:
            Lista de IDs dos chunks inseridos
        """
        if not chunks:
            return []

        now = datetime.now(timezone.utc)
        for chunk in chunks:
            chunk.setdefault("metadata", {})
            chunk["created_at"] = now
            chunk["indexed_in_es"] = False   # Controle de indexação

        result = self.chunks.insert_many(chunks)
        ids = [str(inserted_id) for inserted_id in result.inserted_ids]
        logger.info(f"🧩 {len(chunks)} chunks salvos no MongoDB")
        return ids

    def get_unindexed_chunks(self, batch_size: int = 100) -> list[dict]:
        """
        Retorna chunks que ainda não foram indexados no ElasticSearch.

        Útil para processar em lotes (batch processing):
            while chunks := mongo_client.get_unindexed_chunks():
                embedder.process(chunks)
        """
        return list(
            self.chunks.find({"indexed_in_es": False}).limit(batch_size)
        )

    def mark_chunks_as_indexed(self, chunk_ids: list[str]) -> None:
        """
        Marca chunks como já indexados no ElasticSearch.
        Evita reindexação desnecessária.
        """
        object_ids = [ObjectId(cid) for cid in chunk_ids]
        self.chunks.update_many(
            {"_id": {"$in": object_ids}},
            {
                "$set": {
                    "indexed_in_es": True,
                    "indexed_at": datetime.now(timezone.utc)
                }
            }
        )
        logger.debug(f"✅ {len(chunk_ids)} chunks marcados como indexados")

    def get_stats(self) -> dict:
        """Retorna estatísticas do banco de dados."""
        return {
            "total_documents": self.documents.count_documents({}),
            "processed_documents": self.documents.count_documents({"processed": True}),
            "total_chunks": self.chunks.count_documents({}),
            "indexed_chunks": self.chunks.count_documents({"indexed_in_es": True}),
            "pending_chunks": self.chunks.count_documents({"indexed_in_es": False}),
        }


# ─────────────────────────────────────────────────────────────
# Instância global — Singleton Pattern
# Use: from src.storage.mongo_client import mongo_client
# ─────────────────────────────────────────────────────────────
mongo_client = MongoDBClient()
