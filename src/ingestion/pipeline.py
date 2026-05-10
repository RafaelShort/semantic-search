"""
Pipeline de ingestão de documentos.

Fluxo completo: extrai texto, divide em chunks, salva documento + chunks
"""

from pathlib import Path
from typing import Optional

from loguru import logger
from tqdm import tqdm

from src.ingestion.loaders import DocumentData, DocumentLoader
from src.ingestion.chunker import Chunk, TextChunker
from src.storage.mongo_client import mongo_client


class IngestionPipeline:
    """
    Orquestra o fluxo completo de ingestão.
    """

    def __init__(self):
        self.loader  = DocumentLoader()
        self.chunker = TextChunker()

    def setup(self) -> None:
        """Inicializa conexões com banco de dados."""
        mongo_client.connect()
        mongo_client.create_indexes()
        logger.info("Pipeline de ingestão inicializado")

    def teardown(self) -> None:
        """Fecha conexões."""
        mongo_client.disconnect()
        logger.info("Pipeline encerrado")

    # Métodos públicos de ingestão

    def ingest_file(self, file_path: str) -> Optional[str]:
        """
        Ingere um único arquivo.

        Returns:
            document_id se bem-sucedido, None se falhar
        """
        logger.info(f"📥 Ingerindo arquivo: {file_path}")
        doc = self.loader.load(file_path)

        if not doc:
            return None

        return self._process_document(doc)

    def ingest_url(self, url: str) -> Optional[str]:
        """
        Ingere uma página web.
        """
        logger.info(f"Ingerindo URL: {url}")
        doc = self.loader.load(url)

        if not doc:
            return None

        return self._process_document(doc)

    def ingest_directory(
        self,
        directory: str,
        recursive: bool = False
    ) -> dict:
        """
        Ingere todos os documentos de uma pasta.
        """
        logger.info(f"Ingerindo diretório: {directory}")
        documents = self.loader.load_directory(directory, recursive)

        if not documents:
            logger.warning("Nenhum documento encontrado na pasta")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        stats = {"total": len(documents), "success": 0, "failed": 0, "skipped": 0}

        # tqdm mostra barra de progresso no terminal
        for doc in tqdm(documents, desc="Ingerindo documentos", unit="doc"):
            try:
                doc_id = self._process_document(doc)
                if doc_id:
                    stats["success"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                logger.error(f"Erro ao processar '{doc.source}': {exc}")
                stats["failed"] += 1

        logger.info(
            f"Ingestão concluída | "
            f"Sucesso: {stats['success']} | "
            f"Ignorados: {stats['skipped']} | "
            f"Falhas: {stats['failed']}"
        )

        return stats

    # Processamento interno

    def _process_document(self, doc: DocumentData) -> Optional[str]:
        """
        Processa um DocumentData:
        1. Salva o documento bruto no MongoDB
        2. Gera os chunks
        3. Salva os chunks no MongoDB
        """
        if not doc.is_valid():
            logger.warning(f"Documento inválido ou vazio: {doc.source}")
            return None

        # 1. Salva documento bruto no MongoDB
        document_id = mongo_client.save_document(
            source=doc.source,
            content=doc.content,
            metadata=doc.metadata
        )

        # 2. Gera chunks
        chunks = self.chunker.chunk_document(doc, document_id)

        if not chunks:
            logger.warning(f"Nenhum chunk gerado para: {doc.source}")
            return document_id

        # 3. Salva chunks no MongoDB
        chunk_dicts = [chunk.to_dict() for chunk in chunks]
        mongo_client.save_chunks(chunk_dicts)

        # 4. Atualiza contagem de chunks no documento
        mongo_client.update_document(document_id, {
            "chunks_count": len(chunks),
            "processed":    False   # False = ainda não tem embeddings
        })

        # Mostra estatísticas dos chunks
        stats = self.chunker.get_stats(chunks)
        logger.info(
            f"   Chunks: {stats['total_chunks']} | "
            f"Tamanho médio: {stats['avg_size_chars']} chars"
        )

        return document_id
