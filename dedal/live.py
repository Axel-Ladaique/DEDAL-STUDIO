"""Live telemetry session management for DEDAL Studio."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from .crsf import CRSFReader, TELEMETRY_STATE, TELEMETRY_LOCK


@dataclass
class ArmedStats:
    """Accumulates max/avg stats for the current armed period only."""

    gps_alt_max: float = float("-inf")
    gps_alt_avg: float = 0.0
    gps_speed_max: float = float("-inf")
    gps_speed_avg: float = 0.0
    distance_home_max: float = float("-inf")
    distance_home_avg: float = 0.0
    battery_current_max: float = float("-inf")
    battery_current_avg: float = 0.0
    battery_voltage_min: float = float("inf")
    loop_time_max: float = float("-inf")
    loop_time_avg: float = 0.0
    roll_abs_max: float = 0.0
    pitch_abs_max: float = 0.0
    vario_max: float = float("-inf")
    vario_min: float = float("inf")
    sample_count: int = 0
    armed_start_ts: float = 0.0
    armed_duration_s: float = 0.0

    def update(self, state: dict) -> None:
        if not state.get("armed", False):
            return

        if self.sample_count == 0:
            self.armed_start_ts = time.time()

        n = self.sample_count + 1
        self.armed_duration_s = time.time() - self.armed_start_ts

        def _max_avg(current_max: float, current_avg: float, v: float):
            return max(current_max, v), current_avg + (v - current_avg) / n

        if "gps_alt_m" in state:
            self.gps_alt_max, self.gps_alt_avg = _max_avg(
                self.gps_alt_max, self.gps_alt_avg, state["gps_alt_m"]
            )
        if "gps_speed_kmh" in state:
            self.gps_speed_max, self.gps_speed_avg = _max_avg(
                self.gps_speed_max, self.gps_speed_avg, state["gps_speed_kmh"]
            )
        if "distance_m" in state:
            self.distance_home_max, self.distance_home_avg = _max_avg(
                self.distance_home_max, self.distance_home_avg, state["distance_m"]
            )
        if "battery_current" in state:
            self.battery_current_max, self.battery_current_avg = _max_avg(
                self.battery_current_max, self.battery_current_avg, state["battery_current"]
            )
        if "battery_voltage" in state:
            self.battery_voltage_min = min(self.battery_voltage_min, state["battery_voltage"])
        if "loop_us" in state:
            self.loop_time_max, self.loop_time_avg = _max_avg(
                self.loop_time_max, self.loop_time_avg, state["loop_us"]
            )
        if "attitude_roll_deg" in state:
            self.roll_abs_max = max(self.roll_abs_max, abs(state["attitude_roll_deg"]))
        if "attitude_pitch_deg" in state:
            self.pitch_abs_max = max(self.pitch_abs_max, abs(state["attitude_pitch_deg"]))
        if "vario_m_s" in state:
            self.vario_max = max(self.vario_max, state["vario_m_s"])
            self.vario_min = min(self.vario_min, state["vario_m_s"])

        self.sample_count = n

    def reset(self) -> None:
        self.__init__()

    def to_dict(self) -> dict:
        def _safe(v: float) -> Optional[float]:
            if v == float("inf") or v == float("-inf"):
                return None
            return round(v, 2)

        return {
            "armed": self.sample_count > 0,
            "armed_duration_s": round(self.armed_duration_s, 1),
            "gps_alt_max": _safe(self.gps_alt_max),
            "gps_alt_avg": _safe(self.gps_alt_avg) if self.sample_count > 0 else None,
            "gps_speed_max": _safe(self.gps_speed_max),
            "gps_speed_avg": _safe(self.gps_speed_avg) if self.sample_count > 0 else None,
            "distance_home_max": _safe(self.distance_home_max),
            "distance_home_avg": _safe(self.distance_home_avg) if self.sample_count > 0 else None,
            "battery_current_max": _safe(self.battery_current_max),
            "battery_current_avg": _safe(self.battery_current_avg) if self.sample_count > 0 else None,
            "battery_voltage_min": _safe(self.battery_voltage_min),
            "loop_time_max": _safe(self.loop_time_max),
            "loop_time_avg": _safe(self.loop_time_avg) if self.sample_count > 0 else None,
            "roll_abs_max": round(self.roll_abs_max, 1),
            "pitch_abs_max": round(self.pitch_abs_max, 1),
            "vario_max": _safe(self.vario_max),
            "vario_min": _safe(self.vario_min),
            "sample_count": self.sample_count,
        }


class LiveSession:
    """Manages CRSFReader lifecycle and armed-period stats accumulation."""

    def __init__(self) -> None:
        self._reader: Optional[CRSFReader] = None
        self._stats = ArmedStats()
        self._last_armed: bool = False
        self._stats_lock = threading.Lock()
        self._stats_thread: Optional[threading.Thread] = None
        self._stop_stats = threading.Event()

    def connect(self, port: str, baud: int = 921600) -> None:
        if self._reader is not None:
            raise RuntimeError("already connected")
        self._reader = CRSFReader(port, baud)
        self._reader.start()
        self._stop_stats.clear()
        self._stats = ArmedStats()
        self._last_armed = False
        self._stats_thread = threading.Thread(target=self._stats_loop, daemon=True)
        self._stats_thread.start()

    def disconnect(self) -> None:
        self._stop_stats.set()
        if self._stats_thread:
            self._stats_thread.join(timeout=1.0)
            self._stats_thread = None
        if self._reader:
            self._reader.stop()
            self._reader = None

    def is_connected(self) -> bool:
        return self._reader is not None

    def get_state(self) -> dict:
        with TELEMETRY_LOCK:
            return dict(TELEMETRY_STATE)

    def get_stats(self) -> dict:
        with self._stats_lock:
            return self._stats.to_dict()

    def _stats_loop(self) -> None:
        while not self._stop_stats.is_set():
            with TELEMETRY_LOCK:
                state = dict(TELEMETRY_STATE)
            armed = state.get("armed", False)
            if armed and not self._last_armed:
                # Reset stats at the start of each new arm cycle
                with self._stats_lock:
                    self._stats.reset()
            self._last_armed = armed
            if armed:
                with self._stats_lock:
                    self._stats.update(state)
            self._stop_stats.wait(0.1)


_live_session = LiveSession()
