<div align="center">

# Motor de Busca Semântico

### Busca inteligente por significado, não apenas palavras-chave

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ElasticSearch](https://img.shields.io/badge/ElasticSearch-8.11-005571?style=for-the-badge&logo=elasticsearch&logoColor=white)](https://elastic.co)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)

</div>

---

## Sobre o Projeto

Sistema completo de **busca semântica** que encontra documentos por **significado**, não apenas por palavras exatas.

> Exemplo: buscar *"como computadores entendem texto"* retorna resultados sobre **Processamento de Linguagem Natural** — mesmo sem nenhuma palavra em comum.

Construído com uma stack de **IA com engenharia de dados**, o projeto cobre o pipeline:
da ingestão de documentos até a API REST de busca.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| 🧠 **Busca Semântica** | Encontra documentos por significado usando embeddings vetoriais |
| 🔤 **Busca por Palavras-chave** | Busca tradicional BM25, rápida e precisa |
| ⚡ **Busca Híbrida** | Combina semântica + palavras-chave com pesos configuráveis |
| 📄 **Multi-formato** | Suporta PDF, TXT, DOCX e páginas web (URL) |
| ✂️ **Chunking Inteligente** | Divide documentos com overlap para não perder contexto |
| 🔀 **Reranking** | Reordena resultados por relevância e diversidade |
| 🌐 **API REST** | Endpoints documentados com Swagger UI |
| 🐳 **Docker** | Infraestrutura completa em um comando |

---


---

## Como Executar

### Pré-requisitos

- [Python 3.12+](https://python.org)
- [Docker Desktop](https://docker.com/products/docker-desktop)
- Git

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/semantic-search.git
cd semantic-search
```

### 2. Clonar o repositório

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Ativar (Linux/Mac)
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

### 4. Subir a infraestrutura

```bash
docker compose up -d

python scripts/verify_setup.py
```

### 5. Ingerir documentos de exemplo

```bash
python scripts/ingest_documents.py --directory data/sample_docs
```

### 6. Gerar embeddings e indexar

```bash
python scripts/run_embeddings.py
```

### 7. Iniciar a API

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 8. Acessar
- Interface	URL
- Swagger UI	http://localhost:8000/docs
- ReDoc	http://localhost:8000/redoc
- Kibana	http://localhost:5601
- Mongo Express	http://localhost:8081

## Endpoints da API

### POST /api/v1/search

```json
{
  "query": "como funciona aprendizado de máquina",
  "mode": "hybrid",
  "top_k": 5,
  "semantic_weight": 0.7,
  "keyword_weight": 0.3,
  "rerank": true,
  "deduplicate": true
}
```

Resposta:
```json
{
  "query": "como funciona aprendizado de máquina",
  "mode": "hybrid",
  "total_results": 3,
  "time_ms": 312.4,
  "results": [
    {
      "chunk_id": "abc123",
      "content": "O Aprendizado de Máquina é um subcampo da IA...",
      "source": "inteligencia_artificial.txt",
      "score": 1.0,
      "chunk_index": 1,
      "search_type": "hybrid"
    }
  ]
}
```


### POST /api/v1/ingest/url

```json
{
  "url": "https://pt.wikipedia.org/wiki/Inteligência_artificial"
}
```

### GET /api/v1/health

```json
{
  "status": "healthy",
  "mongodb": true,
  "elasticsearch": true,
  "version": "1.0.0"
}
```

## Testes via Terminal
```bash
# Busca híbrida
python scripts/search_test.py --query "redes neurais"

# Busca semântica pura
python scripts/search_test.py --query "como computadores entendem texto" --mode semantic

# Busca por palavras-chave
python scripts/search_test.py --query "BM25 TF-IDF" --mode keyword

# Modo interativo
python scripts/search_test.py --interactive
```

## Conceitos Aplicados
- Embeddings Vetoriais — representação semântica de textos em espaço de alta dimensão
- Busca kNN Aproximada — algoritmo HNSW do ElasticSearch para busca vetorial eficiente
- BM25 — algoritmo probabilístico de ranking usado pelos maiores motores de busca
- Sliding Window Chunking — divisão de texto com sobreposição para preservar contexto
- Busca Híbrida com RRF — fusão de rankings semântico e léxico
- Padrão Repository — abstração das camadas de storage (MongoDB, ElasticSearch)
- Pipeline Pattern — fluxo de ingestão em etapas desacopladas
