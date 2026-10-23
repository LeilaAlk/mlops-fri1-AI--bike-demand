"""Lab 5 logging: one structured line per request, metadata only."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from test_api import VALID, write_model

from bike_demand import api
from bike_demand.observability import JsonFormatter

pytestmark = pytest.mark.api

LOGGER = "bike_demand.service"


def request_lines(caplog):
    return [r for r in caplog.records if r.name == LOGGER and r.msg == "request"]


def start(monkeypatch, directory):
    monkeypatch.setenv(api.MODEL_DIR_ENV, str(directory))
    monkeypatch.setenv(api.REVISION_ENV, "rev-test")
    return TestClient(api.app)


def test_one_line_per_request_with_identity(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    with start(monkeypatch, write_model(tmp_path / "model")) as client:
        client.post("/predict", json=VALID, headers={"X-Request-ID": "req-1"})
        client.post("/predict", json={**VALID, "hr": 24})
    first, second = (r.fields for r in request_lines(caplog))
    assert first["request_id"] == "req-1"
    assert (first["status"], first["outcome"]) == (200, "predicted")
    assert first["model_version"] == "test-v1"
    assert first["service_revision"] == "rev-test"
    assert len(first["model_sha256"]) == 64
    assert (second["status"], second["outcome"]) == (422, "rejected")
    assert second["request_id"] != "req-1"
    assert second["duration_ms"] >= 0


def test_request_id_is_returned_and_unsafe_ids_replaced(monkeypatch, tmp_path):
    with start(monkeypatch, write_model(tmp_path / "model")) as client:
        kept = client.get("/health", headers={"X-Request-ID": "abc-123"})
        replaced = client.get("/health", headers={"X-Request-ID": "bad id\n<x>"})
    assert kept.headers["X-Request-ID"] == "abc-123"
    assert replaced.headers["X-Request-ID"] != "bad id\n<x>"


def test_missing_model_is_logged_at_startup(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    (tmp_path / "empty").mkdir()
    with start(monkeypatch, tmp_path / "empty") as client:
        client.post("/predict", json=VALID)
    events = [r.msg for r in caplog.records if r.name == LOGGER]
    assert events[0] == "model_unavailable"
    assert request_lines(caplog)[0].fields["outcome"] == "unavailable"


def test_request_body_is_never_logged(monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    with start(monkeypatch, write_model(tmp_path / "model")) as client:
        client.post("/predict", json={**VALID, "windspeed": 0.123456})
    text = " ".join(JsonFormatter().format(r) for r in caplog.records)
    assert "0.123456" not in text
    assert "windspeed" not in text


def test_formatter_writes_one_json_object():
    record = logging.LogRecord(LOGGER, logging.INFO, __file__, 1, "request", None, None)
    record.fields = {"status": 200}
    line = JsonFormatter().format(record)
    assert "\n" not in line
    assert json.loads(line)["status"] == 200
