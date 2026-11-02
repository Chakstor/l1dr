from app.prompts.loader import render_estimation_prompt
import pytest
from jinja2 import TemplateNotFound, UndefinedError

from app.prompts.loader import env
from app.schemas.estimation import (
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


def make_request(**overrides):
    data = {
        "description": "Aplicación web para gestionar las reservas de un salón audiovisual.",
        "project_type": ProjectType.WEB_SAAS,
        "detail_level": DetailLevel.MEDIUM,
        "output_format": OutputFormat.NARRATIVE,
    }
    return EstimationRequest(**{**data, **overrides})


def test_examples_are_included_in_system_prompt():
    system, _ = render_estimation_prompt(make_request())

    assert "<ejemplos>" in system
    assert "Total estimado: 160 horas." in system


def test_project_type_is_rendered_as_plain_value():
    system, _ = render_estimation_prompt(make_request(project_type=ProjectType.DATA_PIPELINE))

    assert "Tipo de proyecto: data_pipeline" in system
    assert "ProjectType" not in system


def test_strict_undefined_fails_when_a_variable_is_missing():
    template = env.get_template("estimation/v1/user.j2")

    with pytest.raises(UndefinedError):
        template.render()


def test_unknown_version_fails():
    with pytest.raises(TemplateNotFound):
        render_estimation_prompt(make_request(), version="v99")
