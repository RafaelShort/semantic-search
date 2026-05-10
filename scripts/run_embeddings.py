#!/usr/bin/env python3
"""
Script de geração de embeddings e indexação.

Uso no PowerShell:
    # Processar todos os chunks pendentes:
    python scripts/run_embeddings.py

    # Ver info do modelo:
    python scripts/run_embeddings.py --model-info

    # Recriar índice do zero (APAGA TUDO no ES!):
    python scripts/run_embeddings.py --recreate-index
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.embeddings.indexer import EmbeddingIndexer
from src.embeddings.embedder import embedder
from src.storage.mongo_client import mongo_client
from src.storage.elastic_client import es_client

console = Console()


@click.command()
@click.option("--batch-size",     "-b", default=32,    help="Tamanho do lote")
@click.option("--recreate-index", "-r", is_flag=True,  help="Recria índice ES (apaga dados!)")
@click.option("--model-info",     "-m", is_flag=True,  help="Exibe info do modelo")
def main(batch_size, recreate_index, model_info):

    console.print()
    console.print(Panel.fit(
        "[bold blue] Pipeline de Embeddings[/bold blue]\n"
        "[dim]Motor de Busca Semântico — Etapa 3[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))
    console.print()

    # Informação do modelo
    if model_info:
        console.print("🔍 Carregando informações do modelo...\n")
        info = embedder.get_model_info()
        _show_model_info(info)
        return

    # Recriar índice
    if recreate_index:
        console.print(
            "[bold red]⚠️  Atenção![/bold red] "
            "Isso vai apagar todos os dados do ElasticSearch.\n"
        )
        confirm = console.input("Digite [bold]SIM[/bold] para confirmar: ")
        if confirm.strip().upper() != "SIM":
            console.print("❌ Operação cancelada.")
            return

        es_client.connect()
        es_client.create_index(force_recreate=True)

        # Marca todos os chunks como não indexados no MongoDB
        mongo_client.connect()
        mongo_client.chunks.update_many(
            {},
            {"$set": {"indexed_in_es": False, "indexed_at": None}}
        )
        mongo_client.disconnect()

        console.print("✅ Índice recriado! Rode sem --recreate-index para indexar.\n")
        return

    # Executar indexação
    indexer = EmbeddingIndexer(batch_size=batch_size)

    try:
        indexer.setup()
        stats = indexer.run()
        _show_stats(stats)

        # Mostra estatísticas finais do MongoDB e ES
        console.print()
        _show_final_stats()

    finally:
        indexer.teardown()


def _show_model_info(info: dict) -> None:
    table = Table(border_style="dim", header_style="bold cyan")
    table.add_column("Propriedade", style="cyan")
    table.add_column("Valor",       style="bold")

    table.add_row("Modelo",         info["model_name"])
    table.add_row("Dimensão",       str(info["dimension"]))
    table.add_row("Dispositivo",    info["device"])
    table.add_row("Máx. tokens",    str(info["max_tokens"]))

    console.print(table)


def _show_stats(stats: dict) -> None:
    console.print()
    table = Table(border_style="dim", header_style="bold cyan")
    table.add_column("Métrica",    style="cyan")
    table.add_column("Valor",      style="bold", justify="right")

    table.add_row("Total processado", str(stats["total_processed"]))
    table.add_row("✅ Indexados",     f"[green]{stats['total_indexed']}[/green]")
    table.add_row("❌ Falhas",        f"[red]{stats['total_failed']}[/red]")
    table.add_row("Lotes executados", str(stats["batches"]))

    console.print(table)


def _show_final_stats() -> None:
    mongo_client.connect()
    mongo_stats = mongo_client.get_stats()
    mongo_client.disconnect()

    es_client.connect()
    es_stats = es_client.get_stats()

    table = Table(
        title="📊 Status Atual",
        border_style="dim",
        header_style="bold cyan"
    )
    table.add_column("Onde",      style="cyan")
    table.add_column("Métrica",   style="dim")
    table.add_column("Valor",     style="bold", justify="right")

    table.add_row(
        "MongoDB",
        "Chunks pendentes",
        f"[yellow]{mongo_stats['pending_chunks']}[/yellow]"
    )
    table.add_row(
        "MongoDB",
        "Chunks indexados",
        f"[green]{mongo_stats['indexed_chunks']}[/green]"
    )
    table.add_row(
        "ElasticSearch",
        "Documentos no índice",
        f"[green]{es_stats['docs_count']}[/green]"
    )
    table.add_row(
        "ElasticSearch",
        "Tamanho do índice",
        f"{es_stats['store_size_mb']} MB"
    )

    console.print(table)


if __name__ == "__main__":
    main()
