from app.prompts.loader import render_estimation_prompt
from app.schemas import (
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)

def test_description_is_in_user_prompt():
    request = EstimationRequest(
        description="Aplicación web para gestionar las reservas de un salón audiovisual.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.NARRATIVE
    )

    _, user = render_estimation_prompt(request)

    assert "<project_description>" in user
    assert request.description in user
    assert "</project_description>" in user

def test_phases_table_instructions():
    phases_request = EstimationRequest(
        description="Aplicación web para gestionar las reservas de un salón audiovisual.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.PHASES_TABLE,
    )

    narrative_request = EstimationRequest(
        description="Aplicación web para gestionar las reservas de un salón audiovisual.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
        output_format=OutputFormat.NARRATIVE,
    )

    phases_system, _ = render_estimation_prompt(phases_request)
    narrative_system, _ = render_estimation_prompt(narrative_request)

    assert "tabla por fases" in phases_system
    assert "tabla por fases" not in narrative_system

def test_detailed_includes_assupmtions():
    detailed_request = EstimationRequest(
        description="Aplicación web para gestionar las reservas de un salón audiovisual.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.DETAILED,
        output_format=OutputFormat.NARRATIVE,
    )

    summary_request = EstimationRequest(
        description="Aplicación web para gestionar las reservas de un salón audiovisual.",
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.SUMMARY,
        output_format=OutputFormat.NARRATIVE,
    )

    detailed_system, _ = render_estimation_prompt(detailed_request)
    summary_system, _ = render_estimation_prompt(summary_request)

    assert "asunciones para cada fase" in detailed_system
    assert "asunciones para cada fase" not in summary_system