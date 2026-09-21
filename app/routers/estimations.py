from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings
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

    return EstimationResponse(
        estimation=estimation,
        model=settings.llm_model,
        provider=settings.llm_provider,
    )