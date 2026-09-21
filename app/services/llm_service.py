from openai import OpenAI
from app.config import settings
from app.context.examples import ESTIMATION_EXAMPLES

client = OpenAI(api_key=settings.openai_api_key)

examples_text = ""

for example in ESTIMATION_EXAMPLES:
    examples_text += f"""
    Resumen de la reunión: {example["meeting_summary"]}
    Estimación: {example["estimation"]}
    ---
    """

SYSTEM_PROMPT = f"""
Eres un estimador de proyectos de software experto.

Tu tarea es analizar la transcripción de una reunión con un cliente
y generar una estimación tomando como referencia estimaciones previas.

Ejemplos de estimaciones previas: {examples_text}

Genera una estimación que incluya un desglose de tareas, horas estimadas,
total de horas, equipo recomendado y duración estimada.
"""

def generate_estimation(transcription: str) -> str:

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": transcription
            },
        ],
    )

    return response.choices[0].message.content