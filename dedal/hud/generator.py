"""HUD generator — reads flight_pack.json, renders transparent PNG sequence.

EKF velocities (Vfwd, Vlat, Vz, Vh) come pre-computed from the pack;
no re-computation is done here.
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import cv2

from .renderer import FlightFrame, ProfessionalHUD, build_gps_map


def _f(v, d: float = 0.0) -> float:
    return float(v) if v is not None else d


def _i(v, d: int = 0) -> int:
    return int(v) if v is not None else d


def load_pack(pack_path: Path) -> list[FlightFrame]:
    """Deserialise flight_pack.json → list[FlightFrame]."""
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    frames: list[FlightFrame] = []
    for fr in data.get("frames", []):
        frames.append(FlightFrame(
            timestamp_us = _i(fr.get("t_us")),
            armed        = _i(fr.get("armed")),
            flight_mode  = _i(fr.get("fm")),
            pitch_deg    = _f(fr.get("pitch")),
            roll_deg     = _f(fr.get("roll")),
            yaw_deg      = _f(fr.get("yaw")),
            gps_alt_m    = _f(fr.get("alt_m")),
            gps_speed_ms = _f(fr.get("spd_ms")),
            gps_lat      = _f(fr.get("lat")),
            gps_lon      = _f(fr.get("lon")),
            gps_sats     = _i(fr.get("sats")),
            gps_valid    = _i(fr.get("gps_ok")),
            m1_pwm       = _i(fr.get("m1")),
            m3_pwm       = _i(fr.get("m3")),
            vbat_v       = _f(fr.get("vbat")),
            accel_z      = _f(fr.get("accel_z"), 1.0),
            Vfwd         = _f(fr.get("Vfwd")),
            Vlat         = _f(fr.get("Vlat")),
            Vz           = _f(fr.get("Vz")),
            Vh           = _f(fr.get("Vh")),
        ))
    return frames


def generate_hud(
    pack_path: Path,
    output_dir: Path,
    fps: int = 25,
    width: int = 1920,
    height: int = 1080,
    cells: int = 6,
    min_gps_sats: int = 0,
    t_start_s: float = 0.0,
    t_end_s: float | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
    cancel_event=None,
) -> int:
    """Render a transparent PNG sequence from flight_pack.json.

    Clears *output_dir* before writing.  Calls *progress_cb(current, total)*
    every *fps* frames.  Returns the total frame count rendered.

    t_start_s / t_end_s: seconds from the beginning of the log (t0).
    """
    frames = load_pack(pack_path)
    if not frames:
        raise ValueError("flight_pack.json contains no frames")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    MW = int(577 * width / 1920)
    MH = int(608 * height / 1080)
    gps_data = build_gps_map(frames, MW, MH, min_gps_sats)

    hud = ProfessionalHUD(width, height, cells, gps_data, min_gps_sats)
    t0 = frames[0].timestamp_us
    duration_s = (frames[-1].timestamp_us - t0) / 1e6

    start_s = max(0.0, t_start_s)
    end_s   = min(duration_s, t_end_s if t_end_s is not None else duration_s)
    if end_s <= start_s:
        raise ValueError(f"Invalid time range: t_start_s={start_s} >= t_end_s={end_s}")

    fi_start = int(start_s * fps)
    fi_end   = int(end_s   * fps)
    total    = max(1, fi_end - fi_start)

    for n, fi in enumerate(range(fi_start, fi_end)):
        if cancel_event is not None and cancel_event.is_set():
            return n
        target = t0 + fi / fps * 1e6
        idx = min(range(len(frames)), key=lambda i: abs(frames[i].timestamp_us - target))
        frame = hud.render(frames[idx], idx, t0)
        cv2.imwrite(str(output_dir / f"frame_{n:06d}.png"), frame)
        if progress_cb and (n + 1) % fps == 0:
            progress_cb(n + 1, total)

    if progress_cb:
        progress_cb(total, total)
    return total
