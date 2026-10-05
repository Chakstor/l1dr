from openai import OpenAI
from app.config import settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.sessions import ConversationHistory, ProjectMetadata

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

def generate_estimation(
        transcription: str,
        project_metadata: ProjectMetadata,
        history: ConversationHistory
) -> str:
    
    metadata_text = f"""
Información conocida del proyecto:
- Nombre: {project_metadata.project_name}
- Tamaño del equipo: {project_metadata.assumed_team_size}
- Tecnologías: {", ".join(project_metadata.mentioned_technologies)}
- Alcance acordado: {project_metadata.agreed_scope}
- Restricciones: {", ".join(project_metadata.explicit_constraints)}
- Opciones rechazadas: {", ".join(project_metadata.rejected_options)}
"""

    system_prompt = SYSTEM_PROMPT + metadata_text

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    for message in history.messages:
        messages.append({
            "role": message.role,
            "content": message.content,
        })

    messages.append({
        "role": "user",
        "content": transcription,
    }) 

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
    )

    return response.choices[0].message.content


def extract_project_metadata(
    current_metadata: ProjectMetadata,
    user_turn: str,
    assistant_turn: str,
) -> ProjectMetadata:

    prompt = f"""
Actualiza los metadatos de un proyecto de software basándote en el último turno de conversación.

Reglas:
- Solo actualiza campos cuando haya evidencia clara.
- Conserva los valores existentes salvo que el usuario los cambie explícitamente.
- Si el usuario retira un dato anterior, elimínalo.
- En las listas, añade elementos nuevos sin duplicar los existentes.

Metadatos actuales:
{current_metadata.model_dump_json()}

Último turno:
USER: {user_turn}
ASSISTANT: {assistant_turn}
"""
    response = client.chat.completions.parse(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": "Extrae metadatos estructurados de proyectos de software.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        response_format=ProjectMetadata,
    )

    return response.choices[0].message.parsed