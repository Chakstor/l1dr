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

## Probar con la transcripción de ejemplo

En `samples/estimate_request.json` hay una transcripción de reunión de ejemplo
(clínica dental con 3 sedes que quiere reservas online).

Con el servidor arrancado:

```bash
curl -X POST http://localhost:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d @samples/estimate_request.json
```

También puedes copiar el contenido del JSON en Swagger (`/docs`) → `POST /api/v1/estimate` → _Try it out_.

## Interfaz conversacional (Streamlit)

Interfaz de chat para pegar una transcripción y ver la estimación en streaming.
El panel lateral muestra el system prompt activo, los ejemplos CAG inyectados
y las métricas de la última llamada (tokens, tiempo hasta el primer token y tiempo total).

```bash
uv run streamlit run streamlit_app.py
```

Disponible en `http://localhost:8501`. Usa la misma configuración (`.env`) y la misma
lógica de llamada al LLM que la API.
