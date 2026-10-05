# Estimador CAG

API de estimación de proyectos de software con memoria conversacional,
desarrollada con FastAPI y un cliente en Streamlit.

## Instalación

Dependencias:

```bash
uv sync
```

Crear un archivo `.env` con la configuración necesaria para el proveedor
LLM (ver .env.example).

## Ejecutar la API

```bash
uv run uvicorn app.main:app --reload
```

La API estará disponible en:

`http://localhost:8000/docs`

## Ejecutar Streamlit

En otra terminal:

```bash
uv run streamlit run streamlit_app.py
```

## Sesiones y memoria conversacional

Cada conversación utiliza una sesión identificada con su id: `session_id`.

La API expone:

- `POST /sessions`: crea una nueva sesión.
- `POST /sessions/{session_id}/estimate`: genera una estimación
  utilizando el contexto de la sesión.

Cada sesión mantiene dos tipos de información:

- `ConversationHistory`: los últimos 6 turnos de conversación mediante una ventana deslizante.
- `ProjectMetadata`: información estructurada del proyecto (nombre, equipo, tecnologías, etc.)

## Adjuntos

El endpoint acepta archivos PDF y DOCX mediante `multipart/form-data`.

Se ha elegido el **Camino B: extracción local de texto**.

- PDF: `pypdf`
- DOCX: `python-docx`

El texto extraído se añade al contexto enviado al LLM utilizando un separador:

```text
--- attachment: filename.pdf ---
contenido del documento
```

Se eligió este enfoque porque mantiene el procesamiento independiente de
las capacidades multimodales de un proveedor concreto y permite
controlar directamente el texto que se incorpora al contexto.

## Extracción de project_metadata

Después de cada respuesta se realiza una segunda llamada al LLM para
actualizar `ProjectMetadata`.

El extractor recibe:

- metadata actual
- mensaje del usuario
- respuesta del asistente

y devuelve un nuevo `ProjectMetadata` estructurado.

Se eligió un **LLM extractor** en lugar de una heurística basada en
regex porque permite interpretar información expresada de distintas
formas y actualizar los datos estructurados de manera más robusta.

Como contrapartida, este enfoque añade una segunda llamada al LLM en
cada turno, aumentando el coste y la latencia.

## Tests

Ejecutar:

```bash
uv run python -m pytest tests/test_sessions.py -v
```

Los tests comprueban:

1.  Que la ventana deslizante conserva únicamente los últimos 6 turnos.
2.  Que `project_metadata` persiste y se actualiza entre peticiones de
    una misma sesión.
3.  Que el contenido extraído de un PDF se incorpora al contexto de la
    estimación.
