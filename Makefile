.PHONY: help up down logs verify install clean restart

help:  ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up:  ## Sobe todos os serviços Docker
	@echo "Iniciando serviços..."
	docker compose up -d
	@echo "Aguardando serviços inicializarem (40s)..."
	@sleep 40
	@$(MAKE) verify

down:  ## Para todos os serviços Docker
	docker compose down

restart:  ## Reinicia os serviços
	docker compose restart

logs:  ## Exibe logs dos serviços
	docker compose logs -f

verify:  ## Verifica se a infraestrutura está funcionando
	python scripts/verify_setup.py

install:  ## Instala dependências Python
	pip install -r requirements.txt

clean:  ## Remove containers e volumes
	@echo "Isso vai apagar todos os dados. Tem certeza? [y/N]" && read ans && [ $${ans:-N} = y ]
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
