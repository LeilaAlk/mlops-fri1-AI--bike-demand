import pytest
from pydantic import ValidationError

from bike_demand.schemas import PredictRequest
from bike_demand.validate import FEATURES

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


def test_schema_fields_match_training_features():
    assert tuple(PredictRequest.model_fields) == FEATURES


def test_valid_request_is_accepted():
    assert PredictRequest(**VALID).hr == 17


@pytest.mark.parametrize(
    ("field", "value"),
    [("season", 0), ("hr", 24), ("temp", 1.5), ("hum", -0.1), ("hr", "17")],
)
def test_out_of_range_or_wrong_type_is_rejected(field, value):
    with pytest.raises(ValidationError):
        PredictRequest(**{**VALID, field: value})


def test_target_column_is_rejected():
    with pytest.raises(ValidationError):
        PredictRequest(**VALID, cnt=100)
