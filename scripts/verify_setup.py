#!/usr/bin/env python3
"""
Script de verificação da infraestrutura.

Executa verificações em todos os serviços e exibe um
relatório visual com o status de cada um.

Uso:
    python scripts/verify_setup.py
    # ou
    make verify
"""

import sys
from pathlib import Path
from time import time

# Garante que o diretório raiz está no path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import settings
from src.storage.mongo_client import mongo_client
from src.storage.elastic_client import es_client

console = Console()


def check_mongodb() -> tuple[bool, str, float]:
    """Testa conexão, criação de índices e operação de escrita."""
    start = time()
    try:
        mongo_client.connect()
        mongo_client.create_indexes()

        # Testa escrita real
        mongo_client.save_document(
            source="verify://test",
            content="Documento de verificação — pode ser ignorado",
            metadata={"type": "verification_test"}
        )

        stats = mongo_client.get_stats()
        elapsed = round((time() - start) * 1000, 1)

        return (
            True,
            f"DB: '{settings.mongodb_db_name}' | "
            f"Docs: {stats['total_documents']} | "
            f"{elapsed}ms",
            elapsed
        )
    except Exception as exc:
        return False, str(exc), 0
    finally:
        try:
            mongo_client.disconnect()
        except Exception:
            pass


def check_elasticsearch() -> tuple[bool, str, float]:
    """Testa conexão, criação de índice e estatísticas."""
    start = time()
    try:
        es_client.connect()
        es_client.create_index()

        stats = es_client.get_stats()
        elapsed = round((time() - start) * 1000, 1)

        return (
            True,
            f"Índice: '{settings.elasticsearch_index}' | "
            f"Docs: {stats['docs_count']} | "
            f"{elapsed}ms",
            elapsed
        )
    except Exception as exc:
        return False, str(exc), 0


def main():
    # Header
    console.print()
    console.print(Panel.fit(
        "[bold blue]🔍 Motor de Busca Semântico[/bold blue]\n"
        "[dim]Etapa 1 — Verificação de Infraestrutura[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))
    console.print()

    # Executar verificações
    checks = [
        ("🍃  MongoDB",        check_mongodb),
        ("🔍  ElasticSearch",  check_elasticsearch),
    ]

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for name, check_fn in checks:
            task = progress.add_task(f"Verificando {name}...", total=None)
            success, message, elapsed = check_fn()
            progress.remove_task(task)
            results.append((name, success, message, elapsed))

    # Tabela de resultados
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1)
    )
    table.add_column("Serviço",  style="cyan",  width=20)
    table.add_column("Status",   style="bold",  width=14)
    table.add_column("Detalhes", style="dim")

    all_ok = True
    for name, success, message, _ in results:
        if success:
            status = "[green]✅ ONLINE[/green]"
        else:
            status = "[red]❌ OFFLINE[/red]"
            all_ok = False
        table.add_row(name, status, message)

    console.print(table)
    console.print()

    # Resultado final
    if all_ok:
        console.print(Panel(
            "[bold green]✅ Infraestrutura 100% operacional![/bold green]\n\n"
            "[dim]Acesse as interfaces web:[/dim]\n"
            "  [cyan]•[/cyan] ElasticSearch  → [link]http://localhost:9200[/link]\n"
            "  [cyan]•[/cyan] Kibana         → [link]http://localhost:5601[/link]\n"
            "  [cyan]•[/cyan] Mongo Express  → [link]http://localhost:8081[/link]\n\n"
            "[bold]Próximo passo:[/bold] [yellow]Etapa 2 — Ingestão de Documentos[/yellow]",
            border_style="green",
            padding=(1, 2)
        ))
    else:
        console.print(Panel(
            "[bold red]❌ Alguns serviços estão offline.[/bold red]\n\n"
            "[bold]Passos para resolver:[/bold]\n"
            "  1. [yellow]docker compose up -d[/yellow]\n"
            "  2. Aguarde ~40 segundos\n"
            "  3. [yellow]python scripts/verify_setup.py[/yellow]\n\n"
            "[dim]Se o problema persistir, verifique os logs:[/dim]\n"
            "  [yellow]docker compose logs elasticsearch[/yellow]\n"
            "  [yellow]docker compose logs mongodb[/yellow]",
            border_style="red",
            padding=(1, 2)
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
