"""
Motor de Busca Semântico.

Três modos de busca disponíveis:

1. SEMÂNTICA (semantic)
   Usa embeddings vetoriais para encontrar documentos
   com significado similar, mesmo sem palavras em comum.
   Ex: "veículo" encontra "automóvel", "carro", "carro elétrico"

2. PALAVRAS-CHAVE (keyword)
   Busca tradicional BM25 — exata e rápida.
   Melhor para termos técnicos, nomes próprios, siglas.
   Ex: "Python 3.12" encontra exatamente "Python 3.12"

3. HÍBRIDA (hybrid)  ← Recomendada
   Combina semântica + palavras-chave com pesos configuráveis.
   Aproveita o melhor dos dois mundos.
"""

from dataclasses import dataclass, field
from loguru import logger

from src.embeddings.embedder import embedder
from src.storage.elastic_client import es_client


# ─────────────────────────────────────────────────────────────
# Estrutura de resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """Representa um resultado de busca."""
    chunk_id:    str
    content:     str
    source:      str
    score:       float
    chunk_index: int
    metadata:    dict = field(default_factory=dict)
    search_type: str = "hybrid"

    def to_dict(self) -> dict:
        return {
            "chunk_id":    self.chunk_id,
            "content":     self.content,
            "source":      self.source,
            "score":       round(self.score, 4),
            "chunk_index": self.chunk_index,
            "metadata":    self.metadata,
            "search_type": self.search_type,
        }


# ─────────────────────────────────────────────────────────────
# Motor de Busca
# ─────────────────────────────────────────────────────────────

class SearchEngine:
    """
    Orquestra os três modos de busca.

    Uso:
        engine = SearchEngine()
        engine.setup()

        # Busca híbrida (recomendada)
        results = engine.search("como funciona machine learning")

        # Busca semântica pura
        results = engine.search("redes neurais", mode="semantic")

        # Busca por palavras-chave
        results = engine.search("Python BM25", mode="keyword")
    """

    def __init__(self):
        self._connected = False

    def setup(self) -> None:
        """Inicializa conexão com ElasticSearch."""
        es_client.connect()
        self._connected = True
        logger.info("🔍 Motor de busca inicializado")

    def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight:  float = 0.3,
        min_score:       float = 0.0,
    ) -> list[SearchResult]:
        """
        Executa uma busca e retorna os resultados ordenados por relevância.

        Args:
            query:            Texto da busca
            mode:             "hybrid" | "semantic" | "keyword"
            top_k:            Número máximo de resultados
            semantic_weight:  Peso da busca semântica (0.0 a 1.0)
            keyword_weight:   Peso da busca por palavras-chave (0.0 a 1.0)
            min_score:        Score mínimo para incluir resultado

        Returns:
            Lista de SearchResult ordenada por score (maior primeiro)
        """
        if not query or not query.strip():
            raise ValueError("Query não pode estar vazia")

        logger.info(f"🔍 Buscando: '{query}' | Modo: {mode} | Top-K: {top_k}")

        if mode == "semantic":
            results = self._semantic_search(query, top_k)
        elif mode == "keyword":
            results = self._keyword_search(query, top_k)
        elif mode == "hybrid":
            results = self._hybrid_search(
                query, top_k, semantic_weight, keyword_weight
            )
        else:
            raise ValueError(f"Modo inválido: '{mode}'. Use: semantic, keyword, hybrid")

        # Filtra por score mínimo
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        logger.info(f"✅ {len(results)} resultados encontrados")
        return results

    # ─────────────────────────────────────────────────────────
    # Busca Semântica
    # ─────────────────────────────────────────────────────────

    def _semantic_search(self, query: str, top_k: int) -> list[SearchResult]:
        """
        Busca por similaridade vetorial (kNN).

        Processo:
        1. Converte a query em embedding
        2. Busca os k vetores mais próximos no ElasticSearch
        3. Retorna os chunks correspondentes
        """
        # Converte query em vetor
        query_vector = embedder.embed(query)

        # Query kNN no ElasticSearch
        es_query = {
            "knn": {
                "field":         "content_embedding",
                "query_vector":  query_vector,
                "k":             top_k,
                "num_candidates": top_k * 10,
            },
            "_source": ["content", "source", "chunk_index", "metadata"],
        }

        raw_results = es_client.search(es_query, size=top_k)
        return self._parse_results(raw_results, search_type="semantic")

    # ─────────────────────────────────────────────────────────
    # Busca por Palavras-chave (BM25)
    # ─────────────────────────────────────────────────────────

    def _keyword_search(self, query: str, top_k: int) -> list[SearchResult]:
        """
        Busca tradicional BM25.

        Usa o algoritmo BM25 do ElasticSearch — mesmo algoritmo
        usado por motores de busca como Google e Bing internamente.
        """
        es_query = {
            "query": {
                "multi_match": {
                    "query":  query,
                    "fields": ["content^2", "metadata.title"],
                    "type":   "best_fields",
                    "fuzziness": "AUTO",  # Tolerância a erros de digitação
                }
            },
            "_source": ["content", "source", "chunk_index", "metadata"],
        }

        raw_results = es_client.search(es_query, size=top_k)
        return self._parse_results(raw_results, search_type="keyword")

    # ─────────────────────────────────────────────────────────
    # Busca Híbrida
    # ─────────────────────────────────────────────────────────

    def _hybrid_search(
        self,
        query: str,
        top_k: int,
        semantic_weight: float,
        keyword_weight:  float,
    ) -> list[SearchResult]:
        """
        Combina busca semântica + palavras-chave.

        Estratégia de combinação:
        1. Executa as duas buscas independentemente
        2. Normaliza os scores de cada uma (0 a 1)
        3. Combina com pesos: score = sem*0.7 + kw*0.3
        4. Ordena pelo score combinado
        5. Remove duplicatas (mesmo chunk pode aparecer nas duas buscas)

        Por que 70% semântico + 30% palavras-chave?
        - A busca semântica captura o significado
        - A busca por palavras-chave captura termos exatos
        - O peso semântico maior prioriza intenção sobre exatidão
        """
        # Executa as duas buscas
        semantic_results = self._semantic_search(query, top_k * 2)
        keyword_results  = self._keyword_search(query,  top_k * 2)

        # Normaliza scores para escala 0-1
        semantic_results = self._normalize_scores(semantic_results)
        keyword_results  = self._normalize_scores(keyword_results)

        # Combina resultados usando chunk_id como chave
        combined: dict[str, SearchResult] = {}

        for result in semantic_results:
            combined[result.chunk_id] = result
            combined[result.chunk_id].score *= semantic_weight
            combined[result.chunk_id].search_type = "hybrid"

        for result in keyword_results:
            if result.chunk_id in combined:
                # Chunk apareceu nas duas buscas — soma os scores ponderados
                combined[result.chunk_id].score += result.score * keyword_weight
            else:
                # Chunk novo — só da busca por palavras-chave
                result.score *= keyword_weight
                result.search_type = "hybrid"
                combined[result.chunk_id] = result

        # Ordena por score combinado e retorna top_k
        sorted_results = sorted(
            combined.values(),
            key=lambda r: r.score,
            reverse=True
        )

        return sorted_results[:top_k]

    # ─────────────────────────────────────────────────────────
    # Utilitários
    # ─────────────────────────────────────────────────────────

    def _parse_results(
        self,
        raw_results: dict,
        search_type: str
    ) -> list[SearchResult]:
        """Converte resposta do ElasticSearch em SearchResult."""
        results = []
        hits = raw_results.get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit.get("_source", {})
            results.append(SearchResult(
                chunk_id=    hit["_id"],
                content=     source.get("content", ""),
                source=      source.get("source", ""),
                score=       hit.get("_score", 0.0) or 0.0,
                chunk_index= source.get("chunk_index", 0),
                metadata=    source.get("metadata", {}),
                search_type= search_type,
            ))

        return results

    def _normalize_scores(
        self,
        results: list[SearchResult]
    ) -> list[SearchResult]:
        """
        Normaliza scores para escala 0-1.
        Necessário para combinar buscas com escalas diferentes.
        """
        if not results:
            return results

        max_score = max(r.score for r in results)
        min_score = min(r.score for r in results)
        score_range = max_score - min_score

        if score_range == 0:
            for r in results:
                r.score = 1.0
        else:
            for r in results:
                r.score = (r.score - min_score) / score_range

        return results
