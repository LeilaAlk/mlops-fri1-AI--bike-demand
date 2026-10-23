"""Prediction API: serve the saved, evaluated baseline model. Never trains."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException

from bike_demand.observability import (
    configure_logging,
    install_request_logging,
    log_event,
)
from bike_demand.preflight import sha256
from bike_demand.schemas import PredictRequest, PredictResponse
from bike_demand.validate import FEATURES

# Settings come from the environment at start-up, never from the image's code.
# Folder holding model.joblib and model-metadata.json written by bike_demand.train.
MODEL_DIR_ENV = "BIKE_DEMAND_MODEL_DIR"
DEFAULT_MODEL_DIR = "artifacts"
# Optional: SHA-256 of the model the operator expects; a mismatch keeps the
# service not ready (503) instead of serving another model.
EXPECTED_SHA_ENV = "BIKE_DEMAND_EXPECTED_MODEL_SHA256"
# Code identity: the Git commit the image was built from (set by the Dockerfile).
REVISION_ENV = "SERVICE_REVISION"

# One shared model-availability state, read by /health, /version and /predict.
state: dict = {
    "model": None,
    "version": None,
    "sha256": None,
    "error": "not loaded yet",
}


def model_dir() -> Path:
    return Path(os.environ.get(MODEL_DIR_ENV, DEFAULT_MODEL_DIR))


def service_revision() -> str:
    return os.environ.get(REVISION_ENV, "unknown")


def load_model(directory: Path) -> tuple[object, str, str]:
    """Load a trusted local model; return it with its metadata version and hash."""
    model_path = directory / "model.joblib"
    metadata_path = directory / "model-metadata.json"
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"no model.joblib/model-metadata.json in {directory}")
    metadata = json.loads(metadata_path.read_text())
    if list(metadata["features"]) != list(FEATURES):
        raise ValueError("model metadata: feature order differs from the contract")
    digest = sha256(model_path)
    if digest != metadata["model_sha256"]:
        raise ValueError("model.joblib checksum differs from its metadata")
    expected = os.environ.get(EXPECTED_SHA_ENV)
    if expected and digest != expected:
        raise ValueError(
            f"model.joblib sha256 {digest[:12]} differs from expected {expected[:12]}"
        )
    # Only load locally produced/trusted model files, never downloaded ones.
    return joblib.load(model_path), str(metadata["model_version"]), digest


def refresh_state() -> None:
    try:
        model, version, digest = load_model(model_dir())
    except (OSError, ValueError, KeyError) as error:
        state.update(model=None, version=None, sha256=None, error=str(error))
    else:
        state.update(model=model, version=version, sha256=digest, error=None)


def log_startup() -> None:
    if state["model"] is None:
        log_event(
            "model_unavailable", logging.ERROR, reason=state["error"], **identity()
        )
    else:
        log_event("model_loaded", **identity())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start -> load -> check -> ready: requests are accepted only after this.
    configure_logging(os.environ.get("BIKE_DEMAND_LOG_LEVEL", "INFO"))
    refresh_state()
    log_startup()
    yield
    state.update(model=None, version=None, sha256=None, error="service stopped")


app = FastAPI(title="Bike demand prediction", version="0.1.0", lifespan=lifespan)


def identity() -> dict:
    """Fields added to every log line: which code and which model answered."""
    return {
        "service_revision": service_revision(),
        "model_version": state["version"],
        "model_sha256": state["sha256"],
    }


install_request_logging(app, identity)


def require_model():
    if state["model"] is None:
        raise HTTPException(
            status_code=503, detail=f"model unavailable: {state['error']}"
        )
    return state["model"]


@app.get("/health")
def health() -> dict:
    require_model()
    return {"status": "ok", "model_version": state["version"]}


@app.get("/version")
def version() -> dict:
    """Which code and which model are answering. Always 200, even when not ready."""
    return {
        "service_revision": service_revision(),
        "model_version": state["version"],
        "model_hash": state["sha256"],
        "ready": state["model"] is not None,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    model = require_model()
    row = pd.DataFrame([request.model_dump()], columns=list(FEATURES))
    prediction = float(model.predict(row)[0])
    if not np.isfinite(prediction) or prediction < 0:
        raise HTTPException(status_code=500, detail="model returned an invalid value")
    return PredictResponse(prediction=prediction, model_version=state["version"])
