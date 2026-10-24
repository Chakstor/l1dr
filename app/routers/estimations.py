from fastapi import APIRouter
from pydantic import BaseModel
from app.config import get_settings
from app.services.llm_service import generate_estimation

router = APIRouter()

class EstimationRequest(BaseModel):
    transcription: str

class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str

@router.post("/api/v1/estimate", response_model=EstimationResponse)
def estimate(request: EstimationRequest):
    estimation = generate_estimation(request.transcription)
    settings = get_settings()

    return EstimationResponse(
        estimation=estimation,
        model=settings.LLM_MODEL,
        provider=settings.LLM_PROVIDER,
    )