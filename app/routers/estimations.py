from app.sessions import Session, sessions
from app.services.attachment_service import extract_attachment_text
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.services.llm_service import (generate_estimation, extract_project_metadata)

router = APIRouter()

@router.post("/sessions")
def create_session():
    session = Session()

    sessions[session.session_id] = session

    return {
        "session_id": session.session_id
    }

@router.post("/sessions/{session_id}/estimate")
async def estimate_session(
    session_id: str,
    transcript: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
):
    if session_id not in sessions:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    session = sessions[session_id]
    context = transcript

    for attachment in attachments:
        attachment_text = await extract_attachment_text(attachment)
        context += (
            f"\n\n--- attachment: {attachment.filename} --- \n"
            f"{attachment_text}"
        )

    estimation = generate_estimation(
        context,
        session.project_metadata,
        session.history,
    )

    updated_metadata = extract_project_metadata(
        session.project_metadata,
        context,
        estimation
    )

    session.project_metadata = updated_metadata

    session.history.add_turn(
        context,
        estimation
    )

    return {
        "estimation": estimation,
        "project_metadata": session.project_metadata
    }
