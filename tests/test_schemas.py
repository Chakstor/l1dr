import pytest
from pydantic import ValidationError

from app.schemas.estimation import DetailLevel, EstimationRequest, OutputFormat, ProjectType

VALID = {
    "description": "Aplicación web para gestionar reservas de salas.",
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def test_valid_request_converts_strings_to_enums():
    request = EstimationRequest(**VALID)

    assert request.project_type is ProjectType.WEB_SAAS
    assert request.detail_level is DetailLevel.MEDIUM
    assert request.output_format is OutputFormat.PHASES_TABLE


def test_description_too_short_fails():
    with pytest.raises(ValidationError):
        EstimationRequest(**{**VALID, "description": "muy corta"})


def test_description_too_long_fails():
    with pytest.raises(ValidationError):
        EstimationRequest(**{**VALID, "description": "x" * 80001})


@pytest.mark.parametrize("field", ["project_type", "detail_level", "output_format"])
def test_unknown_option_fails(field):
    with pytest.raises(ValidationError):
        EstimationRequest(**{**VALID, field: "valor_inventado"})


@pytest.mark.parametrize("field", ["project_type", "detail_level", "output_format"])
def test_missing_option_fails(field):
    data = {key: value for key, value in VALID.items() if key != field}

    with pytest.raises(ValidationError):
        EstimationRequest(**data)
