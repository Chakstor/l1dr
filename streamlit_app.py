"""Interfaz de chat del estimador.

Streamlit es solo un CLIENTE de la API: le envía la transcripción por HTTP
(POST /api/v1/estimate/stream) y pinta la respuesta según llega por SSE.
No importa nada de `app/`, así que se podría cambiar por React, Angular...
sin tocar el backend.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from estimator_client import EstimatorAPIError, EstimatorClient, StreamResult

load_dotenv()
API_BASE_URL = os.getenv("ESTIMATOR_API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Estimador de Proyectos", page_icon="📊")
st.title("Estimador de Proyectos de Software")
st.caption("Pega la transcripción de una reunión y recibe la estimación en streaming.")


@st.cache_resource
def get_client() -> EstimatorClient:
    """Un único cliente HTTP para toda la app (reutiliza la conexión)."""
    return EstimatorClient(API_BASE_URL)


@st.cache_data(ttl=60, show_spinner=False)
def get_context() -> dict:
    """Prompt, ejemplos y modelos de la API. Se guarda 60 s para no pedirlo en cada rerun."""
    return get_client().get_context()


if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None


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


def render_sidebar() -> None:
    """Panel lateral: métricas de la última llamada, system prompt y ejemplos CAG."""

    with st.sidebar:
        st.header("Contexto CAG")

        try:
            context = get_context()
        except EstimatorAPIError as exc:
            st.error(f"No se pudo cargar el contexto desde `{API_BASE_URL}`: {exc}")
            context = None

        if context:
            st.markdown(
                f"**Primario:** `{context['primary_model']}`  \n"
                f"**Fallback:** `{context['fallback_model']}`"
            )

        st.subheader("Última llamada")
        if st.session_state.last_result is None:
            st.info("Aún no hay llamadas. Envía una transcripción para ver las métricas.")
        else:
            render_metrics(st.session_state.last_result)

        if context:
            with st.expander("System prompt activo"):
                st.code(context["system_prompt"], language="markdown")

            with st.expander(f"Ejemplos inyectados ({len(context['examples'])})"):
                for i, example in enumerate(context["examples"], start=1):
                    st.markdown(f"**Ejemplo {i}: resumen de la reunión**")
                    st.text(example["meeting_summary"].strip())
                    st.markdown(f"**Ejemplo {i}: estimación**")
                    st.markdown(example["estimation"].strip())
                    st.divider()

        if st.button("Limpiar conversación"):
            st.session_state.messages = []
            st.session_state.last_result = None
            st.rerun()

        st.caption(f"API: `{API_BASE_URL}`")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if transcription := st.chat_input("Pega aquí la transcripción de la reunión..."):
    st.session_state.messages.append({"role": "user", "content": transcription})
    with st.chat_message("user"):
        st.markdown(transcription)

    with st.chat_message("assistant"):
        result = StreamResult()
        try:
            estimation = st.write_stream(get_client().stream_estimation(transcription, result))
        except EstimatorAPIError as exc:
            st.error(f"No se pudo generar la estimación: {exc}")
        else:
            st.session_state.messages.append({"role": "assistant", "content": estimation})
            st.session_state.last_result = result

render_sidebar()
