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


def load_pack(pack_path: Path) -> list[FlightFrame]:
    """Deserialise flight_pack.json → list[FlightFrame]."""
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    frames: list[FlightFrame] = []
    for fr in data.get("frames", []):
        frames.append(FlightFrame(
            timestamp_us = int(fr.get("t_us", 0)),
            armed        = int(fr.get("armed", 0)),
            flight_mode  = int(fr.get("fm", 0)),
            pitch_deg    = float(fr.get("pitch", 0.0)),
            roll_deg     = float(fr.get("roll",  0.0)),
            yaw_deg      = float(fr.get("yaw",   0.0)),
            gps_alt_m    = float(fr.get("alt_m",  0.0)),
            gps_speed_ms = float(fr.get("spd_ms", 0.0)),
            gps_lat      = float(fr.get("lat",    0.0)),
            gps_lon      = float(fr.get("lon",    0.0)),
            gps_sats     = int(fr.get("sats",   0)),
            gps_valid    = int(fr.get("gps_ok", 0)),
            m1_pwm       = int(fr.get("m1",     0)),
            m3_pwm       = int(fr.get("m3",     0)),
            vbat_v       = float(fr.get("vbat",  0.0)),
            accel_z      = float(fr.get("accel_z", 1.0)),
            Vfwd         = float(fr.get("Vfwd",  0.0)),
            Vlat         = float(fr.get("Vlat",  0.0)),
            Vz           = float(fr.get("Vz",    0.0)),
            Vh           = float(fr.get("Vh",    0.0)),
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
    progress_cb: Callable[[int, int], None] | None = None,
) -> int:
    """Render a transparent PNG sequence from flight_pack.json.

    Clears *output_dir* before writing.  Calls *progress_cb(current, total)*
    every *fps* frames.  Returns the total frame count rendered.
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
    total = int((frames[-1].timestamp_us - t0) / 1e6 * fps)
    if total < 1:
        total = 1

    for fi in range(total):
        target = t0 + fi / fps * 1e6
        idx = min(range(len(frames)), key=lambda i: abs(frames[i].timestamp_us - target))
        frame = hud.render(frames[idx], idx, t0)
        cv2.imwrite(str(output_dir / f"frame_{fi:06d}.png"), frame)
        if progress_cb and (fi + 1) % fps == 0:
            progress_cb(fi + 1, total)

    if progress_cb:
        progress_cb(total, total)
    return total
