from collections.abc import Iterator

from app.context.examples import ESTIMATION_EXAMPLES
from app.dependencies import get_llm_wrapper
from app.services.llm_wrapper import LLMWrapper, StreamMetrics

MAX_TOKENS = 4000

class LLMServiceError(Exception):
    """Se lanza cuando falla la llamada al proveedor LLM."""


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------

def format_examples(examples: list[dict]) -> str:
    """Convierte la lista de ejemplos en un bloque de texto para el system prompt."""
    
    parts = []

    for i, example in enumerate(examples, start=1):
        parts.append(
            f"--- EJEMPLO {i} ---\n"
            f"Resumen de la reunión:\n{example['meeting_summary'].strip()}\n\n"
            f"Estimación:\n{example['estimation'].strip()}\n"
        )

    return "\n".join(parts)


def build_system_prompt() -> str:
    """Construye el system prompt: rol + instrucciones + ejemplos (CAG)."""
    
    examples_text = format_examples(ESTIMATION_EXAMPLES)
    
    return (
        "Eres un estimador de proyectos de software experto.\n\n"
        "Tu tarea es analizar la transcripción de una reunión con un cliente "
        "y generar una estimación tomando como referencia estimaciones previas.\n\n"
        "Genera una estimación que incluya un desglose de tareas, horas estimadas, "
        "total de horas, equipo recomendado y duración estimada.\n\n"
        "Ejemplos de estimaciones previas:\n\n"
        f"{examples_text}"
    ) 


# ---------------------------------------------------------------------------
# Punto de entrada
#
# Este módulo decide QUÉ se le pide al LLM (el prompt). CÓMO se llama al
# proveedor (fallback, caché, coste, logs) lo resuelve el wrapper.
# ---------------------------------------------------------------------------

def generate_estimation(transcription: str, wrapper: LLMWrapper | None = None) -> dict:
    """Genera una estimación completa. Devuelve el dict con tokens, latencia, coste y cache_hit."""

    wrapper = wrapper or get_llm_wrapper()

    try:
        return wrapper.complete(
            system_prompt=build_system_prompt(),
            user_message=transcription,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:
        raise LLMServiceError(f"LLM call failed: {exc}") from exc


def stream_estimation(
    transcription: str,
    metrics: StreamMetrics,
    wrapper: LLMWrapper | None = None,
) -> Iterator[str]:
    """Genera la estimación en streaming. Va entregando el texto a trozos
    y rellena `metrics` (tokens, coste, TTFT, latencia) cuando termina."""

    wrapper = wrapper or get_llm_wrapper()

    try:
        yield from wrapper.complete_stream(
            system_prompt=build_system_prompt(),
            user_message=transcription,
            metrics=metrics,
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:
        raise LLMServiceError(f"LLM stream failed: {exc}") from exc
