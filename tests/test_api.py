"""API tests: normal, invalid and missing-model cases, run without a server."""

import json

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.dummy import DummyRegressor

from bike_demand import api
from bike_demand.preflight import sha256
from bike_demand.validate import FEATURES

pytestmark = pytest.mark.api

VALID = {
    "season": 3,
    "yr": 1,
    "mnth": 7,
    "hr": 17,
    "holiday": 0,
    "weekday": 3,
    "workingday": 1,
    "weathersit": 1,
    "temp": 0.7,
    "atemp": 0.65,
    "hum": 0.5,
    "windspeed": 0.2,
}


def write_model(directory, constant=42.0, version="test-v1", features=None):
    """Save a tiny constant model with metadata, like bike_demand.train does."""
    directory.mkdir(parents=True, exist_ok=True)
    x = pd.DataFrame([VALID] * 3)[list(FEATURES)]
    model = DummyRegressor(strategy="constant", constant=constant).fit(x, [1, 2, 3])
    model_path = directory / "model.joblib"
    joblib.dump(model, model_path)
    metadata = {
        "features": list(features if features is not None else FEATURES),
        "model_sha256": sha256(model_path),
        "model_version": version,
    }
    (directory / "model-metadata.json").write_text(json.dumps(metadata))
    return directory


def make_client(monkeypatch, directory):
    monkeypatch.setenv(api.MODEL_DIR_ENV, str(directory))
    return TestClient(api.app)


@pytest.fixture
def model_dir(tmp_path):
    return write_model(tmp_path / "model")


@pytest.fixture
def client(monkeypatch, model_dir):
    with make_client(monkeypatch, model_dir) as test_client:
        yield test_client


@pytest.fixture
def client_without_model(monkeypatch, tmp_path):
    empty = tmp_path / "no-model"
    empty.mkdir()
    with make_client(monkeypatch, empty) as test_client:
        yield test_client


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "test-v1"}


def test_predict_ok(client):
    response = client.post("/predict", json=VALID)
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] == pytest.approx(42.0)
    assert body["prediction"] >= 0
    assert body["model_version"] == "test-v1"


def test_missing_model_health_is_503(client_without_model):
    response = client_without_model.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"].startswith("model unavailable")


def test_missing_model_predict_is_503(client_without_model):
    response = client_without_model.post("/predict", json=VALID)
    assert response.status_code == 503
    assert "prediction" not in response.json()


def test_invalid_request_without_model_is_422(client_without_model):
    response = client_without_model.post("/predict", json={**VALID, "hr": 24})
    assert response.status_code == 422


def test_tampered_model_is_refused(monkeypatch, model_dir):
    model_path = model_dir / "model.joblib"
    model_path.write_bytes(model_path.read_bytes() + b"tampered")
    with make_client(monkeypatch, model_dir) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 503
    assert "checksum" in response.json()["detail"]


def test_feature_order_mismatch_is_refused(monkeypatch, tmp_path):
    directory = write_model(tmp_path / "model", features=list(reversed(FEATURES)))
    with make_client(monkeypatch, directory) as test_client:
        response = test_client.get("/health")
    assert response.status_code == 503
    assert "feature order" in response.json()["detail"]


def test_negative_prediction_is_not_returned(monkeypatch, tmp_path):
    directory = write_model(tmp_path / "model", constant=-5.0)
    with make_client(monkeypatch, directory) as test_client:
        response = test_client.post("/predict", json=VALID)
    assert response.status_code == 500
    assert "prediction" not in response.json()


@pytest.mark.parametrize("field", ["cnt", "casual", "registered", "comment"])
def test_extra_fields_are_rejected(client, field):
    response = client.post("/predict", json={**VALID, field: 1})
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["hr", "temp"])
def test_missing_field_is_rejected(client, field):
    payload = {key: value for key, value in VALID.items() if key != field}
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("season", 0),
        ("season", 5),
        ("hr", -1),
        ("hr", 24),
        ("temp", 1.5),
        ("windspeed", -0.1),
    ],
)
def test_out_of_range_is_rejected(client, field, value):
    response = client.post("/predict", json={**VALID, field: value})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hr", "17"),
        ("hr", 17.5),
        ("hr", True),
    ],
)
def test_wrong_type_is_rejected(client, field, value):
    response = client.post("/predict", json={**VALID, field: value})
    assert response.status_code == 422
