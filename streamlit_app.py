import streamlit as st
from openai import OpenAI
from app.config import settings
from app.services.llm_service import SYSTEM_PROMPT

client = OpenAI(api_key=settings.openai_api_key)

st.title("Estimador de Proyectos de Software")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

transcription = st.chat_input("Pega aquí la transcripción de la reunión...")

if transcription:
    st.session_state.messages.append({
        "role": "user",
        "content": transcription
    })

    with st.chat_message("user"):
        st.markdown(transcription)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcription},
            ],
            stream=True,
        )

        estimation = st.write_stream(stream)

    st.session_state.messages.append({
        "role": "assistant",
        "content": estimation
    })