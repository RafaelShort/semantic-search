#!/usr/bin/env python3
"""
Script de ingestão de documentos.

Uso no PowerShell:
    # Ingerir toda a pasta sample_docs:
    python scripts/ingest_documents.py --directory data/sample_docs

    # Ingerir um arquivo específico:
    python scripts/ingest_documents.py --file documento.pdf

    # Ingerir uma URL:
    python scripts/ingest_documents.py --url https://exemplo.com

    # Ver estatísticas do banco:
    python scripts/ingest_documents.py --stats
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.ingestion.pipeline import IngestionPipeline
from src.storage.mongo_client import mongo_client

console = Console()


@click.command()
@click.option("--directory", "-d", default=None, help="Pasta com documentos")
@click.option("--file",      "-f", default=None, help="Arquivo específico")
@click.option("--url",       "-u", default=None, help="URL para ingerir")
@click.option("--stats",     "-s", is_flag=True,  help="Mostra estatísticas")
def main(directory, file, url, stats):

    console.print()
    console.print(Panel.fit(
        "[bold blue]📥 Pipeline de Ingestão[/bold blue]\n"
        "[dim]Motor de Busca Semântico — Etapa 2[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))
    console.print()

    pipeline = IngestionPipeline()

    try:
        pipeline.setup()

        # ── Mostrar estatísticas ───────────────────────────
        if stats:
            _show_stats()
            return

        # ── Ingerir diretório ──────────────────────────────
        if directory:
            console.print(f"📂 Ingerindo diretório: [cyan]{directory}[/cyan]\n")
            result = pipeline.ingest_directory(directory)
            _show_ingestion_result(result)

        # ── Ingerir arquivo ───────────────────────────────
        elif file:
            console.print(f"📄 Ingerindo arquivo: [cyan]{file}[/cyan]\n")
            doc_id = pipeline.ingest_file(file)
            if doc_id:
                console.print(f"✅ Documento salvo | ID: [green]{doc_id}[/green]")
            else:
                console.print("❌ Falha ao ingerir arquivo", style="red")

        # ── Ingerir URL ───────────────────────────────────
        elif url:
            console.print(f"🌐 Ingerindo URL: [cyan]{url}[/cyan]\n")
            doc_id = pipeline.ingest_url(url)
            if doc_id:
                console.print(f"✅ URL salva | ID: [green]{doc_id}[/green]")
            else:
                console.print("❌ Falha ao ingerir URL", style="red")

        # ── Nenhuma opção passada ──────────────────────────
        else:
            console.print(
                "[yellow]ℹ️  Nenhuma fonte especificada.\n\n"
                "Exemplos de uso:[/yellow]\n"
                "  python scripts/ingest_documents.py [cyan]--directory data/sample_docs[/cyan]\n"
                "  python scripts/ingest_documents.py [cyan]--file documento.pdf[/cyan]\n"
                "  python scripts/ingest_documents.py [cyan]--url https://exemplo.com[/cyan]\n"
                "  python scripts/ingest_documents.py [cyan]--stats[/cyan]"
            )

    finally:
        pipeline.teardown()


def _show_ingestion_result(result: dict) -> None:
    table = Table(border_style="dim", show_header=True, header_style="bold cyan")
    table.add_column("Métrica",    style="cyan")
    table.add_column("Valor",      style="bold", justify="right")

    table.add_row("Total encontrado",  str(result["total"]))
    table.add_row("✅ Sucesso",        f"[green]{result['success']}[/green]")
    table.add_row("⏭️  Ignorados",     f"[yellow]{result['skipped']}[/yellow]")
    table.add_row("❌ Falhas",         f"[red]{result['failed']}[/red]")

    console.print(table)


def _show_stats() -> None:
    mongo_client.connect()
    stats = mongo_client.get_stats()
    mongo_client.disconnect()

    table = Table(border_style="dim", show_header=True, header_style="bold cyan")
    table.add_column("Métrica",    style="cyan")
    table.add_column("Valor",      style="bold", justify="right")

    table.add_row("Total de documentos",     str(stats["total_documents"]))
    table.add_row("Documentos processados",  str(stats["processed_documents"]))
    table.add_row("Total de chunks",         str(stats["total_chunks"]))
    table.add_row("Chunks indexados no ES",  str(stats["indexed_chunks"]))
    table.add_row("Chunks pendentes",        str(stats["pending_chunks"]))

    console.print(table)


if __name__ == "__main__":
    main()
