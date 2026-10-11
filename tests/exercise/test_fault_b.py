from pathlib import Path

import pytest

from bike_demand.validate import load_data

pytestmark = pytest.mark.exercise
FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_fault_b_weathersit_out_of_range_is_rejected():
    with pytest.raises(ValueError, match="weathersit: require integers"):
        load_data(FIXTURES / "weathersit-out-of-range.csv")


def test_fault_b_valid_control_passes():
    frame = load_data(FIXTURES / "missing-hours.csv")
    assert len(frame) == 6
