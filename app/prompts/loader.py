"""Carga y renderiza las plantillas Jinja2 versionadas de los prompts.

Estructura en disco: app/prompts/<caso_de_uso>/<version>/<rol>.j2
Cambiar de versión es cambiar un string ("v1" → "v2"), no refactorizar código.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.estimation import EstimationRequest

PROMPTS_DIR = Path(__file__).parent

env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

def render_estimation_prompt(
    request: EstimationRequest,
    version: str = "v1",
) -> tuple[str, str]:
    """Devuelve (system, user) listos para enviarse al LLM como mensajes separados."""
    system_template = env.get_template(
        f"estimation/{version}/system.j2"
    )
    user_template = env.get_template(
        f"estimation/{version}/user.j2"
    )

    # mode="json" convierte los Enum en su valor de texto ("web_saas", no ProjectType.WEB_SAAS)
    context = request.model_dump(mode="json")

    system = system_template.render(**context)
    user = user_template.render(**context)

    return system, user


def render_estimation_examples(version: str = "v1") -> str:
    """Solo el bloque de ejemplos (contexto estático CAG) de una versión del prompt."""
    return env.get_template(f"estimation/{version}/examples.j2").render()
