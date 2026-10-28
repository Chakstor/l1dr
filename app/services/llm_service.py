import time
import structlog

from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES

log = structlog.get_logger()

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
# ---------------------------------------------------------------------------

def generate_estimation(transcription: str) -> dict:
    """Genera una estimación con el proveedor configurado y mide tokens y latencia."""

    settings = get_settings()
    system_prompt = build_system_prompt()

    log.info("generating_estimation", provider=settings.LLM_PROVIDER, model=settings.LLM_MODEL)

    start = time.perf_counter()

    try:
        if settings.LLM_PROVIDER == "openai":
            result = _call_openai(system_prompt, transcription)
        else:
            result = _call_anthropic(system_prompt, transcription)

    except Exception as exc:
        log.error("llm_call_failed", provider=settings.LLM_PROVIDER, error=str(exc))
        raise LLMServiceError(f"LLM call failed: {exc}") from exc

    result["latency_ms"] = int((time.perf_counter() - start) * 1000)

    log.info(
        "estimation_generated",
        provider=result["provider"],
        model=result["model"],
        finish_reason=result["finish_reason"],
        latency_ms=result["latency_ms"],
        **result["usage"],
    )

    return result


# ---------------------------------------------------------------------------
# Proveedores: los dos devuelven un dict con la misma forma
# ---------------------------------------------------------------------------

def _call_openai(system: str, user_message: str) -> dict:
    """Llama a la Chat Completions API de OpenAI."""

    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        max_completion_tokens=MAX_TOKENS,
        messages=[
            { "role": "system", "content": system },
            { "role": "user", "content": user_message },
        ]
    )

    usage = response.usage
    
    return {
        "estimation": response.choices[0].message.content,
        "model": response.model,
        "provider": "openai",
        "finish_reason": response.choices[0].finish_reason,
        "usage": {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }
    }

def _call_anthropic(system: str, user_message: str) -> dict:
    """Llama a la Messages API de Anthropic."""

    from anthropic import Anthropic

    settings = get_settings()
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{ "role": "user", "content": user_message }]
    )
    
    # En este caso la respuesta es una lista de bloques; nos quedamos con el primero de tipo texto
    
    # Same as below, but in one line
    # text = next((block.text for block in response.content if block.type == "text"), "")

    text = ""

    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    usage = response.usage

    return {
        "estimation": text,
        "model": response.model,
        "provider": "anthropic",
        "finish_reason": response.stop_reason,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.input_tokens + usage.output_tokens
        }
    }