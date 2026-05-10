"""
Rotas da API FastAPI.

Endpoints disponíveis:
    GET  /health          → Status dos serviços
    GET  /stats           → Estatísticas do sistema
    POST /search          → Busca semântica
    POST /ingest/url      → Ingere uma URL
    POST /ingest/file     → Ingere um arquivo (upload)
"""

import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File
from loguru import logger

from src.api.schemas import (
    SearchRequest, SearchResponse, SearchResultItem,
    IngestRequest, IngestResponse,
    HealthResponse, StatsResponse,
)
from src.search.engine import SearchEngine
from src.search.reranker import ResultReranker
from src.ingestion.pipeline import IngestionPipeline
from src.embeddings.indexer import EmbeddingIndexer
from src.storage.mongo_client import mongo_client
from src.storage.elastic_client import es_client

router = APIRouter()

search_engine = SearchEngine()
reranker      = ResultReranker()

# Health Check

@router.get("/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check():
    """Verifica se todos os serviços estão operacionais."""
    mongo_ok = False
    es_ok    = False

    # MongoDB
    for _attempt in range(2):
        try:
            if _attempt == 0:
                mongo_client._client.admin.command("ping")
            else:
                mongo_client.connect()
            mongo_ok = True
            break
        except Exception:
            continue

    # ElasticSearch
    for _attempt in range(2):
        try:
            if _attempt == 0:
                es_ok = bool(es_client.client.ping())
            else:
                es_client.connect()
                es_ok = True
            break
        except Exception:
            continue

    status = "healthy" if (mongo_ok and es_ok) else "degraded"

    return HealthResponse(
        status=        status,
        mongodb=       mongo_ok,
        elasticsearch= es_ok,
    )


# Estatísticas

@router.get("/stats", response_model=StatsResponse, tags=["Sistema"])
async def get_stats():
    """Retorna estatísticas do sistema."""
    try:
        mongo_stats = mongo_client.get_stats()
        es_stats    = es_client.get_stats()

        return StatsResponse(
            total_documents=     mongo_stats["total_documents"],
            processed_documents= mongo_stats["processed_documents"],
            total_chunks=        mongo_stats["total_chunks"],
            indexed_chunks=      mongo_stats["indexed_chunks"],
            pending_chunks=      mongo_stats["pending_chunks"],
            es_docs_count=       es_stats["docs_count"],
            es_index_size_mb=    es_stats["store_size_mb"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# Busca

@router.post("/search", response_model=SearchResponse, tags=["Busca"])
async def search(request: SearchRequest):
    """
    Executa busca semântica nos documentos indexados.

    **Modos de busca:**
    - `hybrid` *(recomendado)*: Combina semântica + palavras-chave
    - `semantic`: Busca por significado usando embeddings vetoriais
    - `keyword`: Busca tradicional BM25 por palavras exatas
    """
    start_time = time.time()

    if request.mode not in {"hybrid", "semantic", "keyword"}:
        raise HTTPException(
            status_code=400,
            detail=f"Modo inválido: '{request.mode}'. Use: hybrid, semantic, keyword"
        )

    try:
        results = search_engine.search(
            query=           request.query,
            mode=            request.mode,
            top_k=           request.top_k,
            semantic_weight= request.semantic_weight,
            keyword_weight=  request.keyword_weight,
            min_score=       request.min_score,
        )

        if request.rerank and results:
            results = reranker.rerank(results, query=request.query)

        if request.deduplicate and results:
            results = reranker.deduplicate(results)

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return SearchResponse(
            query=         request.query,
            mode=          request.mode,
            total_results= len(results),
            results=[
                SearchResultItem(**r.to_dict())
                for r in results
            ],
            time_ms= elapsed_ms,
        )

    except Exception as exc:
        logger.error(f"❌ Erro na busca: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

# Ingestão

@router.post("/ingest/url", response_model=IngestResponse, tags=["Ingestão"])
async def ingest_url(request: IngestRequest):
    """
    Ingere e indexa o conteúdo de uma URL.
    """
    pipeline = IngestionPipeline()
    indexer  = EmbeddingIndexer()

    try:
        pipeline.setup()
        doc_id = pipeline.ingest_url(request.url)

        if not doc_id:
            raise HTTPException(
                status_code=422,
                detail="Não foi possível extrair conteúdo da URL"
            )

        indexer.setup()
        indexer.run()

        chunks_count = mongo_client.chunks.count_documents(
            {"document_id": doc_id}
        )

        return IngestResponse(
            success=      True,
            document_id=  doc_id,
            message=      "URL ingerida com sucesso",
            chunks_count= chunks_count,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Erro ao ingerir URL: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        pipeline.teardown()


@router.post("/ingest/file", response_model=IngestResponse, tags=["Ingestão"])
async def ingest_file(file: Annotated[UploadFile, File()]):
    """
    Ingere e indexa um arquivo enviado via upload.

    Formatos suportados: .txt, .pdf, .docx, .md
    """
    import tempfile
    import shutil

    allowed_extensions = {".txt", ".pdf", ".docx", ".doc", ".md"}
    file_extension     = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo não suportado: '{file_extension}'. "
                   f"Permitidos: {', '.join(allowed_extensions)}"
        )

    pipeline = IngestionPipeline()
    indexer  = EmbeddingIndexer()
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=file_extension,
            delete=False
        ) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        pipeline.setup()
        doc_id = pipeline.ingest_file(tmp_path)

        if not doc_id:
            raise HTTPException(
                status_code=422,
                detail="Não foi possível processar o arquivo"
            )

        indexer.setup()
        indexer.run()

        chunks_count = mongo_client.chunks.count_documents(
            {"document_id": doc_id}
        )

        return IngestResponse(
            success=      True,
            document_id=  doc_id,
            message=      f"Arquivo '{file.filename}' ingerido com sucesso",
            chunks_count= chunks_count,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"❌ Erro ao ingerir arquivo: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        pipeline.teardown()
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
