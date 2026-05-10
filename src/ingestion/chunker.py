"""
Chunker divide documentos em pedaços menores.

Modelos de embedding têm limite de tokens (~512 tokens).
Documentos grandes precisam ser divididos para serem processados.
Chunks menores promovem embeddings mais precisos e relevantes.
Sliding Window com respeito a parágrafos
"""

from dataclasses import dataclass, field
from loguru import logger

from src.config import settings
from src.ingestion.loaders import DocumentData


@dataclass
class Chunk:
    """
    Representa um pedaço de texto de um documento.
    """
    content:     str          # Texto do chunk
    document_id: str          # ID do documento no MongoDB
    chunk_index: int          # Posição do chunk no documento
    source:      str          # Origem
    metadata:    dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.content)

    def to_dict(self) -> dict:
        """Converte para dict — usado ao salvar no MongoDB."""
        return {
            "content":     self.content,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "source":      self.source,
            "metadata":    self.metadata,
        }


class TextChunker:
    """
    Divide texto em chunks com sobreposição.

    Args:
        chunk_size:    Tamanho máximo de cada chunk em caracteres
        chunk_overlap: Sobreposição entre chunks consecutivos
    """

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) deve ser "
                f"menor que chunk_size ({chunk_size})"
            )

        self.chunk_size    = chunk_size
        self.chunk_overlap = chunk_overlap

        logger.debug(
            f"TextChunker inicializado | "
            f"size={chunk_size} | overlap={chunk_overlap}"
        )

    def chunk_document(
        self,
        document: DocumentData,
        document_id: str
    ) -> list[Chunk]:
        """
        Divide um DocumentData em chunks.

        Args:
            document:    Documento carregado pelo loader
            document_id: ID do documento no MongoDB
        """
        if not document.content or not document.content.strip():
            logger.warning(f"Documento vazio: {document.source}")
            return []

        # Divide o texto em parágrafos primeiro
        paragraphs = self._split_into_paragraphs(document.content)

        # Agrupa parágrafos em chunks do tamanho configurado
        raw_chunks = self._group_paragraphs_into_chunks(paragraphs)

        # Converte strings em objetos Chunk
        chunks = []
        for index, chunk_text in enumerate(raw_chunks):
            chunk = Chunk(
                content=chunk_text,
                document_id=document_id,
                chunk_index=index,
                source=document.source,
                metadata={
                    **document.metadata,
                    "doc_type":    document.doc_type,
                    "chunk_index": index,
                    "chunk_total": len(raw_chunks),
                    "chunk_size":  len(chunk_text),
                }
            )
            chunks.append(chunk)

        logger.info(
            f"Chunking concluído | "
            f"{len(chunks)} chunks | "
            f"Origem: '{document.source.split('/')[-1]}'"
        )

        return chunks

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """
        Divide o texto em parágrafos.
        Parágrafos são separados por linha em branco.
        Parágrafos muito longos são quebrados em sentenças.
        """
        # Divide por linhas em branco
        raw_paragraphs = [
            p.strip()
            for p in text.split("\n\n")
            if p.strip()
        ]

        paragraphs = []
        for para in raw_paragraphs:
            if len(para) <= self.chunk_size:
                # Parágrafo cabe em um chunk
                paragraphs.append(para)
            else:
                # Parágrafo muito longo
                sentences = self._split_into_sentences(para)
                paragraphs.extend(sentences)

        return paragraphs

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Divide um texto longo em sentenças.
        Usado quando um parágrafo é maior que chunk_size.
        """
        import re

        # Divide por pontuação final seguida de espaço e letra maiúscula
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", text)

        result = []
        current = ""

        for sentence in sentences:
            if len(current) + len(sentence) <= self.chunk_size:
                current += (" " if current else "") + sentence
            else:
                if current:
                    result.append(current)
                # Sentença maior que chunk_size
                if len(sentence) > self.chunk_size:
                    result.extend(self._split_by_words(sentence))
                else:
                    current = sentence

        if current:
            result.append(current)

        return result

    def _split_by_words(self, text: str) -> list[str]:
        """
        Último recurso: divide por palavras quando a sentença
        é maior que chunk_size.
        """
        words = text.split()
        chunks = []
        current = ""

        for word in words:
            if len(current) + len(word) + 1 <= self.chunk_size:
                current += (" " if current else "") + word
            else:
                if current:
                    chunks.append(current)
                current = word

        if current:
            chunks.append(current)

        return chunks

    def _group_paragraphs_into_chunks(
        self,
        paragraphs: list[str]
    ) -> list[str]:
        """
        Agrupa parágrafos em chunks com overlap.
        - Avança pelo texto adicionando parágrafos
        - Quando atinge chunk_size, salva e recua chunk_overlap chars
        - Garante que nenhum contexto importante seja perdido nas bordas
        """
        if not paragraphs:
            return []

        chunks     = []
        current    = ""
        overlap_buffer = "" 

        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para

            if len(candidate) <= self.chunk_size:
                # Se couber, adiciona ao chunk atual
                current = candidate
            else:
                # Se não couber, salva chunk atual e inicia novo com overlap
                if current:
                    chunks.append(current)

                    # Overlap: pega os últimos N chars do chunk atual
                    if self.chunk_overlap > 0:
                        overlap_buffer = current[-self.chunk_overlap:]
                        current = (overlap_buffer + "\n\n" + para).strip()
                    else:
                        current = para
                else:
                    # Parágrafo isolado maior que chunk_size
                    current = para

        # Adiciona o último chunk
        if current:
            chunks.append(current)

        return chunks

    def get_stats(self, chunks: list[Chunk]) -> dict:
        """Retorna estatísticas dos chunks gerados."""
        if not chunks:
            return {}

        sizes = [len(c.content) for c in chunks]
        return {
            "total_chunks":   len(chunks),
            "avg_size_chars": round(sum(sizes) / len(sizes)),
            "min_size_chars": min(sizes),
            "max_size_chars": max(sizes),
            "chunk_size_cfg": self.chunk_size,
            "overlap_cfg":    self.chunk_overlap,
        }
