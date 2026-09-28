import httpx
import streamlit as st
from app.schemas import DetailLevel, OutputFormat, ProjectType

st.title("Estimador de Software")

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        placeholder="Describe las necesidades del proyecto...",
    )

    project_type = st.selectbox(
        "Tipo de proyecto",
        options=list(ProjectType),
        format_func=lambda option: option.value
    )

    detail_level = st.selectbox(
        "Nivel de detalle",
        options=list(DetailLevel),
        format_func=lambda option: option.value
    )

    output_format = st.selectbox(
        "Formato de salida",
        options=list(OutputFormat),
        format_func=lambda option: option.value
    )

    submitted = st.form_submit_button("Generar estimación")

if submitted:
    request_data = {
        "description": description,
        "project_type": project_type.value,
        "detail_level": detail_level.value,
        "output_format": output_format.value,
    }

    response = httpx.post(
        "http://localhost:8000/estimate",
        json=request_data,
    )

    if response.status_code == 200:
        result = response.json()
        st.markdown(result["text"])
    else:
        st.error("Error al generar la estimación")