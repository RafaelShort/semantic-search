"""
Embedder — transforma texto em vetores numéricos.

O que é um embedding?
    Um embedding é uma representação numérica de um texto.
    Textos com significados similares ficam "próximos" no espaço vetorial.

    Exemplo:
    "cachorro"  → [0.12, -0.34, 0.87, ...]  (384 números)
    "cão"       → [0.11, -0.32, 0.85, ...]  (muito próximo!)
    "automóvel" → [-0.45, 0.23, -0.12, ...] (distante)

Modelo usado: all-MiniLM-L6-v2
    - Rápido e leve
    - 384 dimensões
    - Suporte a múltiplos idiomas
    - Ideal para busca semântica
"""

from typing import Optional
from loguru import logger
from sentence_transformers import SentenceTransformer

from src.config import settings


class TextEmbedder:
    """
    Gera embeddings de texto usando Sentence Transformers.

    O modelo é carregado uma única vez (lazy loading)
    e reutilizado para todas as chamadas — evita recarregar
    o modelo a cada embedding gerado.

    Uso:
        embedder = TextEmbedder()
        vector = embedder.embed("texto qualquer")
        vectors = embedder.embed_batch(["texto 1", "texto 2"])
    """

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._model_name = settings.embedding_model_name

    def _load_model(self) -> None:
        """
        Carrega o modelo de embedding (lazy loading).

        O download acontece apenas na primeira vez (~80MB).
        Nas execuções seguintes, usa o cache local.
        """
        if self._model is not None:
            return

        logger.info(f"🧠 Carregando modelo: '{self._model_name}'")
        logger.info("   (Primeira execução pode demorar — baixando modelo...)")

        self._model = SentenceTransformer(self._model_name)

        # Verifica dimensão real do modelo
        test_embedding = self._model.encode("test")
        real_dim = len(test_embedding)

        logger.info(
            f"✅ Modelo carregado | "
            f"Dimensão: {real_dim} | "
            f"Dispositivo: {self._model.device}"
        )

        # Alerta se dimensão divergir da configuração
        if real_dim != settings.embedding_dimension:
            logger.warning(
                f"⚠️  Dimensão real ({real_dim}) diferente da config "
                f"({settings.embedding_dimension}). "
                f"Atualize EMBEDDING_DIMENSION no .env!"
            )

    def embed(self, text: str) -> list[float]:
        """
        Gera embedding de um único texto.

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats representando o vetor
        """
        self._load_model()

        if not text or not text.strip():
            raise ValueError("Texto vazio não pode ser embedding-ado")

        vector = self._model.encode(
            text,
            normalize_embeddings=True,  # Normaliza para cosine similarity
            show_progress_bar=False
        )

        return vector.tolist()

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> list[list[float]]:
        """
        Gera embeddings de múltiplos textos de forma otimizada.

        Processar em lotes é muito mais eficiente que
        chamar embed() individualmente para cada texto.

        Args:
            texts:         Lista de textos
            batch_size:    Quantos textos processar por vez
            show_progress: Exibe barra de progresso

        Returns:
            Lista de vetores (um por texto)
        """
        self._load_model()

        if not texts:
            return []

        # Filtra textos vazios e guarda os índices
        valid_texts  = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)
            else:
                logger.warning(f"⚠️  Texto vazio ignorado no índice {i}")

        if not valid_texts:
            return []

        logger.info(f"🧠 Gerando embeddings para {len(valid_texts)} textos...")

        vectors = self._model.encode(
            valid_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        logger.info(f"✅ {len(vectors)} embeddings gerados")

        return [v.tolist() for v in vectors]

    def get_model_info(self) -> dict:
        """Retorna informações sobre o modelo carregado."""
        self._load_model()
        test_vec = self._model.encode("test")
        return {
            "model_name": self._model_name,
            "dimension":  len(test_vec),
            "device":     str(self._model.device),
            "max_tokens": self._model.max_seq_length,
        }


# ─────────────────────────────────────────────────────────────
# Instância global — Singleton Pattern
# ─────────────────────────────────────────────────────────────
embedder = TextEmbedder()
