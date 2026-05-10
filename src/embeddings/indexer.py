"""
Indexer — busca chunks pendentes no MongoDB,
gera embeddings e indexa no ElasticSearch.

Fluxo:
    MongoDB (chunks sem embedding)
         │
         ▼
    TextEmbedder (gera vetores)
         │
         ▼
    ElasticSearch (indexa chunk + vetor)
         │
         ▼
    MongoDB (marca chunks como indexados ✅)
"""

from loguru import logger
from tqdm import tqdm

from src.embeddings.embedder import embedder
from src.storage.mongo_client import mongo_client
from src.storage.elastic_client import es_client


class EmbeddingIndexer:
    """
    Orquestra o processo de embedding + indexação.

    Processa chunks em lotes para otimizar:
    - Memória RAM (não carrega tudo de uma vez)
    - Velocidade (batch embedding é mais rápido)
    - Resiliência (falha em um lote não afeta os outros)

    Uso:
        indexer = EmbeddingIndexer()
        indexer.setup()
        stats = indexer.run()
        indexer.teardown()
    """

    def __init__(self, batch_size: int = 32):
        """
        Args:
            batch_size: Quantos chunks processar por vez.
                        Valores maiores = mais rápido, mais RAM.
                        Valores menores = mais lento, menos RAM.
        """
        self.batch_size = batch_size

    def setup(self) -> None:
        """Inicializa conexões."""
        mongo_client.connect()
        mongo_client.create_indexes()
        es_client.connect()
        es_client.create_index()
        logger.info("🚀 Indexer inicializado")

    def teardown(self) -> None:
        """Fecha conexões."""
        mongo_client.disconnect()
        logger.info("👋 Indexer encerrado")

    def run(self) -> dict:
        """
        Executa o pipeline completo de embedding + indexação.

        Fluxo por lote:
        1. Busca chunks pendentes no MongoDB
        2. Extrai os textos
        3. Gera embeddings em lote
        4. Monta documentos para o ElasticSearch
        5. Envia para o ElasticSearch (Bulk API)
        6. Marca chunks como indexados no MongoDB

        Returns:
            Estatísticas da execução
        """
        stats = {
            "total_processed": 0,
            "total_indexed":   0,
            "total_failed":    0,
            "batches":         0,
        }

        # Conta total de chunks pendentes para a barra de progresso
        pending_count = mongo_client.chunks.count_documents(
            {"indexed_in_es": False}
        )

        if pending_count == 0:
            logger.info("ℹ️  Nenhum chunk pendente para indexar")
            return stats

        logger.info(f"📋 {pending_count} chunks pendentes para indexar")

        # Barra de progresso geral
        with tqdm(
            total=pending_count,
            desc="Indexando chunks",
            unit="chunk"
        ) as progress_bar:

            # Processa em lotes até não haver mais pendentes
            while True:
                # Busca próximo lote
                batch = mongo_client.get_unindexed_chunks(
                    batch_size=self.batch_size
                )

                if not batch:
                    break  # Todos os chunks foram processados

                stats["batches"] += 1
                batch_success, batch_failed = self._process_batch(batch)

                stats["total_processed"] += len(batch)
                stats["total_indexed"]   += batch_success
                stats["total_failed"]    += batch_failed

                progress_bar.update(len(batch))

        logger.info(
            f"✅ Indexação concluída | "
            f"Indexados: {stats['total_indexed']} | "
            f"Falhas: {stats['total_failed']} | "
            f"Lotes: {stats['batches']}"
        )

        return stats

    def _process_batch(self, chunks: list[dict]) -> tuple[int, int]:
        """
        Processa um lote de chunks.

        Args:
            chunks: Lista de dicts vindos do MongoDB

        Returns:
            Tuple (sucessos, falhas)
        """
        try:
            # 1. Extrai textos do lote
            texts = [chunk["content"] for chunk in chunks]

            # 2. Gera embeddings em lote
            vectors = embedder.embed_batch(
                texts,
                batch_size=self.batch_size,
                show_progress=False  # Progresso já mostrado pelo tqdm externo
            )

            if len(vectors) != len(chunks):
                logger.error(
                    f"❌ Mismatch: {len(chunks)} chunks, "
                    f"{len(vectors)} embeddings"
                )
                return 0, len(chunks)

            # 3. Monta documentos para o ElasticSearch
            es_documents = []
            for chunk, vector in zip(chunks, vectors):
                es_doc = {
                    "content":           chunk["content"],
                    "content_embedding": vector,
                    "document_id":       chunk["document_id"],
                    "mongo_chunk_id":    str(chunk["_id"]),
                    "source":            chunk.get("source", ""),
                    "chunk_index":       chunk.get("chunk_index", 0),
                    "metadata":          chunk.get("metadata", {}),
                }
                es_documents.append(es_doc)

            # 4. Envia para o ElasticSearch (Bulk API)
            success_count, error_count = es_client.bulk_index(es_documents)

            # 5. Marca chunks como indexados no MongoDB
            if success_count > 0:
                chunk_ids = [str(chunk["_id"]) for chunk in chunks]
                mongo_client.mark_chunks_as_indexed(chunk_ids)

            return success_count, error_count

        except Exception as exc:
            logger.error(f"❌ Erro no lote: {exc}")
            return 0, len(chunks)
