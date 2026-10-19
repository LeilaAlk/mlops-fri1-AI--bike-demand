"""Request and response contracts for the prediction API.

The request is one flat JSON object with exactly the twelve training features.
Unknown fields (including the targets cnt, casual and registered) are rejected.
"""

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    # extra="forbid": any field outside the twelve features is a 422 error.
    # strict=True: no silent coercion ("3" or true are not accepted as integers).
    model_config = ConfigDict(extra="forbid", strict=True)

    season: int = Field(ge=1, le=4)
    yr: int = Field(ge=0, le=1)
    mnth: int = Field(ge=1, le=12)
    hr: int = Field(ge=0, le=23)
    holiday: int = Field(ge=0, le=1)
    weekday: int = Field(ge=0, le=6)
    workingday: int = Field(ge=0, le=1)
    weathersit: int = Field(ge=1, le=4)
    # Normalised weather values, not Celsius or percentages.
    temp: float = Field(ge=0, le=1, allow_inf_nan=False)
    atemp: float = Field(ge=0, le=1, allow_inf_nan=False)
    hum: float = Field(ge=0, le=1, allow_inf_nan=False)
    windspeed: float = Field(ge=0, le=1, allow_inf_nan=False)


class PredictResponse(BaseModel):
    prediction: float
    model_version: str
