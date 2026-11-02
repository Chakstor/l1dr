# Estimador CAG

API desarrollada con FastAPI que genera estimaciones de proyectos
de software utilizando un LLM y contexto estático (CAG).

La entrada es un formulario tipado (descripción + tipo de proyecto, nivel de detalle
y formato de salida) y los prompts viven en plantillas Jinja2 versionadas.

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
| `GET /api/v1/context` | Modelos, versión del prompt y opciones válidas del formulario |
| `POST /api/v1/prompt/preview` | El prompt exacto (system, user y ejemplos) que se enviaría al LLM para una petición, sin llamarlo. Desactivado con `APP_ENV=production` |
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

Cuerpo de la petición (los dos endpoints de estimación):

```json
{
  "description": "Descripción o transcripción del proyecto (20–80 000 caracteres)",
  "project_type": "mobile_app | web_saas | internal_tool | data_pipeline",
  "detail_level": "summary | medium | detailed",
  "output_format": "phases_table | line_items | narrative"
}
```

La respuesta de `POST /api/v1/estimate` incluye `text` (la estimación), `prompt_version`
y los metadatos de la llamada: `model`, `provider`, `usage`, `finish_reason`,
`latency_ms`, `cost_usd` y `cache_hit`.

## Prompts versionados

```
app/prompts/
├── loader.py              # render_estimation_prompt(request, version="v1") -> (system, user)
└── estimation/
    └── v1/
        ├── system.j2      # rol, alcance, formato de salida y nivel de detalle (condicionales)
        ├── user.j2        # la descripción del proyecto en <project_description>
        └── examples.j2    # ejemplos few-shot (CAG), incluidos en system.j2
```

Para crear una versión nueva se copia `v1/` a `v2/`, se modifica y se cambia
`PROMPT_VERSION` en `app/services/llm_service.py`. Cada respuesta indica qué versión la generó.

## Probar con la transcripción de ejemplo

En `samples/estimate_request.json` hay una petición de ejemplo con la transcripción
de una reunión (clínica dental con 3 sedes que quiere reservas online).

Con el servidor arrancado:

```bash
curl -X POST http://localhost:8000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d @samples/estimate_request.json
```

También puedes copiar el contenido del JSON en Swagger (`/docs`) → `POST /api/v1/estimate` → _Try it out_.

## Formulario (Streamlit)

Formulario para describir el proyecto y elegir tipo, nivel de detalle y formato;
la estimación se muestra en streaming. Las opciones de los desplegables las da la API
(`GET /api/v1/context`). El panel lateral muestra los modelos, la versión del prompt
las métricas de la última llamada (tokens, coste, caché, tiempo hasta el primer token y tiempo total)
y el prompt exacto que recibió el LLM (system prompt, mensaje de usuario y ejemplos CAG).

Streamlit es un **cliente HTTP de la API** (`estimator_client.py`): necesita la API arrancada.

```bash
uv run uvicorn app.main:app --reload      # terminal 1
uv run streamlit run streamlit_app.py     # terminal 2
```

Disponible en `http://localhost:8501`. La URL de la API se configura con
`ESTIMATOR_API_BASE_URL` en el `.env` (por defecto `http://localhost:8000`).
Cada mensaje envía su propio `X-Request-ID`, que se muestra en el panel lateral
y aparece en los logs de la API.

## Tests

```bash
uv run pytest -v
```

No llaman a ningún LLM ni necesitan Redis: los proveedores se simulan con `mock_response`
de LiteLLM y Redis con `fakeredis`. Incluyen tests de las plantillas
(`tests/prompts/`), que comprueban qué instrucciones aparecen según cada opción del formulario.
