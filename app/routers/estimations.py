from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_llm_wrapper
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.services.llm_service import LLMServiceError, generate_estimation
from app.services.llm_wrapper import LLMWrapper

router = APIRouter(prefix="/api/v1", tags=["estimations"])

@router.post("/estimate", response_model=EstimationResponse)
def create_estimation(
    request: EstimationRequest,
    wrapper: LLMWrapper = Depends(get_llm_wrapper),
) -> EstimationResponse:
    """Recibe la transcripción de una reunión y devuelve una estimación."""

    try:
        result = generate_estimation(request.transcription, wrapper)
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # **results same as ...result in JS
    return EstimationResponse(**result)
