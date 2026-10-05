from app.sessions import ConversationHistory, MAX_TURNS


def test_history_respects_max_turns():
    history = ConversationHistory()

    for i in range(8):
        history.add_turn(
            user_message=f"Pregunta {i}",
            assistant_message=f"Respuesta {i}",
        )

    assert len(history.messages) == MAX_TURNS * 2

    assert history.messages[0].content == "Pregunta 2"
    assert history.messages[1].content == "Respuesta 2"

    assert history.messages[-2].content == "Pregunta 7"
    assert history.messages[-1].content == "Respuesta 7"


from fastapi.testclient import TestClient

from app.main import app
from app.sessions import ConversationHistory, MAX_TURNS, ProjectMetadata


client = TestClient(app)


def test_metadata_persists_between_requests(monkeypatch):
    def fake_generate_estimation(transcription, project_metadata, history):
        return "Estimación generada"

    def fake_extract_project_metadata(
        current_metadata,
        user_turn,
        assistant_turn,
    ):
        if current_metadata.project_name is None:
            return ProjectMetadata(
                project_name="TravelFlow",
                mentioned_technologies=["React", "TypeScript"],
            )

        return ProjectMetadata(
            project_name=current_metadata.project_name,
            assumed_team_size=4,
            mentioned_technologies=current_metadata.mentioned_technologies,
        )

    monkeypatch.setattr(
        "app.routers.estimations.generate_estimation",
        fake_generate_estimation,
    )

    monkeypatch.setattr(
        "app.routers.estimations.extract_project_metadata",
        fake_extract_project_metadata,
    )

    session_response = client.post("/sessions")
    session_id = session_response.json()["session_id"]

    # Primer turno
    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "El proyecto se llama TravelFlow y utiliza React y TypeScript."
        },
    )

    assert response.status_code == 200
    assert response.json()["project_metadata"]["project_name"] == "TravelFlow"

    # Segundo turno
    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "El equipo estará formado por 4 desarrolladores."
        },
    )

    assert response.status_code == 200

    metadata = response.json()["project_metadata"]

    assert metadata["project_name"] == "TravelFlow"
    assert metadata["assumed_team_size"] == 4
    assert metadata["mentioned_technologies"] == ["React", "TypeScript"]


def test_pdf_content_is_added_to_context(monkeypatch):
    received_context = {}

    def fake_generate_estimation(transcription, project_metadata, history):
        received_context["text"] = transcription
        return "Estimación generada"

    def fake_extract_project_metadata(
        current_metadata,
        user_turn,
        assistant_turn,
    ):
        return current_metadata

    async def fake_extract_attachment_text(file):
        return "El proyecto debe utilizar PostgreSQL."

    monkeypatch.setattr(
        "app.routers.estimations.generate_estimation",
        fake_generate_estimation,
    )

    monkeypatch.setattr(
        "app.routers.estimations.extract_project_metadata",
        fake_extract_project_metadata,
    )

    monkeypatch.setattr(
        "app.routers.estimations.extract_attachment_text",
        fake_extract_attachment_text,
    )

    session_response = client.post("/sessions")
    session_id = session_response.json()["session_id"]

    response = client.post(
        f"/sessions/{session_id}/estimate",
        data={
            "transcript": "Necesito una estimación para este proyecto."
        },
        files={
            "attachments": (
                "requirements.pdf",
                b"fake pdf content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    assert "Necesito una estimación para este proyecto." in received_context["text"]
    assert "El proyecto debe utilizar PostgreSQL." in received_context["text"]
    assert "requirements.pdf" in received_context["text"]