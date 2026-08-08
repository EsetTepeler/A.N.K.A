# A.N.K.A gorev kisayollari (Windows / GNU Make)
# Kullanim: make dev, make cli, make up ...

SHELL := cmd.exe
PY := .venv\Scripts\python.exe

.PHONY: help install run cli up down logs health reset

help:
	@echo Kullanilabilir hedefler:
	@echo   make install  - venv olustur ve bagimliliklari kur
	@echo   make run      - Core API'yi lokalde baslat (reload modunda)
	@echo   make cli      - test CLI'ini ac (ayri terminalde)
	@echo   make up       - docker compose ile tum sistemi baslat
	@echo   make down     - docker compose'u durdur
	@echo   make logs     - core servisinin loglarini izle
	@echo   make health   - saglik kontrolu
	@echo   make reset    - 'default' oturumunun baglamini sifirla
	@echo   make index    - kod projelerini yeniden indexle
	@echo   make rag      - RAG durumunu goster

install:
	python -m venv .venv
	$(PY) -m pip install -r core\requirements.txt websockets

run:
	$(PY) -m uvicorn app.main:app --reload --port 8000 --app-dir core

cli:
	$(PY) cli.py

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f core

health:
	curl http://localhost:8000/health

reset:
	curl -X POST http://localhost:8000/session/default/reset

index:
	curl -X POST http://localhost:8000/rag/reindex

rag:
	curl http://localhost:8000/rag/status
