"""Formulario del estimador (sesión 4).

Streamlit es solo un CLIENTE de la API: le envía los parámetros del formulario
por HTTP (POST /api/v1/estimate/stream) y pinta la respuesta según llega por SSE.
No importa nada de `app/`: hasta las opciones de los desplegables las pide a la API.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from estimator_client import EstimatorAPIError, EstimatorClient, StreamResult

load_dotenv()
API_BASE_URL = os.getenv("ESTIMATOR_API_BASE_URL", "http://localhost:8000")

# Textos que ve el usuario para cada valor que acepta la API
LABELS = {
    "mobile_app": "App móvil",
    "web_saas": "Web / SaaS",
    "internal_tool": "Herramienta interna",
    "data_pipeline": "Pipeline de datos",
    "summary": "Resumen",
    "medium": "Medio",
    "detailed": "Detallado",
    "phases_table": "Tabla por fases",
    "line_items": "Lista de tareas",
    "narrative": "Narrativo",
}

st.set_page_config(page_title="Estimador de Proyectos", page_icon="📊")
st.title("Estimador de Proyectos de Software")
st.caption("Describe el proyecto, elige cómo quieres la estimación y recíbela en streaming.")


@st.cache_resource
def get_client() -> EstimatorClient:
    """Un único cliente HTTP para toda la app (reutiliza la conexión)."""
    return EstimatorClient(API_BASE_URL)


@st.cache_data(ttl=60, show_spinner=False)
def get_context() -> dict:
    """Modelos, versión del prompt y opciones del formulario. Se guarda 60 s."""
    return get_client().get_context()


def label(value: str) -> str:
    return LABELS.get(value, value)


if "last" not in st.session_state:
    st.session_state.last = None


def render_metrics(result: StreamResult) -> None:
    metrics = result.metrics
    if metrics is None:
        st.warning("La API no devolvió métricas para esta llamada.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Tokens entrada", metrics["input_tokens"])
    col2.metric("Tokens salida", metrics["output_tokens"])
    col1.metric("Primer token", f"{metrics['first_token_ms']} ms")
    col2.metric("Tiempo total", f"{metrics['latency_ms'] / 1000:.1f} s")
    col1.metric("Coste", f"${metrics['cost_usd']:.5f}")
    col2.metric("Caché", "HIT ✅" if metrics["cache_hit"] else "MISS")
    st.caption(
        f"Modelo: `{metrics['model']}` · Fin: `{metrics['finish_reason']}`"
        + (" · ⚠️ respondió el fallback" if metrics["fallback_used"] else "")
    )
    st.caption(f"Request ID: `{result.request_id}`")


def render_sidebar(context: dict | None) -> None:
    with st.sidebar:
        st.header("Configuración")
        if context:
            st.markdown(
                f"**Primario:** `{context['primary_model']}`  \n"
                f"**Fallback:** `{context['fallback_model']}`  \n"
                f"**Prompt:** `{context['prompt_version']}`"
            )

        st.subheader("Última llamada")
        if st.session_state.last is None:
            st.info("Aún no hay llamadas. Rellena el formulario para ver las métricas.")
        else:
            request = st.session_state.last["request"]
            st.caption(
                f"{label(request['project_type'])} · {label(request['detail_level'])} · "
                f"{label(request['output_format'])}"
            )
            render_metrics(st.session_state.last["result"])

            if st.button("Limpiar"):
                st.session_state.last = None
                st.rerun()

        st.caption(f"API: `{API_BASE_URL}`")


# --- Contexto de la API (sin él no se puede construir el formulario) ---------

try:
    context = get_context()
except EstimatorAPIError as exc:
    st.error(f"No se pudo conectar con la API en `{API_BASE_URL}`: {exc}")
    render_sidebar(None)
    st.stop()

options = context["options"]

# --- Formulario --------------------------------------------------------------

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        height=200,
        placeholder="Describe el proyecto o pega la transcripción de la reunión...",
    )

    col1, col2, col3 = st.columns(3)
    project_type = col1.selectbox("Tipo de proyecto", options["project_type"], format_func=label)
    detail_level = col2.selectbox("Nivel de detalle", options["detail_level"], index=1, format_func=label)
    output_format = col3.selectbox("Formato de salida", options["output_format"], format_func=label)

    submitted = st.form_submit_button("Generar estimación", type="primary")

# --- Resultado ---------------------------------------------------------------

if submitted:
    request = {
        "description": description,
        "project_type": project_type,
        "detail_level": detail_level,
        "output_format": output_format,
    }
    result = StreamResult()
    try:
        text = st.write_stream(get_client().stream_estimation(request, result))
    except EstimatorAPIError as exc:
        st.error(f"No se pudo generar la estimación: {exc}")
    else:
        st.session_state.last = {"request": request, "text": text, "result": result}
elif st.session_state.last is not None:
    st.markdown(st.session_state.last["text"])

render_sidebar(context)
