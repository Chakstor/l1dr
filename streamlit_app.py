import streamlit as st

from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.services.llm_service import (
    LLMServiceError,
    StreamMetrics,
    build_system_prompt,
    stream_estimation,
)

st.set_page_config(page_title="Estimador de Proyectos", page_icon="📊")
st.title("Estimador de Proyectos de Software")
st.caption("Pega la transcripción de una reunión y recibe la estimación en streaming.")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

def render_sidebar() -> None:
    """Panel lateral: métricas de la última llamada, system prompt y ejemplos CAG."""

    settings = get_settings()

    with st.sidebar:
        st.header("Contexto CAG")
        st.markdown(f"**Proveedor:** `{settings.LLM_PROVIDER}` · **Modelo:** `{settings.LLM_MODEL}`")

        st.subheader("Última llamada")
        metrics = st.session_state.last_metrics
        if metrics is None:
            st.info("Aún no hay llamadas. Envía una transcripción para ver las métricas.")
        else:
            col1, col2 = st.columns(2)
            col1.metric("Tokens entrada", metrics.input_tokens)
            col2.metric("Tokens salida", metrics.output_tokens)
            col1.metric("Primer token", f"{metrics.first_token_ms} ms")
            col2.metric("Tiempo total", f"{metrics.latency_ms / 1000:.1f} s")
            st.caption(f"Modelo: `{metrics.model}` · Fin: `{metrics.finish_reason}`")

        with st.expander("System prompt activo"):
            st.code(build_system_prompt(), language="markdown")

        with st.expander(f"Ejemplos inyectados ({len(ESTIMATION_EXAMPLES)})"):
            for i, example in enumerate(ESTIMATION_EXAMPLES, start=1):
                st.markdown(f"**Ejemplo {i}: resumen de la reunión**")
                st.text(example["meeting_summary"].strip())
                st.markdown(f"**Ejemplo {i}: estimación**")
                st.markdown(example["estimation"].strip())
                st.divider()

        if st.button("Limpiar conversación"):
            st.session_state.messages = []
            st.session_state.last_metrics = None
            st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if transcription := st.chat_input("Pega aquí la transcripción de la reunión..."):
    st.session_state.messages.append({"role": "user", "content": transcription})
    with st.chat_message("user"):
        st.markdown(transcription)

    with st.chat_message("assistant"):
        metrics = StreamMetrics()
        try:
            estimation = st.write_stream(stream_estimation(transcription, metrics))
        except LLMServiceError as exc:
            st.error(f"No se pudo generar la estimación: {exc}")
        else:
            st.session_state.messages.append({"role": "assistant", "content": estimation})
            st.session_state.last_metrics = metrics

if transcription:
    render_sidebar()