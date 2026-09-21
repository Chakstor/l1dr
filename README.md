# Estimador CAG

API desarrollada con FastAPI que genera estimaciones de proyectos
de software utilizando un LLM y contexto estático (CAG).

## Setup

Instalar dependencias:

uv sync

Crear `.env` a partir de `.env.example` y añadir una API key de OpenAI.

## Run

uv run uvicorn app.main:app --reload

## API

POST /api/v1/estimate

GET /health

Swagger:

http://localhost:8000/docs
