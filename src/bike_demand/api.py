"""Prediction API: serve the saved, evaluated baseline model. Never trains."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException

from bike_demand.preflight import sha256
from bike_demand.schemas import PredictRequest, PredictResponse
from bike_demand.validate import FEATURES

# Folder holding model.joblib and model-metadata.json written by bike_demand.train.
MODEL_DIR_ENV = "BIKE_DEMAND_MODEL_DIR"
DEFAULT_MODEL_DIR = "artifacts"

# One shared model-availability state, read by both /health and /predict.
state: dict = {"model": None, "version": None, "error": "not loaded yet"}


def model_dir() -> Path:
    return Path(os.environ.get(MODEL_DIR_ENV, DEFAULT_MODEL_DIR))


def load_model(directory: Path) -> tuple[object, str]:
    """Load a trusted local model and return it with its own metadata version."""
    model_path = directory / "model.joblib"
    metadata_path = directory / "model-metadata.json"
    if not model_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"no model.joblib/model-metadata.json in {directory}")
    metadata = json.loads(metadata_path.read_text())
    if list(metadata["features"]) != list(FEATURES):
        raise ValueError("model metadata: feature order differs from the contract")
    if sha256(model_path) != metadata["model_sha256"]:
        raise ValueError("model.joblib checksum differs from its metadata")
    # Only load locally produced/trusted model files, never downloaded ones.
    return joblib.load(model_path), str(metadata["model_version"])


def refresh_state() -> None:
    try:
        model, version = load_model(model_dir())
    except (OSError, ValueError, KeyError) as error:
        state.update(model=None, version=None, error=str(error))
    else:
        state.update(model=model, version=version, error=None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    refresh_state()
    yield
    state.update(model=None, version=None, error="service stopped")


app = FastAPI(title="Bike demand prediction", version="0.1.0", lifespan=lifespan)


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


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    model = require_model()
    row = pd.DataFrame([request.model_dump()], columns=list(FEATURES))
    prediction = float(model.predict(row)[0])
    if not np.isfinite(prediction) or prediction < 0:
        raise HTTPException(status_code=500, detail="model returned an invalid value")
    return PredictResponse(prediction=prediction, model_version=state["version"])
