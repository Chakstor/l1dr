from pydantic import BaseModel, Field

class EstimationRequest(BaseModel):
    """Petición entrante: la transcripción de la reunión a estimar."""

    transcription: str = Field(
        ...,
        min_length=50,
        description="Meeting transcription"
    )


class TokenUsage(BaseModel):
    """Consumo de tokens de la llamada al LLM."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


class EstimationResponse(BaseModel):
    """Respuesta con la estimación generada y metadatos de la llamada."""

    estimation: str = Field(..., description="Estimación generada, en markdown")
    model: str = Field(..., description="Modelo que respondió relamente")
    provider: str = Field(..., description="Proveedor usado: openai | anthropic")
    usage: TokenUsage
    finish_reason: str = Field(..., description="Motivo por el que el modelo dejó de generar")
    latency_ms: int = Field(...,  description="Tiempo total de la llamada en milisegundos")
    
