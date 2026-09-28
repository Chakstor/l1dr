## Interfaz de producto

El estimador utiliza una interfaz creada con Streamlit que permite definir los parámetros del proyecto a través de un formulario con los siguientes campos:

- Descripción del proyecto
- Tipo de proyecto
- Nivel de detalle
- Formato de salida

La interfaz envía estos datos al servicio FastAPI, que genera los prompts mediante templates Jinja2 (versionados) y realiza la estimación utilizando el LLM configurado.

## Ejecutar el proyecto

La aplicación requiere levantar el servicio FastAPI y la interfaz Streamlit por separado.

### 1. Levantar la API

```bash
uv run uvicorn app.main:app --reload
```

Por defecto, la API estará disponible en:

```bash
http://localhost:8000
```

La documentación Swagger está disponible en:

```bash
http://localhost:8000/docs
```

### 2. Levantar Streamlit

En otra terminal:

```bash
uv run streamlit run streamlit_app.py
```

La interfaz estará disponible por defecto en:

```bash
http://localhost:8501
```

## Tests

Los tests verifican el renderizado de los templates Jinja2 sin realizar llamadas al LLM ni a APIs externas.

Para ejecutarlos:

```bash
uv run pytest
```

Los tests comprueban:

- Que se incluye la descripción del proyecto en el prompt.
- Las instrucciones correspondientes al formato de salida seleccionado.
- Las instrucciones correspondientes al nivel de detalle seleccionado.

## Prompts

Los prompts de estimación están separados del código y versionados bajo:

```bash
app/prompts/estimation/
└── v1/
├── system.j2
├── user.j2
└── examples.j2
```

system.j2 contiene las instrucciones del modelo, user.j2 la descripción del proyecto y examples.j2 los ejemplos utilizados como contexto.
