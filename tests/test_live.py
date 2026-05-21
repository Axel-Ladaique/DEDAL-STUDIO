"""Tests for dedal.live — ArmedStats and LiveSession."""
from __future__ import annotations
import pytest
from dedal.live import ArmedStats


class TestArmedStats:
    def test_initial_state_returns_none_for_all_fields(self):
        s = ArmedStats()
        d = s.to_dict()
        assert d["armed"] is False
        assert d["gps_alt_max"] is None
        assert d["gps_speed_max"] is None
        assert d["battery_voltage_min"] is None
        assert d["sample_count"] == 0

    def test_update_while_not_armed_does_nothing(self):
        s = ArmedStats()
        s.update({"flag_armed": False, "gps_alt_m": 50.0})
        assert s.sample_count == 0

    def test_update_while_armed_accumulates(self):
        s = ArmedStats()
        s.update({"flag_armed": True, "gps_alt_m": 30.0, "gps_speed_kmh": 10.0})
        s.update({"flag_armed": True, "gps_alt_m": 50.0, "gps_speed_kmh": 20.0})
        d = s.to_dict()
        assert d["gps_alt_max"] == 50.0
        assert d["gps_alt_avg"] == pytest.approx(40.0)
        assert d["gps_speed_max"] == 20.0
        assert d["gps_speed_avg"] == pytest.approx(15.0)
        assert d["sample_count"] == 2

    def test_battery_voltage_min_tracked(self):
        s = ArmedStats()
        s.update({"flag_armed": True, "battery_voltage": 24.6})
        s.update({"flag_armed": True, "battery_voltage": 23.8})
        s.update({"flag_armed": True, "battery_voltage": 24.1})
        assert s.to_dict()["battery_voltage_min"] == pytest.approx(23.8)

    def test_roll_pitch_abs_max(self):
        s = ArmedStats()
        s.update({"flag_armed": True, "attitude_roll_deg": -28.5, "attitude_pitch_deg": 15.0})
        s.update({"flag_armed": True, "attitude_roll_deg": 10.0, "attitude_pitch_deg": -22.0})
        d = s.to_dict()
        assert d["roll_abs_max"] == pytest.approx(28.5)
        assert d["pitch_abs_max"] == pytest.approx(22.0)

    def test_vario_max_min(self):
        s = ArmedStats()
        s.update({"flag_armed": True, "vario_m_s": 3.2})
        s.update({"flag_armed": True, "vario_m_s": -2.1})
        d = s.to_dict()
        assert d["vario_max"] == pytest.approx(3.2)
        assert d["vario_min"] == pytest.approx(-2.1)

    def test_reset_clears_all(self):
        s = ArmedStats()
        s.update({"flag_armed": True, "gps_alt_m": 50.0})
        s.reset()
        d = s.to_dict()
        assert d["armed"] is False
        assert d["gps_alt_max"] is None
        assert d["sample_count"] == 0

    def test_missing_fields_ignored_gracefully(self):
        s = ArmedStats()
        s.update({"flag_armed": True})  # no sensor fields
        d = s.to_dict()
        assert d["armed"] is True
        assert d["gps_alt_max"] is None
        assert d["sample_count"] == 1
