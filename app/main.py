from fastapi import FastAPI
from app.routers.estimations import router as estimations_router

app = FastAPI(
    title="Estimador CAG API",
    description="Genera estimaciones de software a partir de transcripciones de reuniones."
)

app.include_router(
    estimations_router
)

@app.get("/health")
def health():
    return {"status": "ok"}