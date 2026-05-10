#!/usr/bin/env python3
"""
Script de teste da busca — usa direto no terminal sem precisar da API.

Uso no PowerShell:
    python scripts/search_test.py
    python scripts/search_test.py --query "machine learning"
    python scripts/search_test.py --query "índice invertido" --mode keyword
    python scripts/search_test.py --query "redes neurais" --top-k 3
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from src.search.engine import SearchEngine
from src.search.reranker import ResultReranker
from src.storage.elastic_client import es_client

console = Console()


@click.command()
@click.option("--query", "-q", default=None,    help="Texto da busca")
@click.option("--mode",  "-m", default="hybrid", help="hybrid | semantic | keyword")
@click.option("--top-k", "-k", default=5,        help="Número de resultados")
@click.option("--interactive", "-i", is_flag=True, help="Modo interativo")
def main(query, mode, top_k, interactive):

    console.print()
    console.print(Panel.fit(
        "[bold blue]🔍 Teste de Busca Semântica[/bold blue]\n"
        "[dim]Motor de Busca Semântico — Etapa 4[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))
    console.print()

    engine   = SearchEngine()
    reranker = ResultReranker()

    engine.setup()

    if interactive or not query:
        _interactive_mode(engine, reranker, mode, top_k)
    else:
        _run_search(engine, reranker, query, mode, top_k)


def _interactive_mode(engine, reranker, mode, top_k):
    """Modo interativo — fica perguntando queries até o usuário sair."""
    console.print(
        "[dim]Modo interativo ativado. "
        "Digite [bold]sair[/bold] para encerrar.\n[/dim]"
    )

    while True:
        try:
            query = console.input("🔍 [bold cyan]Query:[/bold cyan] ").strip()

            if query.lower() in {"sair", "exit", "quit", "q"}:
                console.print("\n👋 Até logo!")
                break

            if not query:
                continue

            _run_search(engine, reranker, query, mode, top_k)
            console.print()

        except KeyboardInterrupt:
            console.print("\n\n👋 Até logo!")
            break


def _run_search(engine, reranker, query, mode, top_k):
    """Executa e exibe os resultados de uma busca."""
    import time

    console.print(
        f"Buscando: [cyan]'{query}'[/cyan] | "
        f"Modo: [yellow]{mode}[/yellow] | "
        f"Top-K: [yellow]{top_k}[/yellow]\n"
    )

    start = time.time()
    results = engine.search(query, mode=mode, top_k=top_k)
    results = reranker.rerank(results, query=query)
    results = reranker.deduplicate(results)
    elapsed = round((time.time() - start) * 1000, 1)

    if not results:
        console.print("[yellow]⚠️  Nenhum resultado encontrado.[/yellow]")
        return

    console.print(
        f"[green]✅ {len(results)} resultado(s)[/green] "
        f"[dim]em {elapsed}ms[/dim]\n"
    )

    for i, result in enumerate(results, 1):
        # Nome curto da fonte
        source_name = Path(result.source).name if result.source else "desconhecido"

        # Trunca o conteúdo para exibição
        preview = result.content[:400].replace("\n", " ")
        if len(result.content) > 400:
            preview += "..."

        console.print(Panel(
            f"[white]{preview}[/white]\n\n"
            f"[dim]📁 {source_name} | "
            f"Chunk #{result.chunk_index} | "
            f"Score: {result.score:.4f} | "
            f"Tipo: {result.search_type}[/dim]",
            title=f"[bold cyan]#{i}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

    console.print()


if __name__ == "__main__":
    main()
