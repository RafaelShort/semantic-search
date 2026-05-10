"""
Aplicação FastAPI principal.

Inicializa a API com:
- Conexões com banco de dados
- Middleware de CORS
- Rotas registradas
- Documentação automática (Swagger)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.api.routes import router, search_engine
from src.storage.mongo_client import mongo_client
from src.storage.elastic_client import es_client


# ─────────────────────────────────────────────────────────────
# Lifecycle — startup e shutdown da aplicação
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    STARTUP:  inicializa conexões
    SHUTDOWN: fecha conexões graciosamente
    """
    # ── STARTUP ──────────────────────────────────────────────
    logger.info("🚀 Iniciando Motor de Busca Semântico...")

    mongo_client.connect()
    mongo_client.create_indexes()
    logger.info("✅ MongoDB conectado")

    es_client.connect()
    es_client.create_index()
    logger.info("✅ ElasticSearch conectado")

    search_engine.setup()
    logger.info("✅ Motor de busca pronto")

    logger.info("🎉 API iniciada com sucesso!")
    logger.info("📖 Documentação: http://localhost:8000/docs")

    yield  # API fica ativa aqui

    # ── SHUTDOWN ──────────────────────────────────────────────
    logger.info("👋 Encerrando API...")
    mongo_client.disconnect()
    logger.info("✅ Conexões encerradas")


# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="🔍 Motor de Busca Semântico",
    description="""
API REST para busca semântica em documentos.

## Funcionalidades

- **Busca Semântica** — encontra documentos por significado, não apenas palavras
- **Busca Híbrida** — combina semântica + palavras-chave
- **Ingestão** — adicione documentos via upload ou URL
- **Multi-formato** — suporta PDF, TXT, DOCX e páginas web

## Como usar

1. Ingira documentos via `/ingest/file` ou `/ingest/url`
2. Busque via `/search`
3. Monitore via `/stats` e `/health`
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
)

# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Em produção, especifique os domínios permitidos
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Rotas
# ─────────────────────────────────────────────────────────────

app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["Sistema"])
async def root():
    """Redirect para documentação."""
    return {
        "message": "🔍 Motor de Busca Semântico",
        "docs":    "http://localhost:8000/docs",
        "health":  "http://localhost:8000/api/v1/health",
    }
