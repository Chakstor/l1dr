# Estimador CAG

API desarrollada con FastAPI que genera estimaciones de proyectos
de software utilizando un LLM y contexto estático (CAG).

## Setup

Instalar dependencias:

uv sync

Crear `.env` a partir de `.env.example` y añadir las API keys. Con una basta;
con las dos (OpenAI y Anthropic) funciona el fallback entre proveedores.

## Run

Levantar Redis (caché de respuestas):

```bash
docker compose up -d
```

Arrancar la API:

```bash
uv run uvicorn app.main:app --reload
```

Si Redis no está levantado, la API funciona igual pero sin caché (aparece un
aviso `cache_unavailable` en los logs al arrancar).

## Cómo llama al LLM

Todas las llamadas pasan por `app/services/llm_wrapper.py` (LiteLLM):

- **Fallback:** intenta `PRIMARY_MODEL` y, si falla, `FALLBACK_MODEL`.
- **Reintentos y timeout:** `LLM_RETRIES` y `LLM_TIMEOUT`.
- **Caché exact-match en Redis:** la misma transcripción devuelve la respuesta guardada
  (`cache_hit: true`, `cost_usd: 0`) durante `CACHE_TTL` segundos.
- **Coste:** cada respuesta incluye `cost_usd`, calculado con los precios de LiteLLM.
- **Trazabilidad:** cada petición lleva un `X-Request-ID` (se devuelve en la cabecera
  de la respuesta) que aparece en todos los logs de esa petición.

## API

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/estimate` | Estimación completa en una sola respuesta JSON |
| `POST /api/v1/estimate/stream` | La misma estimación en streaming (Server-Sent Events) |
| `GET /api/v1/context` | System prompt, ejemplos CAG y modelos configurados |
| `GET /health` | Health check |

El endpoint de streaming envía estos eventos SSE, en orden:
`token` (`{"text": ...}`, muchos) → `metrics` (tokens, coste, caché, fallback, latencias) → `done`.
Si el LLM falla, envía un evento `error` (`{"detail": ...}`) y termina.

Probarlo con curl (`-N` desactiva el buffer para ver los eventos según llegan):

```bash
curl -N -X POST http://localhost:8000/api/v1/estimate/stream \
  -H "Content-Type: application/json" \
  -d @samples/estimate_request.json
```

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
y las métricas de la última llamada (tokens, coste, caché, tiempo hasta el primer token y tiempo total).

Streamlit es un **cliente HTTP de la API** (`estimator_client.py`): necesita la API arrancada.

```bash
uv run uvicorn app.main:app --reload      # terminal 1
uv run streamlit run streamlit_app.py     # terminal 2
```

Disponible en `http://localhost:8501`. La URL de la API se configura con
`ESTIMATOR_API_BASE_URL` en el `.env` (por defecto `http://localhost:8000`).
Cada mensaje envía su propio `X-Request-ID`, que se muestra en el panel lateral
y aparece en los logs de la API.
