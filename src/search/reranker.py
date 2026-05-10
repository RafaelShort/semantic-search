"""
Reranker reordena resultados por relevância contextual.
    A busca inicial retorna candidatos por similaridade.
    O reranker refina a ordem levando em conta:
    - Diversidade (evita chunks muito similares entre si)
    - Posição no documento (chunks do início tendem a ser mais relevantes)
    - Tamanho do chunk (chunks maiores tendem a ter mais contexto)
"""

from loguru import logger
from src.search.engine import SearchResult


class ResultReranker:
    """
    Reordena e filtra resultados de busca.
    """

    def rerank(
        self,
        results:          list[SearchResult],
        query:            str,
        diversity_penalty: float = 0.1,
    ) -> list[SearchResult]:
        """
        Aplica reranking nos resultados.

        Args:
            results:           Lista de SearchResult a reordenar
            query:             Query original (para análise)
            diversity_penalty: Penalidade para chunks do mesmo documento
        """
        if not results:
            return results

        # Aplica penalidade de diversidade
        results = self._apply_diversity_penalty(results, diversity_penalty)

        # Reordena por score final
        results.sort(key=lambda r: r.score, reverse=True)

        logger.debug(f"Reranking aplicado em {len(results)} resultados")
        return results

    def _apply_diversity_penalty(
        self,
        results:  list[SearchResult],
        penalty:  float,
    ) -> list[SearchResult]:
        """
        Penaliza chunks do mesmo documento que já apareceram.
        """
        seen_sources: dict[str, int] = {}

        for result in results:
            source_key = result.source
            count = seen_sources.get(source_key, 0)

            if count > 0:
                # Aplica penalidade proporcional à repetição
                result.score *= (1.0 - penalty * count)

            seen_sources[source_key] = count + 1

        return results

    def deduplicate(
        self,
        results:    list[SearchResult],
        threshold:  float = 0.95,
    ) -> list[SearchResult]:
        """
        Remove resultados quase idênticos.

        Dois resultados são considerados duplicatas se
        compartilham mais de `threshold` % do texto.

        Args:
            results:   Lista de resultados
            threshold: Similaridade mínima para considerar duplicata
        """
        unique = []

        for result in results:
            is_duplicate = False
            for unique_result in unique:
                similarity = self._text_overlap(
                    result.content,
                    unique_result.content
                )
                if similarity >= threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(result)

        if len(unique) < len(results):
            logger.debug(
                f"Deduplicação: {len(results)} → {len(unique)} resultados"
            )

        return unique

    def _text_overlap(self, text1: str, text2: str) -> float:
        """
        Calcula sobreposição de palavras entre dois textos.
        Retorna valor entre 0.0 (nenhuma) e 1.0 (idênticos).
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union        = words1 | words2

        return len(intersection) / len(union)
