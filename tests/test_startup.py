"""Lab 5 start-up: settings from the environment, identity, fail-closed check."""

from fastapi.testclient import TestClient
from test_api import VALID, write_model

from bike_demand import api
from bike_demand.preflight import sha256


def start(monkeypatch, directory, **env):
    monkeypatch.setenv(api.MODEL_DIR_ENV, str(directory))
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return TestClient(api.app)


def test_version_reports_code_and_model_identity(monkeypatch, tmp_path):
    directory = write_model(tmp_path / "model")
    with start(monkeypatch, directory, SERVICE_REVISION="abc123") as client:
        body = client.get("/version").json()
    assert body == {
        "service_revision": "abc123",
        "model_version": "test-v1",
        "model_sha256": sha256(directory / "model.joblib"),
        "ready": True,
    }


def test_version_without_model_is_not_ready(monkeypatch, tmp_path):
    (tmp_path / "empty").mkdir()
    with start(monkeypatch, tmp_path / "empty") as client:
        response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["model_version"] is None


def test_expected_sha_match_is_ready(monkeypatch, tmp_path):
    directory = write_model(tmp_path / "model")
    digest = sha256(directory / "model.joblib")
    env = {api.EXPECTED_SHA_ENV: digest}
    with start(monkeypatch, directory, **env) as client:
        assert client.get("/health").status_code == 200


def test_expected_sha_mismatch_fails_closed(monkeypatch, tmp_path):
    directory = write_model(tmp_path / "model")
    env = {api.EXPECTED_SHA_ENV: "0" * 64}
    with start(monkeypatch, directory, **env) as client:
        health = client.get("/health")
        predict = client.post("/predict", json=VALID)
    assert health.status_code == 503
    assert "differs from expected" in health.json()["detail"]
    assert predict.status_code == 503
