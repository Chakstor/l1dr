from fastapi import APIRouter
from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation

router = APIRouter()

@router.post("/estimate", response_model=EstimationResponse)
def estimate(request: EstimationRequest):
    system, user = render_estimation_prompt(request)

    estimation = generate_estimation(system, user)

    return EstimationResponse(
        text=estimation,
        prompt_version="v1"
    )