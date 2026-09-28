from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from app.schemas import EstimationRequest

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
    system_template = env.get_template(
        f"estimation/{version}/system.j2"
    )
    user_template = env.get_template(
        f"estimation/{version}/user.j2"
    )

    context = request.model_dump(mode="json")

    system = system_template.render(**context)
    user = user_template.render(**context)

    return system, user