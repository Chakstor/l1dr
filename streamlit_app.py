import httpx
import streamlit as st
from openai import OpenAI
from app.config import settings
from app.services.llm_service import SYSTEM_PROMPT

API_URL = "http://localhost:8000"

def create_session():
    response = httpx.post(f"{API_URL}/sessions")
    return response.json()["session_id"]

if "session_id" not in st.session_state:
    st.session_state.session_id = create_session()

st.write("Session ID:", st.session_state.session_id)

client = OpenAI(api_key=settings.openai_api_key)

st.title("Estimador de Proyectos de Software")

if st.button("Nueva conversación"):
    st.session_state.session_id = create_session()
    st.rerun()

with st.form("estimation_form"):
    transcript = st.text_area(
        "Transcripción",
        placeholder="Describe el proyecto o continúa la conversación...",
    )

    attachments = st.file_uploader(
        "Adjuntos",
        type=["pdf", "docx"],
        accept_multiple_files=True,
    )

    submitted = st.form_submit_button("Generar estimación")

if submitted:
    files = [
        (
            "attachments",
            (
                attachment.name,
                attachment.getvalue(),
                attachment.type,
            ),
        )
        for attachment in attachments
    ]

    response = httpx.post(
        f"{API_URL}/sessions/{st.session_state.session_id}/estimate",
        data={
            "transcript": transcript,
        },
        files=files,
        timeout=60.0,
    )

    if response.status_code == 200:
        result = response.json()

        st.markdown(result["estimation"])

        with st.expander("Project metadata"):
            st.json(result["project_metadata"])
    else:
        st.error("Error al generar la estimación")