"""Cliente HTTP de la API del estimador.

Lo usa Streamlit (o cualquier otro frontend en Python) para hablar con la API
por HTTP, sin importar nada de `app/`. Así la lógica de IA vive en un único
sitio: el servicio FastAPI.
"""

import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

STREAM_PATH = "/api/v1/estimate/stream"
CONTEXT_PATH = "/api/v1/context"


class EstimatorAPIError(Exception):
    """La API respondió con un error o no se pudo conectar con ella."""


@dataclass
class StreamResult:
    """Lo que se sabe de una estimación en streaming además del texto."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    metrics: dict[str, Any] | None = None


def parse_sse(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Convierte las líneas de un stream SSE en pares (evento, datos).

    Formato SSE: cada mensaje son líneas `event: ...` y `data: ...`
    terminadas por una línea en blanco. Las líneas que empiezan por `:` son
    comentarios (el servidor los usa como "ping" para mantener viva la conexión).
    """
    event, data_lines = "message", []

    for line in lines:
        if line == "":
            if data_lines:
                yield event, "\n".join(data_lines)
            event, data_lines = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").removeprefix(" "))

    if data_lines:
        yield event, "\n".join(data_lines)


class EstimatorClient:
    def __init__(self, base_url: str, http_client: Any = None, timeout: float = 120.0):
        self.http = http_client or httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    def get_context(self) -> dict[str, Any]:
        """System prompt, ejemplos y modelos configurados en la API."""
        try:
            response = self.http.get(CONTEXT_PATH)
        except httpx.HTTPError as exc:
            raise EstimatorAPIError(f"No se pudo conectar con la API: {exc}") from exc
        if response.status_code != 200:
            raise EstimatorAPIError(_error_detail(response))
        return response.json()

    def stream_estimation(self, transcription: str, result: StreamResult) -> Iterator[str]:
        """Entrega la estimación a trozos. Al terminar, deja las métricas en `result.metrics`."""
        headers = {"Accept": "text/event-stream", "X-Request-ID": result.request_id}

        try:
            with self.http.stream(
                "POST", STREAM_PATH, json={"transcription": transcription}, headers=headers
            ) as response:
                if response.status_code != 200:
                    response.read()
                    raise EstimatorAPIError(_error_detail(response))

                for event, data in parse_sse(response.iter_lines()):
                    if event == "token":
                        yield json.loads(data)["text"]
                    elif event == "metrics":
                        result.metrics = json.loads(data)
                    elif event == "error":
                        raise EstimatorAPIError(json.loads(data)["detail"])
                    elif event == "done":
                        return
        except httpx.HTTPError as exc:
            raise EstimatorAPIError(f"No se pudo conectar con la API: {exc}") from exc


def _error_detail(response: Any) -> str:
    """Mensaje legible a partir de una respuesta de error de FastAPI."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return f"Error {response.status_code}"

    # Los errores de validación (422) traen una lista; nos quedamos con el primero
    if isinstance(detail, list) and detail:
        return f"Error {response.status_code}: {detail[0].get('msg', detail[0])}"
    return f"Error {response.status_code}: {detail}"
