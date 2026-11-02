from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Parámetros del formulario (sesión 4): valores cerrados en vez de texto libre
# ---------------------------------------------------------------------------

class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


# ---------------------------------------------------------------------------
# Petición y respuesta
# ---------------------------------------------------------------------------

class EstimationRequest(BaseModel):
    """Petición tipada que produce el formulario."""

    description: str = Field(
        min_length=20,
        max_length=80000,
        description="Descripción o transcripción del proyecto a estimar",
    )
    project_type: ProjectType = Field(description="Categoría del proyecto")
    detail_level: DetailLevel = Field(description="Nivel de detalle de la estimación")
    output_format: OutputFormat = Field(description="Formato en el que se presenta la estimación")


class TokenUsage(BaseModel):
    """Consumo de tokens de la llamada al LLM."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class EstimationResponse(BaseModel):
    """Estimación en texto libre + versión del prompt + metadatos de la llamada."""

    text: str = Field(..., description="Estimación generada por el LLM, en markdown")
    prompt_version: str = Field(..., description="Versión de las plantillas de prompt usada")
    model: str = Field(..., description="Modelo que respondió realmente")
    provider: str = Field(..., description="Proveedor usado: openai | anthropic")
    usage: TokenUsage
    finish_reason: str = Field(..., description="Motivo por el que el modelo dejó de generar")
    latency_ms: int = Field(..., description="Tiempo total de la llamada en milisegundos")
    cost_usd: float = Field(default=0.0, description="Coste estimado de la llamada en USD (0 si vino de caché)")
    cache_hit: bool = Field(default=False, description="True si la respuesta vino de la caché de Redis")


# ---------------------------------------------------------------------------
# GET /context
# ---------------------------------------------------------------------------

class FormOptions(BaseModel):
    """Valores válidos de cada desplegable del formulario."""

    project_type: list[str]
    detail_level: list[str]
    output_format: list[str]


class ContextResponse(BaseModel):
    """Configuración que necesitan los clientes para construir el formulario."""

    primary_model: str
    fallback_model: str
    prompt_version: str
    options: FormOptions


# ---------------------------------------------------------------------------
# POST /prompt/preview
# ---------------------------------------------------------------------------

class PromptPreviewResponse(BaseModel):
    """El prompt exacto que se enviaría al LLM para una petición, sin llamarlo."""

    prompt_version: str
    system_prompt: str
    user_prompt: str
    examples: str = Field(description="Bloque de ejemplos CAG (ya incluido dentro de system_prompt)")
