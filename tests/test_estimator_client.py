import httpx
import pytest

from estimator_client import EstimatorAPIError, EstimatorClient, StreamResult, parse_sse


def test_parse_sse_reads_events_and_data():
    lines = ["event: token", 'data: {"text": "Hola"}', "", "event: done", "data: [DONE]", ""]

    assert list(parse_sse(lines)) == [("token", '{"text": "Hola"}'), ("done", "[DONE]")]


def test_parse_sse_joins_multiline_data_and_ignores_comments():
    lines = [": ping", "event: token", "data: línea 1", "data: línea 2", ""]

    assert list(parse_sse(lines)) == [("token", "línea 1\nlínea 2")]


def test_parse_sse_uses_message_as_default_event():
    assert list(parse_sse(["data: hola", ""])) == [("message", "hola")]


def test_each_stream_result_gets_its_own_request_id():
    first, second = StreamResult(), StreamResult()

    assert len(first.request_id) == 32
    assert first.request_id != second.request_id


def test_client_wraps_connection_errors():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    http = httpx.Client(base_url="http://api", transport=httpx.MockTransport(refuse))
    client = EstimatorClient("http://api", http_client=http)

    with pytest.raises(EstimatorAPIError, match="No se pudo conectar"):
        list(client.stream_estimation("x" * 60, StreamResult()))

    with pytest.raises(EstimatorAPIError, match="No se pudo conectar"):
        client.get_context()
